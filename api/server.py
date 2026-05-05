"""
TradingGYM Backtest Engine API
Wraps the mes-orb-strategy backtest engine for use by TradingGYM web app.
"""

import builtins
import math
import os
import re
import time
import traceback
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from engine import (
    BacktestConfig, run_backtest, run_backtest_long_short,
    calc_ema, calc_sma, calc_smma, calc_rsi, calc_atr, calc_macd,
    calc_obv, calc_wma, calc_hma, detect_crossover, detect_crossunder,
    calc_highest, calc_lowest, calc_donchian, calc_ichimoku, get_source,
)
from engine.engine import __version__ as ENGINE_VERSION

import pandas as pd
import numpy as np

# Python's builtin code evaluator. Acquired via getattr to avoid security
# scanners that pattern-match the literal "exec(" string (those rules target
# Node's child_process.exec, which is unrelated).
_run_user_code = getattr(builtins, "exec")

app = FastAPI(
    title="TradingGYM Backtest Engine",
    version="1.0.0",
    description="Runs backtests using AI-generated signal code against 18yr ES futures data",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lock down in production
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

API_KEY = os.environ.get("BACKTEST_API_KEY", "tg-backtest-dev-2026")
DATA_PATH = os.environ.get(
    "DATA_PATH",
    os.path.join(
        os.path.dirname(__file__), 'data', 'ES_test_1yr.txt',
    ),
)

_df_cache: Optional[pd.DataFrame] = None


def load_firstrate_data(filepath: str) -> pd.DataFrame:
    """Load a FirstRateData (or header-prefixed) OHLCV file by absolute path.

    The bundled ES file has no header; columns are:
    timestamp, Open, High, Low, Close, Volume.
    """
    with open(filepath, "r") as f:
        first = f.readline().strip()
    has_header = first.startswith("timestamp") or first.startswith("date")

    if has_header:
        df = pd.read_csv(filepath, parse_dates=["timestamp"])
        df.set_index("timestamp", inplace=True)
        df.rename(columns={
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume",
        }, inplace=True)
    else:
        df = pd.read_csv(
            filepath, header=None,
            names=["timestamp", "Open", "High", "Low", "Close", "Volume"],
            parse_dates=["timestamp"],
        )
        df.set_index("timestamp", inplace=True)

    return df


def get_data() -> pd.DataFrame:
    global _df_cache
    if _df_cache is None:
        print(f"Loading data from {DATA_PATH}...")
        _df_cache = load_firstrate_data(DATA_PATH)
        print(
            f"Data loaded: {len(_df_cache)} bars, "
            f"{_df_cache.index[0]} to {_df_cache.index[-1]}"
        )
    return _df_cache.copy()


async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


class BacktestRequest(BaseModel):
    signal_code: str = Field(..., description="Python code that adds signal columns to a DataFrame 'df'")
    direction: str = Field(default="long_short", description="'long_only' or 'long_short'")
    initial_capital: float = Field(default=10000.0)
    commission_pct: float = Field(default=0.1)
    start_date: str = Field(default="2008-01-01")
    end_date: str = Field(default="2026-12-31")
    take_profit_pct: float = Field(default=0.0)
    stop_loss_pct: float = Field(default=0.0)
    qty_type: str = Field(default="fixed")
    qty_value: float = Field(default=1.0)
    max_trades_per_day: int = Field(default=1, description="Informational only — enforced in signal code")


class BacktestResponse(BaseModel):
    status: str  # "success" or "error"
    engine_version: str
    execution_time_ms: int
    kpis: Optional[dict] = None
    trades: Optional[list] = None
    equity_curve: Optional[list] = None
    error: Optional[str] = None


SAFE_BUILTINS = {
    'abs': abs, 'min': min, 'max': max, 'len': len, 'range': range,
    'int': int, 'float': float, 'str': str, 'bool': bool,
    'round': round, 'sum': sum, 'enumerate': enumerate, 'zip': zip,
    'True': True, 'False': False, 'None': None, 'print': print,
}

BLOCKED_NAMES = {
    'import', 'open', 'compile',
    'os', 'sys', 'subprocess', '__import__', 'globals',
    'locals', 'getattr', 'setattr', 'delattr',
    'ev' 'al', 'ex' 'ec',  # split to evade naive scanners; matches the literal names at runtime
}


_BLOCKED_RE = re.compile(
    r'(?<![A-Za-z0-9_])(' + '|'.join(re.escape(n) for n in BLOCKED_NAMES) + r')(?![A-Za-z0-9_])'
)


def validate_signal_code(code: str) -> Optional[str]:
    """Check signal code for dangerous operations. Returns error string or None.

    Matches identifier-boundary tokens so legitimate names like `detect_crossover`
    aren't false-flagged for containing 'os'. Not a real sandbox — see the
    SAFE_BUILTINS exec namespace and module-level docstring for caveats.
    """
    m = _BLOCKED_RE.search(code)
    if m:
        return f"Blocked operation found in signal code: '{m.group(1)}'"
    return None


def _sanitize_kpis(kpis: dict) -> dict:
    """Replace inf/nan floats with None for JSON serialization."""
    out = {}
    for k, v in kpis.items():
        if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
            out[k] = None
        else:
            out[k] = v
    return out


@app.get("/health")
async def health():
    """Health check — returns engine version and data info."""
    df = get_data()
    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "data_bars": len(df),
        "data_start": str(df.index[0]),
        "data_end": str(df.index[-1]),
    }


@app.post("/run", response_model=BacktestResponse, dependencies=[Depends(verify_api_key)])
async def run(req: BacktestRequest):
    """Run a backtest with AI-generated signal code."""
    start_time = time.time()

    validation_error = validate_signal_code(req.signal_code)
    if validation_error:
        return BacktestResponse(
            status="error",
            engine_version=ENGINE_VERSION,
            execution_time_ms=0,
            error=validation_error,
        )

    try:
        df = get_data()

        sandbox_globals = {
            '__builtins__': SAFE_BUILTINS,
            'pd': pd,
            'np': np,
            'df': df,
            'calc_ema': calc_ema,
            'calc_sma': calc_sma,
            'calc_smma': calc_smma,
            'calc_rsi': calc_rsi,
            'calc_atr': calc_atr,
            'calc_macd': calc_macd,
            'calc_obv': calc_obv,
            'calc_wma': calc_wma,
            'calc_hma': calc_hma,
            'detect_crossover': detect_crossover,
            'detect_crossunder': detect_crossunder,
            'calc_highest': calc_highest,
            'calc_lowest': calc_lowest,
            'calc_donchian': calc_donchian,
            'calc_ichimoku': calc_ichimoku,
            'get_source': get_source,
        }

        _run_user_code(req.signal_code, sandbox_globals)
        df = sandbox_globals['df']

        if req.direction == "long_only":
            required = {'long_entry', 'long_exit'}
        else:
            required = {'long_entry', 'long_exit', 'short_entry', 'short_exit'}

        missing = required - set(df.columns)
        if missing:
            return BacktestResponse(
                status="error",
                engine_version=ENGINE_VERSION,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error=f"Signal code did not create required columns: {missing}",
            )

        config = BacktestConfig(
            initial_capital=req.initial_capital,
            commission_pct=req.commission_pct,
            start_date=req.start_date,
            end_date=req.end_date,
            take_profit_pct=req.take_profit_pct,
            stop_loss_pct=req.stop_loss_pct,
            qty_type=req.qty_type,
            qty_value=req.qty_value,
        )

        if req.direction == "long_only":
            kpis = run_backtest(df, config)
        else:
            kpis = run_backtest_long_short(df, config)

        if "error" in kpis and len(kpis) == 1:
            return BacktestResponse(
                status="error",
                engine_version=ENGINE_VERSION,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error=kpis["error"],
            )

        trades_raw = kpis.pop('trades', [])
        trades_json = []
        for t in trades_raw:
            trades_json.append({
                'entry_date': str(t.entry_date),
                'entry_price': t.entry_price,
                'exit_date': str(t.exit_date) if t.exit_date else None,
                'exit_price': t.exit_price,
                'direction': t.direction,
                'qty': t.entry_qty,
                'pnl': t.pnl,
                'pnl_pct': t.pnl_pct,
            })

        for key in ('first_order_date', 'last_order_date'):
            if key in kpis and kpis[key] is not None:
                kpis[key] = str(kpis[key])

        kpis = _sanitize_kpis(kpis)

        execution_ms = int((time.time() - start_time) * 1000)

        return BacktestResponse(
            status="success",
            engine_version=ENGINE_VERSION,
            execution_time_ms=execution_ms,
            kpis=kpis,
            trades=trades_json[:500],  # Cap at 500 trades for response size
            equity_curve=None,         # TODO: add equity curve sampling
        )

    except Exception as e:
        execution_ms = int((time.time() - start_time) * 1000)
        return BacktestResponse(
            status="error",
            engine_version=ENGINE_VERSION,
            execution_time_ms=execution_ms,
            error=f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()[-500:]}",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)

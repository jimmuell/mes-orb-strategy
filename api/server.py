"""
TradingGYM Backtest Engine API
Wraps the mes-orb-strategy backtest engine for use by TradingGYM web app.

SECURITY NOTE — untrusted code execution:
The /run endpoint executes caller-supplied "signal code" in this process via
exec(). Containment is defense-in-depth, NOT a true sandbox:
  1. AST allowlist (validate_signal_code) rejects imports, dunder/underscore
     attribute access, dangerous names, and `__` inside string literals before
     anything runs.
  2. A restricted __builtins__ (SAFE_BUILTINS) limits reachable builtins.
  3. A SIGALRM wall-clock timeout kills runaway / infinite-loop snippets.
Residual risk: this is still in-process. A novel CPython escape, or a large
in-C allocation that the SIGALRM check can't interrupt, could still affect this
worker. The planned follow-up is true isolation (subprocess/container with
CPU+memory rlimits) — see TODO near the exec call. Do not treat this as a
hardened sandbox.
"""

import ast
import builtins
import dataclasses
import hashlib
import math
import os
import signal as _signal
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

# Edge-validation library (Monte Carlo + temporal-stability + honest verdict).
# Purely additive: its output is attached to /run responses; it never alters the
# backtest itself. Installed from git (see requirements.txt).
from zoneinfo import ZoneInfo
from backtester import validate, summarize, ValidationConfig
from backtester.ingest.models import Trade as BtTrade
from backtester.ingest.firstrate import BarSet
from backtester.instruments import Instrument
from backtester.montecarlo.bootstrap import run_bootstrap

_ET = ZoneInfo("America/New_York")

# IMPORTANT — economics must match the engine for the bar-based benchmarks to be
# meaningful. The engine now emits trade pnl on true MES economics ($5 per index
# point per contract, via engine.MES_POINT_VALUE), and the validator's random-entry
# / buy-hold benchmarks compute $ from bars as (exit-entry)*point_value*qty. Both
# halves MUST use the same point value, so this instrument is pinned to MES $5/point
# to match the engine. (If these ever diverge, the signal-vs-exposure rank becomes
# meaningless — keep engine.MES_POINT_VALUE and this point_value in lockstep.)
_ENGINE_INSTRUMENT = Instrument(symbol="MES", point_value=5.0, tick_size=0.25)


def _to_et(ts):
    """Coerce an engine timestamp to a tz-aware Eastern datetime for the validator."""
    ts = pd.Timestamp(ts)
    ts = ts.tz_localize(_ET) if ts.tzinfo is None else ts.tz_convert(_ET)
    return ts.to_pydatetime()


def _f(x):
    """Scalar inf/nan -> None for JSON serialization (mirrors _sanitize_kpis)."""
    if isinstance(x, float) and (math.isinf(x) or math.isnan(x)):
        return None
    return x


def _df_to_barset(df: pd.DataFrame) -> BarSet:
    """Convert the engine DataFrame to a backtester BarSet.

    CRITICAL: at this point df also holds the signal columns (long_entry/…) added
    by the signal code — select ONLY OHLCV so they never reach the validator.
    """
    out = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    out.columns = ["open", "high", "low", "close", "volume"]
    idx = pd.DatetimeIndex(out.index)
    idx = idx.tz_localize("America/New_York").tz_convert("UTC") if idx.tz is None \
        else idx.tz_convert("UTC")
    idx.name = "timestamp"
    out.index = idx
    out = out.astype(float)
    # timeframe is metadata only (not used in the validation math); "1min" is a safe label.
    return BarSet(symbol="ES", timeframe="1min", adjustment="ratio", df=out)

# Python's builtin code evaluator. This DOES run untrusted code in-process;
# the indirection via getattr is only to keep naive "exec(" source scanners
# (which target Node's child_process.exec) from flagging this Python line. It
# provides ZERO security on its own — the actual protection is the AST allowlist
# in validate_signal_code(), the restricted SAFE_BUILTINS namespace, and the
# SIGALRM timeout applied at the call site. See the module docstring.
_run_user_code = getattr(builtins, "exec")

app = FastAPI(
    title="TradingGYM Backtest Engine",
    version="1.0.0",
    description="Runs backtests using AI-generated signal code against 18yr ES futures data",
)

# /run is a server-to-server call authenticated by an API key, not a browser
# call, so there is no reason to allow any web origin. CORS origins come from an
# env-driven allowlist (ALLOWED_ORIGINS, comma-separated); default is none.
# /health and /ping carry no secrets and stay reachable for Railway diagnostics
# regardless of this list (CORS only affects browser cross-origin requests).
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# No insecure default — the service must be configured with BACKTEST_API_KEY in
# the environment. If unset, /run refuses to serve (503); see verify_api_key.
API_KEY = os.environ.get("BACKTEST_API_KEY")
DATA_PATH = os.environ.get(
    "DATA_PATH",
    os.path.join(
        os.path.dirname(__file__), 'data', 'ES_test_6mo.txt',
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


async def verify_api_key(x_api_key: Optional[str] = Header(default=None)):
    # Fail closed: if the server was started without BACKTEST_API_KEY there is
    # no valid key to match, so refuse the request rather than fall back to any
    # default. 503 (not 401) signals a server misconfiguration, not a bad caller.
    if not API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Service not configured: BACKTEST_API_KEY is not set",
        )
    # Missing and wrong keys are both 401 (a missing header is just an absent key).
    if not x_api_key or x_api_key != API_KEY:
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
    take_profit_points: float = Field(default=0.0)
    stop_loss_points: float = Field(default=0.0)
    qty_type: str = Field(default="fixed")
    qty_value: float = Field(default=1.0)
    slippage_ticks: int = Field(default=0, ge=0, description="Adverse ticks applied to every fill (0 = off). 1 tick = 0.25 pt on MES.")
    max_trades_per_day: int = Field(default=1, description="Informational only — enforced in signal code")
    run_validation: bool = Field(default=True, description="run edge-validation")
    validation_iterations: int = Field(
        default=2000, ge=100, le=20000,
        description="Monte Carlo / random-entry iteration budget for edge validation")


class BacktestResponse(BaseModel):
    status: str  # "success" or "error"
    engine_version: str
    execution_time_ms: int
    kpis: Optional[dict] = None
    trades: Optional[list] = None
    equity_curve: Optional[list] = None
    error: Optional[str] = None
    validation: Optional[dict] = None
    validation_error: Optional[str] = None


SAFE_BUILTINS = {
    'abs': abs, 'min': min, 'max': max, 'len': len, 'range': range,
    'int': int, 'float': float, 'str': str, 'bool': bool,
    'round': round, 'sum': sum, 'enumerate': enumerate, 'zip': zip,
    'True': True, 'False': False, 'None': None, 'print': print,
    'isinstance': isinstance, 'issubclass': issubclass, 'type': type,
    'list': list, 'dict': dict, 'tuple': tuple, 'set': set, 'frozenset': frozenset,
    'map': map, 'filter': filter, 'sorted': sorted, 'reversed': reversed,
    'any': any, 'all': all, 'hasattr': hasattr,
    'slice': slice, 'property': property,
    'ValueError': ValueError, 'TypeError': TypeError, 'KeyError': KeyError,
    'IndexError': IndexError, 'AttributeError': AttributeError,
    'StopIteration': StopIteration,
}

# --- AST allowlist validation -------------------------------------------------
#
# Untrusted signal code is parsed and statically validated BEFORE it is executed.
# This is an allowlist (fail-closed): any AST node type not explicitly permitted
# causes rejection. This is far stronger than the old regex denylist, which was
# trivially bypassable. It is still NOT a complete sandbox (see module docstring).
#
# Legitimate signal code only needs to: read df columns, call the provided pd/np
# and calc_*/detect_*/get_source helpers, do arithmetic/boolean/comparison ops,
# index/slice, comprehensions, simple loops, and assign the df[...] signal
# columns. The allowlist below covers exactly that surface.

_ALLOWED_NODES = frozenset({
    ast.Module, ast.Expr,
    ast.Assign, ast.AugAssign, ast.AnnAssign,
    ast.Name, ast.Load, ast.Store, ast.Constant,
    # arithmetic / boolean / comparison expressions
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.LShift, ast.RShift, ast.BitOr, ast.BitXor, ast.BitAnd, ast.MatMult,
    ast.And, ast.Or, ast.Not, ast.UAdd, ast.USub, ast.Invert,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.Is, ast.IsNot, ast.In, ast.NotIn,
    # containers / subscripting / slicing
    ast.Subscript, ast.Slice, ast.Tuple, ast.List, ast.Dict, ast.Set,
    ast.Starred,
    # calls and attribute access (attribute names further constrained below)
    ast.Call, ast.keyword, ast.Attribute,
    # expression-level + simple control flow used by real signal code
    ast.IfExp, ast.If, ast.For, ast.While, ast.Break, ast.Continue, ast.Pass,
    # comprehensions
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.comprehension,
    # locally-defined helper functions within the snippet
    ast.FunctionDef, ast.Return, ast.Lambda, ast.arguments, ast.arg,
})

# Names that must never appear in untrusted code, even though most are already
# absent from SAFE_BUILTINS. Belt-and-suspenders: reject at parse time with a
# clear message instead of relying on a NameError at runtime.
_DENIED_NAMES = frozenset({
    'eval', 'exec', 'compile', '__import__', 'globals', 'locals', 'vars',
    'getattr', 'setattr', 'delattr', 'open', 'input', 'breakpoint',
    'memoryview', 'classmethod', 'staticmethod', 'super', 'object',
    'os', 'sys', 'subprocess', 'importlib', 'builtins', 'ctypes', 'socket',
    'help', 'exit', 'quit', 'copyright', 'credits', 'license',
})


class _SignalCodeValidator(ast.NodeVisitor):
    """Walks the AST and records the first disallowed construct, if any."""

    def __init__(self):
        self.error: Optional[str] = None

    def _fail(self, node, msg: str):
        if self.error is None:
            line = getattr(node, "lineno", "?")
            self.error = f"{msg} (line {line})"

    def generic_visit(self, node):
        if self.error is not None:
            return
        if type(node) not in _ALLOWED_NODES:
            self._fail(node, f"Disallowed syntax: {type(node).__name__}")
            return
        super().generic_visit(node)

    def visit_Attribute(self, node):
        if self.error is not None:
            return
        # Every known in-process exec escape walks dunder/private attributes
        # (__class__, __globals__, __subclasses__, __builtins__, ...). Public
        # pandas/numpy APIs never start with '_', so banning leading-underscore
        # attribute access costs legitimate signal code nothing.
        if node.attr.startswith('_'):
            self._fail(node, f"Disallowed attribute access: '{node.attr}'")
            return
        self.generic_visit(node)

    def visit_Name(self, node):
        if self.error is not None:
            return
        if node.id in _DENIED_NAMES or node.id.startswith('__'):
            self._fail(node, f"Disallowed name: '{node.id}'")
            return
        self.generic_visit(node)

    def visit_Constant(self, node):
        if self.error is not None:
            return
        # Dunders hidden in string literals defeat the Attribute check above via
        # str.format()/% ("{0.__class__}".format(x)). Real signal code has no
        # reason to embed '__' in a string.
        if isinstance(node.value, str) and '__' in node.value:
            self._fail(node, "Disallowed '__' inside a string literal")
            return
        self.generic_visit(node)


def validate_signal_code(code: str) -> Optional[str]:
    """Statically validate untrusted signal code. Returns an error string if the
    code must be rejected, or None if it is allowed to run.

    AST allowlist: rejects imports, dunder/underscore attribute access, a set of
    dangerous names, and '__' in string literals. Stronger than the prior regex
    denylist, but still not a complete sandbox — see the module docstring and the
    SIGALRM timeout / subprocess-isolation TODO at the exec call site.
    """
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        return f"Signal code failed to parse: {e}"

    validator = _SignalCodeValidator()
    validator.visit(tree)
    return validator.error


# --- Execution timeout --------------------------------------------------------
# Wall-clock guard so an infinite loop / runaway snippet can't hang the worker.
# SIGALRM only interrupts at Python bytecode boundaries and only when armed from
# the main thread; uvicorn runs async endpoints on the main thread, so this
# applies in production. It will NOT interrupt a single long-running C call
# (e.g. a giant numpy op) — that gap is part of the residual risk that true
# subprocess/rlimit isolation would close.
EXEC_TIMEOUT_SECONDS = int(os.environ.get("SIGNAL_EXEC_TIMEOUT", "10"))
_HAS_SIGALRM = hasattr(_signal, "SIGALRM")


class SignalExecTimeout(Exception):
    pass


def _alarm_handler(signum, frame):
    raise SignalExecTimeout(
        f"Signal code exceeded the {EXEC_TIMEOUT_SECONDS}s execution time limit"
    )


def _sanitize_kpis(kpis: dict) -> dict:
    """Replace inf/nan floats with None for JSON serialization."""
    out = {}
    for k, v in kpis.items():
        if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
            out[k] = None
        else:
            out[k] = v
    return out


# Upper bound on equity-curve points returned for plotting. The engine emits one
# point per in-range bar (up to ~1.3M for 18yr), which is too large to ship/store;
# downsample to a plottable series. This affects the PLOT ONLY — every KPI
# (net_profit, drawdown, etc.) is computed in the engine from the full series.
MAX_EQUITY_POINTS = 2000


def _serialize_equity_curve(raw: list) -> list:
    """Engine equity series -> ordered, downsampled plot points.

    Each point is ``{"timestamp": <iso str>, "equity": <float>}``. If the series
    exceeds MAX_EQUITY_POINTS it is evenly strided, always keeping the final point
    so the curve's last value matches ``final_equity``. Additive: no KPI changes.
    """
    n = len(raw)
    if n == 0:
        return []
    if n <= MAX_EQUITY_POINTS:
        idxs = range(n)
    else:
        # Evenly spaced indices spanning [0, n-1] inclusive — always keeps the
        # first and last point, never more than MAX_EQUITY_POINTS points.
        idxs = sorted({
            round(i * (n - 1) / (MAX_EQUITY_POINTS - 1))
            for i in range(MAX_EQUITY_POINTS)
        })
    return [
        {"timestamp": str(raw[i]["date"]), "equity": float(raw[i]["equity"])}
        for i in idxs
    ]


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


@app.get("/ping")
async def ping():
    """Simple ping that doesn't load data — for Railway deploy diagnostics."""
    import os
    data_exists = os.path.exists(DATA_PATH)
    data_size = os.path.getsize(DATA_PATH) if data_exists else 0
    return {
        "status": "pong",
        "engine_version": ENGINE_VERSION,
        "data_path": DATA_PATH,
        "data_exists": data_exists,
        "data_size_bytes": data_size,
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

        # Execute untrusted signal code with a wall-clock timeout. The AST
        # allowlist (validate_signal_code, above) has already rejected obvious
        # escapes; SAFE_BUILTINS limits reachable builtins; this alarm bounds
        # runtime. This is still in-process — NOT a hardened sandbox.
        # TODO(security): move this exec into an isolated subprocess/worker with
        # CPU + memory rlimits and a hard kill, so a novel escape or a large
        # in-C allocation can't affect this web process. Tracked as follow-up.
        timeout_armed = False
        old_handler = None
        if _HAS_SIGALRM:
            try:
                old_handler = _signal.signal(_signal.SIGALRM, _alarm_handler)
                _signal.alarm(EXEC_TIMEOUT_SECONDS)
                timeout_armed = True
            except ValueError:
                # signal can only be armed from the main thread; if we're not on
                # it, run without the alarm rather than failing the request.
                timeout_armed = False
        try:
            _run_user_code(req.signal_code, sandbox_globals)
        finally:
            if timeout_armed:
                _signal.alarm(0)
                _signal.signal(_signal.SIGALRM, old_handler)
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
            take_profit_points=req.take_profit_points,
            stop_loss_points=req.stop_loss_points,
            qty_type=req.qty_type,
            qty_value=req.qty_value,
            slippage_ticks=req.slippage_ticks,
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
        # Pop the equity series out of kpis so it's serialized once into the
        # top-level equity_curve field (and not duplicated/raw inside kpis).
        equity_curve_json = _serialize_equity_curve(kpis.pop('equity_curve', []))
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

        # --- Edge validation (additive) --------------------------------------
        # Convert the engine's CLOSED trades to backtester Trades and run the
        # validation suite. engine.py sets Trade.pnl NET of commission
        # (engine.py: net_pnl = gross_pnl - entry_commission - exit_commission),
        # so t.pnl is used as-is — no further commission adjustment.
        validation, validation_error = None, None
        if req.run_validation:
            bt_trades, tid = [], 1
            for t in trades_raw:
                if t.exit_date is None or t.exit_price is None:
                    continue  # skip still-open trades; the validator needs closed trades
                bt_trades.append(BtTrade(
                    trade_id=tid, direction=t.direction,
                    entry_time=_to_et(t.entry_date), entry_price=float(t.entry_price),
                    exit_time=_to_et(t.exit_date), exit_price=float(t.exit_price),
                    qty=int(round(t.entry_qty)), pnl=float(t.pnl),
                ))
                tid += 1

            if len(bt_trades) >= 2:
                try:
                    # Feed the EXACT bars the backtest ran on so the random-entry
                    # and regime analyses light up (instead of "inconclusive: no
                    # bars"). Economics pinned to the engine's $1/point via
                    # _ENGINE_INSTRUMENT; iteration budget is caller-controlled.
                    cfg = ValidationConfig(
                        mc_iterations=req.validation_iterations,
                        random_entry_iterations=req.validation_iterations,
                        instrument=_ENGINE_INSTRUMENT,
                    )
                    result = validate(bt_trades, bars=_df_to_barset(df), config=cfg)
                    v = summarize(result)
                    validation = {
                        "overall": v.overall,
                        "summary": v.summary,
                        "findings": [
                            {"key": f.key, "title": f.title, "status": f.status,
                             "headline": f.headline, "detail": f.detail, "stat": f.stat}
                            for f in v.findings
                        ],
                        "skipped": result.skipped,
                        "regimes": {
                            scheme: {
                                "trade_counts": rb.trade_counts,
                                "per_regime": {
                                    label: {"n_trades": m.total_trades,
                                            "expectancy": _f(m.expectancy),
                                            "win_rate": _f(m.win_rate),
                                            "net_profit": _f(m.net_profit)}
                                    for label, m in rb.per_regime.items()
                                },
                            }
                            for scheme, rb in result.regimes.items()
                        },
                    }
                except Exception as e:
                    # Validation is ADDITIVE and must never break the live backtest.
                    # Surface the failure (don't swallow) so a real bug stays visible.
                    validation_error = f"{type(e).__name__}: {e}"

        execution_ms = int((time.time() - start_time) * 1000)

        return BacktestResponse(
            status="success",
            engine_version=ENGINE_VERSION,
            execution_time_ms=execution_ms,
            kpis=kpis,
            trades=trades_json[:500],  # Cap at 500 trades for response size
            equity_curve=equity_curve_json,  # downsampled [{timestamp, equity}] points
            validation=validation,
            validation_error=validation_error,
        )

    except Exception as e:
        execution_ms = int((time.time() - start_time) * 1000)
        return BacktestResponse(
            status="error",
            engine_version=ENGINE_VERSION,
            execution_time_ms=execution_ms,
            error=f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()[-500:]}",
        )


# ---------------------------------------------------------------------------
# Teachable comparison — POST /run/compare (ADR-026, stop dimension)
# ---------------------------------------------------------------------------
# Runs the user's authoritative config AND a stop-neutralized variant against the
# SAME generated signal, in one logical run, and reports exact dollar deltas.
# Purely additive: the /run single-run path above is left byte-identical.


class CompareResponse(BaseModel):
    status: str  # "success" or "error"
    engine_version: str
    execution_time_ms: int
    primary: Optional[dict] = None
    variants: Optional[list] = None
    teaching: Optional[list] = None
    same_signal: Optional[bool] = None
    error: Optional[str] = None


def _signal_hash(df: pd.DataFrame, cols) -> str:
    """Deterministic hash of the signal columns, to prove the signal series is
    identical across the primary and variant applications (same_signal)."""
    sub = df[list(cols)]
    digest = pd.util.hash_pandas_object(sub, index=True).values.tobytes()
    return hashlib.sha256(digest).hexdigest()


def _exec_signal_into_df(signal_code: str) -> pd.DataFrame:
    """Generate the trade signal ONCE: run signal_code against the data and return
    the df with its signal columns. Mirrors /run's sandbox + SIGALRM timeout (the
    /run handler itself is untouched)."""
    df = get_data()
    sandbox_globals = {
        '__builtins__': SAFE_BUILTINS,
        'pd': pd, 'np': np, 'df': df,
        'calc_ema': calc_ema, 'calc_sma': calc_sma, 'calc_smma': calc_smma,
        'calc_rsi': calc_rsi, 'calc_atr': calc_atr, 'calc_macd': calc_macd,
        'calc_obv': calc_obv, 'calc_wma': calc_wma, 'calc_hma': calc_hma,
        'detect_crossover': detect_crossover, 'detect_crossunder': detect_crossunder,
        'calc_highest': calc_highest, 'calc_lowest': calc_lowest,
        'calc_donchian': calc_donchian, 'calc_ichimoku': calc_ichimoku,
        'get_source': get_source,
    }
    timeout_armed = False
    old_handler = None
    if _HAS_SIGALRM:
        try:
            old_handler = _signal.signal(_signal.SIGALRM, _alarm_handler)
            _signal.alarm(EXEC_TIMEOUT_SECONDS)
            timeout_armed = True
        except ValueError:
            timeout_armed = False
    try:
        _run_user_code(signal_code, sandbox_globals)
    finally:
        if timeout_armed:
            _signal.alarm(0)
            _signal.signal(_signal.SIGALRM, old_handler)
    return sandbox_globals['df']


def _serialize_run(df_signaled: pd.DataFrame, direction: str, config: BacktestConfig):
    """Run one config against the already-signaled df (the engine copies df
    internally, so df_signaled is not mutated). Returns (result_dict, closed_trades).

    Raises RuntimeError on an engine-level error dict so the caller surfaces it.
    """
    if direction == "long_only":
        kpis = run_backtest(df_signaled, config)
    else:
        kpis = run_backtest_long_short(df_signaled, config)

    if "error" in kpis and len(kpis) == 1:
        raise RuntimeError(kpis["error"])

    trades_raw = kpis.pop('trades', [])
    # Same handling as /run: pop the equity series out of kpis and serialize it
    # (downsampled [{timestamp, equity}]) so each compare result carries a curve.
    equity_curve_json = _serialize_equity_curve(kpis.pop('equity_curve', []))
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

    result = {
        "engine_version": ENGINE_VERSION,
        "kpis": kpis,
        "trades": trades_json[:500],
        "equity_curve": equity_curve_json,
    }
    closed = [t for t in trades_json if t['exit_date'] is not None]
    return result, closed


# --- Significance judgment on the teaching delta (ADR-027) -------------------
# Reuse the EXACT machinery behind the single-run "Edge vs Luck" / expectancy CI:
# the percentile bootstrap (run_bootstrap), with the same iterations / seed / CI
# level the validation uses (ValidationConfig defaults) so results are
# deterministic and reproducible. We bootstrap the per-trade PAIRED delta
# (primary − variant over the same signal) and read net_profit_ci — the CI on the
# TOTAL delta, matching the reported delta_net (a total $). No new statistic.
_VC = ValidationConfig()
_BOOTSTRAP_ITERS = _VC.mc_iterations          # 10_000
_BOOTSTRAP_SEED = _VC.seed                    # 42
_BOOTSTRAP_CI_LEVEL = _VC.bootstrap_ci_level  # 0.95
# Same "low-sample" minimum the validation uses to flag runs as having too few
# trades (its temporal-stability checks are skipped below n_windows). Reused here
# rather than inventing a new threshold.
_MIN_TRADES_FOR_VALIDATION = _VC.n_windows    # 5
# run_bootstrap only reads Trade.pnl; the other fields are inert placeholders.
_DUMMY_DT = _to_et(pd.Timestamp("2000-01-01"))


def _paired_deltas(primary_closed: list, variant_closed: list) -> list:
    """Per-trade paired difference (primary.pnl − variant.pnl) over the SAME
    signal, matched by (entry_date, direction). In the aligned case (the stop
    changes only the exit, e.g. ORB) every entry matches 1:1 and the deltas sum
    to delta_net; trades present in only one run are left unmatched."""
    from collections import defaultdict
    vmap = defaultdict(list)
    for t in variant_closed:
        vmap[(t['entry_date'], t['direction'])].append(t['pnl'])
    deltas = []
    for t in primary_closed:
        key = (t['entry_date'], t['direction'])
        if vmap[key]:
            deltas.append(float(t['pnl']) - float(vmap[key].pop(0)))
    return deltas


def _delta_significance(deltas: list) -> dict:
    """Bootstrap a 95% CI on the TOTAL paired delta via run_bootstrap (same code
    path as the single-run net/expectancy CI), and classify vs zero.

    saved = CI entirely > 0; cost = CI entirely < 0; inconclusive = CI straddles 0.
    """
    if not deltas:
        return {"delta_ci_low": 0.0, "delta_ci_high": 0.0,
                "significance": "inconclusive", "n_resamples": 0}
    synthetic = [
        BtTrade(trade_id=i + 1, direction="long",
                entry_time=_DUMMY_DT, entry_price=0.0,
                exit_time=_DUMMY_DT, exit_price=0.0, qty=1, pnl=float(d))
        for i, d in enumerate(deltas)
    ]
    res = run_bootstrap(synthetic, n_iterations=_BOOTSTRAP_ITERS,
                        seed=_BOOTSTRAP_SEED, ci_level=_BOOTSTRAP_CI_LEVEL)
    ci_low, ci_high = res.net_profit_ci
    if ci_low > 0:
        significance = "saved"
    elif ci_high < 0:
        significance = "cost"
    else:
        significance = "inconclusive"
    return {"delta_ci_low": ci_low, "delta_ci_high": ci_high,
            "significance": significance, "n_resamples": res.n_iterations}


@app.post("/run/compare", response_model=CompareResponse,
          dependencies=[Depends(verify_api_key)])
async def run_compare(req: BacktestRequest):
    """TEACH-COMPARE (ADR-026): run the user's config and a stop-neutralized variant
    against the SAME signal in one logical run; report exact teaching deltas."""
    start_time = time.time()

    validation_error = validate_signal_code(req.signal_code)
    if validation_error:
        return CompareResponse(
            status="error", engine_version=ENGINE_VERSION,
            execution_time_ms=0, error=validation_error,
        )

    try:
        # 1) Generate the signal ONCE and reuse it for both applications.
        df = _exec_signal_into_df(req.signal_code)

        if req.direction == "long_only":
            required = ('long_entry', 'long_exit')
        else:
            required = ('long_entry', 'long_exit', 'short_entry', 'short_exit')
        missing = set(required) - set(df.columns)
        if missing:
            return CompareResponse(
                status="error", engine_version=ENGINE_VERSION,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error=f"Signal code did not create required columns: {missing}",
            )

        sig_cols = sorted(required)
        h_before = _signal_hash(df, sig_cols)

        # 2) Primary = the user's full config (authoritative).
        primary_config = BacktestConfig(
            initial_capital=req.initial_capital,
            commission_pct=req.commission_pct,
            start_date=req.start_date,
            end_date=req.end_date,
            take_profit_pct=req.take_profit_pct,
            stop_loss_pct=req.stop_loss_pct,
            take_profit_points=req.take_profit_points,
            stop_loss_points=req.stop_loss_points,
            qty_type=req.qty_type,
            qty_value=req.qty_value,
            slippage_ticks=req.slippage_ticks,
        )
        # 3) Variant = SAME config with only the stop neutralized.
        variant_config = dataclasses.replace(
            primary_config, stop_loss_points=0.0, stop_loss_pct=0.0,
        )

        primary_result, primary_closed = _serialize_run(df, req.direction, primary_config)
        h_mid = _signal_hash(df, sig_cols)   # engine copies df, so the signal must be untouched
        variant_result, variant_closed = _serialize_run(df, req.direction, variant_config)
        h_after = _signal_hash(df, sig_cols)
        same_signal = (h_before == h_mid == h_after)

        # 4) Teaching deltas — deterministic arithmetic, from the stop's POV.
        primary_net = primary_result["kpis"].get("net_profit") or 0.0
        variant_net = variant_result["kpis"].get("net_profit") or 0.0
        delta_net = primary_net - variant_net
        if delta_net > 0:
            direction = "saved"
        elif delta_net < 0:
            direction = "cost"
        else:
            direction = "neutral"

        primary_worst = min((t['pnl'] for t in primary_closed if t['pnl'] is not None),
                            default=0.0)
        variant_worst = min((t['pnl'] for t in variant_closed if t['pnl'] is not None),
                            default=0.0)

        # 5) Significance judgment on the delta (ADR-027): is it distinguishable
        #    from noise? Bootstrap CI on the paired per-trade delta. `direction`
        #    stays the raw sign; `significance` is the judged call.
        sig = _delta_significance(_paired_deltas(primary_closed, variant_closed))
        sufficient_data = len(primary_closed) >= _MIN_TRADES_FOR_VALIDATION

        teaching = [{
            "dimension": "stop",
            "delta_net": delta_net,
            "direction": direction,
            "primary_worst_loss": primary_worst,
            "variant_worst_loss": variant_worst,
            "trade_count": len(primary_closed),
            "delta_ci_low": sig["delta_ci_low"],
            "delta_ci_high": sig["delta_ci_high"],
            "significance": sig["significance"],
            "n_resamples": sig["n_resamples"],
            "sufficient_data": sufficient_data,
        }]
        variants = [{
            "dimension": "stop",
            "label": "no stop",
            "neutralized": {"stop_loss_points": 0},
            "result": variant_result,
        }]

        return CompareResponse(
            status="success",
            engine_version=ENGINE_VERSION,
            execution_time_ms=int((time.time() - start_time) * 1000),
            primary=primary_result,
            variants=variants,
            teaching=teaching,
            same_signal=same_signal,
        )

    except Exception as e:
        return CompareResponse(
            status="error",
            engine_version=ENGINE_VERSION,
            execution_time_ms=int((time.time() - start_time) * 1000),
            error=f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()[-500:]}",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)

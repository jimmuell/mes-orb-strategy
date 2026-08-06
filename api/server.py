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
from __future__ import annotations  # defer annotation eval (PEP 563): _map_compare_columns
# forward-references CompareResponse (defined later). Without this, Python 3.12 (Railway's
# pin) evaluates the annotation at def-time and raises NameError at import -> uvicorn can't
# load server:app -> healthcheck fails. Local Python 3.14 masks it via PEP 649 lazy eval.

import ast
import asyncio
import builtins
import contextlib
import dataclasses
import gc
import hashlib
import hmac
import math
import os
import signal as _signal
import sys
import time
import traceback
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from engine import (
    BacktestConfig, run_backtest, run_backtest_long_short,
    calc_ema, calc_sma, calc_smma, calc_rsi, calc_atr, calc_macd,
    calc_obv, calc_wma, calc_hma, detect_crossover, detect_crossunder,
    calc_highest, calc_lowest, calc_donchian, calc_ichimoku, get_source,
)
from engine.engine import __version__ as ENGINE_VERSION
from callback_writer import get_callback_writer, is_allowed_callback_url

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

    Supports Parquet (ADR-035: the full 18-yr history ships as a compact, pre-parsed
    Parquet so the deployed engine loads it lean) or CSV. Either path returns the SAME
    shape: a DatetimeIndex + Open/High/Low/Close/Volume columns.

    The bundled CSV has no header; columns are:
    timestamp, Open, High, Low, Close, Volume.
    """
    # Parquet branch — must come first (the file is binary; the CSV path below opens
    # it as text). The Parquet is written with the DatetimeIndex + OHLCV columns already
    # in place, so it returns the identical frame shape to the CSV branch.
    if filepath.endswith((".parquet", ".pq")):
        df = pd.read_parquet(filepath, engine="pyarrow")
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.DatetimeIndex(df.index)
        return df

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
    # Constant-time compare (bytes on both sides so it's total for non-ASCII keys) —
    # a plain != leaks the key length/prefix via timing.
    if not x_api_key or not hmac.compare_digest(
            x_api_key.encode("utf-8"), API_KEY.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid API key")


async def enforce_exec_enabled():
    """WIT-03 §8.7 exec-endpoint kill switch. When DISABLE_EXEC_ENDPOINTS is truthy the
    signal_code-accepting endpoints (/run, /run/async, /run/compare, /profile) refuse —
    so the future WIT Railway service sets this flag and the arbitrary-code path is dead
    code there (structured configs only, WIT-03 §1/§8.7). Default OFF: the TradingGYM
    deployment is byte-identical to today. NEVER gates /wit/v1/* or the /health,/ping,/env
    probes. Read dynamically so the flag can flip per deployment without re-import."""
    if os.environ.get("DISABLE_EXEC_ENDPOINTS", "").strip().lower() in ("1", "true"):
        raise HTTPException(
            status_code=403,
            detail="Code-execution endpoints are disabled on this deployment (EXEC_DISABLED)")


class BacktestRequest(BaseModel):
    signal_code: str = Field(..., description="Python code that adds signal columns to a DataFrame 'df'")
    direction: str = Field(default="long_short", description="'long_only' or 'long_short'")
    initial_capital: float = Field(default=10000.0)
    commission_pct: float = Field(default=0.1)
    commission_mode: str = Field(default="percent", description="'percent' | 'flat_per_rt'")
    commission_per_rt: float = Field(default=1.24, description="$ per round-trip, all-in (flat_per_rt mode)")
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
    signal_hash: Optional[str] = None  # deterministic hash of the signal columns


class AsyncBacktestRequest(BacktestRequest):
    """Same body as /run plus the caller-created backtest_runs row id (ADR-037) and the
    callback transport (ADR-040): the engine POSTs progress/results to `callback_url`
    (the backtest-callback edge function), authenticated with `callback_secret`."""
    run_id: str = Field(..., description="UUID of the caller-created backtest_runs row")
    callback_url: str = Field(..., description="backtest-callback edge function URL")
    callback_secret: str = Field(..., description="shared secret sent as X-Callback-Secret")


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


def _to_native(obj):
    """Recursively convert numpy scalars/containers to native Python types so the
    /run/compare response is always JSON-serializable, regardless of which field
    produced them (ADR-031 hardening). numpy.bool_/int64/float64/str_ -> native.

    Coercion only changes TYPES, never VALUES (np.generic.item() returns the exact
    Python-equivalent value). One chokepoint retires the per-field-cast whack-a-mole
    that caused the /run/compare 500 (a numpy.bool_ flips_profitability)."""
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_native(v) for v in obj]
    if isinstance(obj, np.generic):   # np.bool_, np.int64, np.float64, np.str_, ...
        return obj.item()
    return obj


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


@app.get("/env")
async def env():
    """ADR-048 diagnostic — report the RUNNING container's Python + installed package versions,
    so dev/prod drift is visible at a glance (a silent pandas major-version gap made the same
    code O(1) on dev / O(n) in prod and hid an 80x O(n^2) regression). Version numbers aren't
    secret, so no auth — same as /ping. Compare against api/requirements.txt after every deploy."""
    import platform
    from importlib.metadata import version, PackageNotFoundError

    def v(pkg):
        try:
            return version(pkg)
        except PackageNotFoundError:
            return None

    return {
        "engine_version": ENGINE_VERSION,
        "python": platform.python_version(),
        "packages": {p: v(p) for p in (
            "pandas", "numpy", "pyarrow", "fastapi", "uvicorn", "starlette",
            "pydantic", "anyio", "requests", "httpx", "scipy", "backtester",
            "h11", "httptools", "uvloop", "websockets", "urllib3")},
    }


@app.post("/run", response_model=BacktestResponse,
          dependencies=[Depends(enforce_exec_enabled), Depends(verify_api_key)])
async def run(req: BacktestRequest):
    """Run a backtest with AI-generated signal code (synchronous)."""
    return _execute_run_sync(req)


def _execute_run_sync(req: BacktestRequest, on_progress=None) -> BacktestResponse:
    """Core /run pipeline (ADR-037): shared by the synchronous /run endpoint and the
    async background job. `on_progress(pct)` (optional) fires at phase boundaries so the
    async path can drive a progress bar; the sync path passes None (no-op), so its
    behavior is byte-identical to before. No engine logic is duplicated."""
    start_time = time.time()

    def _progress(pct):
        if on_progress is not None:
            on_progress(pct)

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

        sig_cols = [c for c in ('long_entry', 'long_exit', 'short_entry', 'short_exit')
                    if c in df.columns]
        signal_hash = _signal_hash(df, sig_cols) if sig_cols else None
        # ADR-043: slice the signaled df to the backtest window before the engine bar-loop,
        # so runtime scales with the selected range (warmup is already in the signal columns).
        df = _slice_to_range(df, req.start_date, req.end_date)
        _progress(20)  # signal columns ready

        config = BacktestConfig(
            initial_capital=req.initial_capital,
            commission_pct=req.commission_pct,
            commission_mode=req.commission_mode,
            commission_per_rt=req.commission_per_rt,
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

        _progress(60)  # backtest complete
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

        _progress(90)  # validation done; finalizing
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
            signal_hash=signal_hash,
        )

    except Exception as e:
        execution_ms = int((time.time() - start_time) * 1000)
        return BacktestResponse(
            status="error",
            engine_version=ENGINE_VERSION,
            execution_time_ms=execution_ms,
            error=f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()[-500:]}",
        )


# --- Async execution (ADR-037) -----------------------------------------------
#
# /run/async accepts a run_id (a caller-created backtest_runs row), returns 202
# immediately, and drives that Supabase row to completion in a background task —
# no request clock, so full-history runs (~tens of seconds) don't hit Railway's
# ~60s proxy limit. The heavy compute runs in a worker thread (asyncio.to_thread)
# so the event loop stays responsive; the SIGALRM signal timeout simply no-ops off
# the main thread (already handled), which is fine — the run has no deadline here.

_HEARTBEAT_SECONDS = float(os.environ.get("ASYNC_HEARTBEAT_SECONDS", "5"))


@contextlib.contextmanager
def _no_gc(enabled: bool = True):
    """ADR-046: disable Python's cyclic GC for the duration of a backtest run.

    On Railway's Python 3.12 the non-incremental generational GC does O(n^2) work when a
    loop retains many container objects — our per-bar `equity_curve` dicts + Trade/Timestamp
    objects (×7 runs in the compare pipeline). Disabling GC over the bounded run removes it;
    it's result-preserving (GC only reclaims reference CYCLES, of which the run creates none —
    everything is freed by refcount at return). Python 3.13+ (incremental GC) doesn't need
    this, which is why the same code is linear locally and superlinear on Railway."""
    was = gc.isenabled()
    if enabled and was:
        gc.disable()
    try:
        yield
    finally:
        if enabled and was:
            gc.enable()


def _map_compare_columns(resp: CompareResponse) -> dict:
    """Map a successful COMPARE response onto backtest_runs columns (ADR-038).

    An async run must be byte-identical to a synchronous compare run as the edge
    function writes it, so the app renders it the same way:
    - results_detail = the PRIMARY run's KPIs flattened at top level, plus `_teaching`
      (the six blocks, verbatim) and `_same_signal` — the exact keys the app reads
      (BacktestTeachPanel/BacktestCoachPanel read detail._same_signal and detail._teaching;
      BacktestExplainPanel reads flattened KPI fields like sl_exit_count/gross_profit).
    - summary columns come from the PRIMARY run's KPIs; max_drawdown holds the PERCENT
      (max_drawdown_pct), matching the app's column semantics.
    """
    primary = resp.primary or {}
    k = primary.get("kpis") or {}

    # Flatten the primary KPIs at top level (Explain panel reads these), then attach the
    # teaching blocks and the same-signal flag under the exact keys the app reads.
    results_detail = dict(k)
    results_detail["_teaching"] = resp.teaching           # six blocks, verbatim
    if resp.same_signal is not None:
        results_detail["_same_signal"] = resp.same_signal  # app reads detail._same_signal

    fields = {
        "status": "complete",
        "progress": 100,
        "net_pnl": k.get("net_profit"),
        "total_trades": k.get("total_trades"),
        "wins": k.get("num_winning"),
        "losses": k.get("num_losing"),
        "win_rate": k.get("win_rate"),
        "profit_factor": k.get("profit_factor"),
        "max_drawdown": k.get("max_drawdown_pct"),   # PERCENT — matches the app's column
        "avg_winner": k.get("avg_winning"),
        "avg_loser": k.get("avg_losing"),
        "results_detail": results_detail,
        "equity_curve": primary.get("equity_curve"),
        "engine_version": resp.engine_version,
        "execution_time_ms": resp.execution_time_ms,
        "signal_hash": resp.signal_hash,
        "validation": resp.validation,
    }
    if resp.validation_error is not None:
        fields["validation_error"] = resp.validation_error
    return fields


async def _run_async_job(req: AsyncBacktestRequest, writer) -> None:
    """Background task: run the backtest and drive the backtest_runs row to a terminal
    state. Two guarantees (ADR-044) so the app never has to guess:
      1. The row ALWAYS reaches a terminal state — success -> 'complete', any error OR
         crash -> 'failed' with the traceback (truncated). It never goes silent.
      2. A HEARTBEAT re-posts 'running' every few seconds WHILE the compute runs, so a
         stall inside a stage is visible (progress alone only moves at stage boundaries).
    """
    run_id = req.run_id
    state = {"pct": 10}

    def on_progress(pct):
        # progress is best-effort; a failed progress ping must not abort the job
        state["pct"] = pct
        try:
            writer.update_run(run_id, {"status": "running", "progress": pct})
        except Exception:
            pass

    try:
        on_progress(10)  # job picked up
        # AsyncBacktestRequest IS a BacktestRequest (subclass) — the compare core reads
        # only base fields. Run the COMPARE pipeline (same as /run/compare) off the event
        # loop so an async run keeps the six teaching cards; heartbeat while it runs.
        compute = asyncio.create_task(
            asyncio.to_thread(_execute_compare_sync, req, on_progress))
        while True:
            try:
                resp = await asyncio.wait_for(asyncio.shield(compute),
                                              timeout=_HEARTBEAT_SECONDS)
                break
            except asyncio.TimeoutError:
                # still alive — touch the row (bumps updated_at) so the app watchdog can
                # tell a slow run from a dead one and time out in minutes, not never.
                try:
                    await asyncio.to_thread(
                        writer.update_run, run_id,
                        {"status": "running", "progress": state["pct"]})
                except Exception:
                    pass

        if resp.status == "success":
            writer.update_run(run_id, _map_compare_columns(resp))
        else:
            writer.update_run(run_id, {
                "status": "failed",
                "progress": 100,
                "error_message": (resp.error or "Backtest failed")[:2000],
                "engine_version": resp.engine_version,
                "execution_time_ms": resp.execution_time_ms,
            })
    except Exception as e:
        # last-resort guard: the row MUST reach a terminal state, with the traceback.
        try:
            writer.update_run(run_id, {
                "status": "failed",
                "progress": 100,
                "error_message": f"{type(e).__name__}: {e}\n{traceback.format_exc()}"[:2000],
            })
        except Exception:
            pass


@app.post("/run/async", status_code=202,
          dependencies=[Depends(enforce_exec_enabled), Depends(verify_api_key)])
async def run_async(req: AsyncBacktestRequest, background_tasks: BackgroundTasks):
    """Accept a backtest job, return 202 immediately, run it in the background and write
    progress + result to the backtest_runs row (ADR-037). The sync /run is unchanged."""
    writer = get_callback_writer(req.callback_url, req.callback_secret)
    if writer is None:
        raise HTTPException(
            status_code=400,
            detail="callback_url and callback_secret are required",
        )
    # SSRF guard (ADR-040): only POST to the allowed Supabase functions host. Rejected
    # before any request is made / the background task is scheduled.
    if not is_allowed_callback_url(req.callback_url):
        raise HTTPException(status_code=400, detail="callback_url host not allowed")
    background_tasks.add_task(_run_async_job, req, writer)
    return JSONResponse(status_code=202, content={"run_id": req.run_id, "status": "accepted"})


def _cpu_probe_ms(iters: int = 5_000_000) -> float:
    """Fixed CPU-bound busy loop. Run before/after a backtest: if the AFTER time is much
    larger, the process was CPU-throttled during the run (Railway Hobby burst credits
    exhausted) — the flat-then-cliff signature. Discriminates throttling from memory."""
    t = time.perf_counter()
    x = 0
    for _ in range(iters):
        x += 1
    return round((time.perf_counter() - t) * 1000, 1)


@app.post("/profile", dependencies=[Depends(enforce_exec_enabled), Depends(verify_api_key)])
async def profile(req: BacktestRequest, disable_gc: bool = True):
    """ADR-045/046 diagnostic — runs the COMPARE pipeline (the app's real path) and returns a
    per-stage wall-time breakdown, peak RSS, a before/after CPU-throttle probe, and GC
    collection counts, so the Railway superlinearity can be located/confirmed with PRODUCTION
    numbers. `disable_gc` (query, default true) toggles ADR-046's GC-off fix for THIS call, so
    /profile?disable_gc=false vs true A/Bs the fix on one deploy. Additive/read-only.

    Stage marks come from the existing `_progress` hooks (no engine changes):
      start→20 signal-gen (full df) + slice · 20→50 primary run · 50→80 six variants +
      teaching · 80→95 validation · 95→end serialize (_to_native). Hits the ~60s proxy for
      very long ranges — use /run/async (heartbeat) for those."""
    import resource
    probe_before = _cpu_probe_ms()
    gc.collect()
    gc0 = [s["collections"] for s in gc.get_stats()]   # per-generation collection counts
    marks = {}
    t0 = time.perf_counter()

    def on_stage(pct):
        marks[pct] = time.perf_counter() - t0

    with _no_gc(enabled=disable_gc):
        resp = await asyncio.to_thread(_execute_compare_sync, req, on_stage)
    total_ms = round((time.perf_counter() - t0) * 1000, 1)
    probe_after = _cpu_probe_ms()
    gc_collections = [a - b for a, b in zip([s["collections"] for s in gc.get_stats()], gc0)]
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_mb = round(rss / (1024 * 1024 if sys.platform == "darwin" else 1024), 1)

    def span(a, b):
        return round((marks[b] - marks[a]) * 1000, 1) if a in marks and b in marks else None

    stages_ms = {
        "signal_gen+slice": round(marks[20] * 1000, 1) if 20 in marks else None,
        "primary_run": span(20, 50),
        "variants+teaching": span(50, 80),
        "validation": span(80, 95),
        "serialize_finalize": (round(total_ms - marks[95] * 1000, 1) if 95 in marks else None),
    }
    kpis = (resp.primary or {}).get("kpis") or {}
    return {
        "engine_version": ENGINE_VERSION,
        "status": resp.status,
        "range": {"start": req.start_date, "end": req.end_date},
        "run_validation": req.run_validation,
        "trades": kpis.get("total_trades"),
        "total_ms": total_ms,
        "stages_ms": stages_ms,
        "peak_rss_mb": rss_mb,
        "cpu_probe_before_ms": probe_before,
        "cpu_probe_after_ms": probe_after,
        "cpu_throttle_ratio": round(probe_after / probe_before, 2) if probe_before else None,
        "gc_disabled": disable_gc,
        "gc_collections": gc_collections,   # [gen0, gen1, gen2] collections during the run
        "error": resp.error,
    }


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
    # Standard Edge-vs-Luck validation for the PRIMARY (user's) config — same
    # shape/field names as BacktestResponse so the app reads `response.validation`
    # identically on both endpoints (ADR-028). The variant is not validated.
    validation: Optional[dict] = None
    validation_error: Optional[str] = None
    signal_hash: Optional[str] = None  # deterministic hash of the signal columns


def _signal_hash(df: pd.DataFrame, cols) -> str:
    """Deterministic hash of the signal columns, to prove the signal series is
    identical across the primary and variant applications (same_signal)."""
    sub = df[list(cols)]
    digest = pd.util.hash_pandas_object(sub, index=True).values.tobytes()
    return hashlib.sha256(digest).hexdigest()


def _slice_to_range(df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    """ADR-043: slice an ALREADY-signaled df to the inclusive [start, end] window so the
    engine's Python bar-loop scales with the SELECTED range instead of grinding all ~1.29M
    bars on every run (the compare pipeline runs the engine 7-8x per backtest).

    Result-preserving: signals are generated on the FULL df first, so indicator warmup (e.g.
    a 200-period SMA) is already baked into the signal columns. Bounds are normalized to the
    bar-index tz the SAME way the engine does (ADR-022), and the mask mirrors the engine's
    inclusive `start <= bar_date <= end` gate exactly — so the engine trades the identical
    bars whether it receives the full or the sliced df. If the window selects no bars, the
    full df is returned unchanged (the engine then produces its usual 0-trade result rather
    than crashing on an empty index)."""
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    idx_tz = df.index.tz
    if idx_tz is not None:
        start = start.tz_localize(idx_tz) if start.tzinfo is None else start.tz_convert(idx_tz)
        end = end.tz_localize(idx_tz) if end.tzinfo is None else end.tz_convert(idx_tz)
    elif start.tzinfo is not None:
        start = start.tz_localize(None)
        end = end.tz_localize(None)
    mask = (df.index >= start) & (df.index <= end)
    sliced = df.loc[mask]
    return sliced if len(sliced) else df


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


def _validate_primary(closed_trades: list, df: pd.DataFrame,
                      validation_iterations: int):
    """Edge-vs-Luck validation for the PRIMARY result of /run/compare (ADR-028).

    Same machinery and serialized shape as the /run handler — reuses validate /
    summarize / _df_to_barset / _ENGINE_INSTRUMENT. `closed_trades` are the primary
    result's serialized trade dicts (already exit-filtered by _serialize_run).
    Returns (validation_dict_or_None, validation_error_or_None). The variant is
    intentionally NOT validated (neutralized hypothetical; would double MC cost).
    """
    bt_trades = []
    for i, t in enumerate(closed_trades, start=1):
        if t.get('exit_date') is None or t.get('exit_price') is None:
            continue
        bt_trades.append(BtTrade(
            trade_id=i, direction=t['direction'],
            entry_time=_to_et(t['entry_date']), entry_price=float(t['entry_price']),
            exit_time=_to_et(t['exit_date']), exit_price=float(t['exit_price']),
            qty=int(round(t['qty'])), pnl=float(t['pnl']),
        ))

    if len(bt_trades) < 2:
        return None, None

    try:
        cfg = ValidationConfig(
            mc_iterations=validation_iterations,
            random_entry_iterations=validation_iterations,
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
        return validation, None
    except Exception as e:
        # Additive — must never break the compare run. Surface, don't swallow.
        return None, f"{type(e).__name__}: {e}"


@app.post("/run/compare", response_model=CompareResponse,
          dependencies=[Depends(enforce_exec_enabled), Depends(verify_api_key)])
async def run_compare(req: BacktestRequest):
    """TEACH-COMPARE (ADR-026): run the user's config and a stop-neutralized variant
    against the SAME signal in one logical run; report exact teaching deltas."""
    return _execute_compare_sync(req)


def _execute_compare_sync(req: BacktestRequest, on_progress=None) -> CompareResponse:
    """Core /run/compare pipeline (ADR-037 revision): shared by the synchronous
    /run/compare endpoint and the async background job. `on_progress(pct)` (optional)
    fires at phase boundaries; the sync path passes None (no-op), so its behavior is
    byte-identical. No compare/teaching logic is duplicated."""
    start_time = time.time()

    def _progress(pct):
        if on_progress is not None:
            on_progress(pct)

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
        # ADR-043 follow-up: the RETURNED signal_hash is computed on the FULL, PRE-SLICE df so
        # it is range-INDEPENDENT — matching the single-run path, so the app's compare/optimize
        # "same-signal" grouping is consistent across date ranges (the same strategy over two
        # different windows gets the same hash).
        response_signal_hash = _signal_hash(df, sig_cols)

        # ADR-043: slice the signaled df to the window ONCE, up front — so every run
        # (primary + all variants) and every same-signal hash below uses the SAME sliced df
        # (same_signal holds), and the engine loops only the selected range. Result-preserving:
        # warmup is already baked into the signal columns generated on the full df above.
        df = _slice_to_range(df, req.start_date, req.end_date)

        # Internal same-signal chain runs on the SLICED df — it proves the 7 runs share the
        # signal they actually process; leave it as-is.
        h_before = _signal_hash(df, sig_cols)
        _progress(20)  # signal columns ready

        # 2) Primary = the user's full config (authoritative).
        primary_config = BacktestConfig(
            initial_capital=req.initial_capital,
            commission_pct=req.commission_pct,
            commission_mode=req.commission_mode,
            commission_per_rt=req.commission_per_rt,
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
        # 3b) Take-profit dimension (ADR-029): SAME config with only the take-profit
        #     neutralized (trades run to their natural signal exit / stop instead of
        #     capping at TP). Mirrors the stop variant; everything else held constant.
        tp_variant_config = dataclasses.replace(
            primary_config, take_profit_points=0.0, take_profit_pct=0.0,
        )
        # 3c) Commission dimension (ADR-031): SAME config with only commission
        #     neutralized — zero BOTH the flat per-RT fee and the percent rate so the
        #     variant is fee-free regardless of commission_mode. In flat mode this
        #     yields identical trades (fee is a fixed subtraction, sizing buffer is
        #     already 0); in percent mode the sizing buffer relaxes, handled naturally
        #     by the same paired-delta bootstrap.
        commission_variant_config = dataclasses.replace(
            primary_config, commission_per_rt=0.0, commission_pct=0.0,
        )
        # 3d) Slippage dimension (ADR-033): SAME config with only slippage neutralized — zero the
        #     adverse ticks applied to every fill. Every trade is modified (fills move), so the
        #     paired-delta bootstrap applies exactly like commission/stop/TP.
        slippage_variant_config = dataclasses.replace(primary_config, slippage_ticks=0)
        # 3e) Position-size dimension (ADR-034): neutralize to ONE fixed contract. Not a clean
        #     mirror — size has no "zero" and for fixed sizing it just MULTIPLIES every result
        #     (and the drawdown). The card teaches risk amplification, not edge; no bootstrap.
        size_variant_config = dataclasses.replace(primary_config, qty_type="fixed", qty_value=1.0)

        primary_result, primary_closed = _serialize_run(df, req.direction, primary_config)
        _progress(50)  # primary (user's) run done
        h_mid = _signal_hash(df, sig_cols)   # engine copies df, so the signal must be untouched
        variant_result, variant_closed = _serialize_run(df, req.direction, variant_config)
        h_after = _signal_hash(df, sig_cols)
        tp_variant_result, tp_variant_closed = _serialize_run(df, req.direction, tp_variant_config)
        h_after_tp = _signal_hash(df, sig_cols)
        commission_variant_result, commission_variant_closed = _serialize_run(
            df, req.direction, commission_variant_config)
        h_after_commission = _signal_hash(df, sig_cols)
        # Direction variant (ADR-032): toggle the traded side. long_short <-> long_only.
        # Unlike the other variants, the CONFIG is unchanged (primary_config); only the
        # direction PARAM is toggled.
        direction_variant_dir = "long_only" if req.direction == "long_short" else "long_short"
        # The long_short variant needs the short signal columns. A long_only request whose
        # signal never emitted them has no shorts to add, so the variant is identical to the
        # primary (delta 0 / neutral). Guard rather than let a missing-column ValueError take
        # down the whole compare response (ADR-031 lesson: one dimension must not 500 all cards).
        if (direction_variant_dir == "long_short"
                and not {"short_entry", "short_exit"} <= set(df.columns)):
            direction_variant_result, direction_variant_closed = primary_result, primary_closed
        else:
            direction_variant_result, direction_variant_closed = _serialize_run(
                df, direction_variant_dir, primary_config)
        h_after_direction = _signal_hash(df, sig_cols)
        slippage_variant_result, slippage_variant_closed = _serialize_run(
            df, req.direction, slippage_variant_config)
        h_after_slippage = _signal_hash(df, sig_cols)
        size_variant_result, size_variant_closed = _serialize_run(
            df, req.direction, size_variant_config)
        h_after_position = _signal_hash(df, sig_cols)   # signal must survive all seven runs
        same_signal = (h_before == h_mid == h_after == h_after_tp == h_after_commission
                       == h_after_direction == h_after_slippage == h_after_position)

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

        # 5b) Take-profit dimension (ADR-029) — mirror the stop block, appended
        #     SECOND (stop stays first/unchanged). delta_net = primary − tp_variant:
        #     >0 = TP "saved" (locked in gains that would've been given back);
        #     <0 = TP "cost" (capped a winner that would've run). Significance reuses
        #     the same paired-delta bootstrap. Supporting stat is the WINNER side
        #     (max pnl) instead of the stop's worst-loss (min pnl).
        tp_variant_net = tp_variant_result["kpis"].get("net_profit") or 0.0
        tp_delta_net = primary_net - tp_variant_net
        if tp_delta_net > 0:
            tp_direction = "saved"
        elif tp_delta_net < 0:
            tp_direction = "cost"
        else:
            tp_direction = "neutral"

        primary_best = max((t['pnl'] for t in primary_closed if t['pnl'] is not None),
                           default=0.0)
        tp_variant_best = max((t['pnl'] for t in tp_variant_closed if t['pnl'] is not None),
                              default=0.0)

        tp_sig = _delta_significance(_paired_deltas(primary_closed, tp_variant_closed))

        teaching.append({
            "dimension": "take_profit",
            "delta_net": tp_delta_net,
            "direction": tp_direction,
            "primary_best_win": primary_best,
            "variant_best_win": tp_variant_best,
            "trade_count": len(primary_closed),
            "delta_ci_low": tp_sig["delta_ci_low"],
            "delta_ci_high": tp_sig["delta_ci_high"],
            "significance": tp_sig["significance"],
            "n_resamples": tp_sig["n_resamples"],
            "sufficient_data": sufficient_data,
        })
        variants.append({
            "dimension": "take_profit",
            "label": "no take-profit",
            "neutralized": {"take_profit_points": 0},
            "result": tp_variant_result,
        })

        # 5c) Commission dimension (ADR-031) — mirror stop/take-profit, appended THIRD.
        #     delta_net = primary − commission_variant. The variant is fee-free, so its
        #     net is always >= primary net → delta_net <= 0 → direction is "cost"
        #     (or "neutral" at zero commission). The distinctive supporting stat is the
        #     teaching payoff: did the fees flip a profitable setup into a losing one?
        commission_variant_net = commission_variant_result["kpis"].get("net_profit") or 0.0
        commission_delta_net = primary_net - commission_variant_net
        if commission_delta_net > 0:
            commission_direction = "saved"     # not expected for commission, kept for symmetry
        elif commission_delta_net < 0:
            commission_direction = "cost"
        else:
            commission_direction = "neutral"

        # Total fees removed from P&L (a positive $ figure) and the profitability flip.
        # Per-field numpy->native casts are no longer needed here: _to_native() coerces
        # the whole response at the return chokepoint (ADR-031 serialize hardening).
        total_commission = commission_variant_net - primary_net   # == -commission_delta_net, >= 0
        flips_profitability = commission_variant_net > 0.0 and primary_net <= 0.0

        commission_sig = _delta_significance(
            _paired_deltas(primary_closed, commission_variant_closed))

        teaching.append({
            "dimension": "commission",
            "delta_net": commission_delta_net,
            "direction": commission_direction,
            "total_commission": total_commission,
            "flips_profitability": flips_profitability,
            "primary_net": primary_net,
            "variant_net": commission_variant_net,
            "trade_count": len(primary_closed),
            "delta_ci_low": commission_sig["delta_ci_low"],
            "delta_ci_high": commission_sig["delta_ci_high"],
            "significance": commission_sig["significance"],
            "n_resamples": commission_sig["n_resamples"],
            "sufficient_data": sufficient_data,
        })
        variants.append({
            "dimension": "commission",
            "label": "no commission",
            "neutralized": {"commission_per_rt": 0, "commission_pct": 0},
            "result": commission_variant_result,
        })

        # 5d) Direction dimension (ADR-032) — long_short vs long_only. The long trades are
        #     identical in both runs; the delta is ENTIRELY the short trades. delta_net =
        #     your choice − the alternative, so the saved/cost sign reads naturally for BOTH:
        #       - primary long_short: delta_net = shorts' net contribution (shorts made/lost you $)
        #       - primary long_only:  delta_net = -(shorts' would-be contribution) (adding shorts
        #         would have helped -> "cost" you by not doing it; would have hurt -> "saved")
        direction_variant_net = direction_variant_result["kpis"].get("net_profit") or 0.0
        direction_delta_net = primary_net - direction_variant_net
        if direction_delta_net > 0:
            dir_direction = "saved"
        elif direction_delta_net < 0:
            dir_direction = "cost"
        else:
            dir_direction = "neutral"

        # The shorts ARE the delta. Pull them from whichever run holds them, signed so they sum
        # to direction_delta_net, then bootstrap the CI over them directly — NOT _paired_deltas,
        # which drops unmatched trades (i.e. the shorts, the whole effect) and would falsely
        # report "inconclusive".
        if req.direction == "long_short":
            short_pnls = [float(t["pnl"]) for t in primary_closed if t["direction"] == "short"]
            short_deltas = short_pnls
        else:
            short_pnls = [float(t["pnl"]) for t in direction_variant_closed if t["direction"] == "short"]
            short_deltas = [-p for p in short_pnls]
        short_count = len(short_pnls)
        short_net = sum(short_pnls)                                   # shorts' own net, as traded
        # Did the direction choice flip a profitable run into a loss (or vice versa)?
        flips_profitability = (primary_net > 0.0) != (direction_variant_net > 0.0)

        direction_sig = _delta_significance(short_deltas)
        # Sufficiency is about the SHORTS (the delta's sample), not the whole run — reuse the
        # same min-trades threshold the other blocks use.
        direction_sufficient = short_count >= _MIN_TRADES_FOR_VALIDATION

        teaching.append({
            "dimension": "direction",
            "delta_net": direction_delta_net,
            "direction": dir_direction,
            "primary_direction": req.direction,
            "variant_direction": direction_variant_dir,
            "short_trade_count": short_count,
            "short_net": short_net,
            "flips_profitability": flips_profitability,
            "primary_net": primary_net,
            "variant_net": direction_variant_net,
            "trade_count": len(primary_closed),
            "delta_ci_low": direction_sig["delta_ci_low"],
            "delta_ci_high": direction_sig["delta_ci_high"],
            "significance": direction_sig["significance"],
            "n_resamples": direction_sig["n_resamples"],
            "sufficient_data": direction_sufficient,
        })
        variants.append({
            "dimension": "direction",
            "label": direction_variant_dir.replace("_", " "),   # "long only" / "long short"
            "neutralized": {"direction": direction_variant_dir},
            "result": direction_variant_result,
        })

        # 5e) Slippage dimension (ADR-033) — execution-cost mirror of commission. delta_net =
        #     primary − slippage-free variant. Removing adverse slippage can only help or leave
        #     net unchanged, so delta_net <= 0 → "cost" (or "neutral" when slippage_ticks == 0).
        slippage_variant_net = slippage_variant_result["kpis"].get("net_profit") or 0.0
        slippage_delta_net = primary_net - slippage_variant_net
        if slippage_delta_net > 0:
            slippage_direction = "saved"     # not expected; kept for symmetry with the other blocks
        elif slippage_delta_net < 0:
            slippage_direction = "cost"
        else:
            slippage_direction = "neutral"

        total_slippage = slippage_variant_net - primary_net   # $ removed by slippage, >= 0
        slippage_flips = slippage_variant_net > 0.0 and primary_net <= 0.0

        slippage_sig = _delta_significance(
            _paired_deltas(primary_closed, slippage_variant_closed))

        teaching.append({
            "dimension": "slippage",
            "delta_net": slippage_delta_net,
            "direction": slippage_direction,
            "total_slippage": total_slippage,
            "slippage_ticks": req.slippage_ticks,          # for the "no slippage set" nudge / display
            "flips_profitability": slippage_flips,
            "primary_net": primary_net,
            "variant_net": slippage_variant_net,
            "trade_count": len(primary_closed),
            "delta_ci_low": slippage_sig["delta_ci_low"],
            "delta_ci_high": slippage_sig["delta_ci_high"],
            "significance": slippage_sig["significance"],
            "n_resamples": slippage_sig["n_resamples"],
            "sufficient_data": sufficient_data,            # reuse the shared total-trades sufficiency
        })
        variants.append({
            "dimension": "slippage",
            "label": "no slippage",
            "neutralized": {"slippage_ticks": 0},
            "result": slippage_variant_result,
        })

        # 5f) Position-size dimension (ADR-034) — the 6th/final, and NOT a clean mirror. Neutralize
        #     to 1 fixed contract. For fixed sizing the effect is a pure deterministic multiplier
        #     (size scales BOTH net AND drawdown, never the edge), so there is no "real vs luck"
        #     test — significance is "deterministic", not bootstrapped. delta_net = primary − variant
        #     (variant = 1-contract baseline). Neutral is decided by the sizing config, not the sign.
        size_variant_net = size_variant_result["kpis"].get("net_profit") or 0.0
        size_delta_net = primary_net - size_variant_net

        if req.qty_type == "fixed" and req.qty_value == 1.0:
            size_direction = "neutral"          # the run already IS the 1-contract baseline
        elif req.qty_type != "fixed":
            size_direction = "neutral"          # v1: %/cash sizing vs 1 fixed contract is misleading
        elif size_delta_net > 0:
            size_direction = "saved"
        elif size_delta_net < 0:
            size_direction = "cost"
        else:
            size_direction = "neutral"

        _size_is_fixed = req.qty_type == "fixed"
        teaching.append({
            "dimension": "position_size",
            "delta_net": size_delta_net,
            "direction": size_direction,
            "contracts": req.qty_value if _size_is_fixed else None,
            "qty_type": req.qty_type,
            "size_multiple": req.qty_value if _size_is_fixed else None,   # user size / 1 contract
            "primary_net": primary_net,
            "variant_net": size_variant_net,                              # 1-contract baseline
            "primary_max_dd": primary_result["kpis"].get("max_drawdown"),
            "variant_max_dd": size_variant_result["kpis"].get("max_drawdown"),
            "flips_profitability": False,        # pure scaling never flips the sign for fixed sizing
            "trade_count": len(primary_closed),
            "significance": "deterministic",     # no bootstrap — the effect is a multiplier
            "sufficient_data": sufficient_data,
        })
        variants.append({
            "dimension": "position_size",
            "label": "1 contract",
            "neutralized": {"qty_type": "fixed", "qty_value": 1.0},
            "result": size_variant_result,
        })

        _progress(80)  # all variants + teaching blocks built

        # 6) Standard Edge-vs-Luck validation for the PRIMARY (user's) config only
        #    (ADR-028), gated on run_validation exactly like /run. Variant is not
        #    validated. Same field names as /run so the app reads it identically.
        validation, validation_error = None, None
        if req.run_validation:
            validation, validation_error = _validate_primary(
                primary_closed, df, req.validation_iterations)

        _progress(95)  # validation done; finalizing

        # Single numpy->native coercion pass over every structure carrying engine
        # values, so no field can reintroduce the numpy-serialization 500 (ADR-031).
        return CompareResponse(
            status="success",
            engine_version=ENGINE_VERSION,
            execution_time_ms=int((time.time() - start_time) * 1000),
            primary=_to_native(primary_result),
            variants=_to_native(variants),
            teaching=_to_native(teaching),
            same_signal=bool(same_signal),
            validation=_to_native(validation),
            validation_error=validation_error,
            signal_hash=response_signal_hash,  # full-df hash (range-independent) — ADR-043 follow-up
        )

    except Exception as e:
        return CompareResponse(
            status="error",
            engine_version=ENGINE_VERSION,
            execution_time_ms=int((time.time() - start_time) * 1000),
            error=f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()[-500:]}",
        )


# ===========================================================================
# WIT run surface — /wit/v1/* (WIT-P3d)
# Additive: the legacy /run* endpoints and their X-API-Key auth are untouched.
# This surface accepts STRUCTURED wire configs ONLY — there is no signal_code
# field anywhere here (WIT-03 §1). Wire config -> engine config via the P3c
# adapters -> the existing runners; the async job mirrors _run_async_job's
# heartbeat + guaranteed-terminal-state pattern (ADR-037).
# ===========================================================================
import datetime as _dt
import json as _json
import math as _math

from wit.mapper import (strategy_config_to_vporb, event_study_config_to_engine,
                        map_template, UnsupportedConstruct, UntestableStrategy,
                        InvalidConfig, normalize_and_disclose, validate_wire)
from wit.config_hash import config_hash as _wit_config_hash
from wit.run_store import WITRunStore
from wit.vp_orb_runner import run_vp_orb, dataset_date_range, PARQUET_5MIN as _VPORB_PARQUET
from wit.event_study import run_config, load_1min_rth, build_candles, PARQUET_1MIN as _ES_PARQUET_1MIN
from wit.sweeps import build_backtest_sweep, build_event_study_sweep
from wit.verdict import derive_verdict
from wit.extraction.ensemble import extract_template_ensemble
from wit import datasets as _wit_datasets
from wit.config import POINT_VALUE as _WIT_POINT_VALUE, TICK_SIZE as _WIT_TICK_SIZE
from callback_writer import get_wit_callback_writer

_WIT_RUNS = WITRunStore()
_WIT_STAGES = ("loading_data", "simulating", "validating")

# required top-level keys of each wire contract (structural hygiene on inbound configs)
# WIT-P3s: contract files resolved via the shared data-root resolver (env -> repo walk-up ->
# api/_shipped) so the /api-rooted Railway container finds them at import, not just the checkout.
from wit.data_paths import data_path as _wit_data_path


def _load_required(rel):
    with open(_wit_data_path("contract", rel)) as fh:
        return _json.load(fh)["required"]
_WIT_WIRE_REQUIRED = {
    "backtest": _load_required("strategy-config.v1.json"),
    "event_study": _load_required("event-study-config.v1.json"),
}


class WitBudget(BaseModel):
    max_wall_seconds: float = Field(default=600.0, gt=0)


class WitRunRequest(BaseModel):
    evaluation_id: str
    kind: str = Field(..., description="backtest | event_study")
    callback_url: str
    config: dict = Field(..., description="the WIRE StrategyConfig / EventStudyConfig")
    budget: WitBudget = Field(default_factory=WitBudget)
    sweep: bool = Field(default=False, description="run the engine-owned sensitivity grid too")


async def verify_wit_key(authorization: Optional[str] = Header(default=None)):
    """Bearer auth for /wit/v1/* (WIT-03 §2). Own env var — NOT BACKTEST_API_KEY.
    Read dynamically so config changes (and tests) take effect without re-import."""
    key = os.environ.get("WIT_ENGINE_SERVICE_KEY")
    if not key:
        raise HTTPException(status_code=503,
                            detail="Service not configured: WIT_ENGINE_SERVICE_KEY is not set")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    # constant-time compare (bytes both sides so it's total for non-ASCII keys) — a
    # plain != leaks the key length/prefix via timing.
    token = authorization[len("Bearer "):].strip()
    if not hmac.compare_digest(token.encode("utf-8"), key.encode("utf-8")):
        raise HTTPException(status_code=403, detail="Invalid service key")


def _wit_error(status: int, code: str, message: str, detail: dict | None = None):
    return JSONResponse(status_code=status,
                        content={"error": {"code": code, "message": message,
                                           "detail": detail or {}}})


def _finite(x):
    return x if isinstance(x, (int, float)) and _math.isfinite(x) else None


def _provenance(config_hash: str, dataset: str, dataset_id: str | None = None) -> dict:
    # WIT-P5p: dataset_id is optional and additive — event_study's call site (unchanged, still
    # 2-arg) keeps its exact prior shape; only the backtest call site now names the RESOLVED
    # dataset id alongside its filename, mirroring wit/analysis.py's provenance block (WIT-P5o).
    out = {"engine_version": ENGINE_VERSION, "dataset_version": dataset,
          "config_hash": config_hash,
          "completed_at": _dt.datetime.now(_dt.timezone.utc).isoformat()}
    if dataset_id is not None:
        out["dataset_id"] = dataset_id
    return out


# WIT-P4o: the engine appends ONE equity point per BAR (engine.py:958). At 5-min resolution over
# the full window that is ~1e6 points — tens of MB of JSON — which broke the front-office write at
# the Cloudflare edge (520/522) before it ever reached Postgres. A report never needs per-bar
# equity. This reduces the curve that LEAVES the engine to a daily, hard-bounded series. It does
# NOT touch any KPI: max_drawdown et al. are computed inside the engine from the FULL per-bar
# series and read from `kpis` directly; only the emitted `equity_curve` list is shrunk here.
_EQUITY_CURVE_CAP = 5000


def _daily_bounded_equity_curve(raw: list) -> tuple[list, str]:
    """Reduce a per-bar engine equity curve to a daily, capped series for the payload.

    Returns (points, resolution) where points is a list of {"t","equity"} and resolution is
    "daily" or "daily_downsampled":
      1. one point per CALENDAR DATE, keeping the LAST equity recorded that date, chronological
         order preserved (the raw curve is already in bar order);
      2. if the daily series still exceeds the cap, downsample evenly to EXACTLY the cap, always
         retaining the first and last points.
    """
    # 1) daily reduction — last-write-wins per date; dict preserves first-seen (chronological) order.
    by_date: dict[str, float] = {}
    for p in raw or []:
        by_date[str(p.get("date"))[:10]] = _finite(p.get("equity"))   # 'YYYY-MM-DD' from the bar ts
    daily = [{"t": t, "equity": e} for t, e in by_date.items()]

    if len(daily) <= _EQUITY_CURVE_CAP:
        return daily, "daily"

    # 2) hard bound: evenly-spaced indices across [0, n-1], first & last always included, EXACTLY cap.
    n = len(daily)
    idxs = [round(i * (n - 1) / (_EQUITY_CURVE_CAP - 1)) for i in range(_EQUITY_CURVE_CAP)]
    seen, keep = set(), []
    for j in idxs:                       # dedupe (rounding can collide only when n≈cap)
        if j not in seen:
            seen.add(j)
            keep.append(j)
    if len(keep) < _EQUITY_CURVE_CAP:    # backfill unused indices to guarantee exactly cap
        for j in range(n):
            if len(keep) >= _EQUITY_CURVE_CAP:
                break
            if j not in seen:
                seen.add(j)
                keep.append(j)
        keep.sort()
    return [daily[j] for j in keep], "daily_downsampled"


# ── result builders — populate ONLY what the runners actually return (§3.6) ──
def _backtest_result(res, config_hash: str, dataset: str = _wit_datasets.BUILT_IN_DEFAULT.id) -> dict:
    kpis = res.kpis
    metrics = {
        "trades": kpis.get("total_trades"),
        "net_pnl": _finite(kpis.get("net_profit")),
        "profit_factor": _finite(kpis.get("profit_factor")),
        "max_drawdown": _finite(kpis.get("max_drawdown")),
        "win_rate": _finite(kpis.get("win_rate")),
        "avg_trade": _finite(kpis.get("avg_trade")),
        "expectancy_r": None,   # GAP: run_vp_orb does not compute R-expectancy
    }
    # WIT-P4o: emit a DAILY, hard-bounded curve — never the full per-bar series (payload-size fix).
    equity, equity_resolution = _daily_bounded_equity_curve(kpis.get("equity_curve"))
    # OMITTED (not computed by run_vp_orb): confidence.bootstrap, confidence.edge_vs_luck,
    # regimes, sweep_results. trades_url null (no signed-URL infra; Supabase-side).
    # WIT-P5p: name the dataset this SPECIFIC run actually read, never the built-in module
    # constant — a run against any other dataset must not report the ES filename. `dataset` is
    # the id the caller (_wit_compute) resolved its engine_cfg from — the SAME value run_vp_orb
    # itself resolves from internally (WIT-P5o), so datasets.resolve() here reproduces exactly
    # what the run actually read. Defaults to the built-in id so a direct call with no dataset
    # argument (as an existing test does) behaves exactly as before this change.
    _spec = _wit_datasets.resolve(dataset)
    return {"kind": "backtest", "metrics": metrics, "equity_curve": equity,
            "equity_curve_resolution": equity_resolution,
            "verdict": derive_verdict("backtest", metrics),   # WIT-P4t: never claims edge
            "trades_url": None,
            "provenance": _provenance(config_hash, _spec.bars_5min, _spec.id)}


def _event_study_result(d: dict, config_hash: str) -> dict:
    # The event-study runner natively returns per-cell conditional stats + day-clustered
    # CIs (§3.6: "event-study results replace metrics with conditional distributions+CIs").
    return {"kind": "event_study", "event_study": d,
            "verdict": derive_verdict("event_study", {}),   # WIT-P4t: never claims edge
            "provenance": _provenance(config_hash, os.path.basename(_ES_PARQUET_1MIN))}


def _load_and_build_candles(engine_cfg):
    """Event-study data step (module-level so tests can stub it)."""
    one = load_1min_rth(engine_cfg.start, engine_cfg.end)
    return build_candles(one, engine_cfg.timeframe)


def _wit_compute(kind: str, engine_cfg, run_id: str, config_hash: str) -> dict:
    """Runs in a worker thread. Sets REAL pipeline stages; returns the §3.6 result."""
    if kind == "backtest":
        _WIT_RUNS.update(run_id, {"progress": {"stage": "simulating"}})
        return _backtest_result(run_vp_orb(engine_cfg), config_hash, engine_cfg.dataset)
    # event_study: observable load -> validate boundaries
    _WIT_RUNS.update(run_id, {"progress": {"stage": "loading_data"}})
    candles = _load_and_build_candles(engine_cfg)
    _WIT_RUNS.update(run_id, {"progress": {"stage": "validating"}})
    return _event_study_result(run_config(candles, engine_cfg), config_hash)


def _wit_terminal(run_id, writer, status, *, result=None, error=None):
    fields = {"status": status}
    if result is not None:
        fields["result"] = result
    if error is not None:
        fields["error"] = error
    _WIT_RUNS.update(run_id, fields)
    if writer is not None:
        payload = {"run_id": run_id, "status": status}
        if result is not None:
            payload["result"] = result
        if error is not None:
            payload["error"] = error
        try:
            writer.post(payload)     # best-effort; GET is the source of truth
        except Exception:
            pass


def _budget_error(budget_seconds: float) -> dict:
    return {"code": "BUDGET_EXCEEDED",
            "message": f"exceeded {budget_seconds}s wall budget", "detail": {}}


def _engine_error_code(e: Exception) -> str:
    """A typed engine error (e.g. vp_orb_runner.EmptyDataWindow) may carry a WIT-03 §3.7 `code`;
    surface it so the callback reads as a real product state, not always INTERNAL (WIT-P4j)."""
    code = getattr(e, "code", None)
    return code if isinstance(code, str) and code else "INTERNAL"


async def _compute_within_budget(kind: str, engine_cfg, run_id: str, config_hash: str,
                                 budget_left: float, loop) -> tuple[str, dict | None]:
    """Run ONE compute in a worker thread under a wall budget, with heartbeats. Returns
    ('ok', result) or ('timeout', None); the thread is cancelled on timeout. Exceptions
    from the compute propagate to the caller."""
    compute = asyncio.create_task(
        asyncio.to_thread(_wit_compute, kind, engine_cfg, run_id, config_hash))
    start = loop.time()
    while True:
        remaining = budget_left - (loop.time() - start)
        if remaining <= 0:
            compute.cancel()
            return "timeout", None
        try:
            result = await asyncio.wait_for(asyncio.shield(compute),
                                            timeout=min(_HEARTBEAT_SECONDS, remaining))
            return "ok", result
        except asyncio.TimeoutError:
            if loop.time() - start >= budget_left:
                compute.cancel()
                return "timeout", None
            _WIT_RUNS.update(run_id, {"status": "running"})   # heartbeat touch


async def _run_wit_job(run_id: str, kind: str, engine_cfg, config_hash: str,
                       callback_url: str, budget_seconds: float) -> None:
    """Single-run background job: heartbeat + GUARANTEED terminal state (mirrors _run_async_job)."""
    writer = get_wit_callback_writer(callback_url, os.environ.get("WIT_CALLBACK_HMAC_SECRET"))
    _WIT_RUNS.update(run_id, {"status": "running", "progress": {"stage": "loading_data"}})
    loop = asyncio.get_event_loop()
    try:
        status, result = await _compute_within_budget(
            kind, engine_cfg, run_id, config_hash, budget_seconds, loop)
        if status == "timeout":
            _wit_terminal(run_id, writer, "failed", error=_budget_error(budget_seconds))
            return
        _wit_terminal(run_id, writer, "succeeded", result=result)
    except Exception as e:
        tb = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"[:2000]
        _wit_terminal(run_id, writer, "failed",
                      error={"code": _engine_error_code(e), "message": str(e)[:500],
                             "detail": {"traceback": tb}})


async def _run_wit_sweep_job(run_id: str, kind: str, engine_cfg, config_hash: str,
                             callback_url: str, budget_seconds: float) -> None:
    """Sweep background job (WIT-03 §8.5): PRIMARY first (same budget/failure semantics), then the
    engine-owned grid SEQUENTIALLY under the SHARED remaining budget. Cells that don't fit are
    recorded as skipped — never silent. 'succeeded' iff the primary completed."""
    writer = get_wit_callback_writer(callback_url, os.environ.get("WIT_CALLBACK_HMAC_SECRET"))
    _WIT_RUNS.update(run_id, {"status": "running", "progress": {"stage": "loading_data"}})
    loop = asyncio.get_event_loop()
    start = loop.time()
    try:
        # a. primary — a primary over budget fails exactly like a single run
        status, primary_result = await _compute_within_budget(
            kind, engine_cfg, run_id, config_hash, budget_seconds, loop)
        if status == "timeout":
            _wit_terminal(run_id, writer, "failed", error=_budget_error(budget_seconds))
            return
        # b. grid, sequential, shared budget
        grid = (build_backtest_sweep(engine_cfg) if kind == "backtest"
                else build_event_study_sweep(engine_cfg))
        sensitivity: dict = {}
        skipped: list[str] = []
        stopped = False
        for name, cell_cfg in grid.items():
            if stopped:
                skipped.append(name)
                continue
            remaining = budget_seconds - (loop.time() - start)
            if remaining <= 0:
                skipped.append(name)
                stopped = True
                continue
            _WIT_RUNS.update(run_id, {"progress": {"stage": f"sweep:{name}"}})
            try:
                st, cell_result = await _compute_within_budget(
                    kind, cell_cfg, run_id, config_hash, remaining, loop)
            except Exception:
                skipped.append(name)   # a cell error doesn't complete → disclosed, loop continues
                continue
            if st == "ok":
                sensitivity[name] = cell_result
            else:                      # cell ran out of budget → it + the rest are skipped
                skipped.append(name)
                stopped = True
        # c. terminal (succeeded — the primary completed)
        result = dict(primary_result)
        result["sensitivity"] = sensitivity
        result["sweep"] = {"requested": len(grid), "completed": len(sensitivity),
                           "skipped": skipped}
        _wit_terminal(run_id, writer, "succeeded", result=result)
    except Exception as e:
        tb = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"[:2000]
        _wit_terminal(run_id, writer, "failed",
                      error={"code": _engine_error_code(e), "message": str(e)[:500],
                             "detail": {"traceback": tb}})


def _adapt_wire(kind: str, config: dict):
    """Normalize + validate against the shipped contract, then adapt to the engine config
    (WIT-P5n Pillar 2 — the SECOND validation point). Anything bypassing the mapper (e.g. a
    front-office cache-hit path that replays a stored wire) is caught and normalized here too.
    Order: normalize (backtest) BEFORE validate, so a source that says '70%' is corrected not
    rejected; then adapt (whose hard gates raise UNSUPPORTED_CONSTRUCT for their fields). Raises
    for the router to map to the error envelope."""
    if kind == "backtest":
        normalize_and_disclose(config)
    validate_wire(config, kind)
    if kind == "backtest":
        return strategy_config_to_vporb(config)
    return event_study_config_to_engine(config)


@app.post("/wit/v1/runs", status_code=202, dependencies=[Depends(verify_wit_key)])
async def wit_submit_run(req: WitRunRequest, background_tasks: BackgroundTasks):
    if req.kind == "sensitivity_sweep":
        return _wit_error(400, "UNSUPPORTED_CONSTRUCT",
                          "sensitivity_sweep runs are not supported yet",
                          {"kind": "sensitivity_sweep"})
    if req.kind not in ("backtest", "event_study"):
        return _wit_error(400, "INVALID_CONFIG", f"unknown kind '{req.kind}'",
                          {"kind": req.kind})
    if not is_allowed_callback_url(req.callback_url):
        return _wit_error(400, "INVALID_CONFIG", "callback_url host not allowed",
                          {"callback_url": req.callback_url})
    # validate + adapt (mapping bugs are engine bugs; adapter enforces mode/tz)
    try:
        engine_cfg = _adapt_wire(req.kind, req.config)
    except UnsupportedConstruct as e:
        return _wit_error(400, "UNSUPPORTED_CONSTRUCT", str(e),
                          {"field": e.field, "mode": e.mode})
    except InvalidConfig as e:                              # WIT-P5n — must precede ValueError
        return _wit_error(400, "INVALID_CONFIG", str(e), {"field": e.field})
    except UntestableStrategy as e:
        return _wit_error(400, "INVALID_CONFIG", str(e), {"class": e.cls})
    except (KeyError, TypeError, ValueError) as e:
        return _wit_error(400, "INVALID_CONFIG", f"malformed wire config: {e}", {})

    chash = _wit_config_hash(req.config)
    # A sweep and a single run of the same config are DIFFERENT jobs — key them apart so they
    # never collide. The config_hash echoed in provenance stays the plain wire-config hash (the
    # jobs receive `chash`, not the idempotency key).
    idem_hash = chash + ":sweep" if req.sweep else chash
    run_id, is_new = _WIT_RUNS.register(
        req.evaluation_id, idem_hash,
        {"kind": req.kind, "status": "queued", "progress": {"stage": None},
         "result": None, "error": None})
    if is_new:
        _WIT_RUNS.update(run_id, {"status": "queued"})
        job = _run_wit_sweep_job if req.sweep else _run_wit_job
        background_tasks.add_task(job, run_id, req.kind, engine_cfg, chash,
                                  req.callback_url, req.budget.max_wall_seconds)
    state = _WIT_RUNS.get(run_id) or {}
    return JSONResponse(status_code=202,
                        content={"run_id": run_id, "status": state.get("status", "queued"),
                                 "estimated_seconds": None})   # no honest estimator yet


@app.get("/wit/v1/runs/{run_id}", dependencies=[Depends(verify_wit_key)])
async def wit_get_run(run_id: str):
    state = _WIT_RUNS.get(run_id)
    if state is None:
        return _wit_error(404, "INVALID_CONFIG", f"unknown run_id '{run_id}'",
                          {"run_id": run_id})
    body = {"run_id": run_id, "kind": state.get("kind"), "status": state.get("status"),
            "progress": state.get("progress") or {"stage": None}}
    if state.get("status") == "succeeded":
        body["result"] = state.get("result")
    elif state.get("status") == "failed":
        body["error"] = state.get("error")
    return body


# ── GET /wit/v1/datasets (WIT-P5p) — the single source of truth for what data.dataset ids exist ──
# The app must never be able to claim a dataset the engine doesn't have (WIT-P5o's guarantee, now
# queryable). datasets.available() already excludes any catalog entry whose files are missing —
# that is NOT re-checked here. An entry whose ECONOMICS the engine doesn't apply is still listed
# (economics_supported: false) rather than omitted, so the app knows it exists even if disabled.
@app.get("/wit/v1/datasets", dependencies=[Depends(verify_wit_key)])
async def wit_list_datasets():
    out = []
    for spec in _wit_datasets.available():
        try:
            start, end = dataset_date_range(spec.id)
        except Exception as e:
            # A corrupt/unreadable parquet is possible even though the file EXISTS (available()
            # only checks presence, not readability). Drop just this entry — a broken dataset
            # should look absent, not take the whole listing down for every other dataset.
            # (WIT-P5p report: logs exactly what was dropped and why.)
            print(f"[wit_list_datasets] dropping {spec.id!r}: date-range read failed: {e}")
            continue
        out.append({
            "id": spec.id, "label": spec.label, "description": spec.description,
            "symbol": spec.symbol, "point_value": spec.point_value, "tick_size": spec.tick_size,
            "bars_granularity": spec.bars_granularity,   # WIT-P5q
            # Same comparison run_vp_orb's economics guard makes (DatasetEconomicsUnsupported) —
            # reuses wit.config.POINT_VALUE/TICK_SIZE directly, never a second literal threshold.
            "economics_supported": (spec.point_value == _WIT_POINT_VALUE
                                    and spec.tick_size == _WIT_TICK_SIZE),
            "date_range": {"start": start, "end": end},
        })
    return {"datasets": out}


# ── POST /wit/v1/map (WIT-P4b) — filled template → wire config, SYNC ──
# The mapper (map_template) gets an HTTP surface so Supabase never re-implements
# template→config mapping (WIT-04 §6; WIT-03 §1: one implementation). Pure pass-through — no
# run store, no callback, no background task, no budget, no idempotency.
class WitMapRequest(BaseModel):
    template: dict


@app.post("/wit/v1/map", dependencies=[Depends(verify_wit_key)])
async def wit_map_template(req: WitMapRequest):
    try:
        return map_template(req.template)              # 200; body = mapper output VERBATIM
    except UnsupportedConstruct as e:
        return _wit_error(400, "UNSUPPORTED_CONSTRUCT", str(e),
                          {"field": e.field, "mode": e.mode})
    except InvalidConfig as e:                              # WIT-P5n — must precede ValueError
        return _wit_error(400, "INVALID_CONFIG", str(e), {"field": e.field})
    except UntestableStrategy as e:
        # Class C is a PRODUCT OUTCOME, not a 4xx (WIT-04 §6).
        return {"kind": None, "class": e.cls, "untestable": True}
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        # WIT-P4b: AttributeError added to the spec's (KeyError,TypeError,ValueError) tuple so a
        # structurally-malformed template (e.g. a non-dict `fields`) returns a clean 400 instead of
        # a 500 — case-d's stated intent ("malformed template -> INVALID_CONFIG"). Reported.
        return _wit_error(400, "INVALID_CONFIG", f"malformed template: {e}", {})


# ── POST /wit/v1/extract (WIT-P3r) — engine-owned extraction via the k=3 ensemble ──
# Decided P3m-a, unblocked P3q: the ENGINE owns extraction; Supabase merely calls this. Mirrors the
# /wit/v1/runs async-job pattern exactly — same bearer auth (verify_wit_key), same run store +
# idempotency, same heartbeat + GUARANTEED-terminal-state, same signed callback. A dedicated kill
# switch (WIT_DISABLE_EXTRACT) 503s the route; k is env-configurable (WIT_EXTRACT_K, default 3).

# Transcript size cap. The WIT surface otherwise takes structured configs (no raw-text cap existed),
# so this is a NEW documented bound: 200_000 chars (~200 KB). A 2-hour caption track is ~120 KB, so
# this clears realistic transcripts while bounding memory and per-call model cost (k independent sends).
_WIT_EXTRACT_MAX_CHARS = int(os.environ.get("WIT_EXTRACT_MAX_CHARS", "200000"))


def _extract_k() -> int:
    """Ensemble sample count; env-tunable (WIT-P3r). Default 3 (the P3e-7 decision); floored at 1."""
    try:
        return max(1, int(os.environ.get("WIT_EXTRACT_K", "3")))
    except ValueError:
        return 3


async def enforce_extract_enabled():
    """WIT-P3r kill switch. When WIT_DISABLE_EXTRACT is truthy the extract route 503s (e.g. to stop
    model spend without a redeploy). Mirrors the DISABLE_EXEC_ENDPOINTS pattern; scoped to
    /wit/v1/extract only — never gates /wit/v1/runs or the legacy surface."""
    if os.environ.get("WIT_DISABLE_EXTRACT", "").strip().lower() in ("1", "true"):
        raise HTTPException(status_code=503,
                            detail="Extraction endpoint disabled (WIT_DISABLE_EXTRACT)")


class WitSourceMeta(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    channel: Optional[str] = None


class WitExtractRequest(BaseModel):
    evaluation_id: str
    callback_url: str
    transcript: str
    source_meta: WitSourceMeta = Field(default_factory=WitSourceMeta)
    budget: WitBudget = Field(default_factory=WitBudget)


async def _run_wit_extract_job(run_id: str, transcript: str, source_meta: dict,
                               callback_url: str, budget_seconds: float, k: int) -> None:
    """Background extraction job: run extract_template_ensemble(k) in a worker thread under the wall
    budget with heartbeats, then a GUARANTEED terminal state (mirrors _run_wit_job). The wall budget
    covers the WHOLE ensemble (all k sequential extractions share it); a timeout => BUDGET_EXCEEDED."""
    writer = get_wit_callback_writer(callback_url, os.environ.get("WIT_CALLBACK_HMAC_SECRET"))
    _WIT_RUNS.update(run_id, {"status": "running", "progress": {"stage": "extracting"}})
    loop = asyncio.get_event_loop()
    try:
        compute = asyncio.create_task(
            asyncio.to_thread(extract_template_ensemble, transcript, source_meta, k=k))
        start = loop.time()
        res = None
        while res is None:
            if budget_seconds - (loop.time() - start) <= 0:
                compute.cancel()
                _wit_terminal(run_id, writer, "failed", error=_budget_error(budget_seconds))
                return
            try:
                remaining = budget_seconds - (loop.time() - start)
                res = await asyncio.wait_for(asyncio.shield(compute),
                                             timeout=min(_HEARTBEAT_SECONDS, remaining))
            except asyncio.TimeoutError:
                if loop.time() - start >= budget_seconds:
                    compute.cancel()
                    _wit_terminal(run_id, writer, "failed", error=_budget_error(budget_seconds))
                    return
                _WIT_RUNS.update(run_id, {"status": "running"})   # heartbeat touch
        if res.get("status") == "ok":
            # raw_meta carries ensemble_meta (incl. per-run demotions/downgrades) per P3m-a/P3r.
            result = {"template": res["template"], "completeness": res["completeness"],
                      "raw_meta": {**(res.get("raw_meta") or {}),
                                   "ensemble_meta": res.get("ensemble_meta")}}
            _wit_terminal(run_id, writer, "succeeded", result=result)
        else:
            _wit_terminal(run_id, writer, "failed",
                          error={"code": "EXTRACTION_FAILED",
                                 "message": "ensemble extraction failed",
                                 "detail": {"errors": res.get("errors") or [],
                                            "ensemble_meta": res.get("ensemble_meta")}})
    except Exception as e:
        tb = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"[:2000]
        _wit_terminal(run_id, writer, "failed",
                      error={"code": _engine_error_code(e), "message": str(e)[:500],
                             "detail": {"traceback": tb}})


@app.post("/wit/v1/extract", status_code=202,
          dependencies=[Depends(enforce_extract_enabled), Depends(verify_wit_key)])
async def wit_submit_extract(req: WitExtractRequest, background_tasks: BackgroundTasks):
    transcript = req.transcript or ""
    if not transcript.strip():
        return _wit_error(400, "INVALID_CONFIG", "transcript is required and must be non-empty", {})
    if len(transcript) > _WIT_EXTRACT_MAX_CHARS:
        return _wit_error(400, "INVALID_CONFIG",
                          f"transcript exceeds the {_WIT_EXTRACT_MAX_CHARS}-char cap",
                          {"length": len(transcript), "cap": _WIT_EXTRACT_MAX_CHARS})
    if not is_allowed_callback_url(req.callback_url):
        return _wit_error(400, "INVALID_CONFIG", "callback_url host not allowed",
                          {"callback_url": req.callback_url})
    source_meta = req.source_meta.model_dump()
    # idempotency: INTERNAL content hash of transcript + source_meta, never echoed (P3f pattern);
    # prefixed so it can never collide with a run/sweep key for the same evaluation_id.
    idem = "extract:" + hashlib.sha256(
        _json.dumps({"t": transcript, "s": source_meta}, sort_keys=True,
                    separators=(",", ":")).encode("utf-8")).hexdigest()
    run_id, is_new = _WIT_RUNS.register(
        req.evaluation_id, idem,
        {"kind": "extract", "status": "queued", "progress": {"stage": None},
         "result": None, "error": None})
    if is_new:
        _WIT_RUNS.update(run_id, {"status": "queued"})
        background_tasks.add_task(_run_wit_extract_job, run_id, transcript, source_meta,
                                  req.callback_url, req.budget.max_wall_seconds, _extract_k())
    state = _WIT_RUNS.get(run_id) or {}
    return JSONResponse(status_code=202,
                        content={"run_id": run_id, "status": state.get("status", "queued"),
                                 "estimated_seconds": None})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)

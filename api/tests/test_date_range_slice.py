"""ADR-043 — slicing the signaled df to the backtest window is result-preserving.

The engine only trades inside [start, end], only appends equity / updates peak while in
range, and never holds a position before start. So running it on the FULL df (with
config.start/end) must produce identical KPIs to running it on the df PRE-SLICED to
[start, end]. This is what lets us slice before the bar-loop for the speedup.
"""
import numpy as np
import pandas as pd

import server
from server import _slice_to_range
from engine.engine import run_backtest, BacktestConfig


def _multi_year_df():
    # ~3 years of 5-min RTH-ish bars with a simple SMA-cross signal (real warmup).
    idx = pd.date_range("2021-01-04 08:30", "2023-12-29 15:00", freq="15min")
    rng = np.random.default_rng(42)
    close = 4000.0 + np.cumsum(rng.integers(-4, 5, size=len(idx)) * 0.25)
    df = pd.DataFrame({
        "Open": close, "High": close + 0.5, "Low": close - 0.5, "Close": close,
        "Volume": 100.0,
    }, index=idx)
    fast = df["Close"].rolling(20).mean()
    slow = df["Close"].rolling(60).mean()          # 60-bar warmup baked into the signals
    up = (fast > slow) & (fast.shift(1) <= slow.shift(1))
    dn = (fast < slow) & (fast.shift(1) >= slow.shift(1))
    df["long_entry"] = up.fillna(False)
    df["long_exit"] = dn.fillna(False)
    return df


START, END = "2022-06-01", "2022-08-31"   # a mid-range window (warmup lives before it)


def _kpis(df):
    cfg = BacktestConfig(qty_type="fixed", qty_value=1.0, start_date=START, end_date=END)
    return run_backtest(df, cfg)


def test_slice_is_result_preserving():
    full = _multi_year_df()
    presliced = _slice_to_range(full.copy(), START, END)

    k_full = _kpis(full)                 # engine gates [start,end] over the full df
    k_sliced = _kpis(presliced)          # engine runs the already-sliced df

    assert k_full["total_trades"] == k_sliced["total_trades"]
    assert k_full["total_trades"] > 0    # the window actually trades (guards a trivial pass)
    assert k_full["net_profit"] == k_sliced["net_profit"]
    assert k_full["max_drawdown"] == k_sliced["max_drawdown"]
    assert k_full["win_rate"] == k_sliced["win_rate"]
    assert len(k_full["equity_curve"]) == len(k_sliced["equity_curve"])


def test_slice_selects_only_the_window():
    full = _multi_year_df()
    sliced = _slice_to_range(full, START, END)
    assert sliced.index.min() >= pd.Timestamp(START)
    assert sliced.index.max() <= pd.Timestamp(END) + pd.Timedelta(days=1)
    assert 0 < len(sliced) < len(full)   # a real subset


def test_empty_window_returns_full_df_no_crash():
    # a window with no bars -> helper returns the full df so the engine still runs (0 trades),
    # rather than handing an empty index to the bar-loop.
    full = _multi_year_df()
    out = _slice_to_range(full, "1990-01-01", "1990-01-02")
    assert len(out) == len(full)


def test_slice_matches_engine_tz_handling_on_aware_index():
    # tz-aware index (like production UTC bars): slicing must still line up with the engine's
    # normalized bounds and stay a proper subset.
    full = _multi_year_df()
    full.index = full.index.tz_localize("UTC")
    sliced = _slice_to_range(full, START, END)
    assert 0 < len(sliced) < len(full)
    assert sliced.index.tz is not None

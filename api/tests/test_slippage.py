"""Tests for the adverse slippage model (ADR-024).

Deterministic known-answer cases only. tick_size = 0.25, so N ticks of slippage move a
fill by exactly N * 0.25 index points in the adverse direction (buys up, sells down).
slippage_ticks = 0 must be byte-identical to the pre-ADR-024 engine.
"""
import pandas as pd

from engine.engine import (
    run_backtest, run_backtest_long_short, BacktestConfig,
    _apply_slippage, MES_TICK_SIZE,
)

ENTRY = 5000.0
TOL = 1e-6


def _make_df(rows):
    idx = pd.date_range("2023-01-02", periods=len(rows), freq="D")
    cols = {
        "Open":  [r["o"] for r in rows],
        "High":  [r["h"] for r in rows],
        "Low":   [r["l"] for r in rows],
        "Close": [r["c"] for r in rows],
        "long_entry": [r["le"] for r in rows],
        "long_exit":  [r["lx"] for r in rows],
    }
    if any("sl_offset" in r for r in rows):
        cols["sl_offset"] = [r.get("sl_offset", 0.0) for r in rows]
    return pd.DataFrame(cols, index=idx)


# Bar0 signals long; bar1 fills entry at Open=5000; bar2 signals exit; bar3 fills exit.
def _entry_then_signal_exit():
    return [
        {"o": 4999.0, "h": 5001.0, "l": 4998.0, "c": 5000.0, "le": True,  "lx": False},
        {"o": 5000.0, "h": 5003.0, "l": 4999.0, "c": 5001.0, "le": False, "lx": True},   # entry fills @5000, exit signalled
        {"o": 5010.0, "h": 5012.0, "l": 5008.0, "c": 5011.0, "le": False, "lx": False},  # exit fills @5010
        {"o": 5011.0, "h": 5013.0, "l": 5009.0, "c": 5012.0, "le": False, "lx": False},  # flat
    ]


# Bar0 long; bar1 entry@5000; bar2 SL-check bar (Low 4990 reaches a 5pt stop).
def _entry_then_sl():
    return [
        {"o": 4999.0, "h": 5001.0, "l": 4998.0, "c": 5000.0, "le": True,  "lx": False},
        {"o": 5000.0, "h": 5003.0, "l": 4999.0, "c": 5001.0, "le": False, "lx": False},  # entry fills @5000
        {"o": 4998.0, "h": 5000.0, "l": 4990.0, "c": 4992.0, "le": False, "lx": False},  # SL bar
        {"o": 4992.0, "h": 4994.0, "l": 4990.0, "c": 4993.0, "le": False, "lx": False},  # flat
    ]


# ---------------------------------------------------------------------------
# A) Primitive math — _apply_slippage directly
# ---------------------------------------------------------------------------

def test_buy_pays_more():
    cfg = BacktestConfig(slippage_ticks=2)
    assert _apply_slippage(5000.0, "buy", cfg) == 5000.0 + 2 * MES_TICK_SIZE  # 5000.5

def test_sell_gets_less():
    cfg = BacktestConfig(slippage_ticks=2)
    assert _apply_slippage(5000.0, "sell", cfg) == 5000.0 - 2 * MES_TICK_SIZE  # 4999.5

def test_zero_ticks_is_identity():
    cfg = BacktestConfig(slippage_ticks=0)
    assert _apply_slippage(5000.0, "buy", cfg) == 5000.0
    assert _apply_slippage(5000.0, "sell", cfg) == 5000.0

def test_exact_n_times_tick_size():
    cfg = BacktestConfig(slippage_ticks=3)
    assert abs(_apply_slippage(5000.0, "buy", cfg) - 5000.75) < TOL
    assert MES_TICK_SIZE == 0.25


# ---------------------------------------------------------------------------
# B) Plumbing through run_backtest (long-only): entry +slip, exit -slip
# ---------------------------------------------------------------------------

def test_long_entry_and_exit_slipped():
    df = _make_df(_entry_then_signal_exit())
    cfg = BacktestConfig(slippage_ticks=2, commission_pct=0.0,
                         start_date="2023-01-01", end_date="2023-12-31")
    kpis = run_backtest(df, cfg)
    assert kpis["received_slippage_ticks"] == 2
    closed = [t for t in kpis["trades"] if t.exit_date is not None]
    assert closed
    t = closed[0]
    # entry is a BUY: 5000 + 2*0.25 = 5000.5 ; exit is a SELL: 5010 - 0.5 = 5009.5
    assert abs(t.entry_price - 5000.5) < TOL, t.entry_price
    assert abs(t.exit_price - 5009.5) < TOL, t.exit_price


def test_sl_exit_slipped_adverse():
    df = _make_df(_entry_then_sl())
    cfg = BacktestConfig(slippage_ticks=2, stop_loss_points=5.0, commission_pct=0.0,
                         start_date="2023-01-01", end_date="2023-12-31")
    kpis = run_backtest(df, cfg)
    closed = [t for t in kpis["trades"] if t.exit_date is not None]
    assert closed
    t = closed[0]
    # entry BUY 5000+0.5 = 5000.5 ; the stop is measured from the *slipped* entry,
    # so SL = 5000.5 - 5 = 4995.5 (hit intrabar), then the exit SELL slips:
    # 4995.5 - 0.5 = 4995.0.
    assert abs(t.entry_price - 5000.5) < TOL, t.entry_price
    assert abs(t.exit_price - 4995.0) < TOL, t.exit_price


# ---------------------------------------------------------------------------
# C) No-op invariant — slippage_ticks=0 leaves fills exactly at the bar price
# ---------------------------------------------------------------------------

def test_zero_slippage_fills_unchanged():
    df = _make_df(_entry_then_signal_exit())
    cfg = BacktestConfig(slippage_ticks=0, commission_pct=0.0,
                         start_date="2023-01-01", end_date="2023-12-31")
    kpis = run_backtest(df, cfg)
    closed = [t for t in kpis["trades"] if t.exit_date is not None]
    assert closed
    t = closed[0]
    assert abs(t.entry_price - 5000.0) < TOL  # exactly the bar Open, no slip
    assert abs(t.exit_price - 5010.0) < TOL


# ---------------------------------------------------------------------------
# D) long_short path — short entry -slip, cover +slip
# ---------------------------------------------------------------------------

def test_short_entry_and_cover_slipped():
    # Bar0 short signal; bar1 short entry fills @5000; bar2 cover signal; bar3 cover @4990.
    rows = [
        {"o": 4999.0, "h": 5001.0, "l": 4998.0, "c": 5000.0},
        {"o": 5000.0, "h": 5002.0, "l": 4998.0, "c": 4999.0},
        {"o": 4995.0, "h": 4996.0, "l": 4992.0, "c": 4993.0},
        {"o": 4990.0, "h": 4992.0, "l": 4988.0, "c": 4989.0},
    ]
    idx = pd.date_range("2023-01-02", periods=len(rows), freq="D")
    df = pd.DataFrame({
        "Open":  [r["o"] for r in rows],
        "High":  [r["h"] for r in rows],
        "Low":   [r["l"] for r in rows],
        "Close": [r["c"] for r in rows],
        "long_entry":  [False, False, False, False],
        "long_exit":   [False, False, False, False],
        "short_entry": [True,  False, False, False],
        "short_exit":  [False, False, True,  False],
    }, index=idx)
    cfg = BacktestConfig(slippage_ticks=2, commission_pct=0.0,
                         start_date="2023-01-01", end_date="2023-12-31")
    kpis = run_backtest_long_short(df, cfg)
    closed = [t for t in kpis["trades"] if t.exit_date is not None]
    assert closed
    t = closed[0]
    # short entry is a SELL: 5000 - 0.5 = 4999.5 ; cover is a BUY: 4990 + 0.5 = 4990.5
    assert abs(t.entry_price - 4999.5) < TOL, t.entry_price
    assert abs(t.exit_price - 4990.5) < TOL, t.exit_price

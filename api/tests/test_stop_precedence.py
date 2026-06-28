"""Tests for protective stop/target precedence from the entry bar (ADR-025).

Deterministic, known-answer cases only — no live data, no network.

A configured stop/target is a resting protective order that is live the instant the
position exists, including the entry bar. Both run functions now gate the intrabar
TP/SL check on `i >= entry_bar_idx` (was `i > entry_bar_idx`). The strategies here
have NO exits of their own (entry signal only) so the engine stop is the sole exit,
isolating the protective order. When no stop/target is set the block is inert
(`tp_sl_active` False), so the change is a byte-identical no-op (test_no_stop_is_noop).

Entry timing: a signal on bar N fills at bar N+1's Open; that fill bar is the entry
bar, so its High/Low must be able to trigger the stop in the same iteration.
"""
import pandas as pd

from engine.engine import run_backtest, run_backtest_long_short, BacktestConfig

TOL = 1e-6
DATES = "2023-01-01", "2023-12-31"


def _long_df(rows):
    """rows: dicts with o/h/l/c, le (long_entry), lx (long_exit)."""
    idx = pd.date_range("2023-01-02", periods=len(rows), freq="D")
    return pd.DataFrame({
        "Open":  [r["o"] for r in rows],
        "High":  [r["h"] for r in rows],
        "Low":   [r["l"] for r in rows],
        "Close": [r["c"] for r in rows],
        "long_entry": [r["le"] for r in rows],
        "long_exit":  [r["lx"] for r in rows],
    }, index=idx)


def _ls_df(rows):
    """rows: dicts with o/h/l/c + le/lx/se/sx (long/short entry/exit)."""
    idx = pd.date_range("2023-01-02", periods=len(rows), freq="D")
    return pd.DataFrame({
        "Open":  [r["o"] for r in rows],
        "High":  [r["h"] for r in rows],
        "Low":   [r["l"] for r in rows],
        "Close": [r["c"] for r in rows],
        "long_entry":  [r.get("le", False) for r in rows],
        "long_exit":   [r.get("lx", False) for r in rows],
        "short_entry": [r.get("se", False) for r in rows],
        "short_exit":  [r.get("sx", False) for r in rows],
    }, index=idx)


def _closed(kpis):
    return [t for t in kpis["trades"] if t.exit_date is not None]


# ---------------------------------------------------------------------------
# 1) Entry-bar stop (long): SL hit on the very bar the position fills.
# ---------------------------------------------------------------------------
def test_entry_bar_long_stop():
    # bar0 signals; bar1 fills @5000 AND its Low 4994 reaches SL 4995 (stop 5pt),
    # Open 5000 > 4995 so no gap. Pre-fix (i > entry_bar_idx) this never exits on bar1.
    df = _long_df([
        {"o": 4999.0, "h": 5001.0, "l": 4998.0, "c": 5000.0, "le": True,  "lx": False},
        {"o": 5000.0, "h": 5002.0, "l": 4994.0, "c": 4996.0, "le": False, "lx": False},
        {"o": 4996.0, "h": 4998.0, "l": 4994.0, "c": 4995.0, "le": False, "lx": False},
    ])
    kpis = run_backtest(df, BacktestConfig(stop_loss_points=5.0, commission_pct=0.0,
                                           start_date=DATES[0], end_date=DATES[1]))
    assert kpis["sl_exit_count"] > 0
    t = _closed(kpis)[0]
    assert abs(t.exit_price - 4995.0) < TOL, t.exit_price
    assert t.entry_date == t.exit_date, "stop must fire on the entry bar"


# ---------------------------------------------------------------------------
# 2) Entry-bar target (long): TP hit on the entry bar.
# ---------------------------------------------------------------------------
def test_entry_bar_long_target():
    df = _long_df([
        {"o": 4999.0, "h": 5001.0, "l": 4998.0, "c": 5000.0, "le": True,  "lx": False},
        {"o": 5000.0, "h": 5006.0, "l": 4999.0, "c": 5004.0, "le": False, "lx": False},  # High 5006 >= TP 5005
        {"o": 5004.0, "h": 5006.0, "l": 5002.0, "c": 5003.0, "le": False, "lx": False},
    ])
    kpis = run_backtest(df, BacktestConfig(take_profit_points=5.0, commission_pct=0.0,
                                           start_date=DATES[0], end_date=DATES[1]))
    assert kpis["tp_exit_count"] > 0
    t = _closed(kpis)[0]
    assert abs(t.exit_price - 5005.0) < TOL, t.exit_price
    assert t.entry_date == t.exit_date, "target must fire on the entry bar"


# ---------------------------------------------------------------------------
# 3) Short side: stop is ABOVE entry, target BELOW (mirror of 1/2).
# ---------------------------------------------------------------------------
def test_entry_bar_short_stop():
    # bar0 short signal; bar1 fills @5000, High 5006 reaches SL 5005 (entry+5), no gap.
    df = _ls_df([
        {"o": 5001.0, "h": 5002.0, "l": 4999.0, "c": 5000.0, "se": True},
        {"o": 5000.0, "h": 5006.0, "l": 4999.0, "c": 5004.0},
        {"o": 5004.0, "h": 5005.0, "l": 5002.0, "c": 5003.0},
    ])
    kpis = run_backtest_long_short(df, BacktestConfig(stop_loss_points=5.0, commission_pct=0.0,
                                                      start_date=DATES[0], end_date=DATES[1]))
    assert kpis["sl_exit_count"] > 0
    t = _closed(kpis)[0]
    assert t.direction == "short"
    assert abs(t.exit_price - 5005.0) < TOL, t.exit_price
    assert t.entry_date == t.exit_date, "short stop must fire on the entry bar"


def test_entry_bar_short_target():
    # bar1 fills @5000, Low 4994 reaches TP 4995 (entry-5), Open 5000 > 4995 no gap.
    df = _ls_df([
        {"o": 5001.0, "h": 5002.0, "l": 4999.0, "c": 5000.0, "se": True},
        {"o": 5000.0, "h": 5001.0, "l": 4994.0, "c": 4996.0},
        {"o": 4996.0, "h": 4998.0, "l": 4994.0, "c": 4995.0},
    ])
    kpis = run_backtest_long_short(df, BacktestConfig(take_profit_points=5.0, commission_pct=0.0,
                                                      start_date=DATES[0], end_date=DATES[1]))
    assert kpis["tp_exit_count"] > 0
    t = _closed(kpis)[0]
    assert t.direction == "short"
    assert abs(t.exit_price - 4995.0) < TOL, t.exit_price
    assert t.entry_date == t.exit_date, "short target must fire on the entry bar"


# ---------------------------------------------------------------------------
# 4) Loss is capped at the stop distance (not a multi-bar adverse drift).
# ---------------------------------------------------------------------------
def test_loss_capped_at_stop():
    # 2-pt stop, 1 fixed contract. Entry bar dips to the stop (4998); later bars
    # drift to ~4948. The stop must cap the loss at 2 pt * $5 = -$10, NOT the drift.
    df = _long_df([
        {"o": 4999.0, "h": 5001.0, "l": 4998.0, "c": 5000.0, "le": True,  "lx": False},
        {"o": 5000.0, "h": 5001.0, "l": 4997.0, "c": 4999.0, "le": False, "lx": False},  # SL 4998 hit
        {"o": 4980.0, "h": 4982.0, "l": 4975.0, "c": 4978.0, "le": False, "lx": False},  # drift
        {"o": 4950.0, "h": 4952.0, "l": 4945.0, "c": 4948.0, "le": False, "lx": False},  # drift
    ])
    cfg = BacktestConfig(stop_loss_points=2.0, qty_type="fixed", qty_value=1.0,
                         commission_pct=0.0, initial_capital=1_000_000.0,
                         start_date=DATES[0], end_date=DATES[1])
    kpis = run_backtest(df, cfg)
    assert kpis["sl_exit_count"] > 0
    t = _closed(kpis)[0]
    assert abs(t.exit_price - 4998.0) < TOL, t.exit_price          # capped at the stop
    assert abs(t.pnl - (-10.0)) < TOL, t.pnl                       # 2 pt * $5 * 1 contract
    assert t.exit_price > 4990.0, "loss must be capped, not ridden down to the drift"


# ---------------------------------------------------------------------------
# 5) Gap-through still fills at the bar Open (unchanged gap behavior).
# ---------------------------------------------------------------------------
def test_gap_through_fills_at_open():
    # Entry bar does NOT hit the stop; the NEXT bar gaps below the 5-pt stop (4995)
    # by opening at 4990 -> fill at that Open, not the 4995 stop level.
    df = _long_df([
        {"o": 4999.0, "h": 5001.0, "l": 4998.0, "c": 5000.0, "le": True,  "lx": False},
        {"o": 5000.0, "h": 5001.0, "l": 4999.0, "c": 5000.0, "le": False, "lx": False},  # no SL hit
        {"o": 4990.0, "h": 4992.0, "l": 4985.0, "c": 4988.0, "le": False, "lx": False},  # gap below 4995
    ])
    kpis = run_backtest(df, BacktestConfig(stop_loss_points=5.0, commission_pct=0.0,
                                           start_date=DATES[0], end_date=DATES[1]))
    assert kpis["sl_exit_count"] > 0
    t = _closed(kpis)[0]
    assert abs(t.exit_price - 4990.0) < TOL, t.exit_price          # the gap Open, not 4995
    assert t.entry_date != t.exit_date, "gap exit is on the later bar, not entry bar"


# ---------------------------------------------------------------------------
# 6) No stop/target -> byte-identical no-op (regression guard).
# ---------------------------------------------------------------------------
def test_no_stop_is_noop():
    # Strategy exits on its own signal; with all stops 0, tp_sl_active is False so the
    # changed branch is dead -> the trade exits at the signal-driven next Open (5010),
    # exactly as the pre-ADR-025 engine did.
    df = _long_df([
        {"o": 4999.0, "h": 5001.0, "l": 4998.0, "c": 5000.0, "le": True,  "lx": False},
        {"o": 5000.0, "h": 5003.0, "l": 4999.0, "c": 5001.0, "le": False, "lx": True},   # entry @5000, exit signalled
        {"o": 5010.0, "h": 5012.0, "l": 5008.0, "c": 5011.0, "le": False, "lx": False},  # exit fills @5010
        {"o": 5011.0, "h": 5013.0, "l": 5009.0, "c": 5012.0, "le": False, "lx": False},
    ])
    kpis = run_backtest(df, BacktestConfig(commission_pct=0.0,
                                           start_date=DATES[0], end_date=DATES[1]))
    assert kpis["sl_exit_count"] == 0
    assert kpis["tp_exit_count"] == 0
    t = _closed(kpis)[0]
    assert abs(t.entry_price - 5000.0) < TOL, t.entry_price
    assert abs(t.exit_price - 5010.0) < TOL, t.exit_price

"""Tests for constant point-denominated stops & targets (ADR-023).

Deterministic, known-answer cases only — no live data, no network.

Canonical engine unit is index points (1 pt = 1.0 price unit). The constant
config fields (take_profit_points / stop_loss_points) feed the existing offset
slot in _check_tpsl_fill; the primitive itself is unchanged.
"""
import pandas as pd

from engine.engine import run_backtest, BacktestConfig, _check_tpsl_fill

ENTRY = 5000.0
TOL = 1e-6


# ---------------------------------------------------------------------------
# A) Primitive math — _check_tpsl_fill directly
# ---------------------------------------------------------------------------

def test_long_sl_intrabar():
    # sl_level = 5000 - 5 = 4995; Low 4994 <= 4995 (not a gap, Open 5000 > 4995)
    fill = _check_tpsl_fill(
        bar_open=5000.0, bar_high=5002.0, bar_low=4994.0,
        entry_price=ENTRY, position_side="long",
        tp_pct=0.0, sl_pct=0.0, sl_offset=5.0,
    )
    assert fill == (4995.0, "sl")


def test_long_sl_gap_through_fills_at_open():
    # Open 4990 already <= sl_level 4995 -> fill at Open
    fill = _check_tpsl_fill(
        bar_open=4990.0, bar_high=4995.0, bar_low=4985.0,
        entry_price=ENTRY, position_side="long",
        tp_pct=0.0, sl_pct=0.0, sl_offset=5.0,
    )
    assert fill == (4990.0, "sl")


def test_long_tp_intrabar():
    # tp_level = 5000 + 5 = 5005; High 5006 >= 5005 (not a gap, Open 5000 < 5005)
    fill = _check_tpsl_fill(
        bar_open=5000.0, bar_high=5006.0, bar_low=4999.0,
        entry_price=ENTRY, position_side="long",
        tp_pct=0.0, sl_pct=0.0, tp_offset=5.0,
    )
    assert fill == (5005.0, "tp")


def test_short_sl_intrabar():
    # short SL is ABOVE entry: sl_level = 5000 + 5 = 5005; High 5006 >= 5005
    fill = _check_tpsl_fill(
        bar_open=5000.0, bar_high=5006.0, bar_low=4999.0,
        entry_price=ENTRY, position_side="short",
        tp_pct=0.0, sl_pct=0.0, sl_offset=5.0,
    )
    assert fill == (5005.0, "sl")


def test_both_hit_offsets_tp_wins_on_tie():
    # long, tp_offset=sl_offset=5 -> tp_level 5005, sl_level 4995, both hit.
    # Symmetric bar (High-Open == Open-Low == 6) -> TP wins on the `<=` tie.
    fill = _check_tpsl_fill(
        bar_open=5000.0, bar_high=5006.0, bar_low=4994.0,
        entry_price=ENTRY, position_side="long",
        tp_pct=0.0, sl_pct=0.0, tp_offset=5.0, sl_offset=5.0,
    )
    assert fill == (5005.0, "tp")


# ---------------------------------------------------------------------------
# Helpers for run_backtest plumbing tests
# ---------------------------------------------------------------------------

def _make_df(rows):
    """rows: list of dicts with O/H/L/C, long_entry, long_exit, [sl_offset].

    Returns a DataFrame with a DatetimeIndex the engine accepts.
    """
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


def _one_entry_then_sl_bar(extra_trade_bar=None):
    """Bar0 signals long; bar1 fills at Open=5000; bar2 is the SL-check bar.

    `extra_trade_bar` lets a caller override the bar2 dict (e.g. add sl_offset
    or change the Low). Returns the row list.
    """
    bar2 = {"o": 4998.0, "h": 5000.0, "l": 4990.0, "c": 4992.0,
            "le": False, "lx": False}
    if extra_trade_bar:
        bar2.update(extra_trade_bar)
    return [
        {"o": 4999.0, "h": 5001.0, "l": 4998.0, "c": 5000.0, "le": True,  "lx": False},  # signal
        {"o": 5000.0, "h": 5003.0, "l": 4999.0, "c": 5001.0, "le": False, "lx": False},  # entry fill @5000
        bar2,                                                                            # SL check
        {"o": 4992.0, "h": 4994.0, "l": 4990.0, "c": 4993.0, "le": False, "lx": False},  # flat
    ]


# ---------------------------------------------------------------------------
# B) Plumbing — constant stop_loss_points through run_backtest
# ---------------------------------------------------------------------------

def test_config_stop_loss_points_fires():
    df = _make_df(_one_entry_then_sl_bar())
    cfg = BacktestConfig(stop_loss_points=5.0,
                         start_date="2023-01-01", end_date="2023-12-31")
    kpis = run_backtest(df, cfg)

    assert kpis["received_stop_loss_points"] == 5.0
    assert kpis["sl_exit_count"] > 0

    closed = [t for t in kpis["trades"] if t.exit_date is not None]
    assert closed, "expected at least one closed trade"
    for t in closed:
        # non-gap SL exit fills exactly at entry - 5.0 points
        assert abs(t.exit_price - (t.entry_price - 5.0)) < TOL, (
            f"exit {t.exit_price} != entry {t.entry_price} - 5"
        )


# ---------------------------------------------------------------------------
# C) Precedence
# ---------------------------------------------------------------------------

def test_per_bar_offset_column_beats_config_constant():
    # sl_offset column = 3.0 on the trade bars; config constant = 5.0.
    # Column must win -> SL level = entry - 3 = 4997 (bar2 Low 4990 reaches it).
    rows = _one_entry_then_sl_bar({"sl_offset": 3.0})
    # give every bar an sl_offset value so the column exists cleanly
    for r in rows:
        r.setdefault("sl_offset", 3.0)
    df = _make_df(rows)
    cfg = BacktestConfig(stop_loss_points=5.0,
                         start_date="2023-01-01", end_date="2023-12-31")
    kpis = run_backtest(df, cfg)

    closed = [t for t in kpis["trades"] if t.exit_date is not None]
    assert closed
    t = closed[0]
    assert abs(t.exit_price - (t.entry_price - 3.0)) < TOL, (
        f"column offset (3pt) should win: exit {t.exit_price}, entry {t.entry_price}"
    )
    # explicitly NOT the 5-pt config level
    assert abs(t.exit_price - (t.entry_price - 5.0)) > 0.5


def test_points_beats_pct():
    # stop_loss_points=5 (-> 4995) vs stop_loss_pct=0.2 (-> 4990). Points (offset
    # slot) must win. NB: the spec's 0.1% example is degenerate at entry 5000
    # (0.1% * 5000 = 5.0 = 5pt, indistinguishable), so 0.2% is used to make the
    # tiebreak observable. bar2 Low 4985 reaches both levels.
    df = _make_df(_one_entry_then_sl_bar({"l": 4985.0}))
    cfg = BacktestConfig(stop_loss_points=5.0, stop_loss_pct=0.2,
                         start_date="2023-01-01", end_date="2023-12-31")
    kpis = run_backtest(df, cfg)

    closed = [t for t in kpis["trades"] if t.exit_date is not None]
    assert closed
    t = closed[0]
    assert abs(t.exit_price - (t.entry_price - 5.0)) < TOL, (
        f"points (5pt -> {t.entry_price - 5.0}) should bind, got {t.exit_price}"
    )
    # explicitly NOT the 0.2% level (entry * 0.998 = 4990)
    assert abs(t.exit_price - (t.entry_price * 0.998)) > 0.5

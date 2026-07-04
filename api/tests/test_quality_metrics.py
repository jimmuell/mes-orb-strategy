"""ADR-042 — deterministic generation-quality (churn) guard on KPIs.

`kpis["quality"]` is purely additive: it describes HOW the signal traded and never affects
P&L, the existing KPI fields, or trade generation.
"""
import numpy as np
import pandas as pd

from engine.engine import (run_backtest, run_backtest_long_short, BacktestConfig,
                           _quality_metrics, CHURN_TPD_MAX, CHURN_HOLD_MAX)

CFG = dict(qty_type="fixed", qty_value=1.0, start_date="2023-01-01", end_date="2023-12-31")
QUALITY_KEYS = {"trades_per_day", "median_holding_bars", "retouch_exit_share", "churn_suspected"}


def _churn_df(n=24):
    # one calendar day, flat price, entry/exit on alternating bars -> many 1-bar re-touch trades
    idx = pd.date_range("2023-01-03 08:30", periods=n, freq="5min")
    price = [100.0] * n
    return pd.DataFrame({
        "Open": price, "High": [p + 0.25 for p in price], "Low": [p - 0.25 for p in price],
        "Close": price,
        "long_entry": [i % 2 == 0 for i in range(n)],
        "long_exit": [i % 2 == 1 for i in range(n)],
    }, index=idx)


def _sane_df(days=8):
    # one entry/day held ~4 bars, rising price (real exits, not re-touch)
    rows = []
    for d in range(days):
        base = pd.Timestamp("2023-02-01 08:30") + pd.Timedelta(days=d)
        for b in range(6):
            rows.append((base + pd.Timedelta(minutes=5 * b), 100.0 + b))
    idx = pd.DatetimeIndex([r[0] for r in rows])
    px = [r[1] for r in rows]
    return pd.DataFrame({
        "Open": px, "High": [p + 0.5 for p in px], "Low": [p - 0.5 for p in px], "Close": px,
        "long_entry": [i % 6 == 0 for i in range(len(rows))],
        "long_exit": [i % 6 == 4 for i in range(len(rows))],
    }, index=idx)


def test_churn_signal_flagged():
    q = run_backtest(_churn_df(), BacktestConfig(**CFG))["quality"]
    assert set(q) == QUALITY_KEYS
    assert q["churn_suspected"] is True
    assert q["trades_per_day"] > CHURN_TPD_MAX          # > 4
    assert q["median_holding_bars"] <= CHURN_HOLD_MAX   # <= 1 bar
    assert q["retouch_exit_share"] > 0.5                # mostly exits-at-entry


def test_sane_signal_not_flagged():
    q = run_backtest(_sane_df(), BacktestConfig(**CFG))["quality"]
    assert q["churn_suspected"] is False
    assert q["trades_per_day"] <= CHURN_TPD_MAX
    assert q["median_holding_bars"] > CHURN_HOLD_MAX    # holds multiple bars
    assert q["retouch_exit_share"] == 0.0


def test_quality_is_additive_shape_unchanged():
    # every existing KPI field still present; quality is the ONLY addition (a dict with
    # exactly the four keys). Trade generation/shape is untouched.
    k = run_backtest(_sane_df(), BacktestConfig(**CFG))
    for field in ("net_profit", "net_profit_pct", "profit_factor", "max_drawdown",
                  "max_drawdown_pct", "total_trades", "num_winning", "num_losing", "win_rate",
                  "avg_winning", "avg_losing", "sl_exit_count", "tp_exit_count",
                  "equity_curve", "trades"):
        assert field in k, field
    assert isinstance(k["quality"], dict) and set(k["quality"]) == QUALITY_KEYS
    assert isinstance(k["trades"], list)   # trade list shape unchanged


def test_long_short_path_also_reports_quality():
    df = _sane_df().copy()
    df["short_entry"] = False
    df["short_exit"] = False
    q = run_backtest_long_short(df, BacktestConfig(**CFG))["quality"]
    assert set(q) == QUALITY_KEYS


def test_quality_metrics_zero_trades():
    q = _quality_metrics([], _sane_df(), BacktestConfig(**CFG))
    assert q == {"trades_per_day": 0.0, "median_holding_bars": 0.0,
                 "retouch_exit_share": 0.0, "churn_suspected": False}

"""WIT-P4o — the result payload's equity curve is daily and hard-bounded.

The engine appends one equity point per BAR (~1e6 at 5-min over the full window). That payload
broke the front-office write at the Cloudflare edge (520/522) before it reached Postgres. These
tests pin the reduction that keeps the per-bar series inside the engine:
  * one point per calendar date, last value kept, order preserved;
  * over the 5,000 cap → downsampled to EXACTLY the cap, first & last retained, marked;
  * KPIs (max_drawdown et al.) are read from the full series in `kpis` and never move.

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_equity_curve_bound.py -q
"""
from __future__ import annotations

import types

import pandas as pd

import server
from server import _daily_bounded_equity_curve, _EQUITY_CURVE_CAP


def test_daily_reduction_keeps_last_value_per_date_in_order():
    raw = [
        {"date": pd.Timestamp("2020-06-01 09:30"), "equity": 100.0},
        {"date": pd.Timestamp("2020-06-01 09:35"), "equity": 101.0},
        {"date": pd.Timestamp("2020-06-01 15:55"), "equity": 105.0},   # last of 06-01
        {"date": pd.Timestamp("2020-06-02 09:30"), "equity": 200.0},
        {"date": pd.Timestamp("2020-06-02 15:55"), "equity": 202.0},   # last of 06-02
        {"date": pd.Timestamp("2020-06-03 09:30"), "equity": 300.0},   # sole bar of 06-03
    ]
    pts, resolution = _daily_bounded_equity_curve(raw)
    assert resolution == "daily"
    assert pts == [
        {"t": "2020-06-01", "equity": 105.0},
        {"t": "2020-06-02", "equity": 202.0},
        {"t": "2020-06-03", "equity": 300.0},
    ]
    # chronological order preserved
    assert [p["t"] for p in pts] == sorted(p["t"] for p in pts)


def test_over_cap_downsampled_to_exactly_cap_first_and_last_retained():
    # 12,000 distinct calendar dates, one bar each -> daily=12,000 > cap.
    dates = pd.date_range("2000-01-03 09:30", periods=12_000, freq="D")
    raw = [{"date": ts, "equity": float(i)} for i, ts in enumerate(dates)]
    pts, resolution = _daily_bounded_equity_curve(raw)
    assert resolution == "daily_downsampled"
    assert len(pts) == _EQUITY_CURVE_CAP                       # EXACTLY the cap
    assert pts[0] == {"t": "2000-01-03", "equity": 0.0}         # first retained
    assert pts[-1] == {"t": dates[-1].strftime("%Y-%m-%d"),     # last retained
                       "equity": 11_999.0}
    # strictly increasing in time (even spacing, no dupes)
    ts = [p["t"] for p in pts]
    assert ts == sorted(ts)
    assert len(set(ts)) == len(ts)


def test_just_over_cap_still_exactly_cap():
    # n only one above the cap exercises the rounding-collision backfill path.
    dates = pd.date_range("2010-01-01 09:30", periods=_EQUITY_CURVE_CAP + 1, freq="D")
    raw = [{"date": ts, "equity": float(i)} for i, ts in enumerate(dates)]
    pts, resolution = _daily_bounded_equity_curve(raw)
    assert resolution == "daily_downsampled"
    assert len(pts) == _EQUITY_CURVE_CAP
    assert pts[0]["equity"] == 0.0
    assert pts[-1]["equity"] == float(_EQUITY_CURVE_CAP)       # last of n = cap+1 points (index cap)


def test_under_cap_marked_daily_not_downsampled():
    dates = pd.date_range("2021-01-04 09:30", periods=50, freq="D")
    raw = [{"date": ts, "equity": float(i)} for i, ts in enumerate(dates)]
    pts, resolution = _daily_bounded_equity_curve(raw)
    assert resolution == "daily"
    assert len(pts) == 50


def test_empty_curve_is_empty_daily():
    assert _daily_bounded_equity_curve([]) == ([], "daily")
    assert _daily_bounded_equity_curve(None) == ([], "daily")


def test_kpis_untouched_by_reduction():
    """`_backtest_result` must reduce ONLY the emitted curve; every metric is read straight from
    `kpis` (computed by the engine over the full per-bar series) and must be identical."""
    per_bar = [{"date": pd.Timestamp(f"2020-06-{d:02d} {h:02d}:{m:02d}"), "equity": float(d * 100 + h)}
               for d in range(1, 6) for h in (9, 15) for m in (30, 55)]   # multi-bar, multi-day
    kpis = {
        "total_trades": 16, "net_profit": 817.66, "profit_factor": 4.48,
        "max_drawdown": -123.45, "win_rate": 31.3, "avg_trade": 51.1,
        "equity_curve": per_bar,
    }
    res = types.SimpleNamespace(kpis=kpis, trades=[])
    out = server._backtest_result(res, "cfghash")

    # metrics equal the engine's kpis, digit-for-digit
    assert out["metrics"] == {
        "trades": 16, "net_pnl": 817.66, "profit_factor": 4.48,
        "max_drawdown": -123.45, "win_rate": 31.3, "avg_trade": 51.1,
        "expectancy_r": None,
    }
    # the emitted curve is daily (5 dates), NOT the 20 per-bar points
    assert out["equity_curve_resolution"] == "daily"
    assert len(out["equity_curve"]) == 5
    # the engine's own series is not mutated by the reduction
    assert len(kpis["equity_curve"]) == 20

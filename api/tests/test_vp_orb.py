"""WIT-T-0001 vertical-slice tests: volume profile (golden) + runner mechanics.

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_vp_orb.py -q
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from wit.volume_profile import build_volume_profile
from wit.config import VPORBConfig
from wit import vp_orb_runner as R


# ---------------------------------------------------------------------------
# 1. Volume-profile golden fixture — every number hand-computed below.
# ---------------------------------------------------------------------------
def _bar(high, low, vol, close=None):
    close = high if close is None else close
    return {"Open": low, "High": high, "Low": low, "Close": close, "Volume": vol}


def test_volume_profile_golden():
    """Hand-computed profile on a 0.25 grid.

    Bars (High, Low, Volume) — one spread bar exercises uniform distribution,
    the rest are single-price bars:
        spread 100.75/100.25 vol 30  -> 3 rows (100.25,100.50,100.75) = 10 each
        point  100.00        vol  5
        point  100.25        vol  9
        point  100.50        vol 30
        point  100.75        vol 10
        point  101.00        vol 16
    Row volumes (tick 0.25):
        100.00 = 5
        100.25 = 10 + 9  = 19
        100.50 = 10 + 30 = 40   <- POC
        100.75 = 10 + 10 = 20
        101.00 = 16
        total  = 100
    Value area (70% -> target 70):
        start POC 100.50 (40)
        +max(above100.75=20, below100.25=19) -> add 100.75 -> cum 60
        +max(above101.00=16, below100.25=19) -> add 100.25 -> cum 79 >= 70 stop
        band = {100.25, 100.50, 100.75}
    => POC 100.50, VAH 100.75, VAL 100.25, value-area volume 79.
    """
    bars = pd.DataFrame([
        _bar(100.75, 100.25, 30),   # spread bar
        _bar(100.00, 100.00, 5),
        _bar(100.25, 100.25, 9),
        _bar(100.50, 100.50, 30),
        _bar(100.75, 100.75, 10),
        _bar(101.00, 101.00, 16),
    ])
    vp = build_volume_profile(bars, tick_size=0.25, value_area_pct=0.70)
    assert vp is not None
    assert vp.poc == 100.50
    assert vp.vah == 100.75
    assert vp.val == 100.25
    assert vp.total_volume == 100.0
    assert vp.value_area_volume == 79.0
    assert vp.value_area_fraction >= 0.70


def test_volume_profile_uniform_spread():
    """A single wide bar spreads volume evenly across its rows."""
    bars = pd.DataFrame([_bar(100.50, 100.00, 30)])   # 3 rows -> 10 each
    vp = build_volume_profile(bars, tick_size=0.25)
    # All three rows tie at 10; POC tie-break -> nearest VW-mean = the middle row.
    assert vp.poc == 100.25
    assert vp.total_volume == 30.0


def test_volume_profile_empty_and_zero_volume():
    assert build_volume_profile(pd.DataFrame(columns=["High", "Low", "Volume"])) is None
    z = pd.DataFrame([_bar(100.0, 100.0, 0)])
    assert build_volume_profile(z) is None


# ---------------------------------------------------------------------------
# 2. Runner mechanics on a tiny synthetic ET day.
# ---------------------------------------------------------------------------
def _minute_day(date: str, prices_by_min: dict[str, float], vol: int = 100) -> pd.DataFrame:
    """Build 1-min bars for the opening window from a {HH:MM: price} map."""
    rows, idx = [], []
    for hhmm, px in prices_by_min.items():
        idx.append(pd.Timestamp(f"{date} {hhmm}"))
        rows.append({"Open": px, "High": px, "Low": px, "Close": px, "Volume": vol})
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx))


def _five_min_day(date: str, bars: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    """bars: (HH:MM, open, high, low, close). Volume fixed."""
    idx = [pd.Timestamp(f"{date} {b[0]}") for b in bars]
    df = pd.DataFrame(
        [{"Open": b[1], "High": b[2], "Low": b[3], "Close": b[4], "Volume": 500} for b in bars],
        index=pd.DatetimeIndex(idx))
    return df


def test_runner_long_breakout_produces_one_trade():
    """A clean long day: flat opening profile, then a 5-min close above VAH ->
    exactly one long trade, stop below POC, 2R target."""
    date = "2020-06-01"
    # Opening window [09:30,09:45): 15 one-min bars, all at 100.00 -> POC=VAH=VAL=100.00
    one_min = _minute_day(date, {f"09:{m:02d}": 100.00 for m in range(30, 45)})
    # 5-min RTH bars incl. the entry window. Bar at 09:45 closes above VAH(100.00).
    five = _five_min_day(date, [
        ("09:30", 100.0, 100.0, 100.0, 100.0),
        ("09:35", 100.0, 100.0, 100.0, 100.0),
        ("09:40", 100.0, 100.0, 100.0, 100.0),
        ("09:45", 100.0, 101.0, 100.0, 101.0),   # CLOSE 101 > VAH 100 -> long here
        ("09:50", 101.0, 103.0, 100.9, 102.5),   # target zone
        ("09:55", 102.5, 104.0, 102.0, 103.5),
    ] + [(f"{10 + (i // 12):02d}:{(i % 12) * 5:02d}", 103.0, 103.0, 102.0, 103.0)
         for i in range(60)])   # fill out to session end w/ benign bars

    cfg = VPORBConfig(start_date=date, end_date=date)
    sig = R.build_signals_for_day(date, five, one_min, cfg)
    assert sig is not None
    assert sig["direction"] == "long"
    # entry at 09:45 close, stop = POC - 2 ticks = 100.00 - 0.50 = 99.50
    assert sig["entry_price"] == pytest.approx(101.0)
    assert sig["sl_price"] == pytest.approx(99.50)
    # R = entry - sl = 1.50 ; target = entry + 2R = 101 + 3.00 = 104.00
    assert sig["tp_price"] == pytest.approx(104.0)


def test_runner_skips_incomplete_opening_window():
    date = "2020-06-02"
    one_min = _minute_day(date, {f"09:{m:02d}": 100.0 for m in range(30, 40)})  # only 10 bars
    five = _five_min_day(date, [("09:45", 100, 101, 100, 101)])
    cfg = VPORBConfig(start_date=date, end_date=date, min_opening_bars=15)
    assert R.build_signals_for_day(date, five, one_min, cfg) is None


def test_runner_no_break_no_trade():
    date = "2020-06-03"
    one_min = _minute_day(date, {f"09:{m:02d}": 100.0 for m in range(30, 45)})
    # price never closes beyond the value area
    five = _five_min_day(date, [
        ("09:45", 100.0, 100.2, 99.8, 100.0),
        ("09:50", 100.0, 100.2, 99.8, 100.0),
    ])
    cfg = VPORBConfig(start_date=date, end_date=date)
    assert R.build_signals_for_day(date, five, one_min, cfg) is None


def test_runner_body_beyond_mode_stricter_than_close():
    """entry_mode='body' requires the whole body beyond the level; a bar that
    only closes (but doesn't open) beyond VAH qualifies under 'close' but not 'body'."""
    date = "2020-06-04"
    one_min = _minute_day(date, {f"09:{m:02d}": 100.0 for m in range(30, 45)})
    five = _five_min_day(date, [
        ("09:45", 99.5, 101.0, 99.5, 100.5),   # opens 99.5 (below VAH), closes 100.5 (above)
        ("09:50", 100.5, 101.5, 100.4, 101.2),  # opens 100.5 > VAH 100 -> body fully beyond
    ] + [(f"10:{(i)*5:02d}", 101.0, 101.0, 100.5, 101.0) for i in range(6)])
    close_cfg = VPORBConfig(start_date=date, end_date=date, entry_mode="close")
    body_cfg = VPORBConfig(start_date=date, end_date=date, entry_mode="body")
    s_close = R.build_signals_for_day(date, five, one_min, close_cfg)
    s_body = R.build_signals_for_day(date, five, one_min, body_cfg)
    assert s_close["entry_bar"].strftime("%H:%M") == "09:45"   # first close beyond
    assert s_body["entry_bar"].strftime("%H:%M") == "09:50"    # first full body beyond


# ── WIT-P4j — an empty data window fails with a typed, coded engine error, never a pandas IndexError ──
def test_P4j_empty_frame_raises_typed_error_not_indexerror():
    empty = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    empty.index = pd.DatetimeIndex([])
    # a NON-empty 1-min frame so the WIT-P4l opening-data guard passes and this isolates the 5-min
    # empty-window guard specifically (empty `five`).
    one_min = pd.DataFrame({"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0], "Volume": [1]},
                           index=pd.DatetimeIndex(["2020-01-02 09:31"]))
    with pytest.raises(R.EmptyDataWindow) as ei:
        R.run_vp_orb(VPORBConfig(), five=empty, one_min_open=one_min)
    assert ei.value.code == "DATA_UNAVAILABLE"     # a real WIT-03 §3.7 code, not an IndexError
    assert "empty" in str(ei.value).lower()        # clean message, not a pandas traceback


# ── WIT-P4l — unrecognised / empty-frame granularity paths fail typed, never AttributeError ──
def test_P4l_unrecognised_granularity_raises_typed_before_load():
    cfg = VPORBConfig(vp_granularity="ticks_per_row_1")
    with pytest.raises(R.UnsupportedGranularity) as ei:
        R.run_vp_orb(cfg, five=None)        # raises at the top, before any data load
    assert ei.value.code == "UNSUPPORTED_CONSTRUCT"


def test_P4l_empty_1min_opening_raises_typed_not_attributeerror():
    five = pd.DataFrame({"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0], "Volume": [1]},
                        index=pd.DatetimeIndex(["2020-01-02 09:30"]))
    empty_1min = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    with pytest.raises(R.EmptyOpeningData) as ei:
        R.run_vp_orb(VPORBConfig(), five=five, one_min_open=empty_1min)   # 1-min path, empty frame
    assert ei.value.code == "DATA_UNAVAILABLE"

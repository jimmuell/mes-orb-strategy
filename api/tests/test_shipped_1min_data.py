"""WIT-P4m — the shipped RTH 1-minute parquet: presence/shape drift gate + raw-vs-parquet equality.

The parquet `api/data/ES_full_1min_rth.parquet` is DERIVED from the raw LFS text by
`tools/build_1min_rth_parquet.py`. It ships in the image (regular blob) so both compute paths
can run in production. Two tiers of test, in the spirit of the P3s drift gate:

  * Presence / consistency (CI-safe): the parquet exists, is a DatetimeIndex, its dtypes match
    what the old text loaders produced, and its coverage is consistent with the shipped 5-min
    parquet. These run everywhere.
  * Equality (local only): the derived parquet yields results IDENTICAL to the raw text — proven
    by frame equality AND a full backtest-path KPI comparison on the WIT-0001 anchor config. This
    reads the 349 MB raw LFS text, which CI does not have, so it SKIPS when the raw bytes are
    absent (a bare LFS pointer), exactly like the network-gated live tier.

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_shipped_1min_data.py -q
"""
from __future__ import annotations

import datetime as dt
import os

import pandas as pd
import pandas.testing as pdt
import pytest

from wit.config import VPORBConfig
from wit import vp_orb_runner as R
from wit.data_paths import engine_data_path

_PARQUET_1MIN = engine_data_path("ES_full_1min_rth.parquet")
_PARQUET_5MIN = engine_data_path("ES_full_5min_continuous_UNadjusted.parquet")

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
_RAW_1MIN_TXT = os.path.join(_REPO, "data", "raw", "ES_full_1min_continuous_UNadjusted.txt")

_RTH_START = dt.time(9, 30)
_RTH_LAST_1MIN = dt.time(15, 59)
_COLS = ["Open", "High", "Low", "Close", "Volume"]


# ---------------------------------------------------------------------------
# Tier 1 — presence / shape / consistency (CI-safe)
# ---------------------------------------------------------------------------
def test_shipped_1min_parquet_exists_and_shape():
    assert os.path.isfile(_PARQUET_1MIN), f"missing shipped 1-min parquet: {_PARQUET_1MIN}"
    df = pd.read_parquet(_PARQUET_1MIN)
    assert isinstance(df.index, pd.DatetimeIndex)      # not a RangeIndex — the P4l failure class
    assert df.index.is_monotonic_increasing
    assert list(df.columns) == _COLS
    # Same dtypes the old text loaders produced (float64 OHLC, int64 Volume) → identical results.
    assert [str(t) for t in df.dtypes] == ["float64", "float64", "float64", "float64", "int64"]
    # RTH-only: every bar is inside [09:30, 15:59].
    t = df.index.time
    assert t.min() >= _RTH_START and t.max() <= _RTH_LAST_1MIN


def test_shipped_1min_range_consistent_with_5min():
    one = pd.read_parquet(_PARQUET_1MIN, columns=[]).index
    five = pd.read_parquet(_PARQUET_5MIN, columns=[]).index
    five_rth = five[(pd.Series(five.time, index=five) >= _RTH_START).values &
                    (pd.Series(five.time, index=five) <= dt.time(15, 55)).values]
    # Same coverage start; 1-min extends at least as far as the 5-min RTH data.
    assert one.min().date() == five.min().date()
    assert one.max().date() >= five_rth.max().date()
    # No trading day present in the 5-min RTH data is missing from the 1-min data.
    one_days = set(pd.DatetimeIndex(one).normalize())
    five_days = set(pd.DatetimeIndex(five_rth).normalize())
    assert five_days.issubset(one_days), f"{len(five_days - one_days)} 5-min days missing from 1-min"
    # A full RTH session is 390 one-minute bars; median/day sits at 390 (half-days pull it no lower).
    per_day = pd.Series(1, index=pd.DatetimeIndex(one)).groupby(pd.DatetimeIndex(one).normalize()).sum()
    assert 380 <= per_day.median() <= 391


# ---------------------------------------------------------------------------
# Tier 2 — raw-vs-parquet equality (local only; skips without the raw LFS bytes)
# ---------------------------------------------------------------------------
def _raw_available() -> bool:
    return os.path.isfile(_RAW_1MIN_TXT) and os.path.getsize(_RAW_1MIN_TXT) > 1_000_000


def _raw_1min_opening(start, end, rs, re) -> pd.DataFrame:
    """The OLD text-loader logic, verbatim — the reference the parquet must reproduce."""
    df = pd.read_csv(_RAW_1MIN_TXT, header=None, names=["timestamp", *_COLS],
                     parse_dates=["timestamp"]).set_index("timestamp")
    df = df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end) + pd.Timedelta(days=1))]
    t = df.index.time
    a, b = R._parse_hm(rs), R._parse_hm(re)
    return df[(t >= a) & (t < b)]


@pytest.mark.skipif(not _raw_available(),
                    reason="raw 1-min LFS text absent (bare pointer) — equality proof runs locally only")
def test_raw_vs_parquet_kpis_identical():
    """WIT-0001 anchor config: the derived parquet must produce results IDENTICAL to the raw text —
    frame-equal on the opening window AND every backtest KPI equal to the digit. A 2-year slice keeps
    local runtime modest while exercising the full profile→signal→engine path over hundreds of trades.
    (The full 2016–2026 window was verified by hand in the WIT-P4m report; same result.)"""
    cfg = VPORBConfig(start_date="2020-01-02", end_date="2021-12-31")

    raw_open = _raw_1min_opening(cfg.start_date, cfg.end_date, cfg.range_start, cfg.range_end)
    pq_open = R.load_1min_opening(cfg.start_date, cfg.end_date, cfg.range_start, cfg.range_end)
    pdt.assert_frame_equal(raw_open, pq_open, check_exact=True)   # byte-for-byte identical bars

    five = R.load_5min(cfg.start_date, cfg.end_date)
    res_raw = R.run_vp_orb(cfg, five=five.copy(), one_min_open=raw_open)
    res_pq = R.run_vp_orb(cfg, five=five.copy(), one_min_open=pq_open)

    def scalar_kpis(k: dict) -> dict:
        return {kk: k[kk] for kk in sorted(k) if not isinstance(k[kk], (list, dict))}

    assert scalar_kpis(res_raw.kpis) == scalar_kpis(res_pq.kpis)   # every KPI equal, not approximate
    assert len(res_raw.plans) == len(res_pq.plans)
    assert res_raw.kpis["total_trades"] > 0                        # the proof actually traded

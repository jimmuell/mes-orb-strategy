"""WIT-0002 candle-formation event study — golden + rule tests.

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_event_study.py -q
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from wit.path_metrics import compute_path, classify_bucket, PathMetrics
from wit import event_study as ES


# ---------------------------------------------------------------------------
# 1. Path efficiency + counter-retracement (hand-computed 5-sub-bar candles)
# ---------------------------------------------------------------------------
def test_path_efficiency_monotonic_spike():
    # open 100.00, five +0.20 sub-closes -> perfectly monotonic
    pm = compute_path(100.00, [100.20, 100.40, 100.60, 100.80, 101.00])
    assert pm.direction == 1
    assert pm.body == pytest.approx(1.00)
    assert pm.efficiency == pytest.approx(1.0)          # net 1.00 / total 1.00
    assert pm.retrace_price == pytest.approx(0.0)
    assert pm.retrace_pct == pytest.approx(0.0)


def test_counter_retracement_pct_of_body():
    # open 100.00, dips to 100.20 after a 100.60 pop, then closes 101.00
    pm = compute_path(100.00, [100.60, 100.20, 100.40, 100.80, 101.00])
    # steps: .60,.40,.20,.40,.20 -> total 1.80 ; net 1.00 -> eff = 0.5556
    assert pm.efficiency == pytest.approx(1.0 / 1.8, abs=1e-6)
    # max drawdown from running peak 100.60 to 100.20 = 0.40 = 40% of the 1.00 body
    assert pm.retrace_price == pytest.approx(0.40)
    assert pm.retrace_pct == pytest.approx(0.40)


def test_bearish_spike_symmetry():
    pm = compute_path(101.00, [100.80, 100.60, 100.40, 100.20, 100.00])
    assert pm.direction == -1
    assert pm.efficiency == pytest.approx(1.0)
    assert pm.retrace_pct == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 2. Bucket assignment (threshold mode: E=0.50, cap=0.20, P=0.40)
# ---------------------------------------------------------------------------
_TH = dict(spike_eff=0.50, spike_giveback_cap=0.20, pullback_p=0.40)


def test_bucket_spike():
    pm = compute_path(100.00, [100.20, 100.40, 100.60, 100.80, 101.00])
    assert classify_bucket(pm, **_TH) == "spike"           # rp 0 <= cap, eff 1 >= 0.5


def test_bucket_pullback_boundary_inclusive():
    pm = compute_path(100.00, [100.60, 100.20, 100.40, 100.80, 101.00])
    assert pm.retrace_pct == pytest.approx(0.40)
    assert classify_bucket(pm, **_TH) == "pullback"          # rp 0.40 >= P 0.40


def test_bucket_middle():
    # rp 0.30 (between cap 0.20 and P 0.40) -> neither spike nor pullback
    pm = compute_path(100.00, [100.50, 100.20, 100.60, 100.90, 101.00])
    assert pm.retrace_pct == pytest.approx(0.30)
    assert classify_bucket(pm, **_TH) == "middle"


def test_bucket_doji_is_middle():
    pm = compute_path(100.00, [100.10, 99.90, 100.05, 99.95, 100.00])  # body 0
    assert pm.body == 0
    assert classify_bucket(pm, **_TH) == "middle"


# ---------------------------------------------------------------------------
# 3. Completeness gate — 5-min candle needs all 5 sub-bars
# ---------------------------------------------------------------------------
def _one_min(rows):
    idx = [pd.Timestamp(t) for t, *_ in rows]
    data = [{"Open": o, "High": h, "Low": l, "Close": c, "Volume": 100}
            for _, o, h, l, c in rows]
    return pd.DataFrame(data, index=pd.DatetimeIndex(idx))


def test_completeness_gate_drops_short_candle():
    day = "2020-06-01"
    # 09:30 bucket: full 5 sub-bars ; 09:35 bucket: only 4 (missing 09:39) -> dropped
    rows = []
    for m in range(30, 35):
        rows.append((f"{day} 09:{m}:00", 100.0, 100.1, 99.9, 100.0 + 0.05 * (m - 30)))
    for m in range(35, 39):   # only 4 of 5
        rows.append((f"{day} 09:{m}:00", 100.3, 100.4, 100.2, 100.3))
    candles = ES.build_candles(_one_min(rows), "5min")
    times = [ts.strftime("%H:%M") for ts in candles.index]
    assert "09:30" in times
    assert "09:35" not in times          # short bucket dropped
    assert (candles["n"] == 5).all()


# ---------------------------------------------------------------------------
# 4. No horizon past the session close / day boundary
# ---------------------------------------------------------------------------
def test_forward_returns_do_not_cross_day_boundary():
    # two days, 3 candles each; event at the last candle of day 1 must have NaN fwd
    idx, rows = [], []
    for day, base in [("2020-06-01", 100.0), ("2020-06-02", 200.0)]:
        for j, hm in enumerate(["09:30", "09:35", "09:40"]):
            px = base + j
            idx.append(pd.Timestamp(f"{day} {hm}"))
            rows.append({"Open": px, "High": px + 0.5, "Low": px - 0.5, "Close": px + 0.5,
                         "day": pd.Timestamp(day), "dir": 1, "body": 0.5})
    c = pd.DataFrame(rows, index=pd.DatetimeIndex(idx))
    ES._add_forward_outcomes(c)
    last_of_day1 = c.loc["2020-06-01 09:40"]
    assert np.isnan(last_of_day1["fwd_ret_1"])       # +1 would cross into day 2 -> NaN
    first_of_day1 = c.loc["2020-06-01 09:30"]
    assert not np.isnan(first_of_day1["fwd_ret_1"])  # within-day horizon is fine
    assert first_of_day1["fwd_ret_1"] == pytest.approx(1.0)  # dir +1 * (Close_+1 - Close)


# ---------------------------------------------------------------------------
# 5. Day-clustered contrast returns a CI and is deterministic (seed 42)
# ---------------------------------------------------------------------------
def test_day_clustered_contrast_deterministic():
    rng = np.random.default_rng(0)
    days = pd.to_datetime([f"2020-06-{d:02d}" for d in range(1, 21)])
    rows = []
    for d in days:
        for _ in range(10):
            rows.append({"day": d, "bucket": "spike", "val": rng.normal(-1, 1)})
            rows.append({"day": d, "bucket": "pullback", "val": rng.normal(1, 1)})
    df = pd.DataFrame(rows)
    r1 = ES.day_clustered_contrast(df, "bucket", "val", "spike", "pullback")
    r2 = ES.day_clustered_contrast(df, "bucket", "val", "spike", "pullback")
    assert r1["contrast"] == r2["contrast"]          # deterministic
    assert r1["ci"] == r2["ci"]
    assert r1["contrast"] < 0                          # spike mean < pullback mean
    assert r1["ci"][1] < 0                             # CI excludes 0 (clear separation)
    assert r1["method"] == "day_clustered"

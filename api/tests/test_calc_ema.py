"""ADR-036 — vectorized calc_ema must equal the reference per-row recurrence.

The engine's calc_ema was a Python loop (SMA seed + EMA recurrence + NaN carry-
forward). ADR-036 vectorized the recurrence via ewm(adjust=False) seeded at the SMA.
These tests pin the vectorized output to the reference recurrence *to the tick*, so
the swap is a speed change with no results change.
"""
import numpy as np
import pandas as pd

from engine.engine import calc_ema

TICK = 0.25
HALF_TICK = 0.125


def _reference_ema(series: pd.Series, length: int) -> pd.Series:
    """Verbatim prior per-row implementation — the behavioral reference."""
    multiplier = 2.0 / (length + 1)
    ema = pd.Series(np.nan, index=series.index, dtype=float)
    vals = series.values
    valid = ~np.isnan(vals)
    start, count = -1, 0
    for i in range(len(vals)):
        if valid[i]:
            count += 1
            if count == length:
                start = i - length + 1
                break
        else:
            count = 0
    if start < 0:
        return ema
    seed_idx = start + length - 1
    ema.iloc[seed_idx] = np.mean(vals[start:start + length])
    for i in range(seed_idx + 1, len(vals)):
        if np.isnan(vals[i]):
            ema.iloc[i] = ema.iloc[i - 1]
            continue
        ema.iloc[i] = vals[i] * multiplier + ema.iloc[i - 1] * (1 - multiplier)
    return ema


def _synthetic_prices(n=5000, seed=7):
    rng = np.random.default_rng(seed)
    # a random walk quantized to 0.25 ticks, like real ES prices
    steps = rng.integers(-4, 5, size=n) * TICK
    return pd.Series(5000.0 + np.cumsum(steps))


def test_matches_reference_to_the_tick():
    s = _synthetic_prices()
    for length in (9, 21, 50, 200):
        got = calc_ema(s, length).to_numpy()
        ref = _reference_ema(s, length).to_numpy()
        m = ~np.isnan(ref)
        assert not np.isnan(got[m]).any()
        assert np.max(np.abs(got[m] - ref[m])) < HALF_TICK          # under half a tick
        # and identical once rounded to the 0.25 tick grid
        assert np.array_equal(np.round(got[m] / TICK), np.round(ref[m] / TICK))
        # NaN mask identical (same warmup region)
        assert np.array_equal(np.isnan(got), np.isnan(ref))


def test_seed_is_sma_not_first_value():
    # the seed at the first valid window is the SMA of that window (matches ta.ema()),
    # NOT the first value — guards against a naive ewm() swap.
    s = pd.Series([10.0, 20.0, 30.0, 31.0, 32.0])
    ema = calc_ema(s, 3)
    assert np.isnan(ema.iloc[0]) and np.isnan(ema.iloc[1])
    assert abs(ema.iloc[2] - 20.0) < 1e-9        # SMA(10,20,30) = 20, not 10


def test_nan_carry_forward_gap():
    # leading NaN + an interior gap: must match the reference exactly (loop fallback).
    s = pd.Series([np.nan, np.nan, 1.0, 2.0, 3.0, np.nan, 4.0, 5.0, np.nan, 6.0, 7.0, 8.0])
    got = calc_ema(s, 3).to_numpy()
    ref = _reference_ema(s, 3).to_numpy()
    assert np.array_equal(np.isnan(got), np.isnan(ref))
    m = ~np.isnan(ref)
    assert np.allclose(got[m], ref[m], atol=1e-9)


def test_insufficient_data_all_nan():
    s = pd.Series([1.0, 2.0])
    assert calc_ema(s, 5).isna().all()      # fewer than `length` valid -> all NaN

"""ADR-041 — vectorized calc_smma / calc_wma / calc_obv must equal the prior per-row loops.

Each reference below is the verbatim pre-ADR-041 implementation (the source of truth). The
vectorized versions must match to floating-point epsilon on: clean data, NaN-leading input,
an interior-NaN gap (smma/wma), and equal-close ties (obv) — proving tick-identical output.
"""
import numpy as np
import pandas as pd

from engine.engine import calc_smma, calc_wma, calc_obv

ATOL = 1e-9
TICK = 0.25


# --- reference implementations (verbatim prior loops) ------------------------

def _ref_smma(series, length):
    smma = pd.Series(np.nan, index=series.index)
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
        return smma
    seed_idx = start + length - 1
    smma.iloc[seed_idx] = np.mean(vals[start:start + length])
    for i in range(seed_idx + 1, len(vals)):
        if np.isnan(vals[i]):
            smma.iloc[i] = smma.iloc[i - 1]
            continue
        smma.iloc[i] = (smma.iloc[i - 1] * (length - 1) + vals[i]) / length
    return smma


def _ref_wma(series, length):
    weights = np.arange(1, length + 1, dtype=float)
    weight_sum = weights.sum()

    def _weighted_avg(window):
        return np.dot(window, weights) / weight_sum

    return series.rolling(window=length, min_periods=length).apply(_weighted_avg, raw=True)


def _ref_obv(close, volume):
    close_v = close.values
    vol_v = volume.values
    n = len(close_v)
    obv = np.zeros(n)
    for i in range(1, n):
        if close_v[i] > close_v[i - 1]:
            obv[i] = obv[i - 1] + vol_v[i]
        elif close_v[i] < close_v[i - 1]:
            obv[i] = obv[i - 1] - vol_v[i]
        else:
            obv[i] = obv[i - 1]
    return pd.Series(obv, index=close.index)


# --- helpers -----------------------------------------------------------------

def _assert_matches(got, ref):
    g, r = got.to_numpy(dtype=float), ref.to_numpy(dtype=float)
    assert np.array_equal(np.isnan(g), np.isnan(r)), "NaN masks differ"
    m = ~np.isnan(r)
    if m.any():
        assert np.max(np.abs(g[m] - r[m])) <= ATOL


def _walk(n=4000, seed=11):
    rng = np.random.default_rng(seed)
    return pd.Series(5000.0 + np.cumsum(rng.integers(-4, 5, size=n) * TICK))


def _with_leading_nan(s, k=6):
    return pd.concat([pd.Series([np.nan] * k), s]).reset_index(drop=True)


def _with_interior_gap(s, at=50, k=3):
    s = s.copy()
    s.iloc[at:at + k] = np.nan
    return s


LENGTHS = (3, 9, 21, 50)


# --- calc_smma ---------------------------------------------------------------

def test_smma_clean():
    s = _walk()
    for L in LENGTHS:
        _assert_matches(calc_smma(s, L), _ref_smma(s, L))


def test_smma_nan_leading():
    s = _with_leading_nan(_walk())
    for L in LENGTHS:
        _assert_matches(calc_smma(s, L), _ref_smma(s, L))


def test_smma_interior_gap():
    s = _with_interior_gap(_walk())
    for L in LENGTHS:
        _assert_matches(calc_smma(s, L), _ref_smma(s, L))


def test_smma_insufficient_data_all_nan():
    s = pd.Series([1.0, 2.0])
    assert calc_smma(s, 5).isna().all()


# --- calc_wma ----------------------------------------------------------------

def test_wma_clean():
    s = _walk()
    for L in LENGTHS:
        _assert_matches(calc_wma(s, L), _ref_wma(s, L))


def test_wma_nan_leading():
    s = _with_leading_nan(_walk())
    for L in LENGTHS:
        _assert_matches(calc_wma(s, L), _ref_wma(s, L))


def test_wma_interior_gap():
    s = _with_interior_gap(_walk())
    for L in LENGTHS:
        _assert_matches(calc_wma(s, L), _ref_wma(s, L))


def test_wma_shorter_than_length_all_nan():
    s = pd.Series([1.0, 2.0, 3.0])
    assert calc_wma(s, 5).isna().all()


# --- calc_obv ----------------------------------------------------------------

def test_obv_clean():
    s = _walk(seed=3)
    vol = pd.Series(np.arange(1, len(s) + 1, dtype=float) * 10.0)
    _assert_matches(calc_obv(s, vol), _ref_obv(s, vol))


def test_obv_equal_close_ties():
    # repeated closes (ties) must leave OBV unchanged on those bars
    close = pd.Series([100.0, 100.0, 101.0, 101.0, 100.0, 100.0, 100.0, 102.0])
    vol = pd.Series([5.0, 7.0, 3.0, 9.0, 4.0, 8.0, 2.0, 6.0])
    got, ref = calc_obv(close, vol), _ref_obv(close, vol)
    _assert_matches(got, ref)
    assert got.iloc[0] == 0.0                 # obv[0] = 0
    assert got.iloc[1] == got.iloc[0]         # tie -> unchanged
    assert got.iloc[3] == got.iloc[2]         # tie -> unchanged

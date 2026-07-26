"""Fixed-range volume profile → POC / VAH / VAL.

WIT-T-0001 §D2 setup: a fixed-range volume profile over the opening window
[09:30, 09:45) ET, value area = 70%. The guru draws this on NASDAQ; WIT computes
it on ES bars (proxy disclosed in the report).

Method (WIT-T-0001 §B3, the disclosed approximation):
    We do not have tick data. Each input bar's volume is spread **uniformly**
    across the price rows its High–Low span covers, on a `tick_size` grid
    (0.25 for ES). This is the honest approximation to a true tick profile;
    with 1-minute bars the [09:30,09:45) window has ~15 bars (vs 3 at 5-minute),
    so the 1-minute profile is materially richer. Both granularities are
    supported so the report can show a 1-min-vs-5-min robustness comparison.

Definitions:
    POC  — price row with the most volume. Ties broken by the row nearest the
           volume-weighted mean price, then by lower price (fully deterministic).
    Value area — the **smallest contiguous band of rows containing the POC**
           whose volume is ≥ `value_area_pct` of the total. Built by the standard
           Market-Profile greedy expansion: from the POC, repeatedly add whichever
           immediate neighbour (row above the current top vs row below the current
           bottom) holds more volume, until the threshold is reached. The
           larger-neighbour rule is what makes "smallest band" unique when two
           equal-width bands both qualify (ties broken toward the lower row).
    VAH / VAL — the top / bottom price of that band.

All arithmetic is done in integer tick units to avoid floating-point drift on
the 0.25 grid, then converted back to prices.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class VolumeProfile:
    """Result of a fixed-range volume-profile computation."""
    poc: float           # point of control (price)
    vah: float           # value-area high (price)
    val: float           # value-area low (price)
    total_volume: float  # total volume distributed into the profile
    value_area_volume: float  # volume inside [val, vah]
    n_rows: int          # number of price rows in the full profile
    tick_size: float
    value_area_pct: float

    @property
    def value_area_fraction(self) -> float:
        return self.value_area_volume / self.total_volume if self.total_volume else 0.0


def _row_volumes(high: np.ndarray, low: np.ndarray, vol: np.ndarray,
                 tick_size: float) -> tuple[int, np.ndarray]:
    """Distribute each bar's volume uniformly across the tick rows it spans.

    Returns (base_tick_index, volumes) where volumes[k] is the volume on the row
    at price (base_tick_index + k) * tick_size.
    """
    hi_t = np.round(high / tick_size).astype(np.int64)
    lo_t = np.round(low / tick_size).astype(np.int64)
    # Guard against inverted/degenerate bars.
    hi_t = np.maximum(hi_t, lo_t)

    base = int(lo_t.min())
    top = int(hi_t.max())
    n = top - base + 1
    rows = np.zeros(n, dtype=np.float64)

    for h, l, v in zip(hi_t, lo_t, vol):
        span = int(h - l) + 1              # number of rows this bar covers
        share = float(v) / span           # uniform spread
        rows[(l - base):(h - base + 1)] += share
    return base, rows


def _select_poc(rows: np.ndarray, base: int, tick_size: float) -> int:
    """Index (into rows) of the point of control. Deterministic tie-break."""
    peak = rows.max()
    cands = np.flatnonzero(rows == peak)
    if len(cands) == 1:
        return int(cands[0])
    # Tie: choose the row nearest the volume-weighted mean, then the lower price.
    idx = np.arange(len(rows))
    vw_mean = float((idx * rows).sum() / rows.sum())
    best = min(cands, key=lambda c: (abs(c - vw_mean), c))
    return int(best)


def _value_area(rows: np.ndarray, poc_idx: int, value_area_pct: float) -> tuple[int, int]:
    """Greedy Market-Profile value area. Returns (val_idx, vah_idx) into rows."""
    total = rows.sum()
    target = total * value_area_pct
    lo = hi = poc_idx
    cum = rows[poc_idx]
    n = len(rows)
    while cum < target and (lo > 0 or hi < n - 1):
        above = rows[hi + 1] if hi < n - 1 else -1.0   # -1 → unavailable side never wins
        below = rows[lo - 1] if lo > 0 else -1.0
        # Add the heavier neighbour. Ties (and the boundary sentinel) resolve
        # toward the LOWER row so the band is deterministic.
        if above > below:
            hi += 1
            cum += rows[hi]
        else:
            lo -= 1
            cum += rows[lo]
    return lo, hi


def build_volume_profile(bars: pd.DataFrame, tick_size: float = 0.25,
                         value_area_pct: float = 0.70) -> VolumeProfile | None:
    """Build a volume profile from OHLCV bars (any granularity).

    `bars` must have High, Low, Volume columns. Returns None if empty or the
    total volume is zero (caller treats that as an unusable window).
    """
    if bars is None or len(bars) == 0:
        return None
    high = bars["High"].to_numpy(dtype=np.float64)
    low = bars["Low"].to_numpy(dtype=np.float64)
    vol = bars["Volume"].to_numpy(dtype=np.float64)
    if vol.sum() <= 0:
        return None

    base, rows = _row_volumes(high, low, vol, tick_size)
    poc_idx = _select_poc(rows, base, tick_size)
    val_idx, vah_idx = _value_area(rows, poc_idx, value_area_pct)

    to_price = lambda i: round((base + i) * tick_size, 10)
    return VolumeProfile(
        poc=to_price(poc_idx),
        vah=to_price(vah_idx),
        val=to_price(val_idx),
        total_volume=float(rows.sum()),
        value_area_volume=float(rows[val_idx:vah_idx + 1].sum()),
        n_rows=len(rows),
        tick_size=tick_size,
        value_area_pct=value_area_pct,
    )

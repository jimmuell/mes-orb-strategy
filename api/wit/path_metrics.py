"""Intrabar path metrics for the candle-formation event study (WIT-T-0002).

A candle's *formation path* is reconstructed from its 1-minute sub-bars: the node
sequence is [candle open, sub-close_1, ..., sub-close_m] (m = 5 for a 5-min
candle, 15 for a 15-min candle). From that path we measure:

  - **path efficiency** = |close − open| / Σ|node-to-node step|  ∈ (0, 1].
    Near 1 ⇒ near-monotonic ("spike"); lower ⇒ more back-and-forth ("pullback").
  - **counter-retracement** = the largest adverse excursion against the body
    direction along the path (bullish: max(runningMax − node); bearish mirror).
    Reported as a fraction of the body (`retrace_pct`, scale-free so 5-min and
    15-min are comparable — the C3 requirement) and, for reference, in ticks.

These are pure functions of (open, sub_closes, tick_size); no data access, so
they golden-test exactly.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PathMetrics:
    direction: int          # +1 bullish, -1 bearish, 0 doji
    body: float             # |close - open| in price units
    efficiency: float       # net / total path length, in (0,1]; nan if flat path
    retrace_price: float    # max counter-retracement in price units
    retrace_ticks: float    # same, in ticks
    retrace_pct: float      # counter-retracement / body; nan if body == 0


def compute_path(open_price: float, sub_closes, tick_size: float = 0.25) -> PathMetrics:
    """Path metrics for one candle from its opening price and 1-min sub-closes.

    `sub_closes` is the ordered sequence of the candle's 1-minute closes; its last
    element is the candle close. Requires ≥1 sub-close.
    """
    closes = np.asarray(sub_closes, dtype=np.float64)
    if closes.size == 0:
        raise ValueError("sub_closes must be non-empty")
    nodes = np.concatenate([[float(open_price)], closes])
    close = float(closes[-1])
    body_signed = close - float(open_price)
    body = abs(body_signed)
    direction = int(np.sign(body_signed))

    steps = np.abs(np.diff(nodes))
    total = float(steps.sum())
    net = abs(float(nodes[-1] - nodes[0]))
    efficiency = (net / total) if total > 0 else float("nan")

    if direction >= 0:      # bullish (or flat): worst drawdown from a running peak
        retrace_price = float((np.maximum.accumulate(nodes) - nodes).max())
    else:                   # bearish: worst run-up from a running trough
        retrace_price = float((nodes - np.minimum.accumulate(nodes)).max())

    retrace_ticks = retrace_price / tick_size
    retrace_pct = (retrace_price / body) if body > 0 else float("nan")
    # Prices are tick-quantized, so efficiency/retrace ratios are rationals; round
    # away float drift (e.g. 100.60-100.20 -> 0.3999…86) so bucket classification at
    # a threshold boundary is reproducible rather than decided by 1e-15 noise.
    _r = lambda x: x if np.isnan(x) else round(x, 12)
    return PathMetrics(direction=direction, body=round(body, 12),
                       efficiency=_r(efficiency), retrace_price=round(retrace_price, 12),
                       retrace_ticks=_r(retrace_ticks), retrace_pct=_r(retrace_pct))


def classify_bucket(pm: PathMetrics, *, spike_eff: float, spike_giveback_cap: float,
                    pullback_p: float) -> str:
    """Assign a formation path to spike / pullback / middle (threshold mode).

    Disjoint by priority: pullback (real giveback) first, then spike (monotonic,
    small giveback), else middle. All giveback thresholds are % of body.
    """
    rp = pm.retrace_pct
    if pm.body <= 0 or np.isnan(rp):
        return "middle"
    if rp >= pullback_p:
        return "pullback"
    if rp <= spike_giveback_cap and not np.isnan(pm.efficiency) and pm.efficiency >= spike_eff:
        return "spike"
    return "middle"

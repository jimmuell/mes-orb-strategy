"""Engine-owned sensitivity-sweep grids (WIT-03 §8.5).

Callers NEVER define grids — the engine owns the approved variant sets so a sweep always
reproduces the published sensitivity analysis:
  - backtest    -> the WIT-0001 §J2 sweep set (mirrors api/wit/analysis.py)
  - event_study -> the WIT-0002 A4 variant set (the non-primary cells of
                   event_study_report.build_grid(); a test pins that equality, and
                   event_study_report.py is NOT modified — it produced the published numbers)

Variants are one-at-a-time OFF THE GIVEN PRIMARY via .with_(), so a sweep off a non-default
primary preserves that primary in every cell except the varied dimension.

MAX_SWEEP_CELLS = 18: the approved WIT-0002 event grid is 17 variant cells (the published
"18-config grid" = primary + 17); 17 is the binding case, 18 gives one cell of headroom.
(The WIT-P3f prompt's original "16" was a lead-engineer off-by-one; the 17-cell published grid
is authoritative — lead-engineer decision, WIT-P3f.)
"""
from __future__ import annotations

from wit.config import VPORBConfig
from wit.event_study import EventStudyConfig

MAX_SWEEP_CELLS = 18


def build_backtest_sweep(primary: VPORBConfig) -> dict[str, VPORBConfig]:
    """The WIT-0001 §J2 sweep set (mirrors analysis.py), one-at-a-time off `primary`."""
    grid = {
        "entry_body": primary.with_(entry_mode="body"),
        "slippage_0": primary.with_(slippage_ticks=0),
        "slippage_2": primary.with_(slippage_ticks=2),
        "target_first": primary.with_(same_bar_policy="target_first"),
        "vp_5min": primary.with_(vp_granularity="5min"),
    }
    assert len(grid) <= MAX_SWEEP_CELLS, f"backtest sweep {len(grid)} > {MAX_SWEEP_CELLS}"
    return grid


def build_event_study_sweep(primary: EventStudyConfig) -> dict[str, EventStudyConfig]:
    """The WIT-0002 A4 variant set — the non-primary cells of event_study_report.build_grid(),
    reconstructed OFF `primary` (identical names + overrides; equality pinned by a test)."""
    grid: dict[str, EventStudyConfig] = {}
    for k in (1.25, 2.0, 3.0):
        grid[f"k={k}"] = primary.with_(k=k)
    for n in (10, 40):
        grid[f"N={n}"] = primary.with_(n_baseline=n)
    for e in (0.40, 0.60):
        grid[f"E={e}"] = primary.with_(spike_eff=e)
    for cap in (0.15, 0.25):
        grid[f"cap={cap}"] = primary.with_(spike_giveback_cap=cap)
    for pp in (0.33, 0.50):
        grid[f"P={pp}"] = primary.with_(pullback_p=pp)
    grid["regime=insample_median"] = primary.with_(regime_mode="insample_median")
    grid["regime=fixed_0.30"] = primary.with_(regime_mode="fixed")
    grid["regime=ADX>20"] = primary.with_(regime_mode="adx")
    grid["regime_M=40"] = primary.with_(regime_er_m=40)
    grid["bucket=percentile"] = primary.with_(bucket_mode="percentile")
    grid["timeframe=15min"] = primary.with_(timeframe="15min")
    assert len(grid) <= MAX_SWEEP_CELLS, f"event-study sweep {len(grid)} > {MAX_SWEEP_CELLS}"
    return grid

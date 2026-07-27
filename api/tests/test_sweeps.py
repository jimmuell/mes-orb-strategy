"""WIT-P3f — engine-owned sweep grid goldens (exact dataclass equality, no network).

These LOCK the sweep grids to the ones that produced the published WIT-0001 / WIT-0002 reports.
If event_study_report.build_grid() ever changes, test_event_study_grid_matches_build_grid fails.

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_sweeps.py -q
"""
from __future__ import annotations

from wit.config import VPORBConfig
from wit.event_study import EventStudyConfig
from wit.event_study_report import build_grid
from wit.sweeps import build_backtest_sweep, build_event_study_sweep, MAX_SWEEP_CELLS


# ── event-study grid == the published build_grid() non-primary cells ──
def test_event_study_grid_matches_build_grid():
    _, grid = build_grid()
    non_primary = {k: v for k, v in grid.items() if k != "primary"}
    sweep = build_event_study_sweep(EventStudyConfig())
    assert list(sweep.keys()) == list(non_primary.keys())   # same names, same order
    assert sweep == non_primary                             # exact dataclass equality
    assert len(sweep) == 17


# ── backtest grid == the WIT-0001 §J2 five variants ──
def test_backtest_grid_matches_analysis_variants():
    p = VPORBConfig()
    sweep = build_backtest_sweep(p)
    assert sweep == {
        "entry_body": p.with_(entry_mode="body"),
        "slippage_0": p.with_(slippage_ticks=0),
        "slippage_2": p.with_(slippage_ticks=2),
        "target_first": p.with_(same_bar_policy="target_first"),
        "vp_5min": p.with_(vp_granularity="5min"),
    }
    assert len(sweep) == 5


# ── variants derive from the GIVEN primary, not a fresh default ──
def test_backtest_derives_from_given_primary():
    p = VPORBConfig(rr_target=3.0, commission_per_side=1.11)   # non-default, non-swept dims
    sweep = build_backtest_sweep(p)
    for name, cfg in sweep.items():
        assert cfg.rr_target == 3.0, name           # preserved in every cell
        assert cfg.commission_per_side == 1.11, name
    # each cell varies ONLY its own dimension
    assert sweep["entry_body"].entry_mode == "body"
    assert sweep["slippage_2"].slippage_ticks == 2
    assert sweep["vp_5min"].vp_granularity == "5min"


def test_event_study_derives_from_given_primary():
    p = EventStudyConfig(start="2020-01-01", end="2021-01-01")  # window is not a swept dim
    sweep = build_event_study_sweep(p)
    for name, cfg in sweep.items():
        assert cfg.start == "2020-01-01" and cfg.end == "2021-01-01", name
    assert sweep["k=1.25"].k == 1.25
    assert sweep["regime=ADX>20"].regime_mode == "adx"
    assert sweep["timeframe=15min"].timeframe == "15min"


def test_grids_within_cap():
    assert len(build_backtest_sweep(VPORBConfig())) <= MAX_SWEEP_CELLS
    assert len(build_event_study_sweep(EventStudyConfig())) <= MAX_SWEEP_CELLS
    assert MAX_SWEEP_CELLS == 18

"""VP-ORB run configuration — the WIT-T-0001 §I defaults as a dataclass.

Every field here corresponds to a filled template field or a v1 Default
Assumption (WIT-02 §5). The sweep dimensions (entry_mode, slippage_ticks,
same_bar_policy, vp_granularity) are the WIT-T-0001 §J2 interpretation set.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

# MES economics (matches engine.MES_POINT_VALUE / MES_TICK_SIZE and _ENGINE_INSTRUMENT).
TICK_SIZE = 0.25
POINT_VALUE = 5.0


@dataclass(frozen=True)
class VPORBConfig:
    # ── window / data ──
    start_date: str = "2016-04-10"          # approved primary window start
    end_date: str = "2026-04-09"            # data end (approved primary window end)

    # ── opening range / volume profile (WIT-T-0001 §D2) ──
    range_start: str = "09:30"              # ET, inclusive
    range_end: str = "09:45"                # ET, exclusive -> [09:30,09:45)
    value_area_pct: float = 0.70
    min_opening_bars: int = 15              # 1-min: skip day if window incomplete (15 expected)
    min_opening_bars_5min: int = 3          # 5-min VP mode expects 3 bars
    vp_granularity: str = "1min"            # "1min" (canonical) | "5min" (robustness)

    # ── entry (WIT-T-0001 §C1/§D1/§D3) ──
    entry_window_start: str = "09:45"       # first eligible 5-min bar start
    entry_window_last_bar: str = "10:55"    # last eligible 5-min bar start (closes 11:00)
    entry_mode: str = "close"               # "close" (primary) | "body" (whole body beyond)

    # ── exits (WIT-T-0001 §F) ──
    stop_offset_ticks: int = 2              # stop = POC -/+ 2 ticks
    rr_target: float = 2.0                  # target = entry ± rr_target * R
    same_bar_policy: str = "stop_first"     # "stop_first" (primary) | "target_first"
    # time exit: force-flat at the day's last RTH bar (handles half-days) — always on.

    # ── costs (WIT-T-0001 §H) ──
    commission_per_side: float = 0.62
    slippage_ticks: int = 1

    # ── economics / capital ──
    initial_capital: float = 10_000.0

    # ── data source (WIT-P5o) ──
    dataset: str = "ES_5min_continuous"     # catalog id; unspecified behaves exactly as today

    def with_(self, **kw) -> "VPORBConfig":
        """Return a copy with overrides (used to build sweep variants)."""
        return replace(self, **kw)

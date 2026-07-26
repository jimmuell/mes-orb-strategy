"""WIT (WillItTrade) — strategy-verdict lab modules.

Additive layer over the frozen engine (`api/engine`). Nothing here mutates the
engine, the dashboard, the pine scripts, or the existing strategies. WIT builds
signal + per-row stop/target columns and drives `run_backtest_long_short`
unmodified. See docs/wit/ for the founding documents and WIT-T-0001 for the
first filled template (Volume-Profile Opening Range Breakout).
"""

from wit.volume_profile import VolumeProfile, build_volume_profile

__all__ = ["VolumeProfile", "build_volume_profile"]

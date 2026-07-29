"""Shared machine-channel vocabulary (WIT-P4k).

The per-template-field DECLARED mode vocabulary (contract/modes.md, Class A). Moved here from
`wit.mapper` so BOTH sides of the machine channel — the extraction schema validator
(`wit.extraction.schema`) and the mapper (`wit.mapper`) — read ONE definition, without an import
cycle (this module imports nothing from either). `map_template` rejects any token not declared for
the dimension (UnsupportedConstruct); tokens that are declared-but-not-engine-v1 (e.g. `orb_break`,
`market_next_open`) pass the vocabulary gate and are caught by the adapter's baked-constant checks.
"""
from __future__ import annotations

FIELD_MODE_VOCAB = {
    "B1": {"futures_proxy", "direct"},                     # instrument
    "D1": {"vp_value_area_break", "orb_break", "none"},    # bias
    "D2": {"volume_profile_range", "opening_range"},       # setup
    "D3": {"bar_close_beyond_level", "bar_body_beyond_level"},  # entry trigger
    "D4": {"market_on_close", "market_next_open"},         # order
    "E1": {"fixed_contracts"},                             # sizing
    "F1": {"level_offset", "structure"},                   # stop
    "F2": {"r_multiple", "level", "none"},                 # target
    "F4": {"force_flat", "fixed_time", "none"},            # time exit
    "F5": {"stop_first", "target_first"},                  # same-bar
    "C1": {"rth_window"},                                  # session
}

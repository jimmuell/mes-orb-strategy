"""WIT-P3e-1 — extraction prompt builder tests (deterministic, no network).

The mode vocabulary is parsed from contract/modes.md (single source of truth). The
golden below PINS the v1 supported set; when the engine later supports a token, its †
is removed in modes.md and this golden is updated deliberately in that slice.

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_extraction_prompt.py -q
"""
from __future__ import annotations

import re

from wit.extraction.prompt import (supported_modes, unsupported_modes,
                                   build_system_prompt, build_user_prompt)
from wit.extraction.schema import FIELD_IDS

# Never engine-supported in v1 (†-marked in modes.md). Must appear in NO dimension's
# supported list (and — for the distinctive ones — nowhere in the system prompt).
NEVER_SUPPORTED = {"orb_break", "opening_range", "orb_high_low", "market_next_open",
                   "structure", "level", "fixed_time"}

EXPECTED_SUPPORTED = {
    "bias": ["vp_value_area_break"],
    "setup": ["volume_profile_range"],
    "entry.trigger": ["bar_close_beyond_level", "bar_body_beyond_level"],
    "entry.level": ["va_high_low"],
    "order": ["market_on_close"],
    "sizing": ["fixed_contracts"],
    "stop": ["level_offset"],
    "target": ["r_multiple"],
    "time_exit": ["force_flat"],
    "same_bar": ["stop_first", "target_first"],
    "session": ["rth_window"],
    "filters": ["none"],
    "instrument": ["futures_proxy", "direct"],
    "event": ["body_vs_trailing_median"],
    "path_bucket": ["path_threshold", "path_percentile"],
    "regime": ["kaufman_er_trailing_median", "kaufman_er_insample_median",
               "kaufman_er_fixed", "adx_threshold"],
    "timeframe": ["5min", "15min"],
}


# ── vocabulary golden ──
def test_supported_modes_golden():
    assert supported_modes() == EXPECTED_SUPPORTED


def test_per_dimension_spot_asserts():
    s = supported_modes()
    assert "vp_value_area_break" in s["bias"]
    assert "orb_break" not in s["bias"]
    assert "none" in s["filters"]                    # `none` (v1) — supported ONLY here
    assert "none" not in s["target"]
    assert "none" not in s["time_exit"]
    assert "none" not in s["bias"]
    assert "none" not in s.get("regime", [])
    assert "body_vs_trailing_median" in s["event"]
    assert "path_percentile" in s["path_bucket"]
    assert "adx_threshold" in s["regime"]


def test_none_is_per_dimension_not_global():
    # `none` is supported for filters but daggered everywhere else — proving per-dimension parse
    uns = unsupported_modes()
    assert "none" in uns["bias"] and "none" in uns["target"] and "none" in uns["time_exit"]
    assert "none" in uns["regime"]
    assert "none" not in unsupported_modes().get("filters", [])


def test_never_supported_in_no_dimension():
    flat = {t for tokens in supported_modes().values() for t in tokens}
    assert NEVER_SUPPORTED.isdisjoint(flat)


# ── system-prompt guarantees ──
def test_system_prompt_contains_every_supported_token():
    p = build_system_prompt()
    for tokens in supported_modes().values():
        for t in tokens:
            assert t in p, f"supported token missing from prompt: {t}"


def test_system_prompt_offers_no_unsupported_token():
    p = build_system_prompt()
    # the 5 distinctive underscore-tokens must be wholly absent
    for t in ("orb_break", "opening_range", "orb_high_low", "market_next_open", "fixed_time"):
        assert t not in p, f"unsupported token leaked into prompt: {t}"
    # `structure` / `level` must not appear as STANDALONE words (compounds like
    # entry.level, level_offset, bar_close_beyond_level are legitimate)
    assert not re.search(r"(?<![\w.])structure(?![\w])", p)
    assert not re.search(r"(?<![\w.])level(?![\w])", p)


def test_system_prompt_encodes_key_rules():
    p = build_system_prompt()
    for phrase in ("source_quote", "VERBATIM SUBSTRING", "charitably complete",
                   "unspecified", "a setup is not an entry trigger",
                   "CLASS IS AN OUTPUT, NOT AN INPUT", "performance claim"):
        assert phrase in p, f"rule phrase missing: {phrase!r}"


def test_system_prompt_references_all_27_fields():
    p = build_system_prompt()
    assert len(FIELD_IDS) == 27
    for fid in FIELD_IDS:
        assert fid in p, f"field id missing from prompt: {fid}"


# ── user prompt ──
def test_user_prompt_includes_transcript_and_meta():
    u = build_user_prompt("BIG GREEN CANDLE at 9:45",
                          {"url": "http://y", "title": "Vid", "channel": "Chan",
                           "transcript_hash": "abc123"})
    assert "BIG GREEN CANDLE at 9:45" in u
    for v in ("http://y", "Vid", "Chan", "abc123"):
        assert v in u

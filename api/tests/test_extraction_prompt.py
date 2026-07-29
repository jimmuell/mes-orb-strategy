"""WIT-P3e-1 — extraction prompt builder tests (deterministic, no network).

The mode vocabulary is parsed from contract/modes.md (single source of truth). The
golden below PINS the v1 supported set; when the engine later supports a token, its †
is removed in modes.md and this golden is updated deliberately in that slice.

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_extraction_prompt.py -q
"""
from __future__ import annotations

import re

from wit.extraction.prompt import (supported_modes, unsupported_modes, _parse_modes,
                                   build_system_prompt, build_user_prompt)
from wit.extraction.schema import FIELD_IDS
from wit.mapper import FIELD_MODE_VOCAB

# Never engine-supported in v1 (†-marked in modes.md). Must appear in NO dimension's
# supported list (and — for the distinctive ones — nowhere in the system prompt).
NEVER_SUPPORTED = {"orb_break", "opening_range", "orb_high_low", "market_next_open",
                   "structure", "level", "fixed_time"}

EXPECTED_SUPPORTED = {
    "bias": ["vp_value_area_break"],
    "setup": ["volume_profile_range"],
    "entry.trigger": ["bar_close_beyond_level", "bar_body_beyond_level"],
    # entry.level REMOVED in WIT-P4h: it advertised `va_high_low` with Field cell `D3/D1` but the
    # mapper has no entry.level carrier (D1=bias, D3=trigger reject it). In v1 the entry level is
    # derived from the D2 volume profile, so the dimension has no carrier field and is not offered.
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


def _offered_mode_tokens(prompt: str) -> set[str]:
    """Every token actually offered as a `mode` in the vocab block's 'mode ∈ {...}' clauses."""
    tokens: set[str] = set()
    for m in re.finditer(r"mode ∈ \{([^}]*)\}", prompt):
        tokens.update(t.strip() for t in m.group(1).split(",") if t.strip())
    return tokens


def test_system_prompt_offers_no_unsupported_token():
    p = build_system_prompt()
    offered = _offered_mode_tokens(p)
    # exactly the supported set is offered as modes — no more, no less
    assert offered == {t for tokens in supported_modes().values() for t in tokens}
    assert NEVER_SUPPORTED.isdisjoint(offered)
    # the 5 distinctive underscore-tokens appear NOWHERE (not modes, not params, not prose)
    for t in ("orb_break", "opening_range", "orb_high_low", "market_next_open", "fixed_time"):
        assert t not in p, f"unsupported token leaked into prompt: {t}"
    # `structure` never appears as a mode token or param key. (P3e-5 rule 9 legitimately uses
    # the English word "structure" — "executable within this template's own structure" — so the
    # check is scoped to the mode-VOCABULARY block, which is where a leaked token would surface.)
    vocab = p[p.index("CONFIG-RELEVANT MODE VOCABULARY"):]
    assert "structure" not in vocab


def test_vocab_block_names_field_ids_and_param_keys():
    p = build_system_prompt()
    block = p[p.index("CONFIG-RELEVANT MODE VOCABULARY"):]
    assert "field D2" in block          # setup dimension → its template field id
    assert "range_start" in block       # a setup param key
    assert "entry_start" in block       # session (C1) param key
    assert "ticks" in block             # stop (F1) param key


def test_system_prompt_encodes_key_rules():
    p = build_system_prompt()
    for phrase in ("source_quote", "VERBATIM SUBSTRING", "charitably complete",
                   "unspecified", "a setup is not an entry trigger",
                   "CLASS IS AN OUTPUT, NOT AN INPUT", "performance claim"):
        assert phrase in p, f"rule phrase missing: {phrase!r}"


def test_system_prompt_encodes_grounding_and_status_discipline():
    # WIT-P3e-4: the quote-discipline + status-discipline rules must be present as testable text
    p = build_system_prompt()
    for phrase in ("CHARACTER-FOR-CHARACTER",       # QUOTE DISCIPLINE
                   "including caption errors and typos",
                   "is NOT a rule",                  # STATUS DISCIPLINE (Class-B guard)
                   "CHOOSE 'unspecified'",
                   "the honest gap IS the product"):
        assert phrase in p, f"P3e-4 rule phrase missing: {phrase!r}"


def test_system_prompt_encodes_basis_discipline_rule9():
    # WIT-P3e-5: rule 9 phrases present AND rules 1-8's pinned phrases still present (additive)
    p = build_system_prompt()
    for phrase in ("BASIS DISCIPLINE", "narrated_example", "generalized_practice",
                   "stated_rule", "tendency_or_claim", "does NOT support"):
        assert phrase in p, f"P3e-5 rule 9 phrase missing: {phrase!r}"
    # rules 1-8 pinned phrases must survive the additive change
    for phrase in ("charitably complete", "VERBATIM SUBSTRING", "a setup is not an entry trigger",
                   "CLASS IS AN OUTPUT, NOT AN INPUT", "CHARACTER-FOR-CHARACTER",
                   "is NOT a rule", "CHOOSE 'unspecified'"):
        assert phrase in p, f"pre-P3e-5 rule phrase lost: {phrase!r}"


def test_system_prompt_encodes_p3e6_pairing_and_capability_clarifiers():
    # WIT-P3e-6: additive pairing + capability-fact clarifiers present, prior phrases intact
    p = build_system_prompt()
    for phrase in ("Status/basis pairing", "pairs only with basis 'stated_rule'",
                   "supports at most 'implied'", "capability or scope fact",
                   "STATED fact for B-section fields"):
        assert phrase in p, f"P3e-6 clarifier phrase missing: {phrase!r}"
    for phrase in ("BASIS DISCIPLINE", "narrated_example", "generalized_practice",
                   "does NOT support"):
        assert phrase in p, f"prior rule-9 phrase lost: {phrase!r}"


def test_system_prompt_encodes_p3e8_spec_alignment():
    # WIT-P3e-8: narrated-vs-generalized fixed, quote-selection rule, testable defined
    p = build_system_prompt()
    for phrase in ("WITH NO generalization", "the generalization, not",
                   "the demonstration, earns the credit", "MOST GENERAL",
                   "testable=true iff", "testable=false"):
        assert phrase in p, f"P3e-8 phrase missing: {phrase!r}"
    # the contradicting phrase is GONE
    assert "however habitual it" not in p, "removed narrated_example phrase still present"
    # prior pinned rule-9 phrases intact
    for phrase in ("BASIS DISCIPLINE", "narrated_example", "generalized_practice",
                   "does NOT support", "Status/basis pairing"):
        assert phrase in p, f"prior rule phrase lost: {phrase!r}"


def test_system_prompt_references_all_27_fields():
    p = build_system_prompt()
    assert len(FIELD_IDS) == 27
    for fid in FIELD_IDS:
        assert fid in p, f"field id missing from prompt: {fid}"


# ── WIT-P4h: prompt/mapper conformance — the prompt may not offer an unmappable field.mode ──
def test_offered_field_modes_conform_to_mapper():
    """The extraction prompt must never advertise a field.mode placement the mapper rejects
    (WIT-P4h: entry.level offered `va_high_low` with Field cell `D3/D1`, but neither D1 (bias) nor
    D3 (trigger) accepts it — the first live end-to-end submission failed on exactly this).

    FIELD_MODE_VOCAB is the mapper's Class-A field.mode surface. For every dimension that names a
    template field validated there, EVERY field id it names must be such a carrier and EVERY
    supported token it offers must be accepted by each. Dimensions whose modes live elsewhere
    (Class B in J1.params; filters `none`) name no FIELD_MODE_VOCAB carrier and are validated by a
    different path — out of this surface, correctly skipped."""
    ids = set(FIELD_IDS)
    for dim, r in _parse_modes().items():
        if not r["supported"]:
            continue
        field_ids = [t for t in re.findall(r"[A-K]\d+", r["field"] or "") if t in ids]
        carriers = [f for f in field_ids if f in FIELD_MODE_VOCAB]
        if not carriers:
            continue                          # not a field.mode-on-a-carrier dimension
        for fid in field_ids:
            assert fid in FIELD_MODE_VOCAB, (
                f"{dim!r} names field {fid} but the mapper has no field.mode vocabulary for it")
            for tok in r["supported"]:
                assert tok in FIELD_MODE_VOCAB[fid], (
                    f"{dim!r} offers mode {tok!r} on field {fid}, but the mapper rejects it "
                    f"(FIELD_MODE_VOCAB[{fid}] = {sorted(FIELD_MODE_VOCAB[fid])})")


# ── user prompt ──
def test_user_prompt_includes_transcript_and_meta():
    u = build_user_prompt("BIG GREEN CANDLE at 9:45",
                          {"url": "http://y", "title": "Vid", "channel": "Chan",
                           "transcript_hash": "abc123"})
    assert "BIG GREEN CANDLE at 9:45" in u
    for v in ("http://y", "Vid", "Chan", "abc123"):
        assert v in u

"""WIT-P3b — schema validation + completeness-scorer goldens (deterministic, no network).

The two hand-filled templates are the ground-truth calibration anchors:
  WIT-T-0001 (Volume-Profile ORB)      -> Class A
  WIT-T-0002 (Candle Formation Path)   -> Class B

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_completeness.py -q
"""
from __future__ import annotations

import json
import os

import pytest

from wit.extraction import validate_template, score_completeness, FIELD_IDS
from wit.extraction.completeness import assumption_fills

_FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _load(name):
    with open(os.path.join(_FIX, name)) as fh:
        return json.load(fh)


@pytest.fixture
def t0001():
    return _load("WIT-T-0001.template.json")


@pytest.fixture
def t0002():
    return _load("WIT-T-0002.template.json")


# ── schema ──
def test_schema_has_all_27_fields():
    assert len(FIELD_IDS) == 27
    assert FIELD_IDS[0] == "A1" and FIELD_IDS[-1] == "K1"


def test_fixtures_validate(t0001, t0002):
    assert validate_template(t0001) == []
    assert validate_template(t0002) == []


def test_validator_catches_bad_status(t0001):
    t0001["fields"]["B1"]["status"] = "totally-made-up"
    errs = validate_template(t0001)
    assert any("B1.status" in e for e in errs)


def test_validator_requires_source_quote_for_specified(t0001):
    t0001["fields"]["B1"]["source_quote"] = None   # B1 is specified
    errs = validate_template(t0001)
    assert any("B1" in e and "source_quote" in e for e in errs)


def test_validator_exempts_wit_authored_J_from_quote(t0001):
    # J1 is specified with a null source_quote by design (WIT-authored) — must be OK.
    assert t0001["fields"]["J1"]["status"] == "specified"
    assert t0001["fields"]["J1"]["source_quote"] is None
    assert validate_template(t0001) == []


# ── scorer goldens ──
def test_t0001_is_class_A(t0001):
    r = score_completeness(t0001)
    assert r["class"] == "A"
    assert r["required_missing"] == []          # all required fields satisfied
    assert assumption_fills(t0001) <= 6         # WIT-02 §3 Class-A limit (anchor ~5)


def test_t0002_is_class_B(t0002):
    r = score_completeness(t0002)
    assert r["class"] == "B"
    # WIT-P3b-fix: with the entry-conditional gate, an unspecified trigger (D3) gets
    # no default credit, and D4/F4 (entry-presupposing) lose theirs too — so D3, D4
    # and the F2|F4 exit pair join B1/D1 as missing.
    assert r["required_missing"] == ["B1", "D1", "D3", "D4", "F2|F4"]
    assert assumption_fills(t0002) == 5   # was 8 pre-fix (D3/D4/F4 no longer credited)


def test_scores_are_in_range(t0001, t0002):
    for t in (t0001, t0002):
        s = score_completeness(t)["score"]
        assert isinstance(s, int) and 0 <= s <= 100
    # A should out-score B (more of the execution surface is present)
    assert score_completeness(t0001)["score"] > score_completeness(t0002)["score"]


def test_stored_completeness_matches_recomputed(t0001, t0002):
    # the completeness block baked into each fixture must equal a fresh recompute
    for t in (t0001, t0002):
        r = score_completeness(t)
        assert t["completeness"]["class"] == r["class"]
        assert t["completeness"]["required_missing"] == r["required_missing"]
        assert t["completeness"]["score"] == r["score"]


def _minimal_template(specified_ids, extra=None):
    """A full 27-field template with everything unspecified except `specified_ids`."""
    fields = {}
    for fid in FIELD_IDS:
        if fid in specified_ids:
            fields[fid] = {"value": f"stated {fid}", "status": "specified",
                           "source_quote": f"quote for {fid}", "assumption": None}
        else:
            fields[fid] = {"value": None, "status": "unspecified",
                           "source_quote": None, "assumption": None}
    t = {"template_version": "1.0",
         "source": {"url": None, "title": None, "channel": None, "transcript_hash": None},
         "fields": fields, "claims": [], "consistency_flags": [],
         "completeness": {"score": 0, "class": "C", "required_missing": []},
         "interpretations": []}
    if extra:
        t.update(extra)
    return t


def test_no_stated_trigger_never_class_A():
    """WIT-P3b-fix regression: a setup with NO stated entry trigger must never route
    to Class A. B1,B2,D1,D2,F1,F2 specified but D3 (trigger) and D4 unspecified ->
    D3 in required_missing and class != 'A' (no assuming your way into a backtest)."""
    t = _minimal_template({"B1", "B2", "D1", "D2", "F1", "F2"})  # D3, D4 left unspecified
    r = score_completeness(t)
    assert "D3" in r["required_missing"]     # unspecified trigger is missing, never defaulted
    assert "D4" in r["required_missing"]     # order mechanics can't default without a trigger
    assert r["class"] != "A"


def test_class_C_when_no_testable_claim_and_missing_required(t0002):
    # strip testability from every claim -> not A, no testable claim -> C
    for c in t0002["claims"]:
        c["testable"] = False
    assert score_completeness(t0002)["class"] == "C"

"""WIT-P3e-2 — extraction orchestrator tests (DETERMINISTIC, NO network, NO SDK, NO key).

The provider call is monkeypatched; under test are the retry loop, validation gating, the
scorer-owned completeness block, and source filling. The live LLM path is exercised only by the
network-gated golden tier (test_extraction_golden.py).

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_extraction_orchestrator.py -q
"""
from __future__ import annotations

import copy
import json
import os

from wit.extraction import provider, extract

_FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _valid_template():
    with open(os.path.join(_FIX, "WIT-T-0001.template.json")) as fh:
        return json.load(fh)              # a known-valid Class A template


def _invalid_template():
    t = _valid_template()
    t["fields"]["B1"]["status"] = "bogus"  # not in the status enum -> validation error
    return t


def _ret(template):
    return {"template": template, "usage": {"input_tokens": 10, "output_tokens": 20}}


# A fake transcript we fully control; the grounded phrase is a verbatim substring of it,
# the paraphrase deliberately is not (even after whitespace/case normalization). Since
# WIT-P3e-4 grounding is a success gate, a template is only "valid" if its non-J
# specified/implied quotes are grounded in the transcript passed to extract_template.
FAKE_TX = ("Wait for a break of our value area high. The very next 5-minute candle closes "
           "beyond the level. Just click market buy and let the market work.")
GROUNDED = "a break of our value area high"            # verbatim substring of FAKE_TX
PARAPHRASE = "a breakout above the value-area top zone"  # NOT a substring — hallucinated


def _regrounded(template, quote):
    """Copy the valid template, overwriting every NON-J specified/implied source_quote with
    `quote`. Statuses (hence class + schema validity) are untouched — only grounding changes."""
    t = copy.deepcopy(template)
    for fid, f in t["fields"].items():
        if fid[0] == "J":
            continue
        if f.get("status") in ("specified", "implied"):
            f["source_quote"] = quote
    return t


# WIT-P3e-5 CI plumbing (NOT golden tuning — the fixtures on disk are byte-identical): the new
# gates require required fields to DECLARE a basis and every claim quote to be grounded. These
# helpers make an in-memory fake template satisfy those gates against FAKE_TX.
_REQUIRED_BASIS_FIELDS = ("B1", "B2", "D1", "D2", "D3", "D4", "F1", "F2", "F4")


def _with_basis(t, basis="stated_rule"):
    """Declare `basis` on every required specified/implied field (default stated_rule = no demotion)."""
    for fid in _REQUIRED_BASIS_FIELDS:
        f = t["fields"].get(fid)
        if isinstance(f, dict) and f.get("status") in ("specified", "implied"):
            f["basis"] = basis
    return t


def _ci_ready(t):
    """Make a (re)grounded fake template pass ALL P3e-5 CI gates against FAKE_TX: required
    fields declare basis, and claims[] are emptied (the fixture's real claims are not grounded
    in FAKE_TX; claim grounding has its own dedicated tests below)."""
    _with_basis(t)
    t["claims"] = []
    return t


def _grounded_template():
    """A schema-valid Class-A template that passes ALL CI-safe gates against FAKE_TX."""
    return _ci_ready(_regrounded(_valid_template(), GROUNDED))


def test_valid_first_try(monkeypatch):
    monkeypatch.setattr(provider, "extract_once",
                        lambda s, u, *, model, api_key=None: _ret(_grounded_template()))
    r = extract.extract_template(FAKE_TX, {"title": "Vid #2"})
    assert r["status"] == "ok"
    # class is assigned by the deterministic scorer, not the model
    assert r["completeness"]["class"] == "A"
    assert r["template"]["completeness"]["class"] == "A"
    assert r["template"]["completeness"]["required_missing"] == []
    # source filled from source_meta + computed transcript_hash
    assert r["template"]["source"]["title"] == "Vid #2"
    assert r["template"]["source"]["transcript_hash"]
    assert r["raw_meta"]["retries"] == 0
    assert r["raw_meta"]["model"]


def test_invalid_then_valid_retries(monkeypatch):
    seq = [_invalid_template(), _grounded_template()]
    calls = {"n": 0}

    def fake(s, u, *, model, api_key=None):
        t = seq[calls["n"]]
        calls["n"] += 1
        return _ret(t)

    monkeypatch.setattr(provider, "extract_once", fake)
    r = extract.extract_template(FAKE_TX, {}, max_retries=2)
    assert r["status"] == "ok"
    assert calls["n"] == 2                 # repaired on the 2nd attempt
    assert r["raw_meta"]["retries"] == 1   # retry count surfaced (0-indexed attempt that succeeded)


def test_retry_feeds_errors_back(monkeypatch):
    seen_prompts = []

    def fake(s, u, *, model, api_key=None):
        seen_prompts.append(u)
        return _ret(_invalid_template())   # always invalid

    monkeypatch.setattr(provider, "extract_once", fake)
    extract.extract_template("tx", {}, max_retries=1)
    # the retry user turn must contain the validation-error feedback
    assert len(seen_prompts) == 2
    assert "FAILED validation" in seen_prompts[1]
    assert "B1" in seen_prompts[1]


def test_always_invalid_fails_terminally(monkeypatch):
    calls = {"n": 0}

    def fake(s, u, *, model, api_key=None):
        calls["n"] += 1
        return _ret(_invalid_template())

    monkeypatch.setattr(provider, "extract_once", fake)
    r = extract.extract_template("tx", {}, max_retries=2)
    assert r["status"] == "extraction_failed"    # never a silent pass
    assert r["template"] is not None             # last candidate returned
    assert r["errors"]                           # validation errors surfaced
    assert any("B1" in e for e in r["errors"])
    assert calls["n"] == 3                        # max_retries + 1 attempts


def test_non_dict_tool_output_is_handled(monkeypatch):
    monkeypatch.setattr(provider, "extract_once",
                        lambda s, u, *, model, api_key=None: {"template": "not a dict", "usage": {}})
    r = extract.extract_template("tx", {}, max_retries=1)
    assert r["status"] == "extraction_failed"
    assert r["errors"]


# ── WIT-P3e-4: grounding retry loop (schema-valid but hallucinated quote must retry/fail) ──


def test_grounding_paraphrase_retries_and_names_field(monkeypatch):
    seen = []

    def fake(s, u, *, model, api_key=None):
        seen.append(u)
        return _ret(_regrounded(_valid_template(), PARAPHRASE))  # schema-valid, ungrounded

    monkeypatch.setattr(provider, "extract_once", fake)
    r = extract.extract_template(FAKE_TX, {}, max_retries=1)
    assert r["status"] == "extraction_failed"
    assert len(seen) == 2                                   # grounding failure fired a retry
    # the retry user turn carries the grounding error text AND names an offending field
    assert "is not a verbatim substring of the transcript" in seen[1]
    assert "fields.B1.source_quote" in seen[1]


def test_grounding_paraphrase_then_exact_succeeds(monkeypatch):
    seq = [_regrounded(_valid_template(), PARAPHRASE),
           _grounded_template()]
    calls = {"n": 0}

    def fake(s, u, *, model, api_key=None):
        t = seq[calls["n"]]
        calls["n"] += 1
        return _ret(t)

    monkeypatch.setattr(provider, "extract_once", fake)
    r = extract.extract_template(FAKE_TX, {}, max_retries=2)
    assert r["status"] == "ok"
    assert calls["n"] == 2                 # grounded on the 2nd attempt
    assert r["raw_meta"]["retries"] == 1   # the grounding retry is surfaced


def test_grounding_always_paraphrased_fails_terminally(monkeypatch):
    monkeypatch.setattr(provider, "extract_once",
                        lambda s, u, *, model, api_key=None: _ret(
                            _regrounded(_valid_template(), PARAPHRASE)))
    r = extract.extract_template(FAKE_TX, {}, max_retries=2)
    assert r["status"] == "extraction_failed"    # never a silent pass on a hallucinated quote
    assert any("verbatim substring of the transcript" in e for e in r["errors"])


def test_grounding_tolerates_whitespace_and_case(monkeypatch):
    # differs from the transcript ONLY by whitespace runs and case — normalization must tolerate it
    wonky = "  A  BREAK   of Our\nVALUE Area High "
    monkeypatch.setattr(provider, "extract_once",
                        lambda s, u, *, model, api_key=None: _ret(
                            _ci_ready(_regrounded(_valid_template(), wonky))))
    r = extract.extract_template(FAKE_TX, {}, max_retries=0)
    assert r["status"] == "ok"             # no grounding error despite the messy whitespace/case


def test_grounding_never_checks_j_fields(monkeypatch):
    t = _ci_ready(_regrounded(_valid_template(), GROUNDED))   # every non-J field grounded
    t["fields"]["J1"]["status"] = "specified"
    t["fields"]["J1"]["source_quote"] = PARAPHRASE  # ungrounded — but J is WIT-authored, exempt
    monkeypatch.setattr(provider, "extract_once",
                        lambda s, u, *, model, api_key=None: _ret(copy.deepcopy(t)))
    r = extract.extract_template(FAKE_TX, {}, max_retries=0)
    assert r["status"] == "ok"             # an ungrounded J quote does NOT block success


# ── WIT-P3e-5: basis discipline (evidence gate + deterministic demotion) + claims grounding ──


def _claim(quote, testable=False, text="Made $1000 in a day"):
    return {"claim": text, "quote": quote, "testable": testable}


def test_basis_narrated_example_demotes_required_field(monkeypatch):
    t = _grounded_template()
    t["fields"]["D3"]["basis"] = "narrated_example"   # required field, was specified+grounded
    monkeypatch.setattr(provider, "extract_once",
                        lambda s, u, *, model, api_key=None: _ret(copy.deepcopy(t)))
    r = extract.extract_template(FAKE_TX, {}, max_retries=0)
    assert r["status"] == "ok"                          # demotion is deterministic, NOT a failure
    # demoted to unspecified BEFORE scoring, and the demotion is recorded
    assert r["template"]["fields"]["D3"]["status"] == "unspecified"
    assert {"field": "D3", "from_status": "specified", "basis": "narrated_example"} in r["demotions"]
    # class reflects the demotion: a required field is now missing => no longer Class A
    assert r["completeness"]["class"] != "A"
    assert "D3" in r["completeness"]["required_missing"]


def test_missing_basis_retries_with_named_error_then_ok(monkeypatch):
    bad = _grounded_template()
    del bad["fields"]["D3"]["basis"]        # required, specified+grounded, but no basis declared
    seq = [bad, _grounded_template()]
    calls = {"n": 0}
    seen = []

    def fake(s, u, *, model, api_key=None):
        seen.append(u)
        t = seq[calls["n"]]
        calls["n"] += 1
        return _ret(copy.deepcopy(t))

    monkeypatch.setattr(provider, "extract_once", fake)
    r = extract.extract_template(FAKE_TX, {}, max_retries=1)
    assert r["status"] == "ok"
    assert calls["n"] == 2
    assert "fields.D3 is specified but declares no basis" in seen[1]


def test_basis_stated_rule_untouched_demotions_empty(monkeypatch):
    monkeypatch.setattr(provider, "extract_once",
                        lambda s, u, *, model, api_key=None: _ret(_grounded_template()))
    r = extract.extract_template(FAKE_TX, {}, max_retries=0)
    assert r["status"] == "ok"
    assert r["demotions"] == []                         # stated_rule supports the status
    assert r["template"]["fields"]["D3"]["status"] == "specified"


def test_invalid_basis_value_is_validation_error_and_retries(monkeypatch):
    bad = _grounded_template()
    bad["fields"]["D3"]["basis"] = "charitable"         # not in the enum -> schema error
    seq = [bad, _grounded_template()]
    calls = {"n": 0}
    seen = []

    def fake(s, u, *, model, api_key=None):
        seen.append(u)
        t = seq[calls["n"]]
        calls["n"] += 1
        return _ret(copy.deepcopy(t))

    monkeypatch.setattr(provider, "extract_once", fake)
    r = extract.extract_template(FAKE_TX, {}, max_retries=1)
    assert r["status"] == "ok"
    assert calls["n"] == 2
    assert "basis must be one of" in seen[1]


def test_claim_paraphrase_retries_naming_claim_then_ok(monkeypatch):
    bad = _grounded_template()
    bad["claims"] = [_claim(PARAPHRASE)]                # claim quote NOT grounded in FAKE_TX
    good = _grounded_template()
    good["claims"] = [_claim(GROUNDED)]                 # exact substring on retry
    seq = [bad, good]
    calls = {"n": 0}
    seen = []

    def fake(s, u, *, model, api_key=None):
        seen.append(u)
        t = seq[calls["n"]]
        calls["n"] += 1
        return _ret(copy.deepcopy(t))

    monkeypatch.setattr(provider, "extract_once", fake)
    r = extract.extract_template(FAKE_TX, {}, max_retries=1)
    assert r["status"] == "ok"
    assert calls["n"] == 2
    assert "is not a verbatim substring of the transcript" in seen[1]
    assert "Made $1000 in a day" in seen[1]             # the retry error names the claim


def test_claim_always_paraphrased_fails_terminally(monkeypatch):
    def fake(s, u, *, model, api_key=None):
        t = _grounded_template()
        t["claims"] = [_claim(PARAPHRASE)]
        return _ret(t)

    monkeypatch.setattr(provider, "extract_once", fake)
    r = extract.extract_template(FAKE_TX, {}, max_retries=2)
    assert r["status"] == "extraction_failed"           # ungrounded claim can never pass
    assert any("verbatim substring of the transcript" in e for e in r["errors"])
    assert any("Made $1000 in a day" in e for e in r["errors"])

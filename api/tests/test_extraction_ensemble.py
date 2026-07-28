"""WIT-P3e-7 — extraction ensemble tests (DETERMINISTIC, NO network). The per-run
extract_template is monkeypatched to canned run-results so the MERGE logic (vote, ties, medoid,
donor, claims grouping, re-validate+score) is under test in isolation. The live k=3 path is
exercised only by the network-gated golden tier.

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_extraction_ensemble.py -q
"""
from __future__ import annotations

import copy
import json
import os

from wit.extraction import ensemble

_FIX = os.path.join(os.path.dirname(__file__), "fixtures")

# Same controlled transcript as the orchestrator tests; GROUNDED is a verbatim substring so the
# merged template passes the re-check (grounding) by construction.
FAKE_TX = ("Wait for a break of our value area high. The very next 5-minute candle closes "
           "beyond the level. Just click market buy and let the market work.")
GROUNDED = "a break of our value area high"


def _base():
    """A schema-valid Class-A template (WIT-T-0001) whose every non-J specified/implied quote is
    grounded in FAKE_TX and whose claims are emptied (claims grouping has its own direct tests)."""
    with open(os.path.join(_FIX, "WIT-T-0001.template.json")) as fh:
        t = json.load(fh)
    for fid, f in t["fields"].items():
        if fid[0] == "J":
            continue
        if f.get("status") in ("specified", "implied"):
            f["source_quote"] = GROUNDED
    t["claims"] = []
    return t


def _ok(t, retries=0, demotions=None, downgrades=None):
    return {"status": "ok", "template": copy.deepcopy(t), "completeness": t.get("completeness"),
            "demotions": demotions or [], "downgrades": downgrades or [],
            "raw_meta": {"model": "m", "retries": retries, "usage": {}}}


def _failed(errors):
    return {"status": "extraction_failed", "template": None, "errors": errors}


def _seq_extract(seq):
    calls = {"n": 0}

    def fake(transcript, source_meta, *, model=None, api_key=None):
        r = seq[calls["n"]]
        calls["n"] += 1
        return r

    return fake


# ── direct vote-logic tests ──
def test_vote_status_unanimous_majority_tie():
    assert ensemble._vote_status(["implied", "implied", "implied"]) == ("implied", "unanimous")
    assert ensemble._vote_status(["specified", "specified", "unspecified"]) == ("specified", "majority")
    # 1/1/1 tie => least-crediting (unspecified) wins
    assert ensemble._vote_status(["specified", "implied", "unspecified"]) == ("unspecified", "tie")
    # 1-1 specified/implied tie => least-crediting of the two => implied
    assert ensemble._vote_status(["specified", "implied"]) == ("implied", "tie")


# ── direct donor tests (both branches) ──
def test_field_donor_medoid_then_fallback():
    runs = [{"template": {"fields": {"D3": {"status": "specified", "value": "m"}}}},
            {"template": {"fields": {"D3": {"status": "unspecified", "value": "r1"}}}},
            {"template": {"fields": {"D3": {"status": "specified", "value": "r2"}}}}]
    # medoid (index 0) status matches the vote -> donor is the medoid's object
    assert ensemble._field_donor("D3", "specified", runs, 0)["value"] == "m"
    # medoid (index 1) status does NOT match -> fallback to lowest-index matching run (index 0)
    assert ensemble._field_donor("D3", "specified", runs, 1)["value"] == "m"


# ── direct claims-grouping tests ──
def test_merge_claims_groups_variants_and_majority_testable():
    q = "backed by a ten year track record"      # >=12 normalized chars
    runs = [{"template": {"claims": [{"claim": "A", "quote": q, "testable": True}]}},
            {"template": {"claims": [{"claim": "A-variant", "quote": q, "testable": True}]}},
            {"template": {"claims": [{"claim": "A-again", "quote": q, "testable": False}]}}]
    merged = ensemble._merge_claims(runs, medoid_i=0)
    assert len(merged) == 1                        # all three overlap -> one group
    assert merged[0]["testable"] is True           # 2 True vs 1 False
    assert merged[0]["claim"] == "A"               # representative = medoid's member


def test_merge_claims_keeps_distinct_claims_separate():
    runs = [{"template": {"claims": [{"claim": "X", "quote": "the value area high breakout rule",
                                      "testable": True}]}},
            {"template": {"claims": [{"claim": "Y", "quote": "an entirely unrelated statement here",
                                      "testable": False}]}}]
    merged = ensemble._merge_claims(runs, medoid_i=0)
    assert len(merged) == 2                        # no quote overlap -> two groups


# ── end-to-end merge (monkeypatched per-run extract) ──
def test_majority_vote_2_1(monkeypatch):
    a, b, c = _base(), _base(), _base()
    c["fields"]["D3"]["status"] = "unspecified"   # 2 specified vs 1 unspecified
    monkeypatch.setattr(ensemble, "extract_template", _seq_extract([_ok(a), _ok(b), _ok(c)]))
    r = ensemble.extract_template_ensemble(FAKE_TX, {}, k=3)
    assert r["status"] == "ok"
    assert r["template"]["fields"]["D3"]["status"] == "specified"
    assert r["ensemble_meta"]["ok_runs"] == 3


def test_specified_implied_tie_after_drop_resolves_implied(monkeypatch):
    a, b = _base(), _base()
    a["fields"]["D3"]["status"] = "specified"
    b["fields"]["D3"]["status"] = "implied"
    monkeypatch.setattr(ensemble, "extract_template",
                        _seq_extract([_ok(a), _ok(b), _failed(["boom"])]))
    r = ensemble.extract_template_ensemble(FAKE_TX, {}, k=3)
    assert r["status"] == "ok"
    assert r["ensemble_meta"]["ok_runs"] == 2           # the failed run was dropped
    assert r["template"]["fields"]["D3"]["status"] == "implied"   # 1-1 tie -> least-crediting


def test_one_failed_run_still_succeeds(monkeypatch):
    monkeypatch.setattr(ensemble, "extract_template",
                        _seq_extract([_ok(_base()), _ok(_base()), _failed(["x"])]))
    r = ensemble.extract_template_ensemble(FAKE_TX, {}, k=3)
    assert r["status"] == "ok"
    assert r["ensemble_meta"]["ok_runs"] == 2


def test_two_failed_runs_fail_terminally(monkeypatch):
    monkeypatch.setattr(ensemble, "extract_template",
                        _seq_extract([_ok(_base()), _failed(["err-a"]), _failed(["err-b"])]))
    r = ensemble.extract_template_ensemble(FAKE_TX, {}, k=3)
    assert r["status"] == "extraction_failed"
    assert any("err-a" in e for e in r["errors"])
    assert any("err-b" in e for e in r["errors"])


def test_merged_revalidates_and_scores_class_from_scorer(monkeypatch):
    monkeypatch.setattr(ensemble, "extract_template",
                        _seq_extract([_ok(_base()), _ok(_base()), _ok(_base())]))
    r = ensemble.extract_template_ensemble(FAKE_TX, {}, k=3)
    assert r["status"] == "ok"
    assert r["completeness"]["class"] == "A"           # deterministic scorer, base is Class A
    assert r["ensemble_meta"]["unanimous_fields"] == 27
    assert r["ensemble_meta"]["majority_fields"] == 0
    assert r["ensemble_meta"]["tie_fields"] == 0
    # per-run enforcement surfaced
    assert len(r["ensemble_meta"]["per_run"]) == 3


def test_donor_object_provenance_end_to_end(monkeypatch):
    a, b, c = _base(), _base(), _base()
    a["fields"]["D3"]["value"] = "VAL-A"                # all specified+grounded, unanimous vote
    b["fields"]["D3"]["value"] = "VAL-B"
    c["fields"]["D3"]["value"] = "VAL-C"
    monkeypatch.setattr(ensemble, "extract_template", _seq_extract([_ok(a), _ok(b), _ok(c)]))
    r = ensemble.extract_template_ensemble(FAKE_TX, {}, k=3)
    assert r["status"] == "ok"
    # unanimous specified -> medoid is run 0 (lowest index, full agreement) -> its object donates
    assert r["template"]["fields"]["D3"]["value"] == "VAL-A"
    assert r["ensemble_meta"]["medoid_index"] == 0

"""WIT-P3e-2 — extraction GOLDEN regression (NETWORK + LLM + COST gated; NOT run in CI).

Runs the live Anthropic extraction on the two archived transcripts and grades the output against
the two hand-filled fixtures with a SCORED RUBRIC (never byte-equality — LLM prose varies):

  HARD asserts (must hold):
    - completeness class correct (A for WIT-0001, B for WIT-0002)
    - status of every execution-required field matches the fixture (B1,B2,D1-D4,F1) and the
      F2|F4 exit pair's satisfied-ness matches
    - required_missing set matches the fixture
    - GROUNDING (anti-hallucination): every specified/implied field's source_quote is a verbatim
      substring of the transcript (J section exempt — WIT-authored, no quote)
  TOLERANT:
    - value/source_quote by overlap, not exact string
    - claims[] COVERAGE (P3o): every fixture claim matched by quote-fragment overlap
      with an agreeing testable flag; extras allowed, every extracted claim quote grounded
    - consistency_flags[] present where the fixture has them
    - a per-field status-match score must clear a threshold

Enable:  WIT_RUN_LLM_TESTS=1 ANTHROPIC_API_KEY=sk-... python -m pytest tests/test_extraction_golden.py -q
"""
from __future__ import annotations

import json
import os
import re

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("WIT_RUN_LLM_TESTS") or not os.getenv("ANTHROPIC_API_KEY"),
    reason="LLM/network/cost gated; set WIT_RUN_LLM_TESTS=1 and ANTHROPIC_API_KEY to run")

from wit.extraction.extract import extract_template
from wit.extraction.schema import FIELD_IDS

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
_SOURCES = os.path.join(_REPO, "docs", "wit", "sources")
_FIX = os.path.join(_HERE, "fixtures")

REQUIRED = ["B1", "B2", "D1", "D2", "D3", "D4", "F1"]
_SAT = {"specified", "implied"}
STATUS_MATCH_THRESHOLD = 0.75   # >=75% of the 27 fields must match the fixture's status

CASES = [
    ("WIT-S-0001-vp-orb-transcript.md", "WIT-T-0001.template.json", "A"),
    ("WIT-S-0002-candle-formation-transcript.md", "WIT-T-0002.template.json", "B"),
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _satisfied(field: dict) -> bool:
    return field.get("status") in _SAT


@pytest.mark.parametrize("src,fixname,expected_class", CASES)
def test_golden_extraction(src, fixname, expected_class):
    transcript = open(os.path.join(_SOURCES, src), encoding="utf-8").read()
    fixture = json.load(open(os.path.join(_FIX, fixname), encoding="utf-8"))

    r = extract_template(transcript, {"title": src, "url": None, "channel": None})
    assert r["status"] == "ok", f"extraction failed: {r.get('errors')}"
    tpl = r["template"]

    # ── HARD: class ──
    assert r["completeness"]["class"] == expected_class

    # ── HARD: required_missing set ──
    assert set(r["completeness"]["required_missing"]) == \
        set(fixture["completeness"]["required_missing"])

    # ── HARD: execution-required field statuses ──
    for fid in REQUIRED:
        assert tpl["fields"][fid]["status"] == fixture["fields"][fid]["status"], \
            f"{fid}: {tpl['fields'][fid]['status']} != fixture {fixture['fields'][fid]['status']}"
    # F2|F4 pair: satisfied-ness matches the fixture
    fix_pair = _satisfied(fixture["fields"]["F2"]) or _satisfied(fixture["fields"]["F4"])
    got_pair = _satisfied(tpl["fields"]["F2"]) or _satisfied(tpl["fields"]["F4"])
    assert got_pair == fix_pair, "F2|F4 exit-pair satisfied-ness differs from fixture"

    # ── HARD: grounding — every specified/implied source_quote is verbatim in the transcript ──
    ntx = _norm(transcript)
    for fid in FIELD_IDS:
        if fid[0] == "J":              # WIT-authored, no source_quote required
            continue
        f = tpl["fields"][fid]
        if f["status"] in _SAT:
            q = f.get("source_quote")
            assert q, f"{fid} is {f['status']} but has no source_quote"
            assert _norm(q) in ntx, f"{fid} source_quote not grounded in transcript: {q!r}"

    # ── TOLERANT: claims coverage (P3o adjudication) — the fixture list is the
    # REQUIRED CORE, not a cap. Rule 4 asks for EVERY claim, so extras are correct
    # behavior; what matters is (a) no fixture claim missed, (b) every extracted
    # claim grounded. Fixture quotes may join non-contiguous spans with an ellipsis —
    # match per fragment.
    def _fragments(q):
        return [f for f in re.split(r"\.\.\.|…", q or "") if len(_norm(f)) >= 12]

    ex_quotes = [_norm(c.get("quote") or "") for c in tpl["claims"]]
    for fc in fixture["claims"]:
        frags = _fragments(fc["quote"]) or [fc["quote"]]
        hit = [i for i, eq in enumerate(ex_quotes)
               if eq and any(_norm(fr) in eq or eq in _norm(fr) for fr in frags)]
        assert hit, f"fixture claim not covered: {fc['claim']!r}"
        assert any(tpl["claims"][i].get("testable") == fc["testable"] for i in hit), \
            f"claim covered but testable flag differs: {fc['claim']!r}"
    for c in tpl["claims"]:
        q = c.get("quote")
        assert q and _norm(q) in ntx, f"claim quote not grounded: {q!r}"
    if fixture["consistency_flags"]:
        assert len(tpl["consistency_flags"]) >= 1, "expected a consistency flag"

    # ── per-field status-match score + threshold ──
    matches = sum(1 for fid in FIELD_IDS
                  if tpl["fields"][fid]["status"] == fixture["fields"][fid]["status"])
    score = matches / len(FIELD_IDS)
    assert score >= STATUS_MATCH_THRESHOLD, \
        f"per-field status match {score:.2f} < {STATUS_MATCH_THRESHOLD} ({matches}/{len(FIELD_IDS)})"

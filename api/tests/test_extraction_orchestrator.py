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


def test_valid_first_try(monkeypatch):
    monkeypatch.setattr(provider, "extract_once",
                        lambda s, u, *, model, api_key=None: _ret(_valid_template()))
    r = extract.extract_template("some transcript text", {"title": "Vid #2"})
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
    seq = [_invalid_template(), _valid_template()]
    calls = {"n": 0}

    def fake(s, u, *, model, api_key=None):
        t = seq[calls["n"]]
        calls["n"] += 1
        return _ret(t)

    monkeypatch.setattr(provider, "extract_once", fake)
    r = extract.extract_template("tx", {}, max_retries=2)
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

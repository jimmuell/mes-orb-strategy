"""WIT-P4b — POST /wit/v1/map router tests (FastAPI TestClient, NO network, NO LLM).

The endpoint is a pure pass-through over the engine mapper (map_template). GOLDENS (Class A / B)
are EXACT EQUALITY and are NEVER tuned to pass; a failure here STOPs the slice. Reuses the auth
fixtures from test_wit_router.py and the fixture loader from test_mapper.py.

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_wit_map.py -q
"""
from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

import server
from wit.config import VPORBConfig
from wit.event_study import EventStudyConfig
from wit.mapper import (map_template, strategy_config_to_vporb, event_study_config_to_engine)
from wit.extraction import FIELD_IDS

_SVC_KEY = "svc-secret-key"
_AUTH = {"Authorization": f"Bearer {_SVC_KEY}"}
_FIX = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_SERVICE_KEY", _SVC_KEY)
    from wit.run_store import WITRunStore
    monkeypatch.setattr(server, "_WIT_RUNS", WITRunStore())


@pytest.fixture
def client():
    return TestClient(server.app)


def _load(name):
    with open(os.path.join(_FIX, name)) as fh:
        return json.load(fh)


def _class_c_template():
    """Minimal template: a setup but NO trigger and no testable claim -> Class C
    (same construction as test_mapper.py G4)."""
    fields = {fid: {"value": None, "status": "unspecified",
                    "source_quote": None, "assumption": None} for fid in FIELD_IDS}
    fields["D2"] = {"value": "some setup", "status": "specified",
                    "source_quote": "q", "assumption": None}
    return {"template_version": "1.0",
            "source": {"url": None, "title": None, "channel": None, "transcript_hash": None},
            "fields": fields, "claims": [{"claim": "x", "quote": "y", "testable": False}],
            "consistency_flags": [], "completeness": {"score": 0, "class": "C",
                                                      "required_missing": []},
            "interpretations": []}


# ── 1. AUTH ──
def test_no_header_401(client):
    r = client.post("/wit/v1/map", json={"template": {}})
    assert r.status_code == 401


def test_wrong_bearer_403(client):
    r = client.post("/wit/v1/map", json={"template": {}},
                    headers={"Authorization": "Bearer nope"})
    assert r.status_code == 403


def test_service_key_unset_503(client, monkeypatch):
    monkeypatch.delenv("WIT_ENGINE_SERVICE_KEY", raising=False)
    r = client.post("/wit/v1/map", json={"template": {}}, headers=_AUTH)
    assert r.status_code == 503


# ── 2. GOLDEN, Class A (T-0001) — EXACT EQUALITY, two independent anchors ──
def test_golden_class_a_exact(client):
    fixture = _load("WIT-T-0001.template.json")
    r = client.post("/wit/v1/map", json={"template": fixture}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == map_template(fixture)                     # pure pass-through, exact
    # end anchor: the mapped config round-trips to the published VPORBConfig() exactly
    assert strategy_config_to_vporb(r.json()["config"]) == VPORBConfig()


# ── 3. GOLDEN, Class B (T-0002) — EXACT EQUALITY ──
def test_golden_class_b_exact(client):
    fixture = _load("WIT-T-0002.template.json")
    r = client.post("/wit/v1/map", json={"template": fixture}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == map_template(fixture)                     # pure pass-through, exact
    assert event_study_config_to_engine(r.json()["config"]) == EventStudyConfig()


# ── 4. Class C -> 200 untestable (product outcome, not an error) ──
def test_class_c_untestable(client):
    r = client.post("/wit/v1/map", json={"template": _class_c_template()}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"kind": None, "class": "C", "untestable": True}


# ── 5. Unsupported mode -> 400 UNSUPPORTED_CONSTRUCT with {field, mode} ──
def test_unsupported_mode_400(client):
    fixture = _load("WIT-T-0001.template.json")
    fixture["fields"]["D2"]["mode"] = "not_a_real_mode"          # junk token in the vocabulary gate
    r = client.post("/wit/v1/map", json={"template": fixture}, headers=_AUTH)
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "UNSUPPORTED_CONSTRUCT"
    assert body["error"]["detail"]["field"] == "D2"
    assert body["error"]["detail"]["mode"] == "not_a_real_mode"


# ── 6. Malformed input — see WIT-P4b-report §6: the spec's two example inputs DIVERGE from
#      reality, so these assert the TRUE behavior (untuned): an EMPTY template is a valid
#      Class-C outcome (200 untestable), and a non-dict `fields` is malformed (400). ──
def test_empty_template_is_untestable_not_400(client):
    # {} scores Class C (empty = no strategy) -> 200 untestable, NOT 400. (Spec expected 400.)
    r = client.post("/wit/v1/map", json={"template": {}}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"kind": None, "class": "C", "untestable": True}


def test_nondict_fields_is_invalid_config_400(client):
    # {"fields": "nonsense"} -> AttributeError in the mapper's mode gate; the endpoint maps it to
    # a clean 400 INVALID_CONFIG (AttributeError added to the catch — see report).
    r = client.post("/wit/v1/map", json={"template": {"fields": "nonsense"}}, headers=_AUTH)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_CONFIG"


# ── 7. NO STATE: identical bodies across two calls; run store length unchanged ──
def test_no_state_across_calls(client):
    fixture = _load("WIT-T-0001.template.json")
    before = len(server._WIT_RUNS._runs)
    r1 = client.post("/wit/v1/map", json={"template": fixture}, headers=_AUTH)
    r2 = client.post("/wit/v1/map", json={"template": fixture}, headers=_AUTH)
    assert r1.status_code == r2.status_code == 200
    assert r1.content == r2.content                              # byte-identical, no state
    assert len(server._WIT_RUNS._runs) == before                # /wit/v1/map touches no run store

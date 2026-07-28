"""WIT-P3r — POST /wit/v1/extract router tests (FastAPI TestClient, NO network, NO live LLM).

extract_template_ensemble is STUBBED (monkeypatch); under test are routing, auth, idempotency,
the kill switch, transcript validation, budget-terminal-state, and signed-callback propagation of
{template, completeness, raw_meta incl. ensemble_meta}. Mirrors test_wit_router.py's harness.

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_wit_extract.py -q
"""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

import server
import callback_writer

_SVC_KEY = "svc-secret-key"
_HMAC = "cb-hmac-secret"
_CB_URL = "https://myproj.supabase.co/functions/v1/wit-callback"
_AUTH = {"Authorization": f"Bearer {_SVC_KEY}"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_SERVICE_KEY", _SVC_KEY)
    monkeypatch.setenv("WIT_CALLBACK_HMAC_SECRET", _HMAC)
    monkeypatch.delenv("WIT_DISABLE_EXTRACT", raising=False)
    monkeypatch.delenv("WIT_EXTRACT_K", raising=False)
    from wit.run_store import WITRunStore
    monkeypatch.setattr(server, "_WIT_RUNS", WITRunStore())


@pytest.fixture
def client():
    return TestClient(server.app)


@pytest.fixture
def captured_callbacks(monkeypatch):
    calls = []

    def fake_post(self, payload):
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        sig = hmac.new(self._secret, body, hashlib.sha256).hexdigest()
        calls.append({"url": self.url, "sig": sig, "body": body, "payload": payload})

    monkeypatch.setattr(callback_writer.WITCallbackWriter, "post", fake_post)
    return calls


def _ensemble_ok(k=3):
    return {
        "status": "ok",
        "template": {"template_version": "1.0", "fields": {"D2": {"status": "implied"}},
                     "claims": []},
        "completeness": {"score": 21, "class": "B", "required_missing": ["B1"]},
        "demotions": [], "downgrades": [],
        "raw_meta": {"model": "claude-opus-4-8", "ensemble_k": k},
        "ensemble_meta": {"k": k, "ok_runs": k, "medoid_index": 0, "unanimous_fields": 25,
                          "majority_fields": 2, "tie_fields": 0,
                          "per_run": [{"retries": 0, "demotions": [], "downgrades": []}] * k},
    }


def _stub_ok(monkeypatch, seen=None):
    def fake(transcript, source_meta, *, k=3):
        if seen is not None:
            seen["k"] = k
            seen["transcript"] = transcript
            seen["source_meta"] = source_meta
        return _ensemble_ok(k)
    monkeypatch.setattr(server, "extract_template_ensemble", fake)


def _submit(client, transcript="wait for a break of the value area high", evaluation_id="ev-x",
            **over):
    body = {"evaluation_id": evaluation_id, "callback_url": _CB_URL, "transcript": transcript,
            "source_meta": {"title": "Vid", "url": None, "channel": None}, **over}
    return client.post("/wit/v1/extract", json=body, headers=_AUTH)


# ── happy path: template+completeness+ensemble_meta via GET and signed callback ──
def test_extract_happy_path_and_signed_callback(client, monkeypatch, captured_callbacks):
    _stub_ok(monkeypatch)
    r = _submit(client)
    assert r.status_code == 202
    j = r.json()
    assert j["run_id"].startswith("wr_")
    g = client.get(f"/wit/v1/runs/{j['run_id']}", headers=_AUTH).json()
    assert g["status"] == "succeeded"
    res = g["result"]
    assert res["completeness"]["class"] == "B"
    assert res["template"]["fields"]["D2"]["status"] == "implied"
    assert res["raw_meta"]["ensemble_meta"]["k"] == 3
    assert res["raw_meta"]["ensemble_meta"]["tie_fields"] == 0
    assert res["raw_meta"]["ensemble_meta"]["per_run"]           # per-run demotions/downgrades carried
    # terminal callback fired + HMAC verified
    assert captured_callbacks, "no callback fired"
    cb = captured_callbacks[-1]
    assert cb["payload"]["status"] == "succeeded"
    assert cb["payload"]["result"]["raw_meta"]["ensemble_meta"]["ok_runs"] == 3
    expect = hmac.new(_HMAC.encode(), cb["body"], hashlib.sha256).hexdigest()
    assert cb["sig"] == expect


# ── k env plumbs through to the ensemble ──
def test_k_env_passed_to_ensemble(client, monkeypatch):
    seen = {}
    _stub_ok(monkeypatch, seen=seen)
    monkeypatch.setenv("WIT_EXTRACT_K", "5")
    _submit(client)
    assert seen["k"] == 5


# ── auth ──
def test_missing_bearer_401(client):
    r = client.post("/wit/v1/extract",
                    json={"evaluation_id": "e", "callback_url": _CB_URL, "transcript": "x"})
    assert r.status_code == 401


def test_wrong_bearer_403(client):
    r = client.post("/wit/v1/extract",
                    json={"evaluation_id": "e", "callback_url": _CB_URL, "transcript": "x"},
                    headers={"Authorization": "Bearer nope"})
    assert r.status_code == 403


def test_missing_service_key_503(client, monkeypatch):
    monkeypatch.delenv("WIT_ENGINE_SERVICE_KEY", raising=False)
    r = _submit(client)
    assert r.status_code == 503


# ── idempotency (internal content hash of transcript+source_meta) ──
def test_idempotent_same_transcript_one_run(client, monkeypatch):
    _stub_ok(monkeypatch)
    launches = []
    orig = server._run_wit_extract_job

    async def counting(*a, **k):
        launches.append(1)
        return await orig(*a, **k)

    monkeypatch.setattr(server, "_run_wit_extract_job", counting)
    r1 = _submit(client, transcript="identical body", evaluation_id="ev-Z")
    r2 = _submit(client, transcript="identical body", evaluation_id="ev-Z")
    assert r1.json()["run_id"] == r2.json()["run_id"]
    assert len(launches) == 1                                    # second submit launched no job


def test_different_transcript_new_run(client, monkeypatch):
    _stub_ok(monkeypatch)
    r1 = _submit(client, transcript="text A", evaluation_id="ev-W")
    r2 = _submit(client, transcript="text B", evaluation_id="ev-W")
    assert r1.json()["run_id"] != r2.json()["run_id"]


# ── extraction_failed propagates the errors as a terminal failure ──
def test_extraction_failed_propagates(client, monkeypatch, captured_callbacks):
    def fake(transcript, source_meta, *, k=3):
        return {"status": "extraction_failed", "template": None, "errors": ["e1", "e2"],
                "ensemble_meta": {"k": 3, "ok_runs": 1}}
    monkeypatch.setattr(server, "extract_template_ensemble", fake)
    r = _submit(client)
    g = client.get(f"/wit/v1/runs/{r.json()['run_id']}", headers=_AUTH).json()
    assert g["status"] == "failed"
    assert g["error"]["code"] == "EXTRACTION_FAILED"
    assert g["error"]["detail"]["errors"] == ["e1", "e2"]
    assert captured_callbacks[-1]["payload"]["status"] == "failed"


# ── an exception in the ensemble becomes a guaranteed terminal 'failed' (never a hung run) ──
def test_ensemble_exception_becomes_terminal_failed(client, monkeypatch):
    def boom(transcript, source_meta, *, k=3):
        raise RuntimeError("kaboom in the ensemble")
    monkeypatch.setattr(server, "extract_template_ensemble", boom)
    r = _submit(client)
    g = client.get(f"/wit/v1/runs/{r.json()['run_id']}", headers=_AUTH).json()
    assert g["status"] == "failed"
    assert g["error"]["code"] == "INTERNAL"
    assert "kaboom" in g["error"]["detail"]["traceback"]


# ── kill switch ──
def test_kill_switch_503s_extract(client, monkeypatch):
    _stub_ok(monkeypatch)
    monkeypatch.setenv("WIT_DISABLE_EXTRACT", "1")
    r = _submit(client)
    assert r.status_code == 503


def test_kill_switch_does_not_gate_runs(client, monkeypatch):
    monkeypatch.setenv("WIT_DISABLE_EXTRACT", "1")
    # the runs route is not gated by the extract kill switch — it reaches its own validation
    r = client.post("/wit/v1/runs",
                    json={"evaluation_id": "e", "kind": "backtest", "callback_url": _CB_URL,
                          "config": {}}, headers=_AUTH)
    assert r.status_code != 503


# ── transcript validation ──
def test_empty_transcript_400(client, monkeypatch):
    _stub_ok(monkeypatch)
    r = _submit(client, transcript="   ")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_CONFIG"


def test_over_cap_transcript_400(client, monkeypatch):
    _stub_ok(monkeypatch)
    monkeypatch.setattr(server, "_WIT_EXTRACT_MAX_CHARS", 100)
    r = _submit(client, transcript="x" * 101)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_CONFIG"
    assert r.json()["error"]["detail"]["cap"] == 100


# ── disallowed callback host ──
def test_disallowed_callback_host_rejected(client, monkeypatch):
    _stub_ok(monkeypatch)
    r = _submit(client, callback_url="https://evil.example.com/hook")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_CONFIG"

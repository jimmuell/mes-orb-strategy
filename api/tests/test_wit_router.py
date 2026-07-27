"""WIT-P3d — /wit/v1/* router tests (FastAPI TestClient, NO network, NO full-data runs).

The runners are STUBBED (monkeypatch): under test are routing, auth, idempotency, error
mapping, budget, and callback signing — the computation itself is anchored by G1/G2.
Callbacks are captured by monkeypatching WITCallbackWriter.post (no HTTP leaves the box).

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_wit_router.py -q
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import types

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
    # fresh run store per test (avoid idempotency bleed across tests)
    from wit.run_store import WITRunStore
    monkeypatch.setattr(server, "_WIT_RUNS", WITRunStore())


@pytest.fixture
def client():
    return TestClient(server.app)


@pytest.fixture
def captured_callbacks(monkeypatch):
    """Capture every WIT callback POST (url, signature, raw body) — no network."""
    calls = []

    def fake_post(self, payload):
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        sig = hmac.new(self._secret, body, hashlib.sha256).hexdigest()
        calls.append({"url": self.url, "sig": sig, "body": body, "payload": payload})

    monkeypatch.setattr(callback_writer.WITCallbackWriter, "post", fake_post)
    return calls


# ── stubs for the runners (canned results; no data load) ──
def _stub_backtest(monkeypatch, kpis=None):
    kpis = kpis or {"total_trades": 16, "net_profit": 817.66, "profit_factor": 4.48,
                    "max_drawdown": -100.0, "win_rate": 31.3, "avg_trade": 51.1,
                    "equity_curve": [{"date": "2016-04-11", "equity": 10000.0}]}
    monkeypatch.setattr(server, "run_vp_orb",
                        lambda cfg: types.SimpleNamespace(kpis=kpis, trades=[]))


def _stub_event_study(monkeypatch, result=None):
    monkeypatch.setattr(server, "_load_and_build_candles", lambda cfg: object())
    monkeypatch.setattr(server, "run_config",
                        lambda candles, cfg: result or {"n_events": 100, "verdict": "no_edge"})


def _min_wire_backtest():
    return {
        "config_version": "1.0",
        "instrument": {"symbol": "ES", "tick_size": 0.25, "tick_value": 1.25, "proxy_for": "NQ"},
        "data": {"dataset": "ES_5min_continuous", "granularity_needed": "1min",
                 "window": {"start": "2016-04-10", "end": "2026-04-09"}},
        "session": {"tz": "America/New_York", "trade_window": ["09:45", "10:55"],
                    "force_flat": "15:55"},
        "bias": {"mode": "vp_value_area_break", "params": None},
        "setup_entry": {"trigger": "bar_close_beyond_level", "level": "va_high_low",
                        "order": "market_on_close",
                        "params": {"range_start": "09:30", "range_end": "09:45",
                                   "value_area_pct": 0.7, "granularity": "1min"}},
        "sizing": {"mode": "fixed_contracts", "value": 1},
        "exits": {"stop": {"mode": "level_offset", "ref": "poc", "ticks": 2},
                  "target": {"mode": "r_multiple", "value": 2.0}, "management": [],
                  "time_exit": "force_flat", "same_bar_policy": "stop_first"},
        "risk_controls": {"max_trades_per_day": 1, "reentry": "none"},
        "costs": {"commission_per_side": 0.62, "slippage_ticks": 1},
    }


def _min_wire_event_study():
    return {
        "config_version": "1.0",
        "event": {"mode": "body_vs_trailing_median", "params": {"k": 1.5, "n_baseline": 20}},
        "path_bucket": {"mode": "path_threshold",
                        "params": {"spike_eff": 0.5, "spike_giveback_cap": 0.2,
                                   "pullback_p": 0.4, "bucket_mode": "threshold"}},
        "regime": {"mode": "kaufman_er_trailing_median",
                   "params": {"regime_er_m": 20, "regime_trailing_window": 390,
                              "regime_fixed_er": 0.3, "regime_adx_len": 14,
                              "regime_adx_thresh": 20.0}},
        "outcomes": {"horizons_bars": [1, 3, 5, 10],
                     "measures": ["fwd_return", "giveback", "p_against"]},
        "timeframe": "5min",
        "data": {"dataset": "ES_1min_continuous", "granularity_needed": "1min",
                 "window": {"start": "2016-04-11", "end": "2026-04-09"}},
    }


def _submit(client, kind, config, evaluation_id="ev-1", **over):
    body = {"evaluation_id": evaluation_id, "kind": kind, "callback_url": _CB_URL,
            "config": config, **over}
    return client.post("/wit/v1/runs", json=body, headers=_AUTH)


# ── happy paths (both kinds) with terminal callback fired + HMAC verified ──
def test_backtest_happy_path_and_signed_callback(client, monkeypatch, captured_callbacks):
    _stub_backtest(monkeypatch)
    r = _submit(client, "backtest", _min_wire_backtest())
    assert r.status_code == 202
    j = r.json()
    assert j["run_id"].startswith("wr_")
    assert j["status"] in ("queued", "running", "succeeded")
    assert j["estimated_seconds"] is None
    run_id = j["run_id"]
    # background task ran to terminal (TestClient runs BackgroundTasks synchronously)
    g = client.get(f"/wit/v1/runs/{run_id}", headers=_AUTH).json()
    assert g["status"] == "succeeded"
    assert g["result"]["kind"] == "backtest"
    assert g["result"]["metrics"]["trades"] == 16
    assert g["result"]["metrics"]["expectancy_r"] is None          # GAP, not fabricated
    assert g["result"]["provenance"]["config_hash"]
    # a terminal callback fired, signed correctly
    assert captured_callbacks, "no callback fired"
    cb = captured_callbacks[-1]
    assert cb["payload"]["status"] == "succeeded"
    expect = hmac.new(_HMAC.encode(), cb["body"], hashlib.sha256).hexdigest()
    assert cb["sig"] == expect


def test_event_study_happy_path(client, monkeypatch, captured_callbacks):
    _stub_event_study(monkeypatch)
    r = _submit(client, "event_study", _min_wire_event_study())
    assert r.status_code == 202
    g = client.get(f"/wit/v1/runs/{r.json()['run_id']}", headers=_AUTH).json()
    assert g["status"] == "succeeded"
    assert g["result"]["kind"] == "event_study"
    assert g["result"]["event_study"]["verdict"] == "no_edge"


# ── idempotency ──
def test_idempotent_resubmit_same_run(client, monkeypatch):
    _stub_backtest(monkeypatch)
    launches = []
    orig = server._run_wit_job
    async def counting(*a, **k):
        launches.append(1)
        return await orig(*a, **k)
    monkeypatch.setattr(server, "_run_wit_job", counting)
    cfg = _min_wire_backtest()
    r1 = _submit(client, "backtest", cfg, evaluation_id="ev-X")
    r2 = _submit(client, "backtest", cfg, evaluation_id="ev-X")
    assert r1.json()["run_id"] == r2.json()["run_id"]
    assert len(launches) == 1                                     # second submit launched no job


def test_different_config_new_run(client, monkeypatch):
    _stub_backtest(monkeypatch)
    cfg = _min_wire_backtest()
    cfg2 = _min_wire_backtest(); cfg2["costs"]["slippage_ticks"] = 2
    r1 = _submit(client, "backtest", cfg, evaluation_id="ev-Y")
    r2 = _submit(client, "backtest", cfg2, evaluation_id="ev-Y")
    assert r1.json()["run_id"] != r2.json()["run_id"]


# ── auth ──
def test_missing_service_key_503(client, monkeypatch):
    monkeypatch.delenv("WIT_ENGINE_SERVICE_KEY", raising=False)
    r = _submit(client, "backtest", _min_wire_backtest())
    assert r.status_code == 503


def test_missing_bearer_401(client):
    r = client.post("/wit/v1/runs", json={"evaluation_id": "e", "kind": "backtest",
                                          "callback_url": _CB_URL, "config": {}})
    assert r.status_code == 401


def test_wrong_bearer_403(client):
    r = client.post("/wit/v1/runs",
                    json={"evaluation_id": "e", "kind": "backtest",
                          "callback_url": _CB_URL, "config": _min_wire_backtest()},
                    headers={"Authorization": "Bearer nope"})
    assert r.status_code == 403


# ── callback host allowlist ──
def test_disallowed_callback_host_rejected(client, monkeypatch):
    _stub_backtest(monkeypatch)
    r = _submit(client, "backtest", _min_wire_backtest(),
                callback_url="https://evil.example.com/hook")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_CONFIG"


# ── error mapping ──
def test_unknown_mode_unsupported_construct(client):
    cfg = _min_wire_backtest()
    cfg["session"]["tz"] = "America/Chicago"                      # adapter refuses (non-ET)
    r = _submit(client, "backtest", cfg)
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "UNSUPPORTED_CONSTRUCT"
    assert body["error"]["detail"]["field"] == "C1"


def test_sensitivity_sweep_unsupported(client):
    r = _submit(client, "sensitivity_sweep", {})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "UNSUPPORTED_CONSTRUCT"


def test_malformed_wire_invalid_config(client):
    r = _submit(client, "backtest", {"config_version": "1.0"})   # missing required keys
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_CONFIG"


def test_get_unknown_run_404(client):
    r = client.get("/wit/v1/runs/wr_doesnotexist", headers=_AUTH)
    assert r.status_code == 404


# ── budget + crash → guaranteed terminal state ──
def test_budget_exceeded(client, monkeypatch):
    def slow(cfg):
        time.sleep(0.6)
        return types.SimpleNamespace(kpis={}, trades=[])
    monkeypatch.setattr(server, "run_vp_orb", slow)
    monkeypatch.setattr(server, "_HEARTBEAT_SECONDS", 0.05)
    r = _submit(client, "backtest", _min_wire_backtest(),
                budget={"max_wall_seconds": 0.1})
    g = client.get(f"/wit/v1/runs/{r.json()['run_id']}", headers=_AUTH).json()
    assert g["status"] == "failed"
    assert g["error"]["code"] == "BUDGET_EXCEEDED"


def test_stub_that_raises_becomes_terminal_failed(client, monkeypatch):
    def boom(cfg):
        raise RuntimeError("kaboom in the sim")
    monkeypatch.setattr(server, "run_vp_orb", boom)
    r = _submit(client, "backtest", _min_wire_backtest())
    g = client.get(f"/wit/v1/runs/{r.json()['run_id']}", headers=_AUTH).json()
    assert g["status"] == "failed"                               # never a hung "running"
    assert g["error"]["code"] == "INTERNAL"
    assert "kaboom" in g["error"]["detail"]["traceback"]


# ── legacy surface untouched (additive) ──
def test_legacy_run_still_needs_x_api_key_not_bearer(client):
    # /run uses X-API-Key; a WIT bearer must not authenticate it (separate auth)
    r = client.post("/run", json={"signal_code": "x"}, headers=_AUTH)
    assert r.status_code in (401, 422, 503)   # never 200 on a bearer-only request

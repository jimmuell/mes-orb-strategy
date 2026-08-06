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
import os
import time
import types

import pytest
from fastapi.testclient import TestClient

import server
from wit import data_paths as _wit_data_paths, datasets as _wit_datasets_mod
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


# ── WIT-P3g: exec-endpoint kill switch (DISABLE_EXEC_ENDPOINTS) ──
_EXEC_BODIES = {
    "/run": {"signal_code": "x"},
    "/run/compare": {"signal_code": "x"},
    "/profile": {"signal_code": "x"},
    "/run/async": {"signal_code": "x", "run_id": "r",
                   "callback_url": "https://x.supabase.co/f", "callback_secret": "s"},
}


def test_exec_endpoints_403_when_disabled(client, monkeypatch):
    monkeypatch.setenv("DISABLE_EXEC_ENDPOINTS", "1")
    monkeypatch.setenv("BACKTEST_API_KEY", "k")
    hdr = {"X-API-Key": "k"}
    for path, body in _EXEC_BODIES.items():
        r = client.post(path, json=body, headers=hdr)
        assert r.status_code == 403, f"{path} not gated: {r.status_code}"
        assert "EXEC_DISABLED" in r.json()["detail"], path


def test_exec_disabled_does_not_gate_wit_or_probes(client, monkeypatch):
    monkeypatch.setenv("DISABLE_EXEC_ENDPOINTS", "true")   # case-insensitive
    _stub_backtest(monkeypatch)
    # /wit/v1/* still works
    r = _submit(client, "backtest", _min_wire_backtest())
    assert r.status_code == 202
    g = client.get(f"/wit/v1/runs/{r.json()['run_id']}", headers=_AUTH)
    assert g.status_code == 200 and g.json()["status"] == "succeeded"
    # unauthenticated probes still 200
    for probe in ("/health", "/ping", "/env"):
        assert client.get(probe).status_code == 200, probe


def test_exec_endpoints_not_gated_when_flag_off(client, monkeypatch):
    monkeypatch.delenv("DISABLE_EXEC_ENDPOINTS", raising=False)
    monkeypatch.setenv("BACKTEST_API_KEY", "k")
    # wrong key -> reaches auth (401), NOT the 403 EXEC_DISABLED gate -> proves no drift
    r = client.post("/run", json={"signal_code": "x"}, headers={"X-API-Key": "wrong"})
    assert r.status_code == 401
    assert "EXEC_DISABLED" not in r.text


# ── WIT-P3f: sensitivity sweep ──
def test_sweep_true_runs_all_cells(client, monkeypatch, captured_callbacks):
    _stub_backtest(monkeypatch)
    r = _submit(client, "backtest", _min_wire_backtest(), sweep=True)
    assert r.status_code == 202
    g = client.get(f"/wit/v1/runs/{r.json()['run_id']}", headers=_AUTH).json()
    assert g["status"] == "succeeded"
    res = g["result"]
    # primary result intact
    assert res["kind"] == "backtest" and res["metrics"]["trades"] == 16
    # all 5 backtest cells completed, none skipped
    assert set(res["sensitivity"].keys()) == {
        "entry_body", "slippage_0", "slippage_2", "target_first", "vp_5min"}
    assert res["sweep"] == {"requested": 5, "completed": 5, "skipped": []}


def test_sweep_false_has_no_sensitivity(client, monkeypatch):
    _stub_backtest(monkeypatch)
    r = _submit(client, "backtest", _min_wire_backtest())      # sweep defaults False
    g = client.get(f"/wit/v1/runs/{r.json()['run_id']}", headers=_AUTH).json()
    assert g["status"] == "succeeded"
    assert "sensitivity" not in g["result"]
    assert "sweep" not in g["result"]


def test_sweep_budget_skips_disclosed(client, monkeypatch):
    # primary fits (0.15s < 0.25s budget); cells run out of the shared budget -> skipped
    def slow(cfg):
        time.sleep(0.15)
        return types.SimpleNamespace(kpis={"total_trades": 1, "equity_curve": []}, trades=[])
    monkeypatch.setattr(server, "run_vp_orb", slow)
    r = _submit(client, "backtest", _min_wire_backtest(),
                sweep=True, budget={"max_wall_seconds": 0.25})
    g = client.get(f"/wit/v1/runs/{r.json()['run_id']}", headers=_AUTH).json()
    assert g["status"] == "succeeded"                          # primary completed
    res = g["result"]
    assert res["sweep"]["requested"] == 5
    assert res["sweep"]["completed"] + len(res["sweep"]["skipped"]) == 5
    assert res["sweep"]["skipped"]                             # at least one cell skipped, disclosed
    # every skipped cell name is a real grid cell, none silently vanished
    assert set(res["sweep"]["skipped"]) <= {
        "entry_body", "slippage_0", "slippage_2", "target_first", "vp_5min"}


def test_sweep_primary_over_budget_fails(client, monkeypatch):
    def slow(cfg):
        time.sleep(0.6)
        return types.SimpleNamespace(kpis={}, trades=[])
    monkeypatch.setattr(server, "run_vp_orb", slow)
    r = _submit(client, "backtest", _min_wire_backtest(),
                sweep=True, budget={"max_wall_seconds": 0.1})
    g = client.get(f"/wit/v1/runs/{r.json()['run_id']}", headers=_AUTH).json()
    assert g["status"] == "failed"
    assert g["error"]["code"] == "BUDGET_EXCEEDED"


def test_sweep_idempotency_distinct_from_single(client, monkeypatch):
    _stub_backtest(monkeypatch)
    cfg = _min_wire_backtest()
    s1 = _submit(client, "backtest", cfg, evaluation_id="ev-S", sweep=True)
    s2 = _submit(client, "backtest", cfg, evaluation_id="ev-S", sweep=True)
    single = _submit(client, "backtest", cfg, evaluation_id="ev-S", sweep=False)
    assert s1.json()["run_id"] == s2.json()["run_id"]          # same sweep run
    assert single.json()["run_id"] != s1.json()["run_id"]      # sweep vs single -> different runs


# ── WIT-P5p — GET /wit/v1/datasets ──
def test_datasets_endpoint_missing_bearer_401(client):
    r = client.get("/wit/v1/datasets")
    assert r.status_code == 401


def test_datasets_endpoint_wrong_bearer_403(client):
    r = client.get("/wit/v1/datasets", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 403


def test_datasets_endpoint_returns_builtin_with_economics_supported_and_date_range(client):
    r = client.get("/wit/v1/datasets", headers=_AUTH)
    assert r.status_code == 200
    body = r.json()
    ids = {d["id"]: d for d in body["datasets"]}
    assert _wit_datasets_mod.BUILT_IN_DEFAULT.id in ids
    d = ids[_wit_datasets_mod.BUILT_IN_DEFAULT.id]
    assert d["economics_supported"] is True
    assert d["symbol"] == _wit_datasets_mod.BUILT_IN_DEFAULT.symbol
    assert d["point_value"] == _wit_datasets_mod.BUILT_IN_DEFAULT.point_value
    assert d["tick_size"] == _wit_datasets_mod.BUILT_IN_DEFAULT.tick_size
    # a real date range read from the actual data, not a hardcoded label
    assert d["date_range"]["start"] < d["date_range"]["end"]
    assert d["date_range"]["start"].count("-") == 2 and d["date_range"]["end"].count("-") == 2


def test_datasets_endpoint_includes_unsupported_economics_entry_not_omitted(client, monkeypatch, tmp_path):
    """A catalogued dataset whose economics the engine doesn't apply must still be LISTED
    (economics_supported: false) — omitting it would make the 'app never claims a dataset the
    engine doesn't have' guarantee a lie in the other direction (the app wouldn't know it exists)."""
    real_dir = _wit_data_paths.resolve_engine_data_dir()
    for name in (_wit_datasets_mod.BUILT_IN_DEFAULT.bars_5min, _wit_datasets_mod.BUILT_IN_DEFAULT.opening_1min):
        os.symlink(os.path.join(real_dir, name), os.path.join(tmp_path, name))
    unsupported_id = "UNSUPPORTED_ECONOMICS_PROOF"
    with open(os.path.join(tmp_path, "datasets.json"), "w") as fh:
        json.dump({"version": 1, "datasets": [
            {"id": unsupported_id, "label": "Unsupported-economics proof entry",
             "bars_5min": _wit_datasets_mod.BUILT_IN_DEFAULT.bars_5min,
             "opening_1min": _wit_datasets_mod.BUILT_IN_DEFAULT.opening_1min,
             "symbol": "MNQ", "point_value": 2.0, "tick_size": 0.25,
             "bars_granularity": "5min"}]}, fh)
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))

    r = client.get("/wit/v1/datasets", headers=_AUTH)
    assert r.status_code == 200
    ids = {d["id"]: d for d in r.json()["datasets"]}
    assert unsupported_id in ids                          # present, not omitted
    assert ids[unsupported_id]["economics_supported"] is False


def test_datasets_endpoint_excludes_entry_with_missing_files(client, monkeypatch, tmp_path):
    """available() already guarantees a catalogued-but-fileless entry is excluded — assert the
    endpoint doesn't re-add it."""
    missing_id = "FILES_MISSING_PROOF"
    with open(os.path.join(tmp_path, "datasets.json"), "w") as fh:
        json.dump({"version": 1, "datasets": [
            {"id": missing_id, "label": "No files on disk", "bars_5min": "nope_5min.parquet",
             "opening_1min": "nope_1min.parquet", "symbol": "MES",
             "point_value": 5.0, "tick_size": 0.25, "bars_granularity": "5min"}]}, fh)
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))

    r = client.get("/wit/v1/datasets", headers=_AUTH)
    assert r.status_code == 200
    ids = {d["id"] for d in r.json()["datasets"]}
    assert missing_id not in ids
    # and since tmp_path also lacks the BUILT-IN files, the built-in id is excluded here too —
    # proves available()'s file-presence check, not a special case for the built-in id
    assert _wit_datasets_mod.BUILT_IN_DEFAULT.id not in ids


# ── WIT-P5p — honest backtest provenance ──
def test_backtest_provenance_names_the_dataset_actually_used(client, monkeypatch, tmp_path):
    real_dir = _wit_data_paths.resolve_engine_data_dir()
    for name in (_wit_datasets_mod.BUILT_IN_DEFAULT.bars_5min, _wit_datasets_mod.BUILT_IN_DEFAULT.opening_1min):
        os.symlink(os.path.join(real_dir, name), os.path.join(tmp_path, name))
    second_id = "SECOND_DATASET_PROVENANCE_PROOF"
    with open(os.path.join(tmp_path, "datasets.json"), "w") as fh:
        json.dump({"version": 1, "datasets": [
            {"id": second_id, "label": "Second id, same files",
             "bars_5min": _wit_datasets_mod.BUILT_IN_DEFAULT.bars_5min,
             "opening_1min": _wit_datasets_mod.BUILT_IN_DEFAULT.opening_1min,
             "symbol": "MES", "point_value": 5.0, "tick_size": 0.25,
             "bars_granularity": "5min"}]}, fh)
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _stub_backtest(monkeypatch)

    builtin_cfg = _min_wire_backtest()                     # already declares "ES_5min_continuous"
    r_builtin = _submit(client, "backtest", builtin_cfg, evaluation_id="ev-prov-builtin")
    assert r_builtin.status_code == 202
    g_builtin = client.get(f"/wit/v1/runs/{r_builtin.json()['run_id']}", headers=_AUTH).json()
    assert g_builtin["status"] == "succeeded"
    prov_builtin = g_builtin["result"]["provenance"]
    assert prov_builtin["dataset_id"] == _wit_datasets_mod.BUILT_IN_DEFAULT.id

    second_cfg = _min_wire_backtest()
    second_cfg["data"]["dataset"] = second_id
    r_second = _submit(client, "backtest", second_cfg, evaluation_id="ev-prov-second")
    assert r_second.status_code == 202
    g_second = client.get(f"/wit/v1/runs/{r_second.json()['run_id']}", headers=_AUTH).json()
    assert g_second["status"] == "succeeded"
    prov_second = g_second["result"]["provenance"]
    assert prov_second["dataset_id"] == second_id
    assert prov_second["dataset_id"] != prov_builtin["dataset_id"]   # names the dataset ACTUALLY used

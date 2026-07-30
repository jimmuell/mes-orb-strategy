"""WIT-P4t — v1 verdict block: tested/no-edge/inconclusive, and NEVER a claim of edge.

Ratified rule (2026-07-30): a v1 result may say a strategy was tested and showed no edge, or that
the outcome is inconclusive — it may never claim an edge. These tests pin the rule and, with an
exhaustive grid, guard the HARD RULE that no code path can ever emit an edge claim.

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_verdict.py -q
"""
from __future__ import annotations

import itertools

import server
from wit.verdict import derive_verdict

_ALLOWED = {"tested_no_edge", "tested_inconclusive"}


# ── the ratified rule, branch by branch ──────────────────────────────────────
def test_negative_pf_below_one_is_no_edge_with_pf_in_reason():
    v = derive_verdict("backtest", {"profit_factor": 0.90, "net_pnl": -9672, "trades": 4158})
    assert v["code"] == "tested_no_edge"
    assert v["label"] == "Tested — no edge demonstrated"
    assert "0.90" in v["reason"]


def test_positive_result_is_inconclusive_and_makes_no_edge_claim():
    v = derive_verdict("backtest", {"profit_factor": 1.30, "net_pnl": 5000, "trades": 100})
    assert v["code"] == "tested_inconclusive"
    assert v["label"] == "Tested — inconclusive"
    assert "no edge claim is made" in v["reason"]


def test_nonpositive_net_with_pf_ge_one_is_no_edge():
    # net exactly 0, PF >= 1  -> no edge
    assert derive_verdict("backtest", {"profit_factor": 1.0, "net_pnl": 0, "trades": 50})["code"] \
        == "tested_no_edge"
    # net negative, PF >= 1  -> no edge (net_pnl <= 0 dominates a healthy-looking PF)
    assert derive_verdict("backtest", {"profit_factor": 1.5, "net_pnl": -1, "trades": 50})["code"] \
        == "tested_no_edge"


def test_zero_trades_or_none_metrics_is_inconclusive_insufficient():
    for m in (
        {"profit_factor": 1.3, "net_pnl": 5, "trades": 0},
        {"profit_factor": 1.3, "net_pnl": 5, "trades": None},
        {"profit_factor": None, "net_pnl": 5, "trades": 10},
        {"profit_factor": 1.3, "net_pnl": None, "trades": 10},
        {},
    ):
        v = derive_verdict("backtest", m)
        assert v["code"] == "tested_inconclusive"
        assert "insufficient" in v["reason"]


def test_event_study_is_always_inconclusive():
    v = derive_verdict("event_study", {})
    assert v["code"] == "tested_inconclusive"
    assert v["label"] == "Tested — inconclusive"
    assert "statistical confidence layer" in v["reason"]


# ── exhaustive guard: no path may ever claim edge ────────────────────────────
def test_exhaustive_no_path_ever_claims_edge():
    pfs = [None, -5.0, 0.0, 0.5, 0.99, 1.0, 1.0000001, 1.5, 4.48, 1e9]
    nets = [None, -1e9, -1, 0, 1, 5000, 1e9]
    trades = [None, 0, 1, 2561, 10_000_000]
    seen_codes = set()
    for pf, net, tr in itertools.product(pfs, nets, trades):
        for kind in ("backtest", "event_study"):
            v = derive_verdict(kind, {"profit_factor": pf, "net_pnl": net, "trades": tr})
            assert v["code"] in _ALLOWED, (kind, pf, net, tr, v)
            seen_codes.add(v["code"])
            # the word "edge" may appear in a LABEL only inside the exact no-edge phrase
            if "edge" in v["label"]:
                assert v["label"] == "Tested — no edge demonstrated", v
            # and never a positive edge claim anywhere in the reason
            low = v["reason"].lower()
            for banned in ("evidence of edge", "edge demonstrated", "promising",
                           "has edge", "shows edge", "profitable edge"):
                assert banned not in low, (banned, v)
    # both codes are actually reachable across the grid (guard isn't vacuously passing)
    assert seen_codes == _ALLOWED


# ── router payload test: a happy-path backtest result carries the verdict block ──
def test_router_backtest_payload_carries_verdict(monkeypatch):
    import types
    import callback_writer
    from wit.run_store import WITRunStore
    from fastapi.testclient import TestClient

    monkeypatch.setenv("WIT_ENGINE_SERVICE_KEY", "svc-secret-key")
    monkeypatch.setenv("WIT_CALLBACK_HMAC_SECRET", "cb-hmac-secret")
    monkeypatch.setattr(server, "_WIT_RUNS", WITRunStore())
    monkeypatch.setattr(callback_writer.WITCallbackWriter, "post", lambda self, payload: None)
    # PF 4.48, net +817.66 -> positive -> inconclusive ("no edge claim is made")
    monkeypatch.setattr(server, "run_vp_orb", lambda cfg: types.SimpleNamespace(
        kpis={"total_trades": 16, "net_profit": 817.66, "profit_factor": 4.48,
              "max_drawdown": -100.0, "win_rate": 31.3, "avg_trade": 51.1,
              "equity_curve": [{"date": "2016-04-11", "equity": 10000.0}]},
        trades=[]))

    auth = {"Authorization": "Bearer svc-secret-key"}
    client = TestClient(server.app)
    body = {"evaluation_id": "ev-verdict", "kind": "backtest",
            "callback_url": "https://myproj.supabase.co/functions/v1/wit-callback",
            "config": _min_wire_backtest()}
    r = client.post("/wit/v1/runs", json=body, headers=auth)
    assert r.status_code == 202
    run_id = r.json()["run_id"]

    result = client.get(f"/wit/v1/runs/{run_id}", headers=auth).json()["result"]
    v = result["verdict"]
    assert set(v.keys()) == {"code", "label", "reason"}
    assert v["code"] in _ALLOWED
    assert v["code"] == "tested_inconclusive"
    assert v["label"] == "Tested — inconclusive"
    assert "no edge claim is made" in v["reason"]


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

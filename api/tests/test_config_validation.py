"""WIT-P5n — every engine parameter specified, enforced at the boundary, disclosed in the result.

Covers the three pillars: the config_validator + shipped-contract constraints (Pillar 1/2), the
normalize-then-validate ordering and rejection envelope (Pillar 2), and the two disclosure codes
(Pillar 3: D2_value_area_normalized and notapplied_*). New file — no existing test is modified.

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_config_validation.py -q
"""
from __future__ import annotations

import copy
import json
import math
import os
import types

import pytest

import server
from wit.mapper import (map_template, normalize_and_disclose, validate_wire, InvalidConfig,
                        strategy_config_to_vporb)

_FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _anchor_wire():
    with open(os.path.join(_FIX, "WIT-T-0001.template.json")) as fh:
        return map_template(json.load(fh))["config"]


def _accepts(mutate):
    w = _anchor_wire()
    mutate(w)
    normalize_and_disclose(w)
    try:
        validate_wire(w, "backtest")
        return None
    except InvalidConfig as e:
        return e.field


# ── Pillar 3a — value_area_pct is a fraction: normalize (1,100], reject the rest ──
def test_value_area_pct_boundary_table():
    # accepted as-is (no code): 0.7, 1
    for v in (0.7, 1):
        assert _accepts(lambda c, v=v: c["setup_entry"]["params"].__setitem__("value_area_pct", v)) is None
    # normalized then accepted: 70 -> 0.70, 100 -> 1.0
    for v, exp in ((70, 0.70), (100, 1.0)):
        w = _anchor_wire()
        w["setup_entry"]["params"]["value_area_pct"] = v
        w["assumptions_applied"] = []
        normalize_and_disclose(w)
        assert w["setup_entry"]["params"]["value_area_pct"] == exp
        assert "D2_value_area_normalized" in w["assumptions_applied"]
        validate_wire(w, "backtest")   # must not raise
    # rejected (no normalization saves them): 0, -1, 101, null, "0.70", NaN, +inf
    for v in (0, -1, 101, None, "0.70", float("nan"), float("inf")):
        assert _accepts(lambda c, v=v: c["setup_entry"]["params"].__setitem__("value_area_pct", v)) \
            == "setup_entry.params.value_area_pct", f"{v!r} should be rejected"


def test_value_area_pct_already_fraction_gets_no_code():
    w = _anchor_wire()
    assert w["setup_entry"]["params"]["value_area_pct"] == 0.7
    assert "D2_value_area_normalized" not in w["assumptions_applied"]


# ── Pillar 2 — honoured range/enum enforcement ──
def test_negative_stop_ticks_rejected():
    assert _accepts(lambda c: c["exits"]["stop"].__setitem__("ticks", -2)) == "exits.stop.ticks"
    assert _accepts(lambda c: c["exits"]["stop"].__setitem__("ticks", 0)) == "exits.stop.ticks"
    assert _accepts(lambda c: c["exits"]["stop"].__setitem__("ticks", 2)) is None   # positive OK


def test_enum_fields_reject_out_of_set():
    # same_bar_policy: validator-enforced (the runner has no gate — it would silently fall through)
    assert _accepts(lambda c: c["exits"].__setitem__("same_bar_policy", "coin_flip")) \
        == "exits.same_bar_policy"
    # target.value must be a positive R-multiple
    assert _accepts(lambda c: c["exits"]["target"].__setitem__("value", -1)) == "exits.target.value"
    # costs must be non-negative
    assert _accepts(lambda c: c["costs"].__setitem__("commission_per_side", -0.5)) \
        == "costs.commission_per_side"


def test_event_study_enum_and_range_enforced():
    with open(os.path.join(_FIX, "WIT-T-0002.template.json")) as fh:
        w = map_template(json.load(fh))["config"]
    validate_wire(w, "event_study")                      # conforming anchor passes
    bad = copy.deepcopy(w); bad["timeframe"] = "3min"
    with pytest.raises(InvalidConfig):
        validate_wire(bad, "event_study")
    bad2 = copy.deepcopy(w); bad2["path_bucket"]["params"]["spike_eff"] = 50   # prose, not a fraction
    with pytest.raises(InvalidConfig) as ei:
        validate_wire(bad2, "event_study")
    assert "spike_eff" in ei.value.field


# ── Pillar 2 — not-honoured fields are NOT rejected (they don't affect the run) ──
def test_not_honoured_out_of_enum_value_is_accepted_not_rejected():
    # production sent these out-of-contract-enum values; they must pass validation (relaxed to type)
    assert _accepts(lambda c: c["exits"]["stop"].__setitem__("ref", "point_of_control")) is None
    assert _accepts(lambda c: c["setup_entry"].__setitem__("level", "value_area_high_or_low")) is None


# ── Pillar 3b — a not-honoured field carrying a non-default value is disclosed ──
def test_not_honoured_nondefault_value_discloses_code():
    w = _anchor_wire(); w["assumptions_applied"] = []
    w["exits"]["stop"]["ref"] = "va"
    w["risk_controls"]["max_trades_per_day"] = 3
    normalize_and_disclose(w)
    assert "notapplied_exits_stop_ref" in w["assumptions_applied"]
    assert "notapplied_risk_controls_max_trades_per_day" in w["assumptions_applied"]


def test_conforming_config_has_no_spurious_codes():
    m = map_template(json.load(open(os.path.join(_FIX, "WIT-T-0001.template.json"))))
    codes = set(m["assumptions_applied"])
    assert "D2_value_area_normalized" not in codes
    assert not any(c.startswith("notapplied_") for c in codes)


def test_disclosure_is_idempotent():
    w = _anchor_wire(); w["assumptions_applied"] = []
    w["setup_entry"]["params"]["value_area_pct"] = 70
    w["exits"]["stop"]["ref"] = "va"
    normalize_and_disclose(w)
    first = list(w["assumptions_applied"])
    normalize_and_disclose(w)                             # second pass adds nothing (already 0.70)
    assert w["assumptions_applied"] == first


# ── Pillar 2 — the /wit/v1/runs inbound boundary catches a config bypassing the mapper ──
def _min_wire():
    return {"config_version": "1.0",
            "instrument": {"symbol": "ES", "tick_size": 0.25, "tick_value": 1.25, "proxy_for": "NQ"},
            "data": {"dataset": "ES_5min_continuous", "granularity_needed": "1min",
                     "window": {"start": "2016-04-10", "end": "2026-04-09"}},
            "session": {"tz": "America/New_York", "trade_window": ["09:45", "10:55"], "force_flat": "15:55"},
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
            "costs": {"commission_per_side": 0.62, "slippage_ticks": 1}}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_SERVICE_KEY", "svc")
    monkeypatch.setenv("WIT_CALLBACK_HMAC_SECRET", "hmac")
    from wit.run_store import WITRunStore
    monkeypatch.setattr(server, "_WIT_RUNS", WITRunStore())
    import callback_writer
    monkeypatch.setattr(callback_writer.WITCallbackWriter, "post", lambda self, payload: None)
    monkeypatch.setattr(server, "run_vp_orb", lambda cfg: types.SimpleNamespace(
        kpis={"total_trades": 1, "net_profit": 1.0, "profit_factor": 1.0, "max_drawdown": 0.0,
              "win_rate": 100.0, "avg_trade": 1.0, "equity_curve": []}, trades=[]))
    from fastapi.testclient import TestClient
    return TestClient(server.app)


def _submit(client, config):
    return client.post("/wit/v1/runs",
                       json={"evaluation_id": "ev", "kind": "backtest",
                             "callback_url": "https://x.supabase.co/functions/v1/wit-callback",
                             "config": config},
                       headers={"Authorization": "Bearer svc"})


def test_inbound_rejects_nonconforming_bypassing_mapper(client):
    # null value_area_pct — would TypeError deep in the engine; must be a clean 400 INVALID_CONFIG
    bad = _min_wire(); bad["setup_entry"]["params"]["value_area_pct"] = None
    r = _submit(client, bad)
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_CONFIG"
    assert "value_area_pct" in r.json()["error"]["message"]

    # negative stop.ticks
    bad2 = _min_wire(); bad2["exits"]["stop"]["ticks"] = -2
    r2 = _submit(client, bad2)
    assert r2.status_code == 400 and r2.json()["error"]["code"] == "INVALID_CONFIG"
    assert r2.json()["error"]["detail"]["field"] == "exits.stop.ticks"


def test_inbound_normalizes_before_validating(client):
    # value_area_pct 70 bypassing the mapper must be normalized (accepted, 202), not rejected
    ok = _min_wire(); ok["setup_entry"]["params"]["value_area_pct"] = 70
    assert _submit(client, ok).status_code == 202
    # but 101 is out of the (1,100] normalization window -> rejected
    bad = _min_wire(); bad["setup_entry"]["params"]["value_area_pct"] = 101
    assert _submit(client, bad).status_code == 400

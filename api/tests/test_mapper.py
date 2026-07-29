"""WIT-P3c-2 — Class A mapper + VPORB adapter goldens (no network).

G1 is the anchor: the T-0001 template must map+adapt to exactly the VPORBConfig that
produced the published WIT-0001 report (VPORBConfig() defaults).

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_mapper.py -q
"""
from __future__ import annotations

import copy
import json
import os

import pytest

from wit.config import VPORBConfig
from wit.event_study import EventStudyConfig
from wit.mapper import (map_template, strategy_config_to_vporb, event_study_config_to_engine,
                        UnsupportedConstruct, UntestableStrategy)
from wit.extraction import FIELD_IDS

_FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _load(name):
    with open(os.path.join(_FIX, name)) as fh:
        return json.load(fh)


# ── G1 — the anchor: round-trip equals VPORBConfig() exactly ──
def test_G1_t0001_roundtrip_equals_vporbconfig():
    t = _load("WIT-T-0001.template.json")
    mapped = map_template(t)
    assert mapped["kind"] == "backtest"
    cfg = strategy_config_to_vporb(mapped["config"])
    assert cfg == VPORBConfig()                         # exact frozen-dataclass equality
    assert set(mapped["assumptions_applied"]) >= {"B3", "E1", "F4", "F5", "H1", "H2"}


def test_G1_no_prose_value_needed():
    """The mapper must read only mode/params/status — prove it by blanking every prose
    `value` and confirming the config is unchanged."""
    t = _load("WIT-T-0001.template.json")
    baseline = strategy_config_to_vporb(map_template(t)["config"])
    for fid in t["fields"]:
        t["fields"][fid]["value"] = "XXXX prose scrambled XXXX"
    assert strategy_config_to_vporb(map_template(t)["config"]) == baseline == VPORBConfig()


# ── G3 — unknown mode -> UnsupportedConstruct(field, mode) ──
def test_G3_unknown_mode_raises_unsupported():
    t = _load("WIT-T-0001.template.json")
    t["fields"]["D2"]["mode"] = "harmonic_pattern"
    with pytest.raises(UnsupportedConstruct) as exc:
        map_template(t)
    assert exc.value.field == "D2"
    assert exc.value.mode == "harmonic_pattern"


def test_G3_baked_constant_mismatch_raises_at_adapter():
    """A declared-but-not-v1 token passes the vocabulary gate, then the adapter's
    baked-constant rule catches it (order = market_next_open is not runnable)."""
    t = _load("WIT-T-0001.template.json")
    t["fields"]["D4"]["mode"] = "market_next_open"      # declared token, not engine-v1
    wire = map_template(t)["config"]                    # passes vocabulary gate
    with pytest.raises(UnsupportedConstruct) as exc:
        strategy_config_to_vporb(wire)
    assert exc.value.field == "D4"


def test_G3_non_ET_tz_raises_never_converts():
    t = _load("WIT-T-0001.template.json")
    wire = map_template(t)["config"]
    wire["session"]["tz"] = "America/Chicago"
    with pytest.raises(UnsupportedConstruct) as exc:
        strategy_config_to_vporb(wire)
    assert exc.value.field == "C1"
    assert exc.value.mode == "America/Chicago"


# ── G4 — Class C -> refuse (never a config) ──
def _class_c_template():
    """Minimal template: required trigger (D3) unspecified, no testable claim -> C."""
    fields = {fid: {"value": None, "status": "unspecified",
                    "source_quote": None, "assumption": None} for fid in FIELD_IDS}
    # give it a setup but NO trigger, and no testable claim
    fields["D2"] = {"value": "some setup", "status": "specified",
                    "source_quote": "q", "assumption": None}
    return {"template_version": "1.0",
            "source": {"url": None, "title": None, "channel": None, "transcript_hash": None},
            "fields": fields, "claims": [{"claim": "x", "quote": "y", "testable": False}],
            "consistency_flags": [], "completeness": {"score": 0, "class": "C", "required_missing": []},
            "interpretations": []}


def test_G4_class_C_refused():
    with pytest.raises(UntestableStrategy) as exc:
        map_template(_class_c_template())
    assert exc.value.cls == "C"


# ── G2 — Class B anchor: round-trip equals EventStudyConfig() exactly ──
def test_G2_t0002_roundtrip_equals_eventstudyconfig():
    t = _load("WIT-T-0002.template.json")
    mapped = map_template(t)
    assert mapped["kind"] == "event_study"
    cfg = event_study_config_to_engine(mapped["config"])
    assert cfg == EventStudyConfig()                     # exact frozen-dataclass equality


def test_G2_no_prose_value_needed():
    t = _load("WIT-T-0002.template.json")
    for fid in t["fields"]:
        t["fields"][fid]["value"] = "XXXX prose scrambled XXXX"
    assert event_study_config_to_engine(map_template(t)["config"]) == EventStudyConfig()


def test_class_B_unknown_regime_token_raises():
    t = _load("WIT-T-0002.template.json")
    t["fields"]["J1"]["params"]["regime"]["mode"] = "my_special_regime"
    with pytest.raises(UnsupportedConstruct) as exc:
        map_template(t)
    assert exc.value.field == "J1.regime"
    assert exc.value.mode == "my_special_regime"


def test_class_B_adapter_unmapped_regime_enum_raises():
    """A declared-but-not-mapped regime token ('none') passes the mapper vocab gate but
    has no engine enum -> the adapter refuses, never a silent default."""
    t = _load("WIT-T-0002.template.json")
    t["fields"]["J1"]["params"]["regime"]["mode"] = "none"   # in REGIME_MODES, not in the engine map
    wire = map_template(t)["config"]
    with pytest.raises(UnsupportedConstruct) as exc:
        event_study_config_to_engine(wire)
    assert exc.value.field == "regime"


# ── WIT-P4i — §5 Default Assumption Policy applied in the mapper (deterministic, not model output) ──
def _unspec(mode=None, params=None):
    return {"value": None, "status": "unspecified", "source_quote": None,
            "assumption": None, "mode": mode, "params": params}


def test_P4i_unspecified_E1_defaults_to_one_contract():
    t = _load("WIT-T-0001.template.json")
    t["fields"]["E1"] = _unspec()                       # mode null, params null
    cfg = map_template(t)["config"]
    assert cfg["sizing"] == {"mode": "fixed_contracts", "value": 1}   # §5 default supplied
    assert "E1" in cfg["assumptions_applied"]                          # disclosed as assumed


def test_P4i_specified_E1_is_not_overwritten():
    t = _load("WIT-T-0001.template.json")
    t["fields"]["E1"] = {"value": "5 contracts", "status": "specified", "source_quote": "five",
                         "assumption": None, "mode": "fixed_contracts", "params": {"value": 5}}
    cfg = map_template(t)["config"]
    assert cfg["sizing"] == {"mode": "fixed_contracts", "value": 5}   # source value kept, no default
    assert "E1" not in cfg["assumptions_applied"]                      # specified => not an assumption


def test_P4i_unspecified_costs_default_to_policy():
    t = _load("WIT-T-0001.template.json")
    t["fields"]["H1"] = _unspec()
    t["fields"]["H2"] = _unspec()
    cfg = map_template(t)["config"]
    assert cfg["costs"] == {"commission_per_side": 0.62, "slippage_ticks": 1}
    assert "H1" in cfg["assumptions_applied"] and "H2" in cfg["assumptions_applied"]


def test_P4i_partially_filled_unspecified_H1_keeps_its_value():
    t = _load("WIT-T-0001.template.json")
    # unspecified, but the extractor carried a commission — per-KEY: keep it, do NOT default to 0.62
    t["fields"]["H1"] = _unspec(params={"commission_per_side": 1.5})
    cfg = map_template(t)["config"]
    assert cfg["costs"]["commission_per_side"] == 1.5


def test_P4i_unspecified_F4_F5_default_to_policy():
    t = _load("WIT-T-0001.template.json")
    t["fields"]["F4"] = _unspec()
    t["fields"]["F5"] = _unspec()
    cfg = map_template(t)["config"]
    assert cfg["exits"]["time_exit"] == "force_flat"      # §5 default
    assert cfg["exits"]["same_bar_policy"] == "stop_first"  # §5 default


def test_P4i_null_trigger_raises_not_body_entry():
    t = _load("WIT-T-0001.template.json")
    wire = map_template(t)["config"]
    wire["setup_entry"]["trigger"] = None                # the silent null->body-entry substitution
    with pytest.raises(UnsupportedConstruct) as exc:
        strategy_config_to_vporb(wire)
    assert exc.value.field == "D3"
    assert exc.value.mode is None

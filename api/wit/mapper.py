"""Template -> wire config -> engine config (WIT-03 §3.4; WIT-P3c-2, Class A).

Two layers (per the P3c design):
  1. map_template(template) -> {kind, config, assumptions_applied}
       Reads ONLY each field's mode/params/status — NEVER the prose `value`. Emits the
       portable wire StrategyConfig (contract/strategy-config.v1.json). kind comes from
       the completeness class (never re-derived): A->backtest, B->P3c-3, C->refuse.
  2. strategy_config_to_vporb(wire) -> VPORBConfig
       Engine-internal adapter: wire -> the frozen VPORBConfig the runner consumes.
       Enforces the tz rule (ET only, verbatim — never convert) and the baked-constant
       rule (the runner hardcodes bias/order/sizing/time_exit; a divergent template must
       fail loud). Mode-vocabulary tokens: contract/modes.md (Class A).

This slice is CLASS A ONLY. The Class B path is P3c-3.
"""
from __future__ import annotations

import json
import os

from wit.config import VPORBConfig
from wit.extraction.completeness import score_completeness

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
_STRATEGY_CONFIG_SCHEMA = os.path.join(_REPO, "contract", "strategy-config.v1.json")

# Per-template-field DECLARED mode vocabulary (contract/modes.md, Class A). map_template
# rejects any token not declared for the dimension (UnsupportedConstruct). Tokens that are
# declared-but-not-engine-v1 (e.g. orb_break, market_next_open) pass the vocabulary gate
# here and are caught by the adapter's baked-constant/capability checks.
FIELD_MODE_VOCAB = {
    "B1": {"futures_proxy", "direct"},                     # instrument
    "D1": {"vp_value_area_break", "orb_break", "none"},    # bias
    "D2": {"volume_profile_range", "opening_range"},       # setup
    "D3": {"bar_close_beyond_level", "bar_body_beyond_level"},  # entry trigger
    "D4": {"market_on_close", "market_next_open"},         # order
    "E1": {"fixed_contracts"},                             # sizing
    "F1": {"level_offset", "structure"},                   # stop
    "F2": {"r_multiple", "level", "none"},                 # target
    "F4": {"force_flat", "fixed_time", "none"},            # time exit
    "F5": {"stop_first", "target_first"},                  # same-bar
    "C1": {"rth_window"},                                  # session
}
_ET_TZ = "America/New_York"


class UnsupportedConstruct(Exception):
    """A construct the engine v1 cannot run (WIT-03 §3.7). Fails loud, names the token."""
    def __init__(self, field: str, mode):
        self.field = field
        self.mode = mode
        super().__init__(f"{field}: mode '{mode}' not supported in engine v1")


class UntestableStrategy(Exception):
    """Class C — no runnable config; refuse (never emit a config)."""
    def __init__(self, cls: str):
        self.cls = cls
        super().__init__(f"class {cls}: untestable — no config produced")


def _field(template: dict, fid: str) -> dict:
    f = template.get("fields", {}).get(fid)
    return f if isinstance(f, dict) else {}


def _mode(template: dict, fid: str):
    return _field(template, fid).get("mode")


def _params(template: dict, fid: str) -> dict:
    p = _field(template, fid).get("params")
    return p if isinstance(p, dict) else {}


def _check_mode(template: dict, fid: str):
    """Reject any mode token not declared for the field's dimension (contract/modes.md)."""
    m = _mode(template, fid)
    if m is None:
        return
    if m not in FIELD_MODE_VOCAB.get(fid, set()):
        raise UnsupportedConstruct(field=fid, mode=m)


# ---------------------------------------------------------------------------
# map_template
# ---------------------------------------------------------------------------
def map_template(template: dict) -> dict:
    cls = score_completeness(template)["class"]     # kind from the scorer, never re-derived
    if cls == "C":
        raise UntestableStrategy(cls="C")
    if cls == "B":
        raise NotImplementedError("Class B mapper: P3c-3")
    if cls != "A":
        raise UntestableStrategy(cls=cls)

    # validate every config-relevant field's mode against the vocabulary first
    for fid in ("B1", "C1", "D1", "D2", "D3", "D4", "E1", "F1", "F2", "F4", "F5"):
        _check_mode(template, fid)

    assumptions: list[str] = []

    def assumed(fid: str):
        # a field WIT had to assume (§5 default) = status unspecified; record it
        if _field(template, fid).get("status") == "unspecified":
            assumptions.append(fid)

    d2 = _params(template, "D2")
    c1 = _params(template, "C1")
    b1 = _params(template, "B1")
    f1 = _params(template, "F1")
    f2 = _params(template, "F2")
    h1 = _params(template, "H1")
    h2 = _params(template, "H2")
    window = _params(template, "J1").get("window", {})

    for fid in ("B3", "E1", "F4", "F5", "H1", "H2"):
        assumed(fid)
    assumptions.append("initial_capital")           # lab default; no template source

    config = {
        "config_version": "1.0",
        "instrument": {
            "symbol": b1.get("symbol"), "tick_size": b1.get("tick_size"),
            "tick_value": b1.get("tick_value"), "proxy_for": b1.get("proxy_for"),
        },
        "data": {
            "dataset": "ES_5min_continuous",
            "granularity_needed": d2.get("granularity"),
            "window": {"start": window.get("start"), "end": window.get("end")},
        },
        "session": {
            "tz": c1.get("tz"),
            "trade_window": [c1.get("entry_start"), c1.get("entry_last_bar")],
            "force_flat": "15:55",
        },
        "filters": {"regime": [], "calendar": []},
        "bias": {"mode": _mode(template, "D1"), "params": None},
        "setup_entry": {
            "trigger": _mode(template, "D3"),
            "level": _params(template, "D3").get("level"),
            "order": _mode(template, "D4"),
            "params": {
                "range_start": d2.get("range_start"), "range_end": d2.get("range_end"),
                "value_area_pct": d2.get("value_area_pct"), "granularity": d2.get("granularity"),
            },
        },
        "sizing": {"mode": _mode(template, "E1"), "value": _params(template, "E1").get("value")},
        "exits": {
            "stop": {"mode": _mode(template, "F1"), "ref": f1.get("ref"), "ticks": f1.get("ticks")},
            "target": {"mode": _mode(template, "F2"), "value": f2.get("value")},
            "management": [],
            "time_exit": _mode(template, "F4"),
            "same_bar_policy": _mode(template, "F5"),
        },
        "risk_controls": {"max_trades_per_day": 1, "reentry": "none"},
        "costs": {
            "commission_per_side": h1.get("commission_per_side"),
            "slippage_ticks": h2.get("slippage_ticks"),
        },
        "assumptions_applied": assumptions,
    }
    _structural_hygiene(config)
    return {"kind": "backtest", "config": config, "assumptions_applied": assumptions}


def _structural_hygiene(config: dict) -> None:
    """Light structural check that the emitted wire config has the contract's top-level
    keys (contract/strategy-config.v1.json). Not a full JSON-Schema validation (no dep)."""
    with open(_STRATEGY_CONFIG_SCHEMA) as fh:
        required = json.load(fh)["required"]
    missing = [k for k in required if k not in config]
    if missing:
        raise ValueError(f"emitted StrategyConfig missing required keys: {missing}")


# ---------------------------------------------------------------------------
# adapter: wire StrategyConfig -> VPORBConfig
# ---------------------------------------------------------------------------
def strategy_config_to_vporb(wire: dict) -> VPORBConfig:
    session = wire["session"]
    # TZ RULE (lead-engineer pinned): ET only, mapped VERBATIM. Never convert.
    if session.get("tz") != _ET_TZ:
        raise UnsupportedConstruct(field="C1", mode=session.get("tz"))

    # BAKED-CONSTANT RULE: the runner hardcodes these — a divergent template fails loud.
    if wire["bias"]["mode"] != "vp_value_area_break":
        raise UnsupportedConstruct(field="D1", mode=wire["bias"]["mode"])
    if wire["setup_entry"]["order"] != "market_on_close":
        raise UnsupportedConstruct(field="D4", mode=wire["setup_entry"]["order"])
    if wire["sizing"]["mode"] != "fixed_contracts" or wire["sizing"]["value"] != 1:
        raise UnsupportedConstruct(field="E1",
                                   mode=f'{wire["sizing"]["mode"]}:{wire["sizing"]["value"]}')
    if wire["exits"]["time_exit"] != "force_flat":
        raise UnsupportedConstruct(field="F4", mode=wire["exits"]["time_exit"])

    trigger = wire["setup_entry"]["trigger"]
    entry_mode = "close" if trigger == "bar_close_beyond_level" else "body"
    sp = wire["setup_entry"]["params"]
    tw = session["trade_window"]

    # min_opening_bars/_5min and initial_capital are engine-mechanical / lab defaults
    # (B3 completeness gate; capital) — not portable StrategyConfig fields, so the adapter
    # takes VPORBConfig's own defaults (recorded in assumptions_applied by the mapper).
    return VPORBConfig(
        start_date=wire["data"]["window"]["start"],
        end_date=wire["data"]["window"]["end"],
        range_start=sp["range_start"],
        range_end=sp["range_end"],
        value_area_pct=sp["value_area_pct"],
        vp_granularity=sp["granularity"],
        entry_window_start=tw[0],
        entry_window_last_bar=tw[1],
        entry_mode=entry_mode,
        stop_offset_ticks=wire["exits"]["stop"]["ticks"],
        rr_target=wire["exits"]["target"]["value"],
        same_bar_policy=wire["exits"]["same_bar_policy"],
        commission_per_side=wire["costs"]["commission_per_side"],
        slippage_ticks=wire["costs"]["slippage_ticks"],
    )

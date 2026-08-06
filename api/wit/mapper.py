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
import math
import os

from wit.config import VPORBConfig
from wit.event_study import EventStudyConfig
from wit.extraction.completeness import score_completeness

from wit.data_paths import data_path
from wit.config_validator import validate as _validate_schema

# WIT-P3s: resolved via the shared data-root resolver (env -> repo walk-up -> api/_shipped).
_STRATEGY_CONFIG_SCHEMA = data_path("contract", "strategy-config.v1.json")
_EVENT_STUDY_SCHEMA = data_path("contract", "event-study-config.v1.json")

# Per-template-field DECLARED mode vocabulary (contract/modes.md, Class A). WIT-P4k moved the ONE
# definition to wit.vocab so the extraction schema validator and the mapper share it; re-exported
# here so existing `from wit.mapper import FIELD_MODE_VOCAB` callers are unchanged.
from wit.vocab import FIELD_MODE_VOCAB
_ET_TZ = "America/New_York"


# ---------------------------------------------------------------------------
# WIT-P5n — normalization + disclosure + contract validation at the boundary
# ---------------------------------------------------------------------------
class InvalidConfig(ValueError):
    """A wire config that does not conform to its contract (WIT-P5n Pillar 2). Subclasses
    ValueError so the existing router except-clauses surface it as INVALID_CONFIG with the
    offending field named — never a bare TypeError from downstream engine arithmetic."""
    code = "INVALID_CONFIG"

    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(f"config failed contract validation — {message}")


# Class-A fields the runner BAKES rather than honours (WIT-P5i). A specified value that differs
# from the baked constant is DISCLOSED (notapplied_<path>), never rejected — the run is unaffected,
# but the report must say so. Arrays compare against the empty baked list.
_MISSING = object()
_BAKED_NOT_HONOURED = [
    (("instrument", "symbol"), "ES"),
    (("data", "granularity_needed"), "1min"),
    (("session", "force_flat"), "15:55"),
    (("setup_entry", "level"), "va_high_low"),
    (("exits", "stop", "ref"), "poc"),
    (("exits", "stop", "mode"), "level_offset"),
    (("exits", "target", "mode"), "r_multiple"),
    (("risk_controls", "max_trades_per_day"), 1),
    (("risk_controls", "reentry"), "none"),
    (("filters", "regime"), []),
    (("filters", "calendar"), []),
    (("exits", "management"), []),
]


def _get_path(cfg: dict, path):
    cur = cfg
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return _MISSING
        cur = cur[k]
    return cur


def normalize_and_disclose(config: dict) -> dict:
    """Class-A ONLY. Normalize setup_entry.params.value_area_pct in (1,100] -> /100 (disclosed as
    D2_value_area_normalized), and disclose every declared-but-not-applied field whose specified
    value differs from the baked constant (notapplied_<path>). Idempotent: re-running adds nothing
    (so the mapper and the /wit/v1/runs boundary can both call it). Mutates + returns `config`."""
    codes = config.setdefault("assumptions_applied", [])

    # 3a — value_area_pct is a FRACTION; a percentage in (1,100] is normalized and disclosed.
    params = config.get("setup_entry", {}).get("params")
    if isinstance(params, dict):
        v = params.get("value_area_pct")
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 1 < v <= 100:
            params["value_area_pct"] = v / 100.0
            if "D2_value_area_normalized" not in codes:
                codes.append("D2_value_area_normalized")

    # 3b — a not-honoured field carrying a non-baked value is disclosed, not applied.
    for path, baked in _BAKED_NOT_HONOURED:
        val = _get_path(config, path)
        if val is _MISSING or val == baked:
            continue
        code = "notapplied_" + "_".join(path)
        if code not in codes:
            codes.append(code)
    return config


def validate_wire(config: dict, kind: str) -> None:
    """Validate a wire config against its shipped JSON-Schema contract (WIT-P5n Pillar 2). Raises
    InvalidConfig naming the first offending field. `kind` is 'backtest' or 'event_study'."""
    schema_path = _STRATEGY_CONFIG_SCHEMA if kind == "backtest" else _EVENT_STUDY_SCHEMA
    with open(schema_path) as fh:
        schema = json.load(fh)
    errs = _validate_schema(config, schema)
    if errs:
        field = errs[0].split(":", 1)[0].strip() or None
        raise InvalidConfig(errs[0], field=field)

# Class B (event study) dimension vocabularies (contract/modes.md). The mode tokens live
# INSIDE the carrier field's params (J1.params.event/path_bucket/regime.mode), not on
# field.mode — Class B is WIT-authored, so the whole event-study spec sits under J1.
EVENT_MODES = {"body_vs_trailing_median"}
PATH_MODES = {"path_threshold", "path_percentile"}
REGIME_MODES = {"kaufman_er_trailing_median", "kaufman_er_insample_median",
                "kaufman_er_fixed", "adx_threshold", "none"}
TIMEFRAMES = {"5min", "15min"}
# vocab regime token -> engine EventStudyConfig.regime_mode enum
REGIME_TOKEN_TO_ENGINE = {
    "kaufman_er_trailing_median": "trailing_median",
    "kaufman_er_insample_median": "insample_median",
    "kaufman_er_fixed": "fixed",
    "adx_threshold": "adx",
}
# vocab path token -> engine EventStudyConfig.bucket_mode enum
PATH_TOKEN_TO_BUCKET = {"path_threshold": "threshold", "path_percentile": "percentile"}


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


# WIT-02 §5 Default Assumption Policy (v1), transcribed by field (WIT-P4i). Defaults are
# deterministic policy and belong in CODE, not in the model's output. A default is supplied ONLY
# when BOTH hold: the field's status is "unspecified", AND the specific mode/param key is null or
# absent — applied per KEY, never overwriting a value the source specified or the extractor implied,
# and never on a specified/implied field. D3/D4 get NO default (Class A requires them; a null there
# must fail loudly, not be guessed). B3 is a data-layer disclosure, not a wire value, and is untouched.
_SECTION5_DEFAULTS = {
    "E1": {"mode": "fixed_contracts", "params": {"value": 1}},
    "H1": {"params": {"commission_per_side": 0.62}},
    "H2": {"params": {"slippage_ticks": 1}},
    "F4": {"mode": "force_flat"},
    "F5": {"mode": "stop_first"},
}


def _defaulted_mode(template: dict, fid: str):
    """Effective mode: the source's, or the §5 default IFF the field is unspecified AND mode is
    null/absent. Never overrides a specified/implied mode; a genuinely-null mode with no §5 default
    stays None (a required field with a null mode fails downstream — never silently defaulted)."""
    src = _mode(template, fid)
    if src is not None:
        return src
    d = _SECTION5_DEFAULTS.get(fid, {})
    if "mode" in d and _field(template, fid).get("status") == "unspecified":
        return d["mode"]
    return None


def _defaulted_param(template: dict, fid: str, key: str):
    """Effective param value for `key`: the source's, or the §5 default IFF the field is unspecified
    AND this key is null/absent. Per-key: an unspecified field that already carries this key keeps it."""
    src = _params(template, fid).get(key)
    if src is not None:
        return src
    d = _SECTION5_DEFAULTS.get(fid, {}).get("params", {})
    if key in d and _field(template, fid).get("status") == "unspecified":
        return d[key]
    return None


def _normalize_instrument(b1: dict) -> dict:
    """v1 ALWAYS tests ES with MES economics regardless of what the source traded (WIT-02 §B1;
    WIT-P4j) — the source's own market is disclosed as `proxy_for`, never emitted as the tested
    symbol (a report claiming it tested NQ when it ran ES bars is a false disclosure). tick_value
    is never null. proxy_for = the source's market when it isn't ES (its `proxy_for`, else its
    `symbol` when that names something other than ES); null when the source genuinely traded ES."""
    src_symbol, src_proxy = b1.get("symbol"), b1.get("proxy_for")
    proxy_for = src_proxy or (src_symbol if src_symbol not in (None, "ES") else None)
    return {"symbol": "ES", "tick_size": 0.25, "tick_value": 1.25, "proxy_for": proxy_for}


# The DATA resolutions engine v1 can build a volume profile from. Which one WIT uses is a
# methodological LAB choice (WIT-02 §5), not the source's — the D2 granularity is only advisory.
_VP_GRANULARITIES = ("1min", "5min")


def _profile_granularity(d2: dict) -> tuple[str, bool]:
    """WIT-02 §5: volume-profile features are computed from the finest licensed data; the choice is
    WIT's, not the guru's (WIT-P4l). Honor the template's D2 granularity ONLY when it is one the
    runner supports; for anything else — null, absent, or a category error like 'ticks_per_row_1'
    (that names the profile's PRICE-row size, which the engine FIXES at TICK_SIZE and which this
    function never touches, not a DATA time-resolution) — default to '1min' (finest data) and
    disclose. Returns (granularity, was_defaulted). Not a silent substitution of strategy semantics:
    the price-row size is unchanged; only the disclosed data resolution is defaulted."""
    g = d2.get("granularity")
    if g in _VP_GRANULARITIES:
        return g, False
    return "1min", True


# ---------------------------------------------------------------------------
# map_template
# ---------------------------------------------------------------------------
def map_template(template: dict) -> dict:
    cls = score_completeness(template)["class"]     # kind from the scorer, never re-derived
    if cls == "C":
        raise UntestableStrategy(cls="C")
    if cls == "B":
        return _map_class_b(template)
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
    window = _params(template, "J1").get("window", {})

    # J1 test window is WIT's to fill, never the guru's (WIT-02 §J). When absent, resolve to the
    # FULL available-data range (lead decision WIT-P4j: v1 tests ALL data, not a trailing window)
    # read live from the dataset so it never goes stale — and disclose it as J1_window. A window the
    # template already carries is used verbatim and is NOT disclosed.
    win_start, win_end = window.get("start"), window.get("end")
    window_assumed = win_start is None or win_end is None
    if window_assumed:
        from wit.vp_orb_runner import dataset_date_range
        win_start, win_end = dataset_date_range()

    # WIT-P4l: the profile DATA resolution is a §5 lab choice — honor D2 granularity only if the
    # runner supports it, else default to the finest data ('1min') and disclose. (Price-row size
    # untouched — that is TICK_SIZE, not this field.)
    profile_gran, gran_assumed = _profile_granularity(d2)

    for fid in ("B3", "E1", "F4", "F5", "H1", "H2"):
        assumed(fid)
    assumptions.append("initial_capital")
    if window_assumed:
        assumptions.append("J1_window")           # lab default; no template source
    if gran_assumed:
        assumptions.append("B3_granularity")      # §5 finest-data default; source value not supported

    config = {
        "config_version": "1.0",
        "instrument": _normalize_instrument(b1),      # v1 always ES/MES; source market -> proxy_for
        "data": {
            "dataset": "ES_5min_continuous",
            "granularity_needed": profile_gran,      # §5 lab default (WIT-P4l)
            "window": {"start": win_start, "end": win_end},   # WIT-supplied when absent (WIT-P4j)
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
                "value_area_pct": d2.get("value_area_pct"), "granularity": profile_gran,
            },
        },
        # E1/F4/F5/H1/H2 apply the WIT-02 §5 defaults when unspecified+null (WIT-P4i).
        "sizing": {"mode": _defaulted_mode(template, "E1"),
                   "value": _defaulted_param(template, "E1", "value")},
        "exits": {
            "stop": {"mode": _mode(template, "F1"), "ref": f1.get("ref"), "ticks": f1.get("ticks")},
            "target": {"mode": _mode(template, "F2"), "value": f2.get("value")},
            "management": [],
            "time_exit": _defaulted_mode(template, "F4"),
            "same_bar_policy": _defaulted_mode(template, "F5"),
        },
        "risk_controls": {"max_trades_per_day": 1, "reentry": "none"},
        "costs": {
            "commission_per_side": _defaulted_param(template, "H1", "commission_per_side"),
            "slippage_ticks": _defaulted_param(template, "H2", "slippage_ticks"),
        },
        "assumptions_applied": assumptions,
    }
    _structural_hygiene(config)
    # WIT-P5n: normalize + disclose BEFORE validating, so a source that says "70%" is corrected
    # (not rejected); then refuse anything still non-conforming with a typed InvalidConfig.
    normalize_and_disclose(config)
    validate_wire(config, "backtest")
    return {"kind": "backtest", "config": config,
            "assumptions_applied": config["assumptions_applied"]}


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

    # WIT-P4i: a NULL or unknown trigger must fail loudly — never silently become a body entry
    # (that fabricates a backtest and presents it as real). Only the two declared D3 tokens pass.
    trigger = wire["setup_entry"]["trigger"]
    if trigger == "bar_close_beyond_level":
        entry_mode = "close"
    elif trigger == "bar_body_beyond_level":
        entry_mode = "body"
    else:
        raise UnsupportedConstruct(field="D3", mode=trigger)
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
        dataset=wire["data"]["dataset"],   # WIT-P5o: honoured — unknown ids fail the run, not here
    )


# ---------------------------------------------------------------------------
# Class B — event study (WIT-03 §3.5)
# ---------------------------------------------------------------------------
def _map_class_b(template: dict) -> dict:
    """Build the wire EventStudyConfig from the WIT-authored carrier fields (J1 event/
    path_bucket/regime/outcomes/window; B2 timeframe). Reads ONLY mode/params — never
    prose. Class B is WIT-authored, so §5 defaults rarely apply."""
    j1 = _params(template, "J1")
    event = j1.get("event", {})
    path = j1.get("path_bucket", {})
    regime = j1.get("regime", {})
    outcomes = j1.get("outcomes", {})
    window = j1.get("window", {})
    # timeframe: J1 authoritative; B2 is the guru-source that permits it ("any timeframe").
    timeframe = j1.get("timeframe") or _params(template, "B2").get("timeframe")

    # vocabulary gates (contract/modes.md, Class B) — unknown token fails loud
    if event.get("mode") not in EVENT_MODES:
        raise UnsupportedConstruct(field="J1.event", mode=event.get("mode"))
    if path.get("mode") not in PATH_MODES:
        raise UnsupportedConstruct(field="J1.path_bucket", mode=path.get("mode"))
    if regime.get("mode") not in REGIME_MODES:
        raise UnsupportedConstruct(field="J1.regime", mode=regime.get("mode"))
    if timeframe not in TIMEFRAMES:
        raise UnsupportedConstruct(field="B2", mode=timeframe)

    assumptions: list[str] = []
    for fid in ("J1",):     # J1 is specified (WIT-authored); no §5 default lands. Kept explicit.
        if _field(template, fid).get("status") == "unspecified":
            assumptions.append(fid)

    config = {
        "config_version": "1.0",
        "event": {"mode": event.get("mode"),
                  "params": {"k": event.get("k"), "n_baseline": event.get("n_baseline")}},
        "path_bucket": {"mode": path.get("mode"),
                        "params": {"spike_eff": path.get("spike_eff"),
                                   "spike_giveback_cap": path.get("spike_giveback_cap"),
                                   "pullback_p": path.get("pullback_p"),
                                   "bucket_mode": path.get("bucket_mode")}},
        "regime": {"mode": regime.get("mode"),
                   "params": {"regime_er_m": regime.get("regime_er_m"),
                              "regime_trailing_window": regime.get("regime_trailing_window"),
                              "regime_fixed_er": regime.get("regime_fixed_er"),
                              "regime_adx_len": regime.get("regime_adx_len"),
                              "regime_adx_thresh": regime.get("regime_adx_thresh")}},
        "conditions": ["regime_chop", "regime_trend"],
        "outcomes": {"horizons_bars": outcomes.get("horizons"),
                     "measures": outcomes.get("measures")},
        "timeframe": timeframe,
        "data": {"dataset": "ES_1min_continuous", "granularity_needed": "1min",
                 "window": {"start": window.get("start"), "end": window.get("end")}},
    }
    _event_study_hygiene(config)
    # WIT-P5n Pillar 2: refuse a non-conforming Class-B wire (spike_eff/pullback_p/regime_fixed_er
    # ranges, etc.). No value_area_pct/not-honoured normalization applies to event studies.
    validate_wire(config, "event_study")
    return {"kind": "event_study", "config": config, "assumptions_applied": assumptions}


def _event_study_hygiene(config: dict) -> None:
    with open(_EVENT_STUDY_SCHEMA) as fh:
        required = json.load(fh)["required"]
    missing = [k for k in required if k not in config]
    if missing:
        raise ValueError(f"emitted EventStudyConfig missing required keys: {missing}")


def event_study_config_to_engine(wire: dict) -> EventStudyConfig:
    """Adapter: wire EventStudyConfig -> the frozen engine EventStudyConfig.
    Unknown regime/event/path token -> UnsupportedConstruct; never a silent default."""
    if wire["event"]["mode"] not in EVENT_MODES:
        raise UnsupportedConstruct(field="event", mode=wire["event"]["mode"])
    path_token = wire["path_bucket"]["mode"]
    if path_token not in PATH_TOKEN_TO_BUCKET:
        raise UnsupportedConstruct(field="path_bucket", mode=path_token)
    regime_token = wire["regime"]["mode"]
    if regime_token not in REGIME_TOKEN_TO_ENGINE:
        raise UnsupportedConstruct(field="regime", mode=regime_token)
    if wire["timeframe"] not in TIMEFRAMES:
        raise UnsupportedConstruct(field="timeframe", mode=wire["timeframe"])

    ep = wire["event"]["params"]
    pp = wire["path_bucket"]["params"]
    rp = wire["regime"]["params"]
    win = wire["data"]["window"]
    return EventStudyConfig(
        timeframe=wire["timeframe"],
        k=ep["k"],
        n_baseline=ep["n_baseline"],
        spike_eff=pp["spike_eff"],
        spike_giveback_cap=pp["spike_giveback_cap"],
        pullback_p=pp["pullback_p"],
        bucket_mode=pp["bucket_mode"],
        regime_mode=REGIME_TOKEN_TO_ENGINE[regime_token],
        regime_er_m=rp["regime_er_m"],
        regime_trailing_window=rp["regime_trailing_window"],
        regime_fixed_er=rp["regime_fixed_er"],
        regime_adx_len=rp["regime_adx_len"],
        regime_adx_thresh=rp["regime_adx_thresh"],
        start=win["start"],
        end=win["end"],
    )

"""Load the canonical WIT-02 template schema and validate a template dict.

Dependency decision: **hand-rolled structural validator, zero new deps.**
Rather than add `jsonschema` (which pulls attrs / referencing / rpds-py /
jsonschema-specifications into the ADR-049 full-transitive runtime lock and the
ADR-050 audit surface) for what is simple structural checking, this module
validates the load-bearing rules directly. `schema/strategy-template.v1.json`
remains a valid Draft-2020-12 JSON Schema — the field-id set and the status enum
are read FROM it, so it stays the single source of truth — and any external
consumer (e.g. the Supabase `wit-extract` function) can still run `jsonschema`
against the same file.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

from wit.data_paths import data_path
from wit.vocab import FIELD_MODE_VOCAB   # WIT-P4k: the ONE shared field.mode vocabulary

# WIT-P3s: resolved via the shared data-root resolver (env -> repo walk-up -> api/_shipped) so
# the /api-rooted Railway container finds the schema, not just the dev checkout.
SCHEMA_PATH = data_path("schema", "strategy-template.v1.json")

_STATUS_ENUM = {"specified", "implied", "unspecified"}
_CLASS_ENUM = {"A", "B", "C"}
# Every field object MUST carry these four (WIT-02 §1).
_FIELD_KEYS = {"value", "status", "source_quote", "assumption"}
# Plus OPTIONAL keys: machine-param channel (WIT-P3c-1) mode (string|null) / params
# (object|null), and the evidence declaration (WIT-P3e-5) basis (enum|null). basis is
# OPTIONAL here so the ratified fixtures stay valid WITHOUT it; it is required only of MODEL
# output, enforced by the orchestrator's missing-basis check on REQUIRED fields.
_FIELD_OPTIONAL_KEYS = {"mode", "params", "basis"}
_FIELD_ALLOWED_KEYS = _FIELD_KEYS | _FIELD_OPTIONAL_KEYS
# WIT-P3e-5 evidence bases. narrated_example / tendency_or_claim cannot support a
# specified/implied status — the orchestrator deterministically demotes those.
_BASIS_ENUM = {"stated_rule", "generalized_practice", "narrated_example", "tendency_or_claim"}
# WIT-02 §J: the validation plan (J1/J2) is authored by WIT, not extracted from the
# guru, so a specified J field legitimately has no transcript source_quote. Every
# other section carries the §4.1 quote-for-specified/implied requirement.
_WIT_AUTHORED_SECTIONS = {"J"}


@lru_cache(maxsize=1)
def load_schema() -> dict:
    # Re-resolve at call time (WIT-P3s) so the root is picked up from the current environment;
    # SCHEMA_PATH above resolves at import so a missing root fails the healthcheck loudly.
    with open(data_path("schema", "strategy-template.v1.json")) as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _field_ids() -> tuple[str, ...]:
    """Canonical field id list, read from the schema (single source of truth)."""
    return tuple(load_schema()["properties"]["fields"]["required"])


# Public constant (tuple, order = WIT-02 §2). 27 ids A1..K1.
FIELD_IDS = _field_ids()


def validate_template(template: dict) -> list[str]:
    """Structural validation of a WIT-02 template dict. Returns a list of error
    strings; empty list means valid. Never raises on a malformed template."""
    errs: list[str] = []
    if not isinstance(template, dict):
        return ["template is not an object"]

    top_required = load_schema()["required"]
    for key in top_required:
        if key not in template:
            errs.append(f"missing top-level key: {key}")

    if not isinstance(template.get("template_version"), str):
        errs.append("template_version must be a string")

    # source
    src = template.get("source")
    if not isinstance(src, dict):
        errs.append("source must be an object")
    else:
        for k in ("url", "title", "channel", "transcript_hash"):
            if k not in src:
                errs.append(f"source missing key: {k}")

    # fields — all ids present, each a well-formed field object
    fields = template.get("fields")
    if not isinstance(fields, dict):
        errs.append("fields must be an object")
    else:
        for fid in FIELD_IDS:
            if fid not in fields:
                errs.append(f"fields missing id: {fid}")
                continue
            errs.extend(_validate_field(fid, fields[fid]))
        for extra in set(fields) - set(FIELD_IDS):
            errs.append(f"fields has unknown id: {extra}")

    # claims[]
    claims = template.get("claims")
    if not isinstance(claims, list):
        errs.append("claims must be an array")
    else:
        for i, c in enumerate(claims):
            if not isinstance(c, dict) or not {"claim", "quote", "testable"} <= set(c):
                errs.append(f"claims[{i}] must have claim, quote, testable")
            elif not isinstance(c.get("testable"), bool):
                errs.append(f"claims[{i}].testable must be a boolean")

    # consistency_flags[]
    cf = template.get("consistency_flags")
    if not isinstance(cf, list):
        errs.append("consistency_flags must be an array")
    else:
        for i, f in enumerate(cf):
            if not isinstance(f, dict) or not {"description", "quotes"} <= set(f):
                errs.append(f"consistency_flags[{i}] must have description, quotes")
            elif not isinstance(f.get("quotes"), list):
                errs.append(f"consistency_flags[{i}].quotes must be an array")

    # completeness
    comp = template.get("completeness")
    if not isinstance(comp, dict):
        errs.append("completeness must be an object")
    else:
        if not isinstance(comp.get("score"), int) or isinstance(comp.get("score"), bool):
            errs.append("completeness.score must be an integer")
        if comp.get("class") not in _CLASS_ENUM:
            errs.append("completeness.class must be one of A|B|C")
        if not isinstance(comp.get("required_missing"), list):
            errs.append("completeness.required_missing must be an array")

    # interpretations[]
    interp = template.get("interpretations")
    if not isinstance(interp, list):
        errs.append("interpretations must be an array")
    else:
        for i, it in enumerate(interp):
            if not isinstance(it, dict) or not {"field", "readings"} <= set(it):
                errs.append(f"interpretations[{i}] must have field, readings")
            elif not isinstance(it.get("readings"), list):
                errs.append(f"interpretations[{i}].readings must be an array")

    # WIT-P4k (b)/(c): CLASS-SCOPED machine-channel completeness. For a CLASS A template the field
    # .mode channel IS the config channel, so a CREDITED config-relevant field (status specified /
    # implied) MUST carry a non-null mode — crediting a construct while leaving the machine field
    # empty is incomplete output (the live D1-null bug). An unspecified field may be null (that is
    # the §5 default's job, WIT-P4i). Class B's machine channel lives in J1.params, so its
    # field.modes are legitimately null even when implied — scope by the DETERMINISTIC class, the
    # same class the mapper branches on. Never invents a token: a null just routes to the retry.
    if isinstance(fields, dict):
        from wit.extraction.completeness import score_completeness   # lazy: avoid any import cycle
        try:
            cls = score_completeness(template).get("class")
        except Exception:
            cls = None                       # a malformed template already has structural errors
        if cls == "A":
            for fid in FIELD_MODE_VOCAB:
                f = fields.get(fid)
                if (isinstance(f, dict) and f.get("mode") is None
                        and f.get("status") in ("specified", "implied")):
                    errs.append(f"fields.{fid} is {f.get('status')} but has no mode — a credited "
                                f"config-relevant field must set mode to one of "
                                f"{sorted(FIELD_MODE_VOCAB[fid])} (WIT-P4k)")

    return errs


def _validate_field(fid: str, obj) -> list[str]:
    errs: list[str] = []
    if not isinstance(obj, dict):
        return [f"fields.{fid} must be an object"]
    missing = _FIELD_KEYS - set(obj)
    if missing:
        errs.append(f"fields.{fid} missing keys: {sorted(missing)}")
    extra = set(obj) - _FIELD_ALLOWED_KEYS
    if extra:
        errs.append(f"fields.{fid} has unknown keys: {sorted(extra)}")
    # Optional machine-param keys (WIT-P3c-1): mode string|null, params object|null.
    if "mode" in obj and obj["mode"] is not None and not isinstance(obj["mode"], str):
        errs.append(f"fields.{fid}.mode must be a string or null")
    # WIT-P4k (a): a non-null mode on a config-relevant field MUST be a declared token for that
    # field — an off-vocabulary token is an invalid extraction, caught here (not 3 min later at map).
    if fid in FIELD_MODE_VOCAB and isinstance(obj.get("mode"), str) \
            and obj["mode"] not in FIELD_MODE_VOCAB[fid]:
        errs.append(f"fields.{fid}.mode {obj['mode']!r} is not a declared mode for this field "
                    f"(one of {sorted(FIELD_MODE_VOCAB[fid])}, or null)")
    if "params" in obj and obj["params"] is not None and not isinstance(obj["params"], dict):
        errs.append(f"fields.{fid}.params must be an object or null")
    # WIT-P3e-5: optional evidence declaration; when present (non-null) must be a valid basis.
    if "basis" in obj and obj["basis"] is not None and obj["basis"] not in _BASIS_ENUM:
        errs.append(f"fields.{fid}.basis must be one of {sorted(_BASIS_ENUM)} (got {obj['basis']!r})")
    status = obj.get("status")
    if status not in _STATUS_ENUM:
        errs.append(f"fields.{fid}.status must be one of {sorted(_STATUS_ENUM)} (got {status!r})")
    # WIT-02 §4.1: specified/implied REQUIRE a non-null source_quote — except the
    # WIT-authored validation-plan section (J), which has no transcript to quote.
    if (status in {"specified", "implied"} and not obj.get("source_quote")
            and fid[0] not in _WIT_AUTHORED_SECTIONS):
        errs.append(f"fields.{fid} is {status} but has no source_quote (WIT-02 §4.1)")
    for k in ("source_quote", "assumption"):
        if k in obj and obj[k] is not None and not isinstance(obj[k], str):
            errs.append(f"fields.{fid}.{k} must be a string or null")
    return errs

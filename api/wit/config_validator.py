"""Minimal JSON-Schema-subset validator for WIT wire configs (WIT-P5n, Pillar 2).

WHY A HAND-ROLLED VALIDATOR (not `jsonschema`): the runtime is a FULL LOCK — every direct dep AND
its entire transitive closure is pinned `==`, dev == prod, and CI runs `pip-audit` on every PR
(ADR-048/049/050). Adding `jsonschema` pulls in `attrs`, `referencing`, `jsonschema-specifications`
and the `rpds-py` Rust extension, each of which would have to be pinned and pass the audit gate on a
fresh install — which cannot be confirmed from here, and WIT-P5n forbids adding a dependency without
confirming the gate. This module reads the SAME shipped contract JSON Schema the drift gate protects
and enforces exactly the keywords those contracts use — no more, no less.

Supported keywords: type (incl. "integer"/"number"/"object"/"array"/"string"/"boolean"/"null", or a
list of those), const, enum, required, properties, additionalProperties (false), items, minItems,
maxItems, minimum, maximum, exclusiveMinimum, exclusiveMaximum. Unknown keywords are ignored (they are
descriptive, e.g. `description`, `$comment`), so a not-honoured field left as a permissive `{"type":
"string", "description": "declared but not applied in v1"}` validates by type only — exactly the
WIT-P5n intent (honoured fields are constrained; not-honoured fields are typed and disclosed, never
rejected over a value that does not affect the run).

`validate(instance, schema)` returns a list of human-readable error strings (path + reason); empty
list == valid. It never raises on a bad instance — a caller turns a non-empty list into a typed
INVALID_CONFIG error with the field named.
"""
from __future__ import annotations

import math
from typing import Any


def _is_number(x: Any) -> bool:
    # bool is a subclass of int — a JSON boolean is NOT a number here.
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _is_integer(x: Any) -> bool:
    if isinstance(x, bool):
        return False
    if isinstance(x, int):
        return True
    # JSON has no int/float distinction; accept 2.0 as an integer, reject 2.5.
    return isinstance(x, float) and math.isfinite(x) and x.is_integer()


def _type_ok(value: Any, t: str) -> bool:
    if t == "object":
        return isinstance(value, dict)
    if t == "array":
        return isinstance(value, list)
    if t == "string":
        return isinstance(value, str)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "null":
        return value is None
    if t == "integer":
        return _is_integer(value)
    if t == "number":
        return _is_number(value)
    return True   # unknown type name — do not fail on it


def _check(value: Any, schema: dict, path: str, errs: list) -> None:
    # type
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(value, tt) for tt in types):
            errs.append(f"{path}: expected type {t}, got {type(value).__name__} ({value!r})")
            return   # further keyword checks assume the base type; stop here

    # const / enum
    if "const" in schema and value != schema["const"]:
        errs.append(f"{path}: must equal {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: {value!r} is not one of {schema['enum']}")

    # numeric bounds (guard against bool/non-number)
    if _is_number(value):
        for kw, ok, sym in (
            ("minimum", lambda v, b: v >= b, ">="),
            ("maximum", lambda v, b: v <= b, "<="),
            ("exclusiveMinimum", lambda v, b: v > b, ">"),
            ("exclusiveMaximum", lambda v, b: v < b, "<"),
        ):
            if kw in schema and not (math.isfinite(value) and ok(value, schema[kw])):
                errs.append(f"{path}: {value!r} must be {sym} {schema[kw]}")

    # arrays
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errs.append(f"{path}: needs >= {schema['minItems']} items, got {len(value)}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errs.append(f"{path}: needs <= {schema['maxItems']} items, got {len(value)}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(value):
                _check(item, item_schema, f"{path}[{i}]", errs)

    # objects
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in value:
                errs.append(f"{path}: missing required key {req!r}")
        if schema.get("additionalProperties") is False:
            for k in value:
                if k not in props:
                    errs.append(f"{path}: unexpected key {k!r} (additionalProperties: false)")
        for k, sub in props.items():
            if k in value and isinstance(sub, dict):
                _check(value[k], sub, f"{path}.{k}" if path else k, errs)


def validate(instance: Any, schema: dict) -> list:
    """Return a list of error strings ([] == valid). Never raises on a bad instance."""
    errs: list = []
    _check(instance, schema, "", errs)
    return errs

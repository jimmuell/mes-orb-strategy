"""Deterministic config hash for WIT run idempotency (per the P3c design).

sha256 of the canonical JSON of the WIRE config (sorted keys, compact separators),
so the same config always hashes the same regardless of key order or whitespace,
and stable across engine refactors (the wire config is the portable contract, not
the engine dataclass). The mapper does NOT hash — the router computes this at
submit time (WIT-03 §3.1 idempotency; §3.6 provenance).
"""
from __future__ import annotations

import hashlib
import json


def config_hash(wire_config: dict) -> str:
    canonical = json.dumps(wire_config, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

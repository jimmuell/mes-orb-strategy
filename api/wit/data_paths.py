"""Runtime data-root resolution (WIT-P3s).

The engine reads a handful of repo-root CONFIG files at import/request time —
`schema/strategy-template.v1.json` and `contract/{modes.md,strategy-config.v1.json,
event-study-config.v1.json}`. In the dev checkout these live two directories above
`api/wit/`; but Railway deploys with root directory `/api`, so repo-root files never reach
the container and startup died with `FileNotFoundError: '/schema/strategy-template.v1.json'`
(healthcheck failure on every Phase-3 deploy). This module resolves the data ROOT robustly so
the same code works in the dev checkout AND in the `/api`-rooted container.

Resolution order (first hit wins):
  1. WIT_DATA_ROOT env var, if set and it contains both `schema/` and `contract/`.
  2. The repo root, discovered by walking UP from this module (marker: both `schema/` and
     `contract/` present) — the dev checkout.
  3. `api/_shipped/` — byte-identical copies shipped inside `api/` (drift-gated by a test), so
     the `/api`-rooted container always has them.
On total failure raise FileNotFoundError listing EVERY path searched, so a container debugger
gets the answer in one log line.
"""
from __future__ import annotations

import os

_HERE = os.path.dirname(os.path.abspath(__file__))          # .../api/wit
_API = os.path.dirname(_HERE)                               # .../api
_SHIPPED = os.path.join(_API, "_shipped")                   # .../api/_shipped

# A data root is valid iff it contains BOTH marker directories.
_MARKERS = ("schema", "contract")


def _has_markers(root: str) -> bool:
    return bool(root) and all(os.path.isdir(os.path.join(root, m)) for m in _MARKERS)


def resolve_data_root() -> str:
    """Return the directory that contains `schema/` and `contract/`, per the resolution order.
    NOT cached — the walk is a few isdir() checks, and leaving it live keeps env/layout overrides
    (and tests) honest. Callers that read hot paths already cache their own loads."""
    searched: list[str] = []

    env = os.environ.get("WIT_DATA_ROOT")
    if env:
        searched.append(f"{env} (WIT_DATA_ROOT)")
        if _has_markers(env):
            return env

    d = _HERE
    while True:
        searched.append(f"{d} (walk-up)")
        if _has_markers(d):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent

    searched.append(f"{_SHIPPED} (api/_shipped)")
    if _has_markers(_SHIPPED):
        return _SHIPPED

    raise FileNotFoundError(
        "WIT data root not found (needs a directory containing both 'schema/' and 'contract/'). "
        "Searched, in order: " + " | ".join(searched))


def data_path(*parts: str) -> str:
    """Absolute path to a data file under the resolved root, e.g.
    data_path('schema', 'strategy-template.v1.json')."""
    return os.path.join(resolve_data_root(), *parts)


# ---------------------------------------------------------------------------
# Engine market-data resolution (WIT-P4m)
# ---------------------------------------------------------------------------
# The engine's market-data parquets ship at `api/data/` — the 5-minute bars, and (P4m) the
# derived RTH 1-minute bars. Unlike the repo-ROOT config files P3s had to copy into
# `api/_shipped`, `api/data/` sits INSIDE `api/`, so it is already present in the dev checkout
# AND inside the `/api`-rooted Railway image (as `/app/data`). The "repo walk-up" and "shipped
# copy" tiers therefore coincide at `_API/data` — no separate shipped copy is needed. We still
# honour an env override first, so tests can point the loaders at a temp directory. Crucially,
# NO engine data path is built from the REPO root (`_REPO`) any more — that was the P4m bug:
# `/api`-relative `_REPO` resolves to `/`, and the raw text lived outside `api/` regardless.
_ENGINE_DATA_ENV = "WIT_ENGINE_DATA_DIR"
_ENGINE_DATA_DIR = os.path.join(_API, "data")   # ships in the image AND is the dev location


def resolve_engine_data_dir() -> str:
    """Directory holding the shipped engine market-data parquets. Env override
    (WIT_ENGINE_DATA_DIR, if it exists) wins; otherwise `api/data`. Re-resolved at call time
    so an env override is honoured per-call (tests)."""
    env = os.environ.get(_ENGINE_DATA_ENV)
    if env and os.path.isdir(env):
        return env
    return _ENGINE_DATA_DIR


def engine_data_path(filename: str) -> str:
    """Absolute path to a shipped engine market-data file, e.g.
    engine_data_path('ES_full_1min_rth.parquet')."""
    return os.path.join(resolve_engine_data_dir(), filename)

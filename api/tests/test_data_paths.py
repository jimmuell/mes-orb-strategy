"""WIT-P3s — runtime data-root resolution + shipped-copy drift gate (CI-safe, no network).

Covers the exact production failure: Railway deploys with root /api, so repo-root config files
never reach the container and startup died on FileNotFoundError. The resolver falls back to
api/_shipped; the drift test keeps those copies byte-identical to the repo-root originals.

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_data_paths.py -q
"""
from __future__ import annotations

import os

import pytest

from wit import data_paths

_TESTS = os.path.dirname(os.path.abspath(__file__))   # api/tests
_API = os.path.dirname(_TESTS)                        # api
_REPO = os.path.dirname(_API)                         # repo root
_SHIPPED = os.path.join(_API, "_shipped")

# Every runtime-read repo-root config file that must be shipped (T0 findings).
SHIPPED_FILES = [
    "schema/strategy-template.v1.json",
    "contract/modes.md",
    "contract/strategy-config.v1.json",
    "contract/event-study-config.v1.json",
]


# ── resolution order ──
def test_env_override_wins(tmp_path, monkeypatch):
    (tmp_path / "schema").mkdir()
    (tmp_path / "contract").mkdir()
    monkeypatch.setenv("WIT_DATA_ROOT", str(tmp_path))
    assert data_paths.resolve_data_root() == str(tmp_path)


def test_env_without_markers_is_ignored(tmp_path, monkeypatch):
    # env set but missing schema/+contract/ -> ignored; falls through to the dev-checkout walk-up
    monkeypatch.setenv("WIT_DATA_ROOT", str(tmp_path))
    assert data_paths.resolve_data_root() == _REPO


def test_walkup_finds_repo_root_in_checkout(monkeypatch):
    monkeypatch.delenv("WIT_DATA_ROOT", raising=False)
    assert data_paths.resolve_data_root() == _REPO


def test_shipped_fallback_when_env_and_walkup_absent(tmp_path, monkeypatch):
    # simulate the /api-rooted container: no env, and walk-up starts somewhere with no marker
    # ancestor -> resolution lands on api/_shipped.
    monkeypatch.delenv("WIT_DATA_ROOT", raising=False)
    monkeypatch.setattr(data_paths, "_HERE", str(tmp_path))
    root = data_paths.resolve_data_root()
    assert root == data_paths._SHIPPED
    assert os.path.isdir(os.path.join(root, "schema"))
    assert os.path.isdir(os.path.join(root, "contract"))


def test_total_failure_lists_every_searched_path(tmp_path, monkeypatch):
    monkeypatch.delenv("WIT_DATA_ROOT", raising=False)
    monkeypatch.setattr(data_paths, "_HERE", str(tmp_path))
    monkeypatch.setattr(data_paths, "_SHIPPED", str(tmp_path / "no_shipped_here"))
    with pytest.raises(FileNotFoundError) as ei:
        data_paths.resolve_data_root()
    msg = str(ei.value)
    assert "WIT data root not found" in msg
    assert str(tmp_path) in msg               # the walk-up start is listed
    assert "no_shipped_here" in msg           # the (missing) shipped path is listed


# ── drift gate: shipped copies stay byte-identical to the repo-root originals ──
@pytest.mark.parametrize("rel", SHIPPED_FILES)
def test_shipped_copy_byte_identical(rel):
    with open(os.path.join(_REPO, rel), "rb") as a, open(os.path.join(_SHIPPED, rel), "rb") as b:
        assert a.read() == b.read(), (
            f"api/_shipped/{rel} has DRIFTED from the repo-root original — "
            f"re-copy it (cp {rel} api/_shipped/{rel})")


# ── startup-shaped: the exact prod failure mode, now resolving from api/_shipped ──
def test_startup_reads_resolve_from_shipped(monkeypatch):
    from wit.extraction import schema, prompt
    monkeypatch.setenv("WIT_DATA_ROOT", data_paths._SHIPPED)   # force the container's branch
    for fn in (schema.load_schema, prompt._read_modes, prompt._parse_modes):
        fn.cache_clear()
    try:
        sch = schema.load_schema()
        assert sch["properties"]["fields"]["required"]         # schema loads from _shipped
        p = prompt.build_system_prompt()
        assert "CONFIG-RELEVANT MODE VOCABULARY" in p          # modes.md read from _shipped
    finally:
        # restore caches so the rest of the suite reads via the real (repo-root) resolution
        for fn in (schema.load_schema, prompt._read_modes, prompt._parse_modes):
            fn.cache_clear()

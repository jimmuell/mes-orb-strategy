"""ADR-045 — /profile diagnostic endpoint.

Runs the compare pipeline and returns a per-stage wall-time breakdown, peak RSS, and a
before/after CPU-throttle probe — so the Railway superlinearity can be located with
production numbers. Additive/read-only.
"""
import asyncio

import pandas as pd

import server
from server import profile, BacktestRequest
from engine.engine import __version__ as ENGINE_VERSION

STAGE_KEYS = {"signal_gen+slice", "primary_run", "variants+teaching",
              "validation", "serialize_finalize"}


def _df(monkeypatch):
    rows = []
    for _ in range(8):
        rows += [(100, 101, 99, 100, True, False), (100, 101, 99, 100, False, False),
                 (100, 101, 99, 100, False, True), (101, 102, 100, 101, False, False)]
    idx = pd.date_range("2023-01-02", periods=len(rows), freq="D")
    df = pd.DataFrame({
        "Open": [r[0] for r in rows], "High": [r[1] for r in rows],
        "Low": [r[2] for r in rows], "Close": [r[3] for r in rows],
        "long_entry": [r[4] for r in rows], "long_exit": [r[5] for r in rows],
    }, index=idx)
    monkeypatch.setattr(server, "get_data", lambda: df.copy())


def test_profile_returns_stage_breakdown(monkeypatch):
    _df(monkeypatch)
    r = asyncio.run(profile(BacktestRequest(
        signal_code="pass", direction="long_only", run_validation=False,
        start_date="2023-01-01", end_date="2024-12-31")))
    assert r["status"] == "success"
    assert r["engine_version"] == ENGINE_VERSION
    assert set(r["stages_ms"]) == STAGE_KEYS
    assert r["total_ms"] >= 0
    assert r["peak_rss_mb"] > 0
    # the CPU-throttle probe ran before and after and produced a ratio
    assert r["cpu_probe_before_ms"] > 0 and r["cpu_probe_after_ms"] > 0
    assert r["cpu_throttle_ratio"] is not None
    assert r["trades"] == 8      # primary run's trade count surfaced


def test_profile_route_registered():
    paths = {getattr(rt, "path", "") for rt in server.app.routes}
    assert "/profile" in paths


# --- ADR-046: GC guard ------------------------------------------------------

def test_profile_reports_gc_fields(monkeypatch):
    _df(monkeypatch)
    r = asyncio.run(profile(BacktestRequest(
        signal_code="pass", direction="long_only", run_validation=False,
        start_date="2023-01-01", end_date="2024-12-31"), disable_gc=True))
    assert r["gc_disabled"] is True
    assert r["gc_collections"] == [0, 0, 0]        # gc off -> no collections during the run
    # with gc on, the field is present (counts may be zero for a tiny run)
    r2 = asyncio.run(profile(BacktestRequest(
        signal_code="pass", direction="long_only", run_validation=False,
        start_date="2023-01-01", end_date="2024-12-31"), disable_gc=False))
    assert r2["gc_disabled"] is False
    assert isinstance(r2["gc_collections"], list) and len(r2["gc_collections"]) == 3


def test_run_paths_restore_gc(monkeypatch):
    import gc
    from server import run, run_compare
    _df(monkeypatch)
    assert gc.isenabled()
    req = BacktestRequest(signal_code="pass", direction="long_only", run_validation=False,
                          start_date="2023-01-01", end_date="2024-12-31")
    asyncio.run(run(req))
    assert gc.isenabled()          # /run restored gc
    asyncio.run(run_compare(req))
    assert gc.isenabled()          # /run/compare restored gc

"""ADR-048 — /env reports the running container's Python + package versions (drift visibility)."""
import asyncio
import server
from server import env
from engine.engine import __version__ as ENGINE_VERSION


def test_env_route_registered():
    assert "/env" in {getattr(r, "path", "") for r in server.app.routes}


def test_env_reports_python_and_packages():
    r = asyncio.run(env())
    assert r["engine_version"] == ENGINE_VERSION
    assert r["python"].startswith("3.")
    pk = r["packages"]
    for p in ("pandas", "numpy", "pyarrow", "fastapi", "uvicorn"):
        assert pk.get(p), f"{p} version missing"
    # dev is now pinned to prod's pandas 2.x (ADR-048) — guard the drift that caused the O(n^2)
    assert pk["pandas"].startswith("2."), f"pandas must be 2.x (pinned), got {pk['pandas']}"

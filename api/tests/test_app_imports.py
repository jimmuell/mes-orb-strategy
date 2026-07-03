"""ADR-039: the app must import and /health must answer — this is exactly what
Railway's healthcheck does, and what a green suite failed to catch before."""
from fastapi.testclient import TestClient

import server  # must not raise (forward-ref import crash would fail here)


def test_app_imports_and_exposes_async_route():
    paths = {getattr(r, "path", "") for r in server.app.routes}
    assert "/run/async" in paths
    assert "/health" in paths


def test_health_endpoint_answers():
    client = TestClient(server.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["engine_version"] == "25.15.0"

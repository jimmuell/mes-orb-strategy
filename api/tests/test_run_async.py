"""ADR-037 — async backtest execution (/run/async + Supabase writer).

Exercises the async flow with a FAKE writer — no live Supabase. Asserts:
- /run/async returns 202 quickly with {run_id} and does not block on the backtest;
- 503 when Supabase env vars are unset;
- progress advances; success writes the mapped result + status='complete';
- a forced error writes status='failed' + error_message (never stuck at 'running');
- the exact result->column mapping matches the engine's KPI fields.
"""
import asyncio

import numpy as np
import pandas as pd
import pytest

import server
from server import (AsyncBacktestRequest, _run_async_job, _map_success_columns,
                    _execute_run_sync, BacktestRequest, run_async)
from engine.engine import __version__ as ENGINE_VERSION


class FakeWriter:
    """Records every update_run call; last-write-wins view via .row."""
    def __init__(self, fail_status=None):
        self.calls = []              # list of (run_id, fields) in order
        self.row = {}                # merged latest state
        self._fail_status = fail_status  # raise when a write carries this status

    def update_run(self, run_id, fields):
        if self._fail_status and fields.get("status") == self._fail_status:
            raise RuntimeError("supabase down")
        self.calls.append((run_id, dict(fields)))
        self.row.update(fields)

    def progress_values(self):
        return [f["progress"] for _, f in self.calls if "progress" in f]


def _long_df(n_cycles=6):
    rows = []
    for _ in range(n_cycles):
        rows += [(99, 100, 99, 100, True, False), (100, 101, 99, 100, False, False),
                 (100, 101, 99, 100, False, True), (101, 102, 100, 101, False, False)]
    idx = pd.date_range("2023-01-02", periods=len(rows), freq="D")
    return pd.DataFrame({
        "Open": [r[0] for r in rows], "High": [r[1] for r in rows],
        "Low": [r[2] for r in rows], "Close": [r[3] for r in rows],
        "long_entry": [r[4] for r in rows], "long_exit": [r[5] for r in rows],
    }, index=idx)


@pytest.fixture
def patched_data(monkeypatch):
    monkeypatch.setattr(server, "get_data", lambda: _long_df().copy())


def _req(**kw):
    base = dict(signal_code="pass", direction="long_only", run_validation=False,
                start_date="2023-01-01", end_date="2024-12-31", run_id="row-123")
    base.update(kw)
    return AsyncBacktestRequest(**base)


# --- success path ------------------------------------------------------------

def test_async_success_writes_complete_and_mapped_fields(patched_data):
    w = FakeWriter()
    asyncio.run(_run_async_job(_req(), w))
    assert w.row["status"] == "complete"
    assert w.row["progress"] == 100
    # progress advanced monotonically through phase boundaries
    pv = w.progress_values()
    assert pv[0] == 10 and pv[-1] == 100
    assert pv == sorted(pv) and len(set(pv)) >= 3
    # mapped KPI columns present and typed
    for col in ("net_pnl", "total_trades", "wins", "losses", "win_rate",
                "profit_factor", "max_drawdown", "avg_winner", "avg_loser"):
        assert col in w.row
    assert w.row["total_trades"] == 6
    assert w.row["engine_version"] == ENGINE_VERSION
    assert w.row["signal_hash"] and isinstance(w.row["signal_hash"], str)
    assert isinstance(w.row["results_detail"], dict)
    assert "kpis" in w.row["results_detail"]


def test_mapping_uses_engine_kpi_field_names(patched_data):
    resp = _execute_run_sync(BacktestRequest(**_req().model_dump(exclude={"run_id"})))
    fields = _map_success_columns(resp)
    assert fields["net_pnl"] == resp.kpis["net_profit"]
    assert fields["wins"] == resp.kpis["num_winning"]
    assert fields["losses"] == resp.kpis["num_losing"]
    assert fields["avg_winner"] == resp.kpis["avg_winning"]
    assert fields["avg_loser"] == resp.kpis["avg_losing"]
    assert fields["status"] == "complete" and fields["progress"] == 100


# --- failure path (never stuck at running) -----------------------------------

def test_async_bad_signal_writes_failed(patched_data):
    # signal_code that fails AST validation -> resp.status == 'error' -> row 'failed'
    w = FakeWriter()
    asyncio.run(_run_async_job(_req(signal_code="import os"), w))
    assert w.row["status"] == "failed"
    assert w.row["progress"] == 100
    assert w.row["error_message"]
    assert w.row["status"] != "running"


def test_async_engine_exception_writes_failed(monkeypatch, patched_data):
    # force an exception inside the pipeline -> last-resort guard sets 'failed'
    def boom():
        raise RuntimeError("data blew up")
    monkeypatch.setattr(server, "get_data", boom)
    w = FakeWriter()
    asyncio.run(_run_async_job(_req(), w))
    assert w.row["status"] == "failed"
    assert w.row["progress"] == 100
    assert "data blew up" in w.row["error_message"]


def test_progress_failure_does_not_abort_job(patched_data):
    # if the 'running' progress pings raise, the job still completes to 'complete'
    # (the terminal success write carries status='complete', which is not failed here)
    w = FakeWriter(fail_status="running")
    asyncio.run(_run_async_job(_req(), w))
    assert w.row["status"] == "complete"
    assert w.row["progress"] == 100


# --- endpoint: 202 fast + 503 when unconfigured ------------------------------

def test_endpoint_202_and_does_not_block(monkeypatch, patched_data):
    captured = {}
    monkeypatch.setattr(server, "get_supabase_writer", lambda: FakeWriter())

    class BG:
        def add_task(self, fn, *a, **k):
            captured["task"] = (fn, a)      # queued, NOT awaited here
    resp = asyncio.run(run_async(_req(), BG()))
    assert resp.status_code == 202
    import json
    assert json.loads(bytes(resp.body))["run_id"] == "row-123"
    assert captured["task"][0] is _run_async_job     # the backtest was deferred


def test_endpoint_503_when_supabase_unset(monkeypatch, patched_data):
    monkeypatch.setattr(server, "get_supabase_writer", lambda: None)

    class BG:
        def add_task(self, *a, **k):
            raise AssertionError("must not queue work when unconfigured")
    with pytest.raises(server.HTTPException) as ei:
        asyncio.run(run_async(_req(), BG()))
    assert ei.value.status_code == 503

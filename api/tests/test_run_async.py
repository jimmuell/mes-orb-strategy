"""ADR-037/040 — async backtest execution (/run/async + callback writer).

Exercises the async flow with a FAKE writer — no live callback. Asserts:
- /run/async returns 202 quickly with {run_id} and does not block on the backtest;
- 400 when callback_url/callback_secret are missing (ADR-040);
- progress advances; success writes the mapped result + status='complete';
- a forced error writes status='failed' + error_message (never stuck at 'running');
- the exact result->column mapping matches the engine's KPI fields.
"""
import asyncio

import numpy as np
import pandas as pd
import pytest

import server
from server import (AsyncBacktestRequest, _run_async_job, _map_compare_columns,
                    _execute_compare_sync, BacktestRequest, run_async)
from engine.engine import __version__ as ENGINE_VERSION

TEACHING_DIMS = ["stop", "take_profit", "commission", "direction", "slippage", "position_size"]


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
                start_date="2023-01-01", end_date="2024-12-31", run_id="row-123",
                callback_url="https://test.supabase.co/functions/v1/backtest-callback",
                callback_secret="test")
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


def test_async_keeps_six_teaching_cards(patched_data):
    # the whole point of ADR-037: an async run is a COMPARE run, so
    # results_detail._teaching carries the six blocks in order (not dropped).
    w = FakeWriter()
    asyncio.run(_run_async_job(_req(), w))
    detail = w.row["results_detail"]
    assert "_teaching" in detail, "async run must keep the teaching cards"
    dims = [b["dimension"] for b in detail["_teaching"]]
    assert dims == TEACHING_DIMS
    # same-signal flag under the app's key (ADR-038: leading underscore)
    assert isinstance(detail["_same_signal"], bool)


def _mixed_df():
    # one winner then one LOSER (entry ~100, exit ~90) so max_drawdown (dollars) and
    # max_drawdown_pct (percent) are both non-zero AND different — locks the DD unit.
    rows = [
        (99, 100, 99, 100, True, False),     # signal entry
        (100, 100, 99, 100, False, False),   # entry fills @100
        (100, 101, 99, 100, False, True),    # signal exit
        (101, 102, 100, 101, False, False),  # exit fills @101 -> +1 winner
        (101, 102, 101, 101, True, False),   # signal entry
        (100, 100, 99, 100, False, False),   # entry fills @100
        (95, 95, 90, 92, False, True),       # signal exit (dropped)
        (90, 90, 89, 90, False, False),      # exit fills @90 -> big loss, drawdown
        (90, 91, 90, 90, False, False),      # tail
    ]
    idx = pd.date_range("2023-01-02", periods=len(rows), freq="D")
    return pd.DataFrame({
        "Open": [r[0] for r in rows], "High": [r[1] for r in rows],
        "Low": [r[2] for r in rows], "Close": [r[3] for r in rows],
        "long_entry": [r[4] for r in rows], "long_exit": [r[5] for r in rows],
    }, index=idx)


def test_async_write_matches_sync_shape(monkeypatch):
    # ADR-038: an async row must be byte-identical to what the sync edge function writes.
    monkeypatch.setattr(server, "get_data", lambda: _mixed_df().copy())
    w = FakeWriter()
    asyncio.run(_run_async_job(_req(), w))
    detail = w.row["results_detail"]

    # _teaching: six blocks in order (the app reads detail._teaching)
    assert [b["dimension"] for b in detail["_teaching"]] == TEACHING_DIMS
    # _same_signal present as a bool (leading underscore — the key the app reads)
    assert isinstance(detail["_same_signal"], bool)
    # flattened primary KPIs at top level — Explain-panel fields survive
    assert "net_profit" in detail
    assert "sl_exit_count" in detail
    assert "gross_profit" in detail and "avg_win_loss_ratio" in detail
    # max_drawdown column holds the PERCENT (not the dollar value)
    assert w.row["max_drawdown"] == detail["max_drawdown_pct"]
    # fixture has a real drawdown, so percent != dollars — lock the unit
    assert detail["max_drawdown_pct"] != detail["max_drawdown"]
    assert w.row["max_drawdown"] != detail["max_drawdown"]


def test_mapping_uses_primary_run_kpi_field_names(patched_data):
    # summary columns come from the PRIMARY (user's) run's KPIs (compute_kpis names)
    resp = _execute_compare_sync(BacktestRequest(**_req().model_dump(exclude={"run_id"})))
    k = resp.primary["kpis"]
    fields = _map_compare_columns(resp)
    assert fields["net_pnl"] == k["net_profit"]
    assert fields["wins"] == k["num_winning"]
    assert fields["losses"] == k["num_losing"]
    assert fields["avg_winner"] == k["avg_winning"]
    assert fields["avg_loser"] == k["avg_losing"]
    assert fields["equity_curve"] == resp.primary["equity_curve"]
    assert fields["results_detail"]["_teaching"] == resp.teaching
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


# --- endpoint: 202 fast + 400 when callback missing --------------------------

def test_endpoint_202_and_does_not_block(monkeypatch, patched_data):
    captured = {}
    monkeypatch.setattr(server, "get_callback_writer", lambda *a, **k: FakeWriter())

    class BG:
        def add_task(self, fn, *a, **k):
            captured["task"] = (fn, a)      # queued, NOT awaited here
    resp = asyncio.run(run_async(_req(), BG()))
    assert resp.status_code == 202
    import json
    assert json.loads(bytes(resp.body))["run_id"] == "row-123"
    assert captured["task"][0] is _run_async_job     # the backtest was deferred


def test_endpoint_400_when_callback_missing(patched_data):
    # empty callback_url/secret -> real get_callback_writer returns None -> 400
    class BG:
        def add_task(self, *a, **k):
            raise AssertionError("must not queue work when callback missing")
    with pytest.raises(server.HTTPException) as ei:
        asyncio.run(run_async(_req(callback_url="", callback_secret=""), BG()))
    assert ei.value.status_code == 400


def test_run_async_rejects_ssrf_callback_url(monkeypatch, patched_data):
    # SSRF guard: metadata / private / external / userinfo-bypass hosts -> 400, no POST.
    fake = FakeWriter()
    monkeypatch.setattr(server, "get_callback_writer", lambda *a, **k: fake)

    class BG:
        def add_task(self, *a, **k):
            raise AssertionError("must not schedule work for a disallowed callback_url")

    bad_urls = [
        "http://169.254.169.254/",           # cloud metadata (also http, not https)
        "https://evil.com/",                 # external host
        "http://127.0.0.1/",                 # loopback
        "https://ok.supabase.co@evil.com/",  # userinfo bypass — real host is evil.com
    ]
    for url in bad_urls:
        with pytest.raises(server.HTTPException) as ei:
            asyncio.run(run_async(_req(callback_url=url), BG()))
        assert ei.value.status_code == 400, url
    assert fake.calls == []   # no callback POST attempted for any rejected URL

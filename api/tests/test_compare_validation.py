"""ADR-028 — /run/compare returns the standard Edge-vs-Luck validation for the
PRIMARY result (same field names as /run), gated on run_validation.

Deterministic synthetic fixture (gap-free bars WITH a Volume column, which
_df_to_barset requires) via monkeypatched get_data, mirroring the ADR-026/027 tests.
"""
import asyncio

import pandas as pd

import server
from server import run_compare, BacktestRequest
from engine.engine import __version__ as ENGINE_VERSION


def _cycle(kind):
    # (Open, High, Low, Close, Volume, long_entry, long_exit); entry fills @100
    A = (99, 100, 99, 100, 1000, True, False)
    if kind == "save":
        return [A,
                (100, 101, 99, 99, 1000, False, False),
                (98.5, 99, 90, 91, 1000, False, False),   # primary stops -10; variant rides
                (91, 92, 88, 89, 1000, False, True),
                (91, 92, 90, 91, 1000, False, False)]
    if kind == "cost":
        return [A,
                (100, 101, 99, 99, 1000, False, False),
                (98, 104, 97, 103, 1000, False, False),   # primary stop -10; variant target +20
                (103, 104, 102, 103, 1000, False, False),
                (103, 104, 102, 103, 1000, False, False)]
    raise ValueError(kind)


def _build(kinds):
    rows = []
    for k in kinds:
        rows.extend(_cycle(k))
    idx = pd.date_range("2023-01-02", periods=len(rows), freq="D")
    return pd.DataFrame({
        "Open":  [r[0] for r in rows],
        "High":  [r[1] for r in rows],
        "Low":   [r[2] for r in rows],
        "Close": [r[3] for r in rows],
        "Volume": [r[4] for r in rows],
        "long_entry": [r[5] for r in rows],
        "long_exit":  [r[6] for r in rows],
    }, index=idx)


def _compare(monkeypatch, run_validation):
    df = _build(["save", "cost"] * 5)   # 10 trades — enough to validate
    monkeypatch.setattr(server, "get_data", lambda: df.copy())
    req = BacktestRequest(
        signal_code="pass", direction="long_only", run_validation=run_validation,
        validation_iterations=200,   # small for test speed; finding presence is iteration-independent
        stop_loss_points=2.0, take_profit_points=4.0,
        commission_pct=0.0, slippage_ticks=0, qty_type="fixed", qty_value=1.0,
        start_date="2023-01-01", end_date="2024-12-31",
    )
    resp = asyncio.run(run_compare(req))
    assert resp.status == "success", resp.error
    return resp


def test_version_bumped():
    assert ENGINE_VERSION == "25.21.0"


def test_validation_present_with_edge_vs_luck_when_on(monkeypatch):
    resp = _compare(monkeypatch, run_validation=True)
    assert resp.validation_error is None
    assert isinstance(resp.validation, dict)
    # same shape as /run: overall/summary/findings/skipped/regimes
    assert {"overall", "summary", "findings", "skipped", "regimes"} <= set(resp.validation)
    keys = [f["key"] for f in resp.validation["findings"]]
    assert "edge_vs_luck" in keys


def test_validation_null_when_off(monkeypatch):
    resp = _compare(monkeypatch, run_validation=False)
    assert resp.validation is None
    assert resp.validation_error is None


def test_teaching_unchanged_either_way(monkeypatch):
    on = _compare(monkeypatch, run_validation=True)
    off = _compare(monkeypatch, run_validation=False)
    # teaching / significance / same_signal are independent of validation
    assert on.teaching == off.teaching
    assert on.same_signal is True and off.same_signal is True
    t = on.teaching[0]
    assert "significance" in t and "delta_net" in t

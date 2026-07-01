"""ADR-031 — commission dimension on /run/compare (third teaching block).

`teaching` is a list of per-dimension blocks: stop first, take_profit second,
commission third. Deterministic synthetic fixture via monkeypatched get_data.

Fixture: N closed long round-trips (entry -> long_exit), fixed qty 1, no TP/SL.
In flat mode each closed round-trip costs exactly commission_per_rt, so the
neutralized (fee-free) variant nets exactly N * commission_per_rt more.
"""
import asyncio

import pandas as pd

import server
from server import run_compare, BacktestRequest
from engine.engine import __version__ as ENGINE_VERSION

TOL = 1e-9
N_CYCLES = 6
PER_RT = 1.24


def _cycle():
    # (Open, High, Low, Close, long_entry, long_exit); entry fills next-bar Open,
    # exit fills next-bar Open after the long_exit signal -> one closed round-trip.
    return [
        (99, 100, 99, 100, True, False),   # signal
        (100, 101, 99, 100, False, False), # entry
        (100, 101, 99, 100, False, True),  # exit signal
        (101, 102, 100, 101, False, False),# exit fill -> closed
    ]


def _build(n_cycles):
    rows = []
    for _ in range(n_cycles):
        rows.extend(_cycle())
    idx = pd.date_range("2023-01-02", periods=len(rows), freq="D")
    return pd.DataFrame({
        "Open":  [r[0] for r in rows],
        "High":  [r[1] for r in rows],
        "Low":   [r[2] for r in rows],
        "Close": [r[3] for r in rows],
        "long_entry": [r[4] for r in rows],
        "long_exit":  [r[5] for r in rows],
    }, index=idx)


def _compare(monkeypatch, per_rt=PER_RT, n_cycles=N_CYCLES):
    df = _build(n_cycles)
    monkeypatch.setattr(server, "get_data", lambda: df.copy())
    req = BacktestRequest(
        signal_code="pass", direction="long_only", run_validation=False,
        commission_mode="flat_per_rt", commission_per_rt=per_rt,
        qty_type="fixed", qty_value=1.0,
        start_date="2023-01-01", end_date="2024-12-31",
    )
    resp = asyncio.run(run_compare(req))
    assert resp.status == "success", resp.error
    return resp


def test_version_bumped():
    assert ENGINE_VERSION == "25.6.0"


def test_three_teaching_blocks_in_order(monkeypatch):
    resp = _compare(monkeypatch)
    assert [b["dimension"] for b in resp.teaching] == ["stop", "take_profit", "commission"]
    assert [v["dimension"] for v in resp.variants] == ["stop", "take_profit", "commission"]


def test_stop_and_tp_blocks_unchanged_positions(monkeypatch):
    # regression guard — order of the first two dimensions unchanged.
    resp = _compare(monkeypatch)
    assert resp.teaching[0]["dimension"] == "stop"
    assert resp.teaching[1]["dimension"] == "take_profit"


def test_commission_block_is_cost_with_positive_total(monkeypatch):
    c = _compare(monkeypatch).teaching[2]
    assert c["dimension"] == "commission"
    assert c["direction"] == "cost"
    assert c["total_commission"] > 0
    assert "flips_profitability" in c


def test_total_commission_is_deterministic_flat(monkeypatch):
    c = _compare(monkeypatch).teaching[2]
    # flat mode, all closed round-trips: total == trade_count * commission_per_rt
    assert abs(c["total_commission"] - c["trade_count"] * PER_RT) < 0.01
    assert abs(c["total_commission"] - (N_CYCLES * PER_RT)) < 0.01   # 6 * 1.24 = 7.44


def test_variant_neutralizer_field(monkeypatch):
    v = _compare(monkeypatch).variants[2]
    assert v["dimension"] == "commission"
    assert v["label"] == "no commission"
    assert v["neutralized"] == {"commission_per_rt": 0, "commission_pct": 0}
    assert "result" in v


def test_same_signal_across_four_runs(monkeypatch):
    assert _compare(monkeypatch).same_signal is True


def test_zero_commission_is_neutral(monkeypatch):
    c = _compare(monkeypatch, per_rt=0.0).teaching[2]
    assert c["direction"] == "neutral"
    assert abs(c["total_commission"]) < TOL

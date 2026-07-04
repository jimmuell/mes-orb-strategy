"""ADR-033 — slippage dimension on /run/compare (fifth teaching block).

Clean mirror of the commission block: slippage_ticks modifies every fill, so the
existing _paired_deltas + _delta_significance apply directly. Teaching order:
stop, take_profit, commission, direction, slippage.

Fixture: N closed long round-trips (entry @100, exit @101), fixed qty 1, no TP/SL.
With slippage_ticks=2 (0.5 pt/side) each round-trip's entry fills @100.5 and exit
@100.5 -> +0 vs the +5 without slippage -> $5 removed per trade.
"""
import asyncio

import pandas as pd

import server
from server import run_compare, BacktestRequest
from engine.engine import __version__ as ENGINE_VERSION

TOL = 1e-9
N_CYCLES = 8
TICKS = 2
PER_TRADE_SLIP = 5.0   # 2 ticks * 0.25 pt/side * 2 sides * $5/pt


def _cycle():
    return [
        (99, 100, 99, 100, True, False),
        (100, 101, 99, 100, False, False),
        (100, 101, 99, 100, False, True),
        (101, 102, 100, 101, False, False),
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


def _compare(monkeypatch, ticks=TICKS, n_cycles=N_CYCLES):
    df = _build(n_cycles)
    monkeypatch.setattr(server, "get_data", lambda: df.copy())
    req = BacktestRequest(
        signal_code="pass", direction="long_only", run_validation=False,
        slippage_ticks=ticks, qty_type="fixed", qty_value=1.0,
        start_date="2023-01-01", end_date="2024-12-31",
    )
    resp = asyncio.run(run_compare(req))
    assert resp.status == "success", resp.error
    return resp


def test_version_bumped():
    assert ENGINE_VERSION == "25.17.0"


def test_five_teaching_blocks_in_order(monkeypatch):
    resp = _compare(monkeypatch)
    # stop..slippage in order (ADR-034 appends position_size sixth).
    order = ["stop", "take_profit", "commission", "direction", "slippage"]
    assert [b["dimension"] for b in resp.teaching][:5] == order
    assert [v["dimension"] for v in resp.variants][:5] == order
    assert resp.same_signal is True   # signal survived all runs


def test_slippage_block_cost_and_delta(monkeypatch):
    s = _compare(monkeypatch).teaching[4]
    assert s["dimension"] == "slippage"
    assert s["direction"] == "cost"
    assert s["total_slippage"] > 0
    # delta_net is exactly minus the total slippage removed
    assert abs(s["delta_net"] - (-s["total_slippage"])) < TOL
    # deterministic: 8 round-trips * $5 removed each
    assert abs(s["total_slippage"] - (N_CYCLES * PER_TRADE_SLIP)) < TOL
    assert s["slippage_ticks"] == TICKS
    # paired-delta significance is real here (every trade shifted) — not degenerate empty
    assert s["significance"] == "cost"
    assert s["sufficient_data"] is True
    # full response serializes (ADR-031 _to_native chokepoint covers the new fields)
    _compare(monkeypatch).model_dump_json()


def test_variant_neutralizer_field(monkeypatch):
    v = _compare(monkeypatch).variants[4]
    assert v["dimension"] == "slippage"
    assert v["label"] == "no slippage"
    assert v["neutralized"] == {"slippage_ticks": 0}
    assert "result" in v


def test_zero_slippage_is_neutral(monkeypatch):
    s = _compare(monkeypatch, ticks=0).teaching[4]
    assert s["direction"] == "neutral"
    assert abs(s["total_slippage"]) < TOL
    assert abs(s["delta_net"]) < TOL


def test_prior_blocks_unchanged_positions(monkeypatch):
    # regression guard — the first four dimensions keep their order.
    resp = _compare(monkeypatch)
    assert [b["dimension"] for b in resp.teaching][:4] == ["stop", "take_profit", "commission", "direction"]

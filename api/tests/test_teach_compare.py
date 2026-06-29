"""ADR-026 — /backtest/compare (stop dimension) deterministic tests.

The acceptance anchor (primary worst single-trade loss == -10.00 = 2pt x $5)
requires a CLEAN intrabar stop fill with no gap-through. Real ES data has
overnight gaps (a stop fills at the gapped Open, losing more than the stop
distance), so this uses a hand-crafted, gap-free OHLC fixture via a monkeypatched
get_data(). The conceptual "ORB Pure Price Action, 2020-2025" run is the
post-deploy live check (full data + named strategy), not a unit test.

Fixture: one long trade, 1 contract, stop 2 / target 4 / slippage 0 / commission 0.
  - entry fills at 100.0 (next bar Open after the signal)
  - WITH stop  -> stops at 98.0  -> -2 pt -> -$10.00 (the hard anchor)
  - WITHOUT stop -> rides to target 104.0 -> +4 pt -> +$20.00
Same entry signal both ways; only the exit differs.
"""
import asyncio

import pandas as pd
import pytest

import server
from server import backtest_compare, BacktestRequest
from engine.engine import __version__ as ENGINE_VERSION

# --- golden constants (locked from the first deterministic run) ---
GOLDEN_PRIMARY_WORST = -10.00   # hard anchor: 2pt stop x $5/pt x 1 contract
GOLDEN_VARIANT_WORST = 20.00    # no-stop trade rides to the +4pt target
GOLDEN_PRIMARY_NET = -10.00
GOLDEN_VARIANT_NET = 20.00
GOLDEN_DELTA_NET = GOLDEN_PRIMARY_NET - GOLDEN_VARIANT_NET  # -30.00
TOL = 1e-9


def _fixture_df():
    rows = [
        # O,     H,     L,     C,     long_entry, long_exit
        (99.0,  100.0,  99.0,  100.0, True,  False),  # bar0: signal
        (100.0, 101.0,  99.5,  100.5, False, False),  # bar1: entry fills @100 (TP/SL skipped here)
        (99.5,  101.0,  97.0,  99.0,  False, False),  # bar2: Low 97 <= stop 98 (no gap) -> stop @98
        (102.0, 105.0, 101.0, 103.0,  False, False),  # bar3: High 105 >= target 104 -> no-stop exits @104
        (103.0, 104.0, 102.0, 103.5,  False, False),  # bar4: flat tail
        (103.0, 104.0, 102.0, 103.5,  False, False),  # bar5: flat tail
    ]
    idx = pd.date_range("2023-01-02", periods=len(rows), freq="D")
    return pd.DataFrame({
        "Open":  [r[0] for r in rows],
        "High":  [r[1] for r in rows],
        "Low":   [r[2] for r in rows],
        "Close": [r[3] for r in rows],
        "long_entry": [r[4] for r in rows],
        "long_exit":  [r[5] for r in rows],
    }, index=idx)


def _run_compare(monkeypatch):
    df = _fixture_df()
    monkeypatch.setattr(server, "get_data", lambda: df.copy())
    req = BacktestRequest(
        signal_code="pass",            # columns already present; no-op (AST-valid)
        direction="long_only",
        run_validation=False,
        stop_loss_points=2.0,
        take_profit_points=4.0,
        commission_pct=0.0,
        slippage_ticks=0,
        qty_type="fixed",
        qty_value=1.0,
        start_date="2023-01-01",
        end_date="2023-12-31",
    )
    return asyncio.run(backtest_compare(req))


def test_version_bumped():
    assert ENGINE_VERSION == "25.1.0"


def test_compare_shape_and_anchors(monkeypatch):
    resp = _run_compare(monkeypatch)
    assert resp.status == "success", resp.error

    # shape
    assert resp.primary is not None
    assert isinstance(resp.variants, list) and len(resp.variants) == 1
    assert isinstance(resp.teaching, list) and len(resp.teaching) == 1
    v = resp.variants[0]
    assert v["dimension"] == "stop" and v["label"] == "no stop"
    assert v["neutralized"] == {"stop_loss_points": 0}
    assert "result" in v

    t = resp.teaching[0]
    assert t["dimension"] == "stop"

    # hard anchor: primary worst single-trade loss is exactly -10.00
    assert abs(t["primary_worst_loss"] - GOLDEN_PRIMARY_WORST) < TOL

    # variant worst (no-stop) locked golden
    assert abs(t["variant_worst_loss"] - GOLDEN_VARIANT_WORST) < TOL

    # nets locked golden
    assert abs(resp.primary["kpis"]["net_profit"] - GOLDEN_PRIMARY_NET) < TOL
    assert abs(resp.variants[0]["result"]["kpis"]["net_profit"] - GOLDEN_VARIANT_NET) < TOL


def test_delta_net_and_direction(monkeypatch):
    resp = _run_compare(monkeypatch)
    t = resp.teaching[0]
    primary_net = resp.primary["kpis"]["net_profit"]
    variant_net = resp.variants[0]["result"]["kpis"]["net_profit"]

    # delta is exactly primary.net - variant.net, and matches the locked golden
    assert abs(t["delta_net"] - (primary_net - variant_net)) < TOL
    assert abs(t["delta_net"] - GOLDEN_DELTA_NET) < TOL

    # direction is from the stop's POV: delta < 0 here -> the stop "cost"
    assert t["direction"] == "cost"
    assert t["delta_net"] < 0


def test_same_signal_and_trade_count(monkeypatch):
    resp = _run_compare(monkeypatch)
    t = resp.teaching[0]

    # signal series identical across the two applications
    assert resp.same_signal is True

    # trade_count identical across primary and variant (same entries)
    primary_n = len(resp.primary["trades"])
    variant_n = len(resp.variants[0]["result"]["trades"])
    assert primary_n == variant_n == 1
    assert t["trade_count"] == primary_n

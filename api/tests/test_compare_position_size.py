"""ADR-034 — position-size dimension on /run/compare (sixth & final teaching block).

Teaching order: stop, take_profit, commission, direction, slippage, position_size.
NOT a clean mirror: for fixed sizing the effect is a pure deterministic multiplier
(net AND drawdown scale by the contract count; the edge does not), so there is no
bootstrap significance and neutral is decided by the sizing config, not the delta sign.

Fixture: N closed long round-trips (entry @100, exit @101), no TP/SL.
"""
import asyncio

import pandas as pd

import server
from server import run_compare, BacktestRequest
from engine.engine import __version__ as ENGINE_VERSION

TOL = 1e-6
N_CYCLES = 6


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


def _compare(monkeypatch, qty_type="fixed", qty_value=3.0, n_cycles=N_CYCLES):
    df = _build(n_cycles)
    monkeypatch.setattr(server, "get_data", lambda: df.copy())
    req = BacktestRequest(
        signal_code="pass", direction="long_only", run_validation=False,
        qty_type=qty_type, qty_value=qty_value,
        start_date="2023-01-01", end_date="2024-12-31",
    )
    resp = asyncio.run(run_compare(req))
    assert resp.status == "success", resp.error
    return resp


def test_version_bumped():
    assert ENGINE_VERSION == "25.21.0"


def test_six_teaching_blocks_in_order(monkeypatch):
    resp = _compare(monkeypatch)
    order = ["stop", "take_profit", "commission", "direction", "slippage", "position_size"]
    assert [b["dimension"] for b in resp.teaching] == order
    assert [v["dimension"] for v in resp.variants] == order
    assert resp.same_signal is True   # signal survived all SEVEN runs


def test_fixed_multi_contract_scales_linearly(monkeypatch):
    p = _compare(monkeypatch, "fixed", 3.0).teaching[5]
    assert p["dimension"] == "position_size"
    assert p["qty_type"] == "fixed"
    assert p["contracts"] == 3.0
    assert p["size_multiple"] == 3.0
    assert p["significance"] == "deterministic"     # NOT bootstrapped
    assert p["flips_profitability"] is False
    # net scales linearly with size: primary (3 contracts) == 3 x the 1-contract baseline
    assert abs(p["primary_net"] - 3 * p["variant_net"]) < TOL
    assert abs(p["delta_net"] - (p["primary_net"] - p["variant_net"])) < TOL
    assert p["direction"] == "saved"                # positive net at size > 1
    # the whole point of the card: drawdown ALSO amplifies with size (risk, not edge)
    assert p["primary_max_dd"] is not None and p["variant_max_dd"] is not None
    assert abs(p["primary_max_dd"] - 3 * p["variant_max_dd"]) < TOL
    _compare(monkeypatch, "fixed", 3.0).model_dump_json()   # serializes end-to-end


def test_variant_neutralizer_field(monkeypatch):
    v = _compare(monkeypatch, "fixed", 3.0).variants[5]
    assert v["dimension"] == "position_size"
    assert v["label"] == "1 contract"
    assert v["neutralized"] == {"qty_type": "fixed", "qty_value": 1.0}
    assert "result" in v


def test_fixed_one_contract_is_neutral(monkeypatch):
    p = _compare(monkeypatch, "fixed", 1.0).teaching[5]
    assert p["direction"] == "neutral"      # already the 1-contract baseline
    assert abs(p["delta_net"]) < TOL
    assert p["size_multiple"] == 1.0


def test_non_fixed_is_neutral_v1(monkeypatch):
    p = _compare(monkeypatch, "percent_of_equity", 100.0).teaching[5]
    assert p["direction"] == "neutral"      # v1: %/cash sizing vs 1 fixed contract out of scope
    assert p["qty_type"] == "percent_of_equity"
    assert p["contracts"] is None
    assert p["size_multiple"] is None


def test_prior_five_blocks_unchanged_positions(monkeypatch):
    resp = _compare(monkeypatch)
    assert [b["dimension"] for b in resp.teaching][:5] == \
        ["stop", "take_profit", "commission", "direction", "slippage"]

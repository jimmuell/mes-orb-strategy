"""ADR-031 — commission dimension on /run/compare (third teaching block).

`teaching` is a list of per-dimension blocks: stop first, take_profit second,
commission third. Deterministic synthetic fixture via monkeypatched get_data.

Fixture: N closed long round-trips (entry -> long_exit), fixed qty 1, no TP/SL.
In flat mode each closed round-trip costs exactly commission_per_rt, so the
neutralized (fee-free) variant nets exactly N * commission_per_rt more.
"""
import asyncio

import numpy as np
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
    assert ENGINE_VERSION == "25.18.1"


def test_three_teaching_blocks_in_order(monkeypatch):
    resp = _compare(monkeypatch)
    # stop, take_profit, commission in order (ADR-032 appends direction fourth).
    assert [b["dimension"] for b in resp.teaching][:3] == ["stop", "take_profit", "commission"]
    assert [v["dimension"] for v in resp.variants][:3] == ["stop", "take_profit", "commission"]


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


def test_numpy_types_serialize_at_response_boundary(monkeypatch):
    """ADR-031 hardening regression: the integer-priced fixture yields numpy.int64
    trade prices, numpy.bool_ flips_profitability, and numpy.float64 nets in the
    pre-coercion payload — the class of value that 500'd /run/compare. _to_native
    must coerce them so the FULL response serializes (model_dump_json is what the
    HTTP layer calls — the unit tests that read attributes directly missed this).
    Fails if the _to_native coercion pass is bypassed."""
    resp = _compare(monkeypatch)   # integer OHLC fixture -> numpy-typed values

    # (1) full JSON serialization must not raise (the actual production failure mode)
    resp.model_dump_json()

    # (2) representative coerced fields are native Python types, not numpy scalars
    c = resp.teaching[2]
    assert type(c["flips_profitability"]) is bool
    assert type(c["total_commission"]) is float
    assert type(c["trade_count"]) is int
    price = resp.variants[2]["result"]["trades"][0]["entry_price"]
    assert type(price) is int                      # numpy.int64 -> native int (integer fixture)
    for v in (c["flips_profitability"], c["total_commission"], price):
        assert not isinstance(v, np.generic)

    # (3) coercion changed TYPE not VALUE (flip stays a real bool, price stays 100)
    assert c["flips_profitability"] is False
    assert price == 100


def test_flip_branch_native_bool_and_response_serializes(monkeypatch):
    # ADR-031 regression. FLOAT prices (like real market data) so trade prices
    # serialize as numpy.float64 (a float subclass, OK); the only pre-fix
    # un-serializable value is then the flip flag itself (numpy.bool_ -> 500).
    # High commission: the fee-free variant is profitable but the primary (with
    # fees) is a loss, so the flip branch runs on real numpy engine nets.
    rows = []
    for _ in range(N_CYCLES):
        rows += [
            (99.0, 100.0, 99.0, 100.0, True,  False),
            (100.0, 101.0, 99.0, 100.0, False, False),
            (100.0, 101.0, 99.0, 100.0, False, True),
            (101.0, 102.0, 100.0, 101.0, False, False),
        ]
    idx = pd.date_range("2023-01-02", periods=len(rows), freq="D")
    df = pd.DataFrame({
        "Open":  [r[0] for r in rows], "High": [r[1] for r in rows],
        "Low":   [r[2] for r in rows], "Close": [r[3] for r in rows],
        "long_entry": [r[4] for r in rows], "long_exit": [r[5] for r in rows],
    }, index=idx)
    monkeypatch.setattr(server, "get_data", lambda: df.copy())
    req = BacktestRequest(
        signal_code="pass", direction="long_only", run_validation=False,
        commission_mode="flat_per_rt", commission_per_rt=10.0,
        qty_type="fixed", qty_value=1.0,
        start_date="2023-01-01", end_date="2024-12-31",
    )
    resp = asyncio.run(run_compare(req))
    assert resp.status == "success", resp.error

    c = resp.teaching[2]
    assert c["dimension"] == "commission"
    assert c["flips_profitability"], "fixture must hit the flip branch"
    # Native Python bool, NOT numpy.bool_ (this fails on the pre-ADR-031 engine).
    assert type(c["flips_profitability"]) is bool
    # The assertion the old tests never made: the entire response serializes under
    # real engine types (would raise PydanticSerializationError on numpy.bool_).
    resp.model_dump_json()

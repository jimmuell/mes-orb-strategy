"""ADR-032 — direction dimension on /run/compare (fourth teaching block).

`teaching` order: stop, take_profit, commission, direction. Deterministic synthetic
fixture (all four signal columns) via monkeypatched get_data.

Toggling long_short <-> long_only adds/removes the SHORT trades while the long trades
stay identical, so the delta IS the shorts' signed net. Fixture:
  - long cycle:  long_entry -> long_exit  (entry @100, exit @101 -> +5/contract)
  - short cycle: short_entry -> short_exit (short @100, cover @101 -> -5/contract)
"""
import asyncio

import pandas as pd

import server
from server import run_compare, BacktestRequest
from engine.engine import __version__ as ENGINE_VERSION

TOL = 1e-9
_COLS = ["Open", "High", "Low", "Close",
         "long_entry", "long_exit", "short_entry", "short_exit"]


def _long_cycle():
    return [(99, 100, 99, 100, True, False, False, False),
            (100, 101, 99, 100, False, False, False, False),
            (100, 101, 99, 100, False, True, False, False),
            (101, 102, 100, 101, False, False, False, False)]


def _short_cycle():
    return [(99, 100, 99, 100, False, False, True, False),
            (100, 101, 99, 100, False, False, False, False),
            (100, 101, 99, 100, False, False, False, True),
            (101, 102, 100, 101, False, False, False, False)]


def _build(longs, shorts):
    rows = []
    for _ in range(longs):
        rows.extend(_long_cycle())
    for _ in range(shorts):
        rows.extend(_short_cycle())
    idx = pd.date_range("2023-01-02", periods=len(rows), freq="D")
    return pd.DataFrame({c: [r[i] for r in rows] for i, c in enumerate(_COLS)}, index=idx)


def _compare(monkeypatch, direction, longs, shorts):
    df = _build(longs, shorts)
    monkeypatch.setattr(server, "get_data", lambda: df.copy())
    req = BacktestRequest(
        signal_code="pass", direction=direction, run_validation=False,
        qty_type="fixed", qty_value=1.0,
        start_date="2023-01-01", end_date="2024-12-31",
    )
    resp = asyncio.run(run_compare(req))
    assert resp.status == "success", resp.error
    return resp


def test_version_bumped():
    assert ENGINE_VERSION == "25.23.0"


def test_four_teaching_blocks_in_order(monkeypatch):
    resp = _compare(monkeypatch, "long_short", 3, 6)
    # stop..direction in order (ADR-033 appends slippage fifth).
    assert [b["dimension"] for b in resp.teaching][:4] == ["stop", "take_profit", "commission", "direction"]
    assert [v["dimension"] for v in resp.variants][:4] == ["stop", "take_profit", "commission", "direction"]
    assert resp.same_signal is True   # signal survived all runs


def test_long_short_primary_delta_is_the_shorts(monkeypatch):
    resp = _compare(monkeypatch, "long_short", 3, 6)
    d = resp.teaching[3]
    assert d["dimension"] == "direction"
    assert d["primary_direction"] == "long_short" and d["variant_direction"] == "long_only"
    assert d["short_trade_count"] == 6
    # delta_net IS the shorts' signed net
    assert abs(d["delta_net"] - d["short_net"]) < TOL
    # significance computed from the shorts (NOT _paired_deltas) — non-degenerate here.
    # These shorts lose, so it's a real "cost", not the empty-sample "inconclusive".
    assert d["significance"] == "cost"
    assert d["direction"] == "cost"
    assert d["sufficient_data"] is True   # 6 shorts >= n_windows (5)
    # response serializes end-to-end (ADR-031 _to_native chokepoint covers new fields)
    resp.model_dump_json()


def test_long_only_primary_variant_is_long_short(monkeypatch):
    resp = _compare(monkeypatch, "long_only", 3, 6)
    d = resp.teaching[3]
    assert d["primary_direction"] == "long_only" and d["variant_direction"] == "long_short"
    # delta_net = -(shorts' would-be contribution); shorts lose, so NOT trading them "saved".
    assert abs(d["delta_net"] - (-d["short_net"])) < TOL
    assert d["short_trade_count"] == 6
    assert d["direction"] == "saved"
    assert d["delta_net"] > 0


def test_zero_shorts_edge(monkeypatch):
    # long_short primary but the signal only goes long -> no short trades.
    d = _compare(monkeypatch, "long_short", 5, 0).teaching[3]
    assert d["short_trade_count"] == 0
    assert abs(d["delta_net"]) < TOL
    assert d["direction"] == "neutral"
    assert d["sufficient_data"] is False


def test_stop_tp_commission_blocks_unchanged_positions(monkeypatch):
    # regression guard — the first three dimensions keep their order.
    resp = _compare(monkeypatch, "long_short", 3, 6)
    assert [b["dimension"] for b in resp.teaching][:3] == ["stop", "take_profit", "commission"]

"""ADR-029 — take-profit dimension on /run/compare (second teaching block).

`teaching` is a list of per-dimension blocks: stop first (unchanged), take_profit
second. Deterministic synthetic fixture via monkeypatched get_data.

tp_cost cycle: WITH the take-profit the trade caps at the +4pt target (+$20); WITHOUT
it the winner runs to +$40. So per trade delta = primary(+20) − variant(+40) = -$20
=> the TP "cost" upside.
"""
import asyncio

import pandas as pd

import server
from server import run_compare, BacktestRequest
from engine.engine import __version__ as ENGINE_VERSION

TOL = 1e-9
# Golden values for the 6-trade tp_cost fixture (deterministic).
GOLDEN_TP_DELTA_NET = -120.0       # 6 * (20 - 40)
GOLDEN_TP_PRIMARY_BEST = 20.0      # biggest winner locked in WITH the take-profit
GOLDEN_TP_VARIANT_BEST = 40.0      # what it would've reached WITHOUT the cap


def _tp_cost_cycle():
    # (Open, High, Low, Close, long_entry, long_exit); entry fills @100, target=104
    return [
        (99, 100, 99, 100, True, False),    # signal
        (100, 101, 99, 100, False, False),  # entry @100 (no stop/target)
        (101, 104, 100, 103, False, False), # primary hits target @104 (+20); variant rides
        (105, 106, 104, 105, False, False),
        (106, 110, 105, 108, False, True),  # long_exit -> variant exits next open
        (108, 109, 107, 108, False, False), # variant exits @108 (+40)
        (108, 109, 107, 108, False, False), # filler
    ]


def _build(n_cycles):
    rows = []
    for _ in range(n_cycles):
        rows.extend(_tp_cost_cycle())
    idx = pd.date_range("2023-01-02", periods=len(rows), freq="D")
    return pd.DataFrame({
        "Open":  [r[0] for r in rows],
        "High":  [r[1] for r in rows],
        "Low":   [r[2] for r in rows],
        "Close": [r[3] for r in rows],
        "long_entry": [r[4] for r in rows],
        "long_exit":  [r[5] for r in rows],
    }, index=idx)


def _compare(monkeypatch, n_cycles=6):
    df = _build(n_cycles)
    monkeypatch.setattr(server, "get_data", lambda: df.copy())
    req = BacktestRequest(
        signal_code="pass", direction="long_only", run_validation=False,
        stop_loss_points=2.0, take_profit_points=4.0,
        commission_pct=0.0, slippage_ticks=0, qty_type="fixed", qty_value=1.0,
        start_date="2023-01-01", end_date="2024-12-31",
    )
    resp = asyncio.run(run_compare(req))
    assert resp.status == "success", resp.error
    return resp


def test_version_bumped():
    assert ENGINE_VERSION == "25.4.0"


def test_two_teaching_blocks_in_order(monkeypatch):
    resp = _compare(monkeypatch)
    assert [b["dimension"] for b in resp.teaching] == ["stop", "take_profit"]
    assert [v["dimension"] for v in resp.variants] == ["stop", "take_profit"]
    assert resp.same_signal is True   # signal survived all THREE runs


def test_stop_block_unchanged_shape(monkeypatch):
    # stop block keeps its worst-loss stat and does NOT carry the winner stat.
    stop = _compare(monkeypatch).teaching[0]
    assert stop["dimension"] == "stop"
    assert "primary_worst_loss" in stop and "variant_worst_loss" in stop
    assert "primary_best_win" not in stop and "variant_best_win" not in stop


def test_take_profit_block_winner_stat_and_significance(monkeypatch):
    tp = _compare(monkeypatch).teaching[1]
    assert tp["dimension"] == "take_profit"

    # winner stat (not worst-loss)
    assert "primary_best_win" in tp and "variant_best_win" in tp
    assert "primary_worst_loss" not in tp and "variant_worst_loss" not in tp
    assert abs(tp["primary_best_win"] - GOLDEN_TP_PRIMARY_BEST) < TOL
    assert abs(tp["variant_best_win"] - GOLDEN_TP_VARIANT_BEST) < TOL

    # delta + reused significance verdict (CI entirely < 0 -> the TP "cost" upside)
    assert abs(tp["delta_net"] - GOLDEN_TP_DELTA_NET) < TOL
    assert tp["direction"] == "cost"
    assert tp["significance"] == "cost"
    assert tp["delta_ci_high"] < 0
    assert tp["n_resamples"] == 10_000
    assert tp["sufficient_data"] is True
    assert tp["trade_count"] == 6


def test_variant_neutralizer_field(monkeypatch):
    tp_variant = _compare(monkeypatch).variants[1]
    assert tp_variant["label"] == "no take-profit"
    assert tp_variant["neutralized"] == {"take_profit_points": 0}
    assert "result" in tp_variant

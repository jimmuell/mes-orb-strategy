"""ADR-027 — significance judgment on /run/compare teaching deltas.

Deterministic, known-answer cases via a monkeypatched get_data (gap-free synthetic
bars), mirroring the ADR-026 tests. The CI is the percentile bootstrap from the
single-run validation machinery (run_bootstrap, seed 42, 10k iters), so the golden
CI bounds are reproducible.

5-bar cycle templates (entry fills at bar B Open=100; signal on bar A close):
  - "save": primary stops -$10; variant rides down and exits -$45  -> delta +35
  - "cost": primary stops -$10; variant hits the +4pt target +$20   -> delta -30
"""
import asyncio

import pandas as pd

import server
from server import run_compare, BacktestRequest
from engine.engine import __version__ as ENGINE_VERSION

N_RESAMPLES = 10_000
# Golden CI locked from the first deterministic run of the save+cost x4 fixture.
GOLDEN_INCONC_CI_LOW = -175.0
GOLDEN_INCONC_CI_HIGH = 215.0
TOL = 1e-9


def _cycle(kind):
    A = (99, 100, 99, 100, True, False)          # signal bar
    if kind == "save":
        B = (100, 101, 99, 99, False, False)     # entry @100, no stop/target
        C = (98.5, 99, 90, 91, False, False)     # primary stop @98 (-10); variant rides
        D = (91, 92, 88, 89, False, True)        # variant long_exit -> next-open fill
        E = (91, 92, 90, 91, False, False)       # variant exits @91 -> -45
    elif kind == "cost":
        B = (100, 101, 99, 99, False, False)
        C = (98, 104, 97, 103, False, False)     # primary gap-stop @98 (-10); variant target @104 (+20)
        D = (103, 104, 102, 103, False, False)
        E = (103, 104, 102, 103, False, False)
    else:
        raise ValueError(kind)
    return [A, B, C, D, E]


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
        "long_entry": [r[4] for r in rows],
        "long_exit":  [r[5] for r in rows],
    }, index=idx)


def _teaching(monkeypatch, kinds):
    df = _build(kinds)
    monkeypatch.setattr(server, "get_data", lambda: df.copy())
    req = BacktestRequest(
        signal_code="pass", direction="long_only", run_validation=False,
        stop_loss_points=2.0, take_profit_points=4.0,
        commission_pct=0.0, slippage_ticks=0, qty_type="fixed", qty_value=1.0,
        start_date="2023-01-01", end_date="2024-12-31",
    )
    resp = asyncio.run(run_compare(req))
    assert resp.status == "success", resp.error
    return resp.teaching[0]


def test_version_bumped():
    assert ENGINE_VERSION == "25.22.0"


def test_golden_ci_reproducible_and_inconclusive(monkeypatch):
    # save+cost mix -> deltas straddle 0 -> CI brackets 0 -> "inconclusive".
    t = _teaching(monkeypatch, ["save", "cost"] * 4)

    # locked golden CI (reproducible: seed 42, 10k iters)
    assert abs(t["delta_ci_low"] - GOLDEN_INCONC_CI_LOW) < TOL
    assert abs(t["delta_ci_high"] - GOLDEN_INCONC_CI_HIGH) < TOL
    assert t["n_resamples"] == N_RESAMPLES
    assert t["significance"] == "inconclusive"        # CI straddles 0
    assert t["delta_ci_low"] < 0 < t["delta_ci_high"]

    # raw direction is still the sign of delta_net (net +20 here) — distinct from
    # the judged significance call.
    assert t["delta_net"] > 0 and t["direction"] == "saved"
    assert t["sufficient_data"] is True               # 8 trades >= n_windows (5)


def test_clearly_positive_classifies_saved(monkeypatch):
    # every trade the stop saves money -> all deltas > 0 -> CI entirely > 0.
    t = _teaching(monkeypatch, ["save"] * 8)
    assert t["significance"] == "saved"
    assert t["delta_ci_low"] > 0
    assert t["sufficient_data"] is True


def test_sufficient_data_threshold(monkeypatch):
    # tiny sample (1 trade) -> below the validation's n_windows minimum -> False
    tiny = _teaching(monkeypatch, ["save"])
    assert tiny["trade_count"] == 1
    assert tiny["sufficient_data"] is False

    # enough trades -> True (reuses ValidationConfig().n_windows == 5)
    ample = _teaching(monkeypatch, ["save"] * 6)
    assert ample["trade_count"] == 6
    assert ample["sufficient_data"] is True

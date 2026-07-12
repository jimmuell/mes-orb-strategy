"""ADR-044 — the vectorized simulation loop is result-preserving.

The sim loop's per-bar data access was changed from `df.iloc[i]` / `bar["col"]` (a pandas
Series built every iteration) to native numpy-array indexing (~15x faster). These tests lock
the exact numeric output (a golden snapshot) and the dtype-preservation guarantee that keeps
results byte-identical to the pre-ADR-044 engine.
"""
import numpy as np
import pandas as pd
import pytest

from engine.engine import run_backtest, run_backtest_long_short, BacktestConfig


def _df8():
    idx = pd.date_range("2023-01-03 08:30", periods=8, freq="5min")
    O = [100.0, 100.5, 101.0, 101.5, 102.0, 101.5, 101.0, 100.5]
    return pd.DataFrame({
        "Open": O, "High": [o + 0.5 for o in O], "Low": [o - 0.5 for o in O],
        "Close": [o + 0.25 for o in O],
        "long_entry": [True, False, False, False, True, False, False, False],
        "long_exit":  [False, False, True, False, False, False, True, False],
    }, index=idx)


def _cfg():
    return BacktestConfig(qty_type="fixed", qty_value=2.0, commission_mode="flat_per_rt",
                          commission_per_rt=1.24, start_date="2023-01-01", end_date="2023-12-31")


def test_golden_snapshot():
    k = run_backtest(_df8(), _cfg())
    assert k["total_trades"] == 2
    assert len(k["equity_curve"]) == 8                  # one point per in-range bar
    assert k["net_profit"] == pytest.approx(-2.48, abs=1e-9)
    assert k["max_drawdown"] == pytest.approx(-10.62, abs=1e-9)
    t0 = k["trades"][0]
    assert t0.entry_price == pytest.approx(100.5)       # filled at next bar Open
    assert t0.exit_price == pytest.approx(101.5)
    assert t0.pnl == pytest.approx(8.76, abs=1e-9)


def test_preserves_input_dtype_float32():
    # the parquet ships float32; the engine must stay float32 (native-dtype extraction),
    # matching the pre-ADR-044 object-row behavior — this is what keeps results identical.
    df = _df8()
    for c in ("Open", "High", "Low", "Close"):
        df[c] = df[c].astype(np.float32)
    k = run_backtest(df, _cfg())
    assert isinstance(k["net_profit"], np.float32)


def test_preserves_input_dtype_float64():
    df = _df8()  # python floats -> float64 columns
    k = run_backtest(df, _cfg())
    assert isinstance(k["net_profit"], np.float64)


def test_long_short_runs_and_curves_every_bar():
    df = _df8()
    df["short_entry"] = [False, False, False, True, False, False, False, False]
    df["short_exit"] = [False, False, False, False, False, True, False, False]
    k = run_backtest_long_short(df, _cfg())
    assert len(k["equity_curve"]) == 8
    assert k["total_trades"] >= 1

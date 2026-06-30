"""ADR-030 — flat per-round-trip commission. Deterministic, no network.

Fixture (fixed qty=1 MES, $5/pt, no TP/SL): 2 CLOSED round-trips + 1 OPEN trade.
  - cycle: signal bar -> entry fills next-bar Open -> exit signal -> exit fills next Open
  - trade1: entry @100, exit @101
  - trade2: entry @102, exit @103
  - trade3: entry @104, never exits within the window -> OPEN at end
"""
import pandas as pd

from engine.engine import run_backtest, BacktestConfig

TOL = 1e-9


def _fixture_df():
    rows = [
        # O,    H,    L,    C,    long_entry, long_exit
        (99,  100,  99,  100, True,  False),  # b0 signal
        (100, 101,  99,  100, False, False),  # b1 entry @100
        (100, 101,  99,  100, False, True),   # b2 exit signal
        (101, 102, 100, 101, False, False),   # b3 exit @101  (trade1 closed)
        (101, 102, 101, 102, True,  False),   # b4 signal
        (102, 103, 101, 102, False, False),   # b5 entry @102
        (102, 103, 101, 102, False, True),    # b6 exit signal
        (103, 104, 102, 103, False, False),   # b7 exit @103  (trade2 closed)
        (103, 104, 103, 104, True,  False),   # b8 signal
        (104, 105, 103, 104, False, False),   # b9 entry @104  (trade3 OPEN)
        (104, 105, 103, 104, False, False),   # b10 filler (still open)
        (104, 105, 103, 104, False, False),   # b11 filler (still open)
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


def _cfg(**kw):
    base = dict(start_date="2023-01-01", end_date="2023-12-31",
                qty_type="fixed", qty_value=1.0)
    base.update(kw)
    return BacktestConfig(**base)


def _run(**kw):
    kpis = run_backtest(_fixture_df(), _cfg(**kw))
    trades = kpis["trades"]
    closed = [t for t in trades if t.exit_date is not None]
    open_ = [t for t in trades if t.exit_date is None]
    return kpis, trades, closed, open_


def test_default_mode_is_percent_and_reproduces_existing():
    # default config -> percent mode, byte-identical to the prior commission math.
    cfg = BacktestConfig()
    assert cfg.commission_mode == "percent"
    _, trades, closed, _ = _run()  # commission_pct default 0.1 -> rate 0.001
    t1 = closed[0]                  # entry @100, exit @101, qty 1, $5/pt
    # exact existing percent formula: notional * (commission_pct/100)
    assert abs(t1.entry_commission - (100 * 5 * 1 * 0.001)) < TOL   # 0.5
    assert abs(t1.exit_commission - (101 * 5 * 1 * 0.001)) < TOL    # 0.505


def test_flat_closed_round_trip_charged_exactly_1_24():
    _, _, closed, _ = _run(commission_mode="flat_per_rt", commission_per_rt=1.24)
    assert len(closed) == 2
    for t in closed:
        assert abs(t.entry_commission - 0.62) < TOL
        assert abs(t.exit_commission - 0.62) < TOL
        assert abs((t.entry_commission + t.exit_commission) - 1.24) < TOL


def test_flat_open_trade_charged_exactly_half():
    _, _, _, open_ = _run(commission_mode="flat_per_rt", commission_per_rt=1.24)
    assert len(open_) == 1
    t = open_[0]
    assert abs(t.entry_commission - 0.62) < TOL   # half
    assert abs(t.exit_commission - 0.0) < TOL      # never charged exit
    assert (t.entry_commission + t.exit_commission) < 1.24   # never the full round-trip


def test_flat_zero_charges_no_commission():
    # commission_per_rt = 0.0 -> the future commission-neutralized variant
    _, trades, _, _ = _run(commission_mode="flat_per_rt", commission_per_rt=0.0)
    for t in trades:
        assert abs(t.entry_commission - 0.0) < TOL
        assert abs(t.exit_commission - 0.0) < TOL


def test_flat_multi_trade_total_to_the_cent():
    kpis, trades, closed, open_ = _run(commission_mode="flat_per_rt", commission_per_rt=1.24)
    # total over ALL trades = closed_round_trips * 1.24 + open_trades * 0.62
    total_all = sum(t.entry_commission + t.exit_commission for t in trades)
    expected = len(closed) * 1.24 + len(open_) * 0.62
    assert abs(total_all - expected) < TOL
    assert abs(total_all - (2 * 1.24 + 1 * 0.62)) < TOL          # 3.10
    # the total_commission KPI counts CLOSED trades only
    assert abs(kpis["total_commission"] - (2 * 1.24)) < TOL      # 2.48


def test_mode_switch_changes_pnl_not_trades():
    _, pct_trades, pct_closed, _ = _run()  # percent
    _, flat_trades, flat_closed, _ = _run(commission_mode="flat_per_rt", commission_per_rt=1.24)

    # same trades: identical entry/exit dates and prices (commission is downstream of signals)
    def shape(ts):
        return [(t.entry_date, t.entry_price, t.exit_date, t.exit_price) for t in ts]
    assert shape(pct_trades) == shape(flat_trades)

    # but net pnl differs (different commission)
    pct_net = sum(t.pnl for t in pct_closed)
    flat_net = sum(t.pnl for t in flat_closed)
    assert abs(pct_net - flat_net) > TOL

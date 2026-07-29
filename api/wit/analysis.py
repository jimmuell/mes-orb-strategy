"""WIT-0001 analysis + report-data builder.

Reuses the existing `backtester` validation stack (validate / summarize /
run_bootstrap) — NO new statistics are implemented here; this module only maps
engine trades into the validator's inputs and tabulates the outputs, exactly as
api/server.py already does. Produces:

  - the run matrix (primary, full-history, four §J2 sweeps),
  - bootstrap CIs (seed 42, 10k), edge-vs-luck verdict, per-year table,
  - time-in-market stats (tests the "under 90 minutes/day" claim),
  - the per-trade CSV for the primary run,
  - the equity-curve PNG.

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m wit.analysis
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from backtester import validate, summarize, ValidationConfig
from backtester.ingest.models import Trade as BtTrade
from backtester.ingest.firstrate import BarSet
from backtester.instruments import Instrument
from backtester.montecarlo.bootstrap import run_bootstrap

from wit.config import VPORBConfig, POINT_VALUE
from wit import vp_orb_runner as R

_ENGINE_INSTRUMENT = Instrument(symbol="MES", point_value=POINT_VALUE, tick_size=0.25)
_ET = "America/New_York"
_VC = ValidationConfig()   # seed 42, mc_iterations 10_000, ci_level 0.95

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
REPORTS = os.path.join(_REPO, "docs", "wit", "reports")
REPORTS_DATA = os.path.join(REPORTS, "data")


# ---------------------------------------------------------------------------
# backtester bridge (mirrors api/server.py _df_to_barset / BtTrade mapping)
# ---------------------------------------------------------------------------
def _to_et(ts: pd.Timestamp) -> dt.datetime:
    ts = pd.Timestamp(ts)
    return (ts.tz_localize(_ET) if ts.tz is None else ts.tz_convert(_ET)).to_pydatetime()


def _df_to_barset(df: pd.DataFrame) -> BarSet:
    out = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    out.columns = ["open", "high", "low", "close", "volume"]
    idx = pd.DatetimeIndex(out.index)
    idx = idx.tz_localize(_ET).tz_convert("UTC") if idx.tz is None else idx.tz_convert("UTC")
    idx.name = "timestamp"
    out.index = idx
    out = out.astype(float)
    return BarSet(symbol="ES", timeframe="5min", adjustment="unadjusted", df=out)


def _bt_trades(trades) -> list[BtTrade]:
    bt = []
    tid = 1
    for t in trades:
        if t.exit_date is None or t.exit_price is None:
            continue
        bt.append(BtTrade(
            trade_id=tid, direction=t.direction,
            entry_time=_to_et(t.entry_date), entry_price=float(t.entry_price),
            exit_time=_to_et(t.exit_date), exit_price=float(t.exit_price),
            qty=int(round(t.entry_qty)), pnl=float(t.pnl),
        ))
        tid += 1
    return bt


def _closed(trades):
    return [t for t in trades if t.exit_date is not None and t.exit_price is not None]


# ---------------------------------------------------------------------------
# statistics (all from the backtester stack; nothing new computed here)
# ---------------------------------------------------------------------------
def bootstrap_cis(trades) -> dict:
    bt = _bt_trades(trades)
    if len(bt) < 2:
        return {}
    res = run_bootstrap(bt, n_iterations=_VC.mc_iterations, seed=_VC.seed,
                        ci_level=_VC.bootstrap_ci_level)
    return {
        "iterations": res.n_iterations, "seed": res.seed, "ci_level": res.ci_level,
        "net_profit": [res.net_profit_point, list(res.net_profit_ci)],
        "expectancy": [res.expectancy_point, list(res.expectancy_ci)],
        "profit_factor": [res.profit_factor_point, list(res.profit_factor_ci)],
        "win_rate": [res.win_rate_point, list(res.win_rate_ci)],
    }


def edge_vs_luck(trades, df: pd.DataFrame) -> dict:
    bt = _bt_trades(trades)
    if len(bt) < 2:
        return {"overall": "inconclusive", "summary": "fewer than 2 trades"}
    cfg = ValidationConfig(mc_iterations=_VC.mc_iterations,
                           random_entry_iterations=_VC.mc_iterations,
                           instrument=_ENGINE_INSTRUMENT)
    result = validate(bt, bars=_df_to_barset(df), config=cfg)
    v = summarize(result)
    findings = [{"key": f.key, "title": f.title, "status": f.status,
                 "headline": f.headline, "stat": f.stat} for f in v.findings]
    return {"overall": v.overall, "summary": v.summary, "findings": findings,
            "skipped": getattr(result, "skipped", None)}


def per_year_table(trades) -> list[dict]:
    rows = defaultdict(lambda: {"trades": 0, "wins": 0, "net": 0.0})
    for t in _closed(trades):
        y = pd.Timestamp(t.entry_date).year
        rows[y]["trades"] += 1
        rows[y]["wins"] += 1 if t.pnl > 0 else 0
        rows[y]["net"] += t.pnl
    out = []
    for y in sorted(rows):
        r = rows[y]
        out.append({"year": y, "trades": r["trades"],
                    "win_rate": 100 * r["wins"] / r["trades"] if r["trades"] else 0.0,
                    "net_pnl": r["net"]})
    return out


def time_in_market(plans) -> dict:
    """Holding time per trade (entry-bar start -> exit-bar start, minutes).

    max 1 trade/day, so per-trade == per-trading-day. Entry fills at the entry
    bar's close and exit lands within the exit bar, so true holding is within
    ±5 min of this bar-start-to-bar-start measure (the 5-min bar granularity).
    """
    mins = [ (pd.Timestamp(p.exit_bar) - pd.Timestamp(p.entry_bar)).total_seconds() / 60.0
             for p in plans ]
    if not mins:
        return {}
    a = np.array(mins)
    return {"n": len(a), "mean_min": float(a.mean()), "median_min": float(np.median(a)),
            "p90_min": float(np.percentile(a, 90)), "max_min": float(a.max())}


def headline(kpis: dict) -> dict:
    return {k: kpis.get(k) for k in
            ("total_trades", "net_profit", "profit_factor", "max_drawdown",
             "max_drawdown_pct", "win_rate", "avg_trade")}


# ---------------------------------------------------------------------------
# CSV + PNG
# ---------------------------------------------------------------------------
def export_trades_csv(trades, plans, path: str):
    plan_by_entry = {pd.Timestamp(p.entry_bar): p for p in plans}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["entry_time", "exit_time", "direction", "entry_price", "exit_price",
                    "qty", "pnl", "poc", "vah", "val", "sl_price", "tp_price", "exit_reason",
                    "hold_minutes"])
        for t in _closed(trades):
            p = plan_by_entry.get(pd.Timestamp(t.entry_date))
            hold = (pd.Timestamp(t.exit_date) - pd.Timestamp(t.entry_date)).total_seconds() / 60.0
            w.writerow([t.entry_date, t.exit_date, t.direction,
                        f"{t.entry_price:.2f}", f"{t.exit_price:.2f}", int(round(t.entry_qty)),
                        f"{t.pnl:.2f}",
                        f"{p.poc:.2f}" if p else "", f"{p.vah:.2f}" if p else "",
                        f"{p.val:.2f}" if p else "", f"{p.sl_price:.2f}" if p else "",
                        f"{p.tp_price:.2f}" if p else "", p.exit_reason if p else "",
                        f"{hold:.0f}"])


def equity_png(kpis: dict, path: str, title: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    curve = kpis.get("equity_curve", [])
    if not curve:
        return
    dates = [pd.Timestamp(p["date"]) for p in curve]
    eq = [p["equity"] for p in curve]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(dates, eq, lw=1.2, color="#1f4e79")
    ax.axhline(kpis.get("initial_capital", eq[0]), color="#999", lw=0.8, ls="--")
    ax.set_title(title)
    ax.set_ylabel("Equity ($, 1 MES)")
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------------------
# run matrix
# ---------------------------------------------------------------------------
def _summ(res) -> dict:
    k = res.kpis
    d = headline(k)
    d["exit_reasons"] = dict(Counter(p.exit_reason for p in res.plans))
    d["directions"] = dict(Counter(p.direction for p in res.plans))
    d["days_with_trade"] = len(res.plans)
    return d


def build_all() -> dict:
    primary = VPORBConfig()
    print("[1/7] loading data...", flush=True)
    five = R.load_5min(primary.start_date, primary.end_date)
    one = R.load_1min_opening(primary.start_date, primary.end_date,
                              primary.range_start, primary.range_end)

    print("[2/7] primary run...", flush=True)
    res_primary = R.run_vp_orb(primary, five=five, one_min_open=one)

    out = {"generated_window": [primary.start_date, primary.end_date]}
    out["primary"] = _summ(res_primary)
    out["primary"]["bootstrap"] = bootstrap_cis(res_primary.trades)
    out["primary"]["edge_vs_luck"] = edge_vs_luck(res_primary.trades, res_primary.df)
    out["primary"]["per_year"] = per_year_table(res_primary.trades)
    out["primary"]["time_in_market"] = time_in_market(res_primary.plans)

    export_trades_csv(res_primary.trades, res_primary.plans,
                      os.path.join(REPORTS_DATA, "WIT-0001-primary-trades.csv"))
    equity_png(res_primary.kpis, os.path.join(REPORTS, "WIT-0001-equity-curve.png"),
               "VP-ORB — equity curve, 1 MES (primary: 2016-04-11 → 2026-04-09)")

    print("[3/7] full-history run...", flush=True)
    full_cfg = primary.with_(start_date="2008-01-01", end_date="2026-04-09")
    res_full = R.run_vp_orb(full_cfg)
    out["full_history"] = _summ(res_full)
    out["full_history"]["bootstrap"] = bootstrap_cis(res_full.trades)
    out["full_history"]["per_year"] = per_year_table(res_full.trades)

    # sweeps on the primary window (reuse loaded 5-min; 1-min reused where applicable)
    sweeps = {
        "entry_body": primary.with_(entry_mode="body"),
        "slippage_0": primary.with_(slippage_ticks=0),
        "slippage_2": primary.with_(slippage_ticks=2),
        "target_first": primary.with_(same_bar_policy="target_first"),
        "vp_5min": primary.with_(vp_granularity="5min"),
    }
    out["sweeps"] = {}
    for i, (name, scfg) in enumerate(sweeps.items(), start=4):
        print(f"[{i}/7] sweep {name}...", flush=True)
        om = one if scfg.vp_granularity == "1min" else None
        r = R.run_vp_orb(scfg, five=five, one_min_open=om)
        s = headline(r.kpis)
        s["days_with_trade"] = len(r.plans)
        s["edge_vs_luck"] = edge_vs_luck(r.trades, r.df)["overall"]
        out["sweeps"][name] = s

    # provenance
    import engine
    out["provenance"] = {
        "engine_version": engine.__version__,
        "dataset": os.path.basename(R.PARQUET_5MIN),
        "vp_source": os.path.basename(R.PARQUET_1MIN),
        "seed": _VC.seed, "bootstrap_iters": _VC.mc_iterations,
        "commission_per_side": primary.commission_per_side,
        "slippage_ticks": primary.slippage_ticks, "point_value": POINT_VALUE,
        "initial_capital": primary.initial_capital,
    }
    os.makedirs(REPORTS_DATA, exist_ok=True)
    with open(os.path.join(REPORTS_DATA, "WIT-0001-results.json"), "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print("done ->", os.path.join(REPORTS_DATA, "WIT-0001-results.json"))
    return out


if __name__ == "__main__":
    r = build_all()
    print(json.dumps(r, indent=2, default=str))

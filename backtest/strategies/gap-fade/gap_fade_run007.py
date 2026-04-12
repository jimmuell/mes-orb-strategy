"""
Phase 2 Run 007 — Realized Vol Regime Filter (FINAL optimization run)
======================================================================

Adds a 5-day realized-vol regime filter on top of Run 006 Variant C.
Targets the 2021 weakness (post-COVID compressed-vol meme-stock regime
where gaps tended to continue rather than fade).

5-day RV = rolling 5-day standard deviation of daily percent returns,
shifted by 1 day (no look-ahead). Units: percent.

Ablation (5 variants):
  A: RV filter OFF              — Run 006 C baseline
  B: 0.4 ≤ RV ≤ 1.8             — proposed filter
  C: 0.3 ≤ RV ≤ 2.0             — looser bounds
  D: 0.5 ≤ RV ≤ 1.5             — tighter bounds
  E: best RV variant + stop cap — SL = min(gap extreme + 1 tick, 0.15% of entry)

Everything else inherited from Run 006 Variant C:
- 0.32-0.55% gap band
- R:R 1.75 fixed TP
- SMA200 off, news-day filter off
- ADX < 20, ATR% 0.3-2.0 on
- Phase 1 ORB block on
- 9:35-11:00 ET entry window
- Session-close flatten 15:55
- Max 1 trade/day, 1 MES

HARD STOP RULE: this is the final optimization run for Phase 2. If no
variant achieves full-dataset PF ≥ 1.5, Senior Claude ships Run 006
Variant C as the Phase 2 candidate and we proceed to Pine Script
conversion. No Run 008.

REVISED Phase 2 targets (April 2026):
- Win Rate ≥ 50% (revised from 65%)
- Profit Factor ≥ 1.5
- Max Drawdown ≤ 15%
- Walk-forward validated
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gap_fade import (  # noqa: E402
    run_backtest, phase1_signal_days, load_es_data, DATA_FILE,
    compute_metrics, filter_trades, print_metrics, print_yearly,
    exit_breakdown, print_ablation,
)


TIGHT_MIN = 0.32
TIGHT_MAX = 0.55
RR        = 1.75
STOP_CAP  = 0.0015   # 0.15% of entry
YEARS_SPAN = 18


def compute_realized_vol(df: pd.DataFrame, period: int = 5) -> pd.Series:
    """5-day rolling stdev of daily percent returns on RTH closes,
    shifted by 1 day (no look-ahead). Returns a Series indexed by date."""
    rth = df[((df.index.hour == 9) & (df.index.minute >= 30))
             | ((df.index.hour >= 10) & (df.index.hour < 16))]
    daily_close = rth["Close"].groupby(rth.index.date).last()
    daily_close.index = pd.to_datetime(daily_close.index)
    daily_ret = daily_close.pct_change() * 100.0         # daily return in %
    rv = daily_ret.rolling(period, min_periods=period).std().shift(1)
    rv.name = "rv5"
    return rv


def print_2021_callout(trades_by_variant: dict) -> None:
    print("\n" + "=" * 72)
    print("2021 CALLOUT — did the RV filter shave the meme-stock year?")
    print("=" * 72)
    print(f"{'Variant':<32}{'Trades':>10}{'WR':>10}{'PF':>10}{'Net $':>12}")
    print("-" * 72)
    for label, trs in trades_by_variant.items():
        y2021 = [t for t in trs if t.day.year == 2021]
        if not y2021:
            print(f"{label:<32}{'0':>10}{'—':>10}{'—':>10}{'—':>12}")
            continue
        m = compute_metrics(y2021)
        pf = f"{m.profit_factor:.2f}" if m.profit_factor != float("inf") else "inf"
        print(f"{label:<32}{m.trades:>10}{m.win_rate:>9.1f}%{pf:>10}"
              f"{m.net_profit:>12,.0f}")
    print("=" * 72)


def main() -> None:
    print(f"Loading 5-min data: {DATA_FILE}")
    df = load_es_data(DATA_FILE)
    print(f"  Bars: {len(df):,}  Range: {df.index.min()} – {df.index.max()}")

    print("\nComputing Phase 1 ORB signal days...")
    p1_days = phase1_signal_days(df)
    print(f"  Phase 1 signal days: {len(p1_days)}")

    print("\nComputing 5-day realized vol...")
    rv = compute_realized_vol(df, period=5)
    print(f"  RV series: {rv.notna().sum()} valid days "
          f"(range {rv.min():.3f} – {rv.max():.3f}, median {rv.median():.3f})")

    common_kw = dict(
        min_gap_pct=TIGHT_MIN, max_gap_pct=TIGHT_MAX,
        use_sma_filter=False, target_mode="rr", rr=RR,
        phase1_days=p1_days,
    )

    variants = []
    all_trades = {}

    # A: no RV filter
    label = "A: baseline (no RV filter)"
    all_trades[label] = run_backtest(df, **common_kw)
    variants.append(label)

    # B: 0.4-1.8
    label = "B: RV 0.4-1.8 (proposed)"
    all_trades[label] = run_backtest(df, rv_series=rv, min_rv=0.4, max_rv=1.8,
                                     **common_kw)
    variants.append(label)

    # C: 0.3-2.0
    label = "C: RV 0.3-2.0 (looser)"
    all_trades[label] = run_backtest(df, rv_series=rv, min_rv=0.3, max_rv=2.0,
                                     **common_kw)
    variants.append(label)

    # D: 0.5-1.5
    label = "D: RV 0.5-1.5 (tighter)"
    all_trades[label] = run_backtest(df, rv_series=rv, min_rv=0.5, max_rv=1.5,
                                     **common_kw)
    variants.append(label)

    for label in variants:
        print(f"  {label:<32}: {len(all_trades[label])} trades")

    # Pick best of B/C/D by PF
    def score(label):
        mm = compute_metrics(all_trades[label])
        return (mm.profit_factor, mm.net_profit)
    best_rv = max([v for v in variants if v.startswith(("B:", "C:", "D:"))],
                  key=score)
    m_best_rv = compute_metrics(all_trades[best_rv])
    print(f"\n  Best RV variant: {best_rv}  (PF {m_best_rv.profit_factor:.3f})")

    # E: best RV variant + stop cap
    # Extract the min/max from the best label
    parts = best_rv.split("RV ")[1].split(" ")[0]
    rv_lo, rv_hi = [float(x) for x in parts.split("-")]
    e_label = f"E: {best_rv[3:].split(' ')[0]} + stop cap 0.15%"
    all_trades[e_label] = run_backtest(
        df, rv_series=rv, min_rv=rv_lo, max_rv=rv_hi,
        stop_cap_pct=STOP_CAP, **common_kw,
    )
    variants.append(e_label)
    print(f"  {e_label:<40}: {len(all_trades[e_label])} trades")

    rows = [(label, compute_metrics(all_trades[label]), YEARS_SPAN)
            for label in variants]
    print_ablation(rows)

    # Exit breakdowns
    print("\n── Exit breakdown (all variants) ──")
    for label in variants:
        print(f"\n  {label}")
        exit_breakdown(all_trades[label])

    # 2021 callout
    print_2021_callout(all_trades)

    # Best overall
    best_label = max(variants, key=score)
    best_trades = all_trades[best_label]
    best_m = compute_metrics(best_trades)
    print(f"\n>>> Best variant overall: {best_label}")
    print_metrics("Best variant — full dataset", best_m)
    print_yearly(best_trades)

    # Walk-forward
    is_tr  = filter_trades(best_trades, "2008-01-01", "2019-12-31")
    oos_tr = filter_trades(best_trades, "2020-01-01", "2026-12-31")
    is_m  = compute_metrics(is_tr)
    oos_m = compute_metrics(oos_tr)
    print_metrics("In-sample 2008-2019",    is_m)
    print_metrics("Out-of-sample 2020-2026", oos_m)

    # Run 006 C vs Run 007 best
    r006c = dict(trades=327, wr=47.1, pf=1.385, net=1946,
                 aw=45.44, al=-29.20, dd_pct=5.28)
    print("\n" + "=" * 78)
    print("RUN 006 Variant C  vs  RUN 007 best")
    print("=" * 78)
    rows_cmp = [
        ("Trades",        r006c["trades"],          best_m.trades),
        ("Win rate",      f"{r006c['wr']:.1f}%",    f"{best_m.win_rate:.1f}%"),
        ("Profit factor", f"{r006c['pf']:.3f}",     f"{best_m.profit_factor:.3f}"),
        ("Net profit",    f"${r006c['net']:,.0f}",  f"${best_m.net_profit:,.0f}"),
        ("Avg win",       f"${r006c['aw']:.2f}",    f"${best_m.avg_win:.2f}"),
        ("Avg loss",      f"${r006c['al']:.2f}",    f"${best_m.avg_loss:.2f}"),
        ("Max DD %",      f"{r006c['dd_pct']:.2f}%", f"{best_m.max_drawdown_pct:.2f}%"),
    ]
    print(f"{'Metric':<16}{'Run 006 C':>20}{'Run 007 best':>20}")
    print("-" * 56)
    for r in rows_cmp:
        print(f"{r[0]:<16}{str(r[1]):>20}{str(r[2]):>20}")
    print("=" * 78)

    # Revised Phase 2 targets check
    print("\n── Gap to REVISED Phase 2 targets (best variant) ──")
    def fmt(ok): return "✅" if ok else "❌"
    wr_ok = best_m.win_rate >= 50
    pf_ok = best_m.profit_factor >= 1.5
    dd_ok = best_m.max_drawdown_pct <= 15
    print(f"  Win rate:      {best_m.win_rate:.1f}%  (target ≥50%) {fmt(wr_ok)}")
    print(f"  Profit factor: {best_m.profit_factor:.3f} (target ≥1.5) {fmt(pf_ok)}")
    print(f"  Max drawdown:  {best_m.max_drawdown_pct:.2f}% (target ≤15%) {fmt(dd_ok)}")

    # Pine Script candidate check — ALL variants against revised targets
    print("\n── Pine Script candidate check (revised targets) ──")
    candidates = []
    for label in variants:
        mm = compute_metrics(all_trades[label])
        if (mm.win_rate >= 50 and mm.profit_factor >= 1.5
                and mm.max_drawdown_pct <= 15):
            # Also require walk-forward: both IS and OOS profitable
            trs = all_trades[label]
            ism  = compute_metrics(filter_trades(trs, "2008-01-01", "2019-12-31"))
            oosm = compute_metrics(filter_trades(trs, "2020-01-01", "2026-12-31"))
            wf_ok = ism.net_profit > 0 and oosm.net_profit > 0
            candidates.append((label, mm, ism, oosm, wf_ok))

    if candidates:
        print("  🟢 PINE SCRIPT CANDIDATE(S) found:")
        for label, mm, ism, oosm, wf_ok in candidates:
            wf = "✅" if wf_ok else "❌"
            print(f"    • {label}")
            print(f"         Full: WR {mm.win_rate:.1f}%  PF {mm.profit_factor:.3f}  DD {mm.max_drawdown_pct:.2f}%")
            print(f"         IS:   PF {ism.profit_factor:.3f}  Net ${ism.net_profit:,.0f}")
            print(f"         OOS:  PF {oosm.profit_factor:.3f}  Net ${oosm.net_profit:,.0f}  WF {wf}")
    else:
        print("  No variant meets all 3 revised targets on the full dataset.")

    # Hard stop verdict
    print("\n" + "=" * 78)
    print("HARD STOP VERDICT — Phase 2 Run 007 Final")
    print("=" * 78)
    full_pf_crossed = any(
        compute_metrics(all_trades[v]).profit_factor >= 1.5 for v in variants)
    if full_pf_crossed:
        winners = [v for v in variants
                   if compute_metrics(all_trades[v]).profit_factor >= 1.5]
        print(f"  ✅ FULL-DATASET PF ≥ 1.5 ACHIEVED by: {', '.join(winners)}")
        print("  Proceed to Pine Script conversion.")
    else:
        best_full_pf = max(compute_metrics(all_trades[v]).profit_factor
                           for v in variants)
        print(f"  ❌ No variant achieved full-dataset PF ≥ 1.5.")
        print(f"     Best full PF across all Run 007 variants: {best_full_pf:.3f}")
        print("     Hard stop rule triggers: accept Run 006 Variant C as the")
        print("     Phase 2 ship candidate and proceed to Pine Script conversion.")
        print("     Run 006 C: PF 1.385 full, 1.521 IS, 1.299 OOS, DD 5.28%, 14/19 yrs profitable.")
    print("=" * 78)


if __name__ == "__main__":
    main()

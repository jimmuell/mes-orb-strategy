"""
Phase 2 Run 006 — Gap Band Refinement + R:R Sweep
===================================================

Starts from Run 005 Variant F (0.30-0.80%, SMA off, R:R 1.5) and makes
two changes:

1. Tighten the gap band to 0.32-0.55% per the Run 005 decile diagnostic.
   Deciles 1, 8, 10 were negative/flat; deciles 2-7 (0.32-0.55%) were
   profitable.

2. Sweep R:R ∈ {1.25, 1.50, 1.75, 2.00} around the Run 005 optimum.

Plus one entry-window variant (E): tight band, best R:R of A-D, window
restricted to 9:35-10:00 ET (first 25 minutes only).

Everything else inherited from Variant F:
- SMA200 filter: off (permanently dropped)
- News-day filter: off (permanently dropped)
- ADX < 20, ATR% 0.3-2.0, Phase 1 ORB block: on
- SL = gap extreme + 1 tick; session-close flatten
- 5-min bars, 1 MES, max 1 trade/day
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gap_fade import (  # noqa: E402
    run_backtest, phase1_signal_days, load_es_data, DATA_FILE,
    compute_metrics, filter_trades, print_metrics, print_yearly,
    exit_breakdown, gap_decile_diagnostic, print_ablation,
)


TIGHT_MIN = 0.32
TIGHT_MAX = 0.55
RR_GRID = [1.25, 1.50, 1.75, 2.00]
YEARS_SPAN = 18


def main() -> None:
    print(f"Loading 5-min data: {DATA_FILE}")
    df = load_es_data(DATA_FILE)
    print(f"  Bars: {len(df):,}  Range: {df.index.min()} – {df.index.max()}")

    print("\nComputing Phase 1 ORB signal days (block list)...")
    p1_days = phase1_signal_days(df)
    print(f"  Phase 1 signal days: {len(p1_days)}")

    # Variants A-D: 4-point R:R sweep on the tight band, standard window
    variants = []
    all_trades = {}
    for label_letter, rr in zip("ABCD", RR_GRID):
        label = f"{label_letter}: 0.32-0.55%, R:R {rr:.2f}, 9:35-11:00"
        trs = run_backtest(
            df,
            min_gap_pct=TIGHT_MIN, max_gap_pct=TIGHT_MAX,
            use_sma_filter=False, target_mode="rr", rr=rr,
            phase1_days=p1_days,
        )
        all_trades[label] = trs
        variants.append(label)
        print(f"  {label:<42}: {len(trs)} trades")

    # Find best of A-D by PF (tiebreak net)
    def score(label):
        mm = compute_metrics(all_trades[label])
        return (mm.profit_factor, mm.net_profit)
    best_ad = max(variants, key=score)
    best_ad_rr = float(best_ad.split("R:R ")[1].split(",")[0])
    print(f"\n  Best of A-D: {best_ad}  (R:R {best_ad_rr:.2f})")

    # Variant E: same but 9:35-10:00 ET window only
    e_label = f"E: 0.32-0.55%, R:R {best_ad_rr:.2f}, 9:35-10:00 only"
    e_trades = run_backtest(
        df,
        min_gap_pct=TIGHT_MIN, max_gap_pct=TIGHT_MAX,
        use_sma_filter=False, target_mode="rr", rr=best_ad_rr,
        phase1_days=p1_days,
        entry_window_start=(9, 35),
        entry_window_end=(10, 0),
    )
    all_trades[e_label] = e_trades
    variants.append(e_label)
    print(f"  {e_label:<42}: {len(e_trades)} trades")

    rows = [(label, compute_metrics(all_trades[label]), YEARS_SPAN)
            for label in variants]
    print_ablation(rows)

    # Exit breakdowns
    print("\n── Exit breakdown (all variants) ──")
    for label in variants:
        print(f"\n  {label}")
        exit_breakdown(all_trades[label])

    # Best overall
    best_label = max(variants, key=score)
    best_trades = all_trades[best_label]
    best_m = compute_metrics(best_trades)
    print(f"\n>>> Best variant (overall): {best_label}")
    print_metrics("Best variant — full dataset", best_m)
    print_yearly(best_trades)

    # Walk-forward on best
    is_tr  = filter_trades(best_trades, "2008-01-01", "2019-12-31")
    oos_tr = filter_trades(best_trades, "2020-01-01", "2026-12-31")
    is_m = compute_metrics(is_tr)
    oos_m = compute_metrics(oos_tr)
    print_metrics("In-sample 2008-2019",    is_m)
    print_metrics("Out-of-sample 2020-2026", oos_m)

    # Decile diagnostic on best variant (for continued tuning visibility)
    print("\n── Gap-size decile diagnostic (best variant) ──")
    gap_decile_diagnostic(best_trades)

    # Run 005 F vs Run 006 best
    r005_f = dict(trades=528, wr=45.3, pf=1.130, net=1085.90,
                  aw=39.51, al=-28.92, dd_pct=8.34)
    print("\n" + "=" * 78)
    print("RUN 005 Variant F  vs  RUN 006 best")
    print("=" * 78)
    rows_cmp = [
        ("Trades",        r005_f["trades"],   best_m.trades),
        ("Win rate",      f"{r005_f['wr']:.1f}%",  f"{best_m.win_rate:.1f}%"),
        ("Profit factor", f"{r005_f['pf']:.3f}",   f"{best_m.profit_factor:.3f}"),
        ("Net profit",    f"${r005_f['net']:,.0f}", f"${best_m.net_profit:,.0f}"),
        ("Avg win",       f"${r005_f['aw']:.2f}",  f"${best_m.avg_win:.2f}"),
        ("Avg loss",      f"${r005_f['al']:.2f}",  f"${best_m.avg_loss:.2f}"),
        ("Max DD %",      f"{r005_f['dd_pct']:.2f}%", f"{best_m.max_drawdown_pct:.2f}%"),
    ]
    print(f"{'Metric':<16}{'Run 005 F':>20}{'Run 006 best':>20}")
    print("-" * 56)
    for r in rows_cmp:
        print(f"{r[0]:<16}{str(r[1]):>20}{str(r[2]):>20}")
    print("=" * 78)

    # Gap to Phase 2 targets
    print("\n── Gap to Phase 2 targets (best variant) ──")
    def fmt(ok): return "✅" if ok else "❌"
    wr_ok = best_m.win_rate >= 65
    pf_ok = best_m.profit_factor >= 1.5
    dd_ok = best_m.max_drawdown_pct <= 15
    print(f"  Win rate:      {best_m.win_rate:.1f}%  (target ≥65%) {fmt(wr_ok)}")
    print(f"  Profit factor: {best_m.profit_factor:.3f} (target ≥1.5) {fmt(pf_ok)}")
    print(f"  Max drawdown:  {best_m.max_drawdown_pct:.2f}% (target ≤15%) {fmt(dd_ok)}")

    # Pine Script candidate flag — any variant meeting all three targets
    print("\n── Pine Script candidate check ──")
    candidates = []
    for label in variants:
        mm = compute_metrics(all_trades[label])
        if (mm.win_rate >= 65 and mm.profit_factor >= 1.5
                and mm.max_drawdown_pct <= 15):
            candidates.append((label, mm))
    if candidates:
        print("  🟢 PINE SCRIPT CANDIDATE(S) — variants meeting all 3 targets:")
        for label, mm in candidates:
            print(f"    • {label}: WR {mm.win_rate:.1f}%, "
                  f"PF {mm.profit_factor:.3f}, DD {mm.max_drawdown_pct:.2f}%")
    else:
        print("  No variant meets all three Phase 2 targets yet.")
        print("  Best variant gap analysis:")
        gaps = []
        if not wr_ok: gaps.append(f"WR {best_m.win_rate:.1f}% vs 65% target")
        if not pf_ok: gaps.append(f"PF {best_m.profit_factor:.3f} vs 1.5 target")
        if not dd_ok: gaps.append(f"DD {best_m.max_drawdown_pct:.2f}% vs 15% target")
        for g in gaps:
            print(f"    • {g}")


if __name__ == "__main__":
    main()

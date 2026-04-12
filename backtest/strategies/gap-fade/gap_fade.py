"""
Phase 2 Run 005 — Gap Fade Baseline
====================================

First test of the gap-fade paradigm after four VWAP deviation runs
(Runs 001-004) produced zero profitable configurations. See
STRATEGY.md for the full specification.

Implements the gap-fade setup exactly as specified:
- 5-min bars, RTH only (9:30-15:55 ET data convention)
- Gap = (rth_open - prior_rth_close) / prior_rth_close
- Entry window: 9:35-11:00 ET
- Long on gap-down when a bar closes back above rth_open; short on
  gap-up when a bar closes back below rth_open; fill at next bar open
- Target: PDC touch (primary) OR fixed R:R 1.5 off the SL distance
- Stop: gap extreme (9:30 ORB high/low) + 1 tick buffer
- Regime gates: ADX<20 (daily, prior), ATR% 0.3-2.0 (daily, prior),
  optional 200-day SMA
- Phase 1 ORB exclusion: any day where Phase 1 ORB produces a
  confirmed entry signal blocks gap fade for that day
- Max 1 trade/day, session-close flatten at 15:55 ET
- SL fills before TP on same-bar double-breach (pessimistic)

Ablation (7 variants):
  A: 0.20-0.60%, SMA on,  PDC target
  B: 0.20-0.60%, SMA off, PDC target
  C: 0.30-0.80%, SMA on,  PDC target
  D: 0.30-0.80%, SMA off, PDC target
  E: 0.20-0.60%, SMA off, R:R 1.5
  F: 0.30-0.80%, SMA off, R:R 1.5
  G: same gap band as better of A/B, SMA off, PDC, news days excluded
     (news approx = first trading day of each month + third Wed of
     every other month)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# Make Phase 1 helpers + Run 001 shared utilities importable
STRATEGIES_DIR = Path(__file__).resolve().parents[1]
BACKTEST_DIR   = STRATEGIES_DIR.parent
REPO_ROOT      = BACKTEST_DIR.parent
sys.path.insert(0, str(BACKTEST_DIR))
sys.path.insert(0, str(STRATEGIES_DIR))

# Phase 1 signal generator + daily filter helpers (for Phase 1 ORB block)
from strategies.mes_orb_strategy import (  # noqa: E402
    load_es_data, mes_orb_signals,
    compute_regime_sma, compute_prior_day_hl, compute_atr_vol, compute_adx,
)

# Phase 2 shared utilities from Run 001 (compute_daily_filters, metrics)
sys.path.insert(0, str(STRATEGIES_DIR / "vwap-scalp"))
from vwap_scalp import (  # noqa: E402
    compute_daily_filters, compute_metrics, filter_trades, Metrics,
    print_metrics, print_yearly,
)


# ── Constants ─────────────────────────────────────────────────────────────
POINT_VALUE        = 5.0      # 1 MES
COMMISSION         = 0.62     # per side
TICK               = 0.25
ONE_TICK_BUFFER    = TICK     # SL buffer = 1 tick

ENTRY_WINDOW_START = (9, 35)  # inclusive
ENTRY_WINDOW_END   = (11, 0)  # inclusive
SESSION_END        = (15, 55)

DATA_FILE = REPO_ROOT / "data" / "raw" / "ES_full_5min_continuous_UNadjusted.txt"


# ── Trade record ──────────────────────────────────────────────────────────
@dataclass
class Trade:
    entry_time:  pd.Timestamp
    exit_time:   pd.Timestamp
    direction:   str           # "long" / "short"
    entry_price: float
    exit_price:  float
    exit_reason: str           # "tp_pdc" / "tp_rr" / "sl" / "session_close"
    pnl:         float
    day:         pd.Timestamp
    gap_pct:     float
    pdc:         float
    orb_hi:      float
    orb_lo:      float


# ── Phase 1 ORB signal day set (for blocking) ─────────────────────────────
def phase1_signal_days(df: pd.DataFrame) -> set:
    """Run Phase 1 final config signal generator and return the set of
    calendar dates on which a confirmed long or short entry fires.
    Matches Run 014 parameters exactly."""
    regime_sma = compute_regime_sma(df)
    pdh, pdl, pdc = compute_prior_day_hl(df)
    atr_vol = compute_atr_vol(df, period=10)
    adx_arr = compute_adx(df)

    df_sig = mes_orb_signals(
        df.copy(),
        rr_ratio=0.75, sl_frac=0.5, retest_ticks=2,
        min_orb_pct=0.3, max_orb_pct=1.0,
        regime_sma=regime_sma,
        prior_day_high=pdh, prior_day_low=pdl, prior_day_close=pdc,
        bias_mode="close",
        atr_vol_pct=atr_vol, min_atr_pct=0.3, max_atr_pct=2.0,
        adx_values=adx_arr, min_adx=15,
        use_breakout_quality=True,
    )
    fired = df_sig["long_entry"] | df_sig["short_entry"]
    dates = pd.to_datetime(df_sig.index[fired].date)
    return set(dates)


# ── News-day approximation (Variant G) ────────────────────────────────────
def is_news_day(day: pd.Timestamp, trading_days: list[pd.Timestamp]) -> bool:
    """First trading day of the month (NFP approximation) OR third Wed
    of every other month (FOMC approximation)."""
    # First trading day of month: this day's month differs from the prior trading day's month
    idx = trading_days.index(day)
    if idx == 0 or trading_days[idx - 1].month != day.month:
        return True
    # Third Wednesday of every other (even-numbered) month
    if day.weekday() == 2 and day.month % 2 == 0:
        # Is this the 3rd Wed of the month?
        wed_count = sum(1 for d in trading_days
                        if d.year == day.year and d.month == day.month
                        and d.weekday() == 2 and d <= day)
        if wed_count == 3:
            return True
    return False


# ── Core backtest ─────────────────────────────────────────────────────────
def run_backtest(df: pd.DataFrame,
                 min_gap_pct: float,
                 max_gap_pct: float,
                 use_sma_filter: bool,
                 target_mode: str,           # "pdc" or "rr"
                 rr: float = 1.5,
                 use_adx_filter: bool = True,
                 max_adx: float = 20.0,
                 min_atr_pct: float = 0.3,
                 max_atr_pct: float = 2.0,
                 block_phase1: bool = True,
                 exclude_news: bool = False,
                 phase1_days: set | None = None,
                 entry_window_start: tuple = ENTRY_WINDOW_START,
                 entry_window_end: tuple = ENTRY_WINDOW_END,
                 rv_series: pd.Series | None = None,
                 min_rv: float | None = None,
                 max_rv: float | None = None,
                 stop_cap_pct: float | None = None,
                 ) -> list[Trade]:
    if target_mode not in ("pdc", "rr"):
        raise ValueError(target_mode)

    daily = compute_daily_filters(df)

    # RTH mask 9:30–15:55 ET
    h = df.index.hour
    m = df.index.minute
    rth_mask = ((h == 9) & (m >= 30)) | ((h >= 10) & (h < 16))
    rth = df[rth_mask].copy()

    rth_dates = pd.to_datetime(rth.index.date)
    rth["atr_pct"] = daily["atr_pct"].reindex(rth_dates).values
    rth["adx"]     = daily["adx"].reindex(rth_dates).values
    rth["sma200"]  = daily["sma200"].reindex(rth_dates).values
    if rv_series is not None:
        rth["rv"] = rv_series.reindex(rth_dates).values
    else:
        rth["rv"] = np.nan

    # Prior day RTH close, shifted 1 day — last 5-min bar's close of prior day
    last_per_day = rth["Close"].groupby(rth_dates).last()
    last_per_day.index = pd.to_datetime(last_per_day.index)
    prior_close_series = last_per_day.shift(1)
    rth["prior_close"] = prior_close_series.reindex(rth_dates).values

    idx      = rth.index
    opens    = rth["Open"].values
    highs    = rth["High"].values
    lows     = rth["Low"].values
    closes   = rth["Close"].values
    atr_pcts = rth["atr_pct"].values
    adxs     = rth["adx"].values
    sma200s  = rth["sma200"].values
    rvs      = rth["rv"].values
    pclose   = rth["prior_close"].values
    hours    = rth.index.hour.values
    minutes  = rth.index.minute.values
    dates    = np.array(rth_dates)

    day_change = np.where(dates[1:] != dates[:-1])[0] + 1
    day_starts = np.r_[0, day_change]
    day_ends   = np.r_[day_change, len(rth)]

    trading_days_list = [pd.Timestamp(dates[ds]) for ds in day_starts]

    ws_h, ws_m = entry_window_start
    we_h, we_m = entry_window_end

    def in_entry_window(i):
        hh, mm = hours[i], minutes[i]
        after = (hh > ws_h) or (hh == ws_h and mm >= ws_m)
        before = (hh < we_h) or (hh == we_h and mm <= we_m)
        return after and before

    trades: list[Trade] = []

    for day_idx, (ds, de) in enumerate(zip(day_starts, day_ends)):
        day = pd.Timestamp(dates[ds])

        # Daily regime gates
        atr_pct = atr_pcts[ds]
        adx     = adxs[ds]
        sma     = sma200s[ds]
        prior   = pclose[ds]
        if np.isnan(atr_pct) or np.isnan(prior):
            continue
        if not (min_atr_pct <= atr_pct <= max_atr_pct):
            continue
        if use_adx_filter and (np.isnan(adx) or adx >= max_adx):
            continue

        # Realized-vol filter (Run 007+)
        if min_rv is not None or max_rv is not None:
            rv = rvs[ds]
            if np.isnan(rv):
                continue
            if min_rv is not None and rv < min_rv:
                continue
            if max_rv is not None and rv > max_rv:
                continue

        # 9:30 ORB bar = first bar of day (RTH starts at 9:30)
        orb_open = opens[ds]
        orb_hi   = highs[ds]
        orb_lo   = lows[ds]

        # Gap calculation from RTH open vs prior RTH close
        if prior <= 0:
            continue
        gap_pct = (orb_open - prior) / prior * 100.0
        abs_gap = abs(gap_pct)
        if not (min_gap_pct <= abs_gap <= max_gap_pct):
            continue

        # Direction: gap up → short, gap down → long
        direction = "short" if gap_pct > 0 else "long"

        # SMA filter (per-bar close vs prev-day SMA200)
        if use_sma_filter:
            if np.isnan(sma):
                continue
            # Long requires above SMA, short requires below (carries Phase 2 convention)
            if direction == "long" and not (orb_open > sma):
                continue
            if direction == "short" and not (orb_open < sma):
                continue

        # Phase 1 ORB block
        if block_phase1 and phase1_days is not None and day in phase1_days:
            continue

        # News-day exclusion (Variant G)
        if exclude_news and is_news_day(day, trading_days_list):
            continue

        # Set stop level based on direction (gap extreme + 1 tick buffer)
        if direction == "short":
            sl_level = orb_hi + ONE_TICK_BUFFER
        else:
            sl_level = orb_lo - ONE_TICK_BUFFER

        # Optional stop cap: if gap-extreme stop is wider than cap_pct of
        # price, pull it in. Only tightens; never loosens.
        if stop_cap_pct is not None:
            cap_dist = orb_open * stop_cap_pct
            if direction == "short":
                cap_level = orb_open + cap_dist
                if cap_level < sl_level:
                    sl_level = cap_level
            else:
                cap_level = orb_open - cap_dist
                if cap_level > sl_level:
                    sl_level = cap_level

        # Scan for entry trigger between 9:35 and 11:00
        fired = False
        entry_price = np.nan
        entry_idx = -1
        tp_level = np.nan
        sl_dist = np.nan

        # Start at bar ds+1 (9:35) since ds is 9:30 (the ORB bar)
        i = ds + 1
        while i < de:
            # Stop scanning once past 11:00
            if not in_entry_window(i):
                if (hours[i] > we_h) or (hours[i] == we_h and minutes[i] > we_m):
                    break
                i += 1
                continue

            trigger = False
            if direction == "short":
                if closes[i] < orb_open:
                    trigger = True
            else:
                if closes[i] > orb_open:
                    trigger = True

            if trigger and (i + 1 < de):
                fill = opens[i + 1]
                entry_price = fill
                entry_idx = i + 1
                if direction == "long":
                    sl_dist = (fill - sl_level)   # positive points of risk
                    tp_level = (prior if target_mode == "pdc"
                                else fill + sl_dist * rr)
                else:
                    sl_dist = (sl_level - fill)   # positive risk
                    tp_level = (prior if target_mode == "pdc"
                                else fill - sl_dist * rr)
                # Invalidate trade if risk is non-positive (shouldn't happen;
                # guard against edge cases where price already moved past stop)
                if sl_dist <= 0:
                    fired = False
                    break
                fired = True
                break
            i += 1

        if not fired:
            continue

        # Manage position from entry_idx to end of day
        exit_price = np.nan
        exit_reason = ""
        exit_i = -1
        for j in range(entry_idx, de):
            bar_hi = highs[j]
            bar_lo = lows[j]
            is_last = (j == de - 1)

            hit_sl = False
            hit_tp = False
            if direction == "long":
                if bar_lo <= sl_level:
                    hit_sl = True
                if (target_mode == "pdc" and bar_hi >= tp_level) or \
                   (target_mode == "rr"  and bar_hi >= tp_level):
                    hit_tp = True
            else:
                if bar_hi >= sl_level:
                    hit_sl = True
                if bar_lo <= tp_level:
                    hit_tp = True

            if hit_sl:      # pessimistic: SL before TP on same bar
                exit_price = sl_level
                exit_reason = "sl"
                exit_i = j
                break
            if hit_tp:
                exit_price = tp_level
                exit_reason = "tp_pdc" if target_mode == "pdc" else "tp_rr"
                exit_i = j
                break
            if is_last:
                exit_price = closes[j]
                exit_reason = "session_close"
                exit_i = j
                break

        if exit_i < 0:
            continue

        pnl_pts = (exit_price - entry_price) if direction == "long" \
                  else (entry_price - exit_price)
        pnl = pnl_pts * POINT_VALUE - 2 * COMMISSION
        trades.append(Trade(
            entry_time=idx[entry_idx],
            exit_time=idx[exit_i],
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            exit_reason=exit_reason,
            pnl=pnl,
            day=day,
            gap_pct=gap_pct,
            pdc=prior,
            orb_hi=orb_hi,
            orb_lo=orb_lo,
        ))

    return trades


# ── Analysis helpers ──────────────────────────────────────────────────────
def exit_breakdown(trades: list[Trade]) -> None:
    buckets: dict = {}
    for t in trades:
        b = buckets.setdefault(t.exit_reason, {"n": 0, "pnl": 0.0})
        b["n"] += 1
        b["pnl"] += t.pnl
    total = len(trades) or 1
    print(f"  {'Reason':<16}{'Count':>8}{'Share':>10}{'Net $':>14}{'Avg $':>12}")
    print("  " + "-" * 60)
    for reason in ("tp_pdc", "tp_rr", "sl", "session_close"):
        if reason not in buckets:
            continue
        n = buckets[reason]["n"]; p = buckets[reason]["pnl"]
        print(f"  {reason:<16}{n:>8}{n/total*100:>9.1f}%{p:>14,.0f}{p/n:>12,.2f}")


def gap_decile_diagnostic(trades: list[Trade]) -> None:
    if not trades:
        print("  (no trades)")
        return
    arr = sorted(trades, key=lambda t: abs(t.gap_pct))
    n = len(arr)
    print(f"\n  {'Decile':<10}{'Range %':>20}{'Trades':>10}{'WinRt':>10}{'PF':>10}{'Net $':>14}")
    print("  " + "-" * 74)
    for d in range(10):
        lo = int(n * d / 10)
        hi = int(n * (d + 1) / 10)
        bucket = arr[lo:hi]
        if not bucket:
            continue
        gaps = [abs(t.gap_pct) for t in bucket]
        pnls = [t.pnl for t in bucket]
        wins = sum(1 for p in pnls if p > 0)
        gp = sum(p for p in pnls if p > 0)
        gl = -sum(p for p in pnls if p <= 0)
        pf = (gp / gl) if gl > 0 else float("inf")
        pf_str = f"{pf:.2f}" if pf != float("inf") else "inf"
        print(f"  {d+1:<10}"
              f"{min(gaps):.2f}-{max(gaps):.2f}".rjust(22) +
              f"{len(bucket):>10}{wins/len(bucket)*100:>9.1f}%{pf_str:>10}"
              f"{sum(pnls):>14,.0f}")


def print_ablation(rows: list[tuple[str, Metrics, int]]) -> None:
    print("\n" + "=" * 110)
    print("ABLATION — Run 005 Gap Fade (5-min, 9:35–11:00 ET, ADX<20, ATR% 0.3–2.0)")
    print("=" * 110)
    header = (f"{'Variant':<42}{'Trades':>8}{'WinRt':>8}{'PF':>8}"
              f"{'Net$':>12}{'MaxDD$':>12}{'DD%':>8}{'AvgW':>10}{'AvgL':>10}{'T/yr':>7}")
    print(header)
    print("-" * len(header))
    for label, m, years in rows:
        pf = f"{m.profit_factor:.2f}" if m.profit_factor != float("inf") else "inf"
        tpy = (m.trades / years) if years > 0 else 0.0
        sample_flag = "⚠" if m.trades < 300 else " "
        print(f"{label + sample_flag:<42}{m.trades:>8}{m.win_rate:>7.1f}%{pf:>8}"
              f"{m.net_profit:>12,.0f}{m.max_drawdown:>12,.0f}"
              f"{m.max_drawdown_pct:>7.2f}%{m.avg_win:>10,.0f}{m.avg_loss:>10,.0f}"
              f"{tpy:>7.1f}")
    print("=" * 110)
    print("  (⚠ = fewer than 300 trades — flag per go/no-go rule)")


def spot_check_first_n(df: pd.DataFrame, phase1_days: set, n: int = 20) -> None:
    """Run Variant A with spot-logging to show the first N triggered gaps."""
    print(f"\n── SPOT CHECK: first {n} triggered gap-fade setups (Variant A: 0.20–0.60%, SMA on, PDC) ──")
    trades = run_backtest(
        df, min_gap_pct=0.20, max_gap_pct=0.60,
        use_sma_filter=True, target_mode="pdc",
        phase1_days=phase1_days,
    )
    print(f"  {'#':<4}{'date':<12}{'dir':<7}{'gap%':>8}{'entry':>10}{'PDC':>10}{'SL':>10}")
    print("  " + "-" * 62)
    for i, t in enumerate(trades[:n], 1):
        print(f"  {i:<4}{t.day.strftime('%Y-%m-%d'):<12}{t.direction:<7}"
              f"{t.gap_pct:>+7.2f}%{t.entry_price:>10.2f}{t.pdc:>10.2f}"
              f"{(t.orb_hi if t.direction=='short' else t.orb_lo):>10.2f}")


# ── Main ──────────────────────────────────────────────────────────────────
def main() -> None:
    print(f"Loading 5-min data: {DATA_FILE}")
    df = load_es_data(DATA_FILE)
    print(f"  Bars loaded: {len(df):,}")
    print(f"  Range:       {df.index.min()} – {df.index.max()}")

    print("\nComputing Phase 1 ORB signal days (for block list)...")
    p1_days = phase1_signal_days(df)
    print(f"  Phase 1 signal days: {len(p1_days)}")

    # SPOT CHECK FIRST — must look correct before running full grid
    spot_check_first_n(df, p1_days, n=20)

    years_span = 18   # 2008-2026 inclusive, ~18 years

    variants = [
        ("A: 0.20-0.60%, SMA on,  PDC",
         dict(min_gap_pct=0.20, max_gap_pct=0.60, use_sma_filter=True,  target_mode="pdc")),
        ("B: 0.20-0.60%, SMA off, PDC",
         dict(min_gap_pct=0.20, max_gap_pct=0.60, use_sma_filter=False, target_mode="pdc")),
        ("C: 0.30-0.80%, SMA on,  PDC",
         dict(min_gap_pct=0.30, max_gap_pct=0.80, use_sma_filter=True,  target_mode="pdc")),
        ("D: 0.30-0.80%, SMA off, PDC",
         dict(min_gap_pct=0.30, max_gap_pct=0.80, use_sma_filter=False, target_mode="pdc")),
        ("E: 0.20-0.60%, SMA off, R:R 1.5",
         dict(min_gap_pct=0.20, max_gap_pct=0.60, use_sma_filter=False, target_mode="rr", rr=1.5)),
        ("F: 0.30-0.80%, SMA off, R:R 1.5",
         dict(min_gap_pct=0.30, max_gap_pct=0.80, use_sma_filter=False, target_mode="rr", rr=1.5)),
    ]

    print("\nRunning ablation...")
    all_trades: dict[str, list] = {}
    for label, kw in variants:
        trs = run_backtest(df, phase1_days=p1_days, **kw)
        all_trades[label] = trs
        print(f"  {label:<42}: {len(trs)} trades")

    # Variant G: news-day exclusion on better of A/B
    m_a = compute_metrics(all_trades["A: 0.20-0.60%, SMA on,  PDC"])
    m_b = compute_metrics(all_trades["B: 0.20-0.60%, SMA off, PDC"])
    g_base = "A" if m_a.profit_factor >= m_b.profit_factor else "B"
    use_sma_g = (g_base == "A")
    print(f"  (Variant G base = {g_base} — higher PF of A/B)")
    g_trades = run_backtest(df,
                            min_gap_pct=0.20, max_gap_pct=0.60,
                            use_sma_filter=use_sma_g, target_mode="pdc",
                            exclude_news=True, phase1_days=p1_days)
    g_label = f"G: 0.20-0.60% (base {g_base}), no news days"
    all_trades[g_label] = g_trades
    print(f"  {g_label:<42}: {len(g_trades)} trades")

    rows = [(label, compute_metrics(trs), years_span)
            for label, trs in all_trades.items()]
    print_ablation(rows)

    # Best by PF
    def score(item):
        _, trs = item
        mm = compute_metrics(trs)
        return (mm.profit_factor, mm.net_profit)
    best_label, best_trades = max(all_trades.items(), key=score)
    best_m = compute_metrics(best_trades)
    print(f"\n>>> Best variant: {best_label}")

    print("\n── Exit breakdown (all variants) ──")
    for label, trs in all_trades.items():
        print(f"\n  {label}")
        exit_breakdown(trs)

    print_metrics(f"Best variant — full dataset", best_m)
    print_yearly(best_trades)

    # Walk-forward
    is_tr  = filter_trades(best_trades, "2008-01-01", "2019-12-31")
    oos_tr = filter_trades(best_trades, "2020-01-01", "2026-12-31")
    is_m = compute_metrics(is_tr); oos_m = compute_metrics(oos_tr)
    print_metrics("In-sample 2008-2019",    is_m)
    print_metrics("Out-of-sample 2020-2026", oos_m)

    # Gap-size decile diagnostic on best variant
    print("\n── Gap-size decile diagnostic (best variant) ──")
    gap_decile_diagnostic(best_trades)

    # Go/no-go on Variant A specifically
    a_trades = all_trades["A: 0.20-0.60%, SMA on,  PDC"]
    a_is  = filter_trades(a_trades, "2008-01-01", "2019-12-31")
    a_oos = filter_trades(a_trades, "2020-01-01", "2026-12-31")
    a_is_pf  = compute_metrics(a_is).profit_factor
    a_oos_pf = compute_metrics(a_oos).profit_factor
    print("\n" + "=" * 70)
    print("GO/NO-GO VERDICT — Variant A (primary config)")
    print("=" * 70)
    print(f"  Variant A full:  PF = {compute_metrics(a_trades).profit_factor:.3f}")
    print(f"  Variant A IS:    PF = {a_is_pf:.3f}")
    print(f"  Variant A OOS:   PF = {a_oos_pf:.3f}")
    both_above_1 = a_is_pf >= 1.0 and a_oos_pf >= 1.0
    if both_above_1:
        print("  ✅ GO — Variant A PF ≥ 1.0 on both IS and OOS. Proceed to Run 006.")
    else:
        print("  ❌ NO-GO — Variant A fails the PF ≥ 1.0 threshold on at least one window.")
        print("     Hard go/no-go rule triggers: Senior Claude should consider pausing")
        print("     Phase 2 and focusing on Phase 1 paper trading.")
    print("=" * 70)

    # Gap to targets
    print("\n── Gap to Phase 2 targets (best variant) ──")
    def fmt(ok): return "✅" if ok else "❌"
    print(f"  Win rate:      {best_m.win_rate:.1f}%   (target ≥65%) {fmt(best_m.win_rate >= 65)}")
    print(f"  Profit factor: {best_m.profit_factor:.3f} (target ≥1.5) {fmt(best_m.profit_factor >= 1.5)}")
    print(f"  Max drawdown:  {best_m.max_drawdown_pct:.2f}% (target ≤15%) {fmt(best_m.max_drawdown_pct <= 15)}")


if __name__ == "__main__":
    main()

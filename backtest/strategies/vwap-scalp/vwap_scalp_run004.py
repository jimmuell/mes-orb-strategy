"""
Phase 2 Run 004 — Fixed R:R Exit (Final VWAP Deviation Test)
=============================================================

Replaces Run 002's VWAP-touch TP with a fixed R:R target off the 0.10%
stop. Everything else identical to Run 002 best: 1-min bars, 0.10%
deviation, single-bar color confirmation, 10:30–14:30 ET window, ADX<20,
ATR% 0.3–2.0, SMA200, max 3 trades/day, 1 MES, session-close flatten.

Exit rule change only:
- SL: entry * (1 ∓ 0.001) (long / short)  — unchanged
- TP: entry ± (SL distance × RR)           — new
  RR values tested: 0.5, 0.75, 1.0, 1.5, 2.0
- No time stop (Run 003 proved it destroys value)
- Same-bar TP+SL: pessimistic, SL fills first

If all five RR variants produce PF < 1.0, this is a paradigm failure
for the VWAP deviation entry framework on ES futures.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vwap_scalp import (  # noqa: E402
    compute_daily_filters, compute_metrics, filter_trades, Metrics,
    print_metrics, print_yearly, POINT_VALUE, COMMISSION,
)
from vwap_scalp_1min import load_es_1min, DATA_FILE_1MIN  # noqa: E402


SL_PCT             = 0.001            # 0.10%
DEVIATION_PCT      = 0.10
MAX_TRADES_PER_DAY = 3
ENTRY_WINDOW_START = (10, 30)
ENTRY_WINDOW_END   = (14, 30)


@dataclass
class Trade:
    entry_time:  pd.Timestamp
    exit_time:   pd.Timestamp
    direction:   str
    entry_price: float
    exit_price:  float
    exit_reason: str      # "tp" / "sl" / "session_close"
    pnl:         float
    day:         pd.Timestamp
    adx:         float


def run_backtest(df: pd.DataFrame,
                 rr: float,
                 deviation_pct: float = DEVIATION_PCT,
                 use_adx_filter: bool = True,
                 max_adx: float = 20.0,
                 min_atr_pct: float = 0.3,
                 max_atr_pct: float = 2.0,
                 use_sma_filter: bool = True,
                 use_time_window: bool = True) -> list[Trade]:
    dev = deviation_pct / 100.0

    daily = compute_daily_filters(df)

    h = df.index.hour
    m = df.index.minute
    rth_mask = ((h == 9) & (m >= 30)) | ((h >= 10) & (h < 16))
    rth = df[rth_mask].copy()

    rth_dates = pd.to_datetime(rth.index.date)
    rth["atr_pct"] = daily["atr_pct"].reindex(rth_dates).values
    rth["adx"]     = daily["adx"].reindex(rth_dates).values
    rth["sma200"]  = daily["sma200"].reindex(rth_dates).values

    tp_price = (rth["High"] + rth["Low"] + rth["Close"]) / 3.0
    tpv = tp_price * rth["Volume"]
    rth["cum_tpv"] = tpv.groupby(rth_dates).cumsum().values
    rth["cum_v"]   = rth["Volume"].groupby(rth_dates).cumsum().values
    rth["vwap"] = np.where(rth["cum_v"].values > 0,
                           rth["cum_tpv"].values / rth["cum_v"].values,
                           np.nan)

    idx      = rth.index
    opens    = rth["Open"].values
    highs    = rth["High"].values
    lows     = rth["Low"].values
    closes   = rth["Close"].values
    vwaps    = rth["vwap"].values
    atr_pcts = rth["atr_pct"].values
    adxs     = rth["adx"].values
    sma200s  = rth["sma200"].values
    hours    = rth.index.hour.values
    minutes  = rth.index.minute.values
    dates    = np.array(rth_dates)

    trades: list[Trade] = []

    day_change = np.where(dates[1:] != dates[:-1])[0] + 1
    day_starts = np.r_[0, day_change]
    day_ends   = np.r_[day_change, len(rth)]

    win_s_h, win_s_m = ENTRY_WINDOW_START
    win_e_h, win_e_m = ENTRY_WINDOW_END

    def in_entry_window(i):
        if not use_time_window:
            return True
        hh, mm = hours[i], minutes[i]
        after = (hh > win_s_h) or (hh == win_s_h and mm >= win_s_m)
        before = (hh < win_e_h) or (hh == win_e_h and mm <= win_e_m)
        return after and before

    for ds, de in zip(day_starts, day_ends):
        atr_pct = atr_pcts[ds]
        adx     = adxs[ds]
        sma     = sma200s[ds]
        if np.isnan(atr_pct) or np.isnan(sma):
            continue
        if not (min_atr_pct <= atr_pct <= max_atr_pct):
            continue
        if use_adx_filter and (np.isnan(adx) or adx >= max_adx):
            continue

        trades_today = 0
        long_stopped = False
        short_stopped = False

        in_pos = False
        in_dir = None
        entry_price = np.nan
        sl_level = np.nan
        tp_level = np.nan
        entry_time = None

        i = ds
        while i < de:
            vwap = vwaps[i]
            close_i = closes[i]

            if in_pos:
                bar_high = highs[i]
                bar_low  = lows[i]
                is_last_bar = (i == de - 1)

                exit_done = False
                exit_price = np.nan
                reason = ""

                # SL first (pessimistic on same-bar TP+SL)
                if in_dir == "long":
                    if bar_low <= sl_level:
                        exit_price = sl_level
                        reason = "sl"
                        long_stopped = True
                        exit_done = True
                    elif bar_high >= tp_level:
                        exit_price = tp_level
                        reason = "tp"
                        exit_done = True
                else:  # short
                    if bar_high >= sl_level:
                        exit_price = sl_level
                        reason = "sl"
                        short_stopped = True
                        exit_done = True
                    elif bar_low <= tp_level:
                        exit_price = tp_level
                        reason = "tp"
                        exit_done = True

                if not exit_done and is_last_bar:
                    exit_price = close_i
                    reason = "session_close"
                    exit_done = True

                if exit_done:
                    pnl_pts = (exit_price - entry_price) if in_dir == "long" \
                              else (entry_price - exit_price)
                    pnl = pnl_pts * POINT_VALUE - 2 * COMMISSION
                    trades.append(Trade(
                        entry_time=entry_time,
                        exit_time=idx[i],
                        direction=in_dir,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        exit_reason=reason,
                        pnl=pnl,
                        day=pd.Timestamp(dates[ds]),
                        adx=adx,
                    ))
                    in_pos = False
                    in_dir = None
                    i += 1
                    continue

            # Entry — single-bar color confirmation, fill next open
            if not in_pos and trades_today < MAX_TRADES_PER_DAY:
                if not np.isnan(vwap) and in_entry_window(i) and i + 1 < de:
                    diff = close_i - vwap
                    is_green = close_i > opens[i]
                    is_red   = close_i < opens[i]
                    long_sig = (diff <= -dev * close_i and is_green
                                and (not use_sma_filter or close_i > sma)
                                and not long_stopped)
                    short_sig = (diff >=  dev * close_i and is_red
                                 and (not use_sma_filter or close_i < sma)
                                 and not short_stopped)
                    if long_sig or short_sig:
                        fill = opens[i + 1]
                        sl_dist = fill * SL_PCT
                        if long_sig:
                            in_dir = "long"
                            entry_price = fill
                            sl_level = fill - sl_dist
                            tp_level = fill + sl_dist * rr
                        else:
                            in_dir = "short"
                            entry_price = fill
                            sl_level = fill + sl_dist
                            tp_level = fill - sl_dist * rr
                        entry_time = idx[i + 1]
                        in_pos = True
                        trades_today += 1
                        i += 2
                        continue
            i += 1

    return trades


# ── Printers ──────────────────────────────────────────────────────────────
def exit_breakdown(trades: list[Trade]) -> dict:
    out = {"tp": 0, "sl": 0, "session_close": 0}
    pnl = {k: 0.0 for k in out}
    for t in trades:
        out[t.exit_reason] = out.get(t.exit_reason, 0) + 1
        pnl[t.exit_reason] = pnl.get(t.exit_reason, 0.0) + t.pnl
    return {"counts": out, "pnl": pnl}


def print_exit_breakdown(label: str, trades: list[Trade]) -> None:
    bk = exit_breakdown(trades)
    total = len(trades) or 1
    print(f"\n── Exit breakdown: {label} ──")
    print(f"  {'Reason':<16}{'Count':>8}{'Share':>10}{'Net $':>14}{'Avg $':>12}")
    print("  " + "-" * 60)
    for reason in ("tp", "sl", "session_close"):
        c = bk["counts"][reason]
        p = bk["pnl"][reason]
        avg = (p / c) if c else 0.0
        share = c / total * 100
        print(f"  {reason:<16}{c:>8}{share:>9.1f}%{p:>14,.0f}{avg:>12,.2f}")


def print_ablation(rows: list[tuple[str, Metrics]]) -> None:
    print("\n" + "=" * 100)
    print("ABLATION — Run 004 (1-min, 0.10% dev, fixed R:R exit, SL 0.10%)")
    print("=" * 100)
    header = (f"{'Variant':<14}{'Trades':>8}{'WinRt':>8}{'PF':>8}"
              f"{'Net$':>12}{'MaxDD$':>12}{'DD%':>8}{'AvgW':>10}{'AvgL':>10}{'T/day':>8}")
    print(header)
    print("-" * len(header))
    for label, mm in rows:
        pf = f"{mm.profit_factor:.2f}" if mm.profit_factor != float("inf") else "inf"
        print(f"{label:<14}{mm.trades:>8}{mm.win_rate:>7.1f}%{pf:>8}"
              f"{mm.net_profit:>12,.0f}{mm.max_drawdown:>12,.0f}"
              f"{mm.max_drawdown_pct:>7.2f}%{mm.avg_win:>10,.0f}{mm.avg_loss:>10,.0f}"
              f"{mm.trades_per_day:>8.2f}")
    print("=" * 100)


def print_progression(r001, r002, r003, r004) -> None:
    print("\n" + "=" * 98)
    print("PROGRESSION — Run 001 -> 002 -> 003 -> 004 (best variant each)")
    print("=" * 98)
    rows = [
        ("Trades",        r001['trades'],    r002['trades'],    r003['trades'],    r004['trades']),
        ("Win rate",      f"{r001['wr']:.1f}%",  f"{r002['wr']:.1f}%",  f"{r003['wr']:.1f}%",  f"{r004['wr']:.1f}%"),
        ("Profit factor", f"{r001['pf']:.3f}",   f"{r002['pf']:.3f}",   f"{r003['pf']:.3f}",   f"{r004['pf']:.3f}"),
        ("Net profit",    f"${r001['net']:,.0f}", f"${r002['net']:,.0f}", f"${r003['net']:,.0f}", f"${r004['net']:,.0f}"),
        ("Avg win",       f"${r001['aw']:.2f}",  f"${r002['aw']:.2f}",  f"${r003['aw']:.2f}",  f"${r004['aw']:.2f}"),
        ("Avg loss",      f"${r001['al']:.2f}",  f"${r002['al']:.2f}",  f"${r003['al']:.2f}",  f"${r004['al']:.2f}"),
        ("W/L ratio",     f"{r001['wlr']:.2f}",  f"{r002['wlr']:.2f}",  f"{r003['wlr']:.2f}",  f"{r004['wlr']:.2f}"),
        ("Max DD %",      f"{r001['dd']:.2f}%",  f"{r002['dd']:.2f}%",  f"{r003['dd']:.2f}%",  f"{r004['dd']:.2f}%"),
        ("Trades/day",    f"{r001['tpd']:.2f}",  f"{r002['tpd']:.2f}",  f"{r003['tpd']:.2f}",  f"{r004['tpd']:.2f}"),
    ]
    print(f"{'Metric':<16}{'Run 001 5m':>16}{'Run 002 1m':>16}{'Run 003 2b+TS':>18}{'Run 004 fR:R':>18}")
    print("-" * 84)
    for r in rows:
        print(f"{r[0]:<16}{str(r[1]):>16}{str(r[2]):>16}{str(r[3]):>18}{str(r[4]):>18}")
    print("=" * 98)


def main() -> None:
    print(f"Loading 1-min data: {DATA_FILE_1MIN}")
    df = load_es_1min()
    print(f"  Bars loaded: {len(df):,}")
    print(f"  Range:       {df.index.min()} – {df.index.max()}")

    rr_values = [0.5, 0.75, 1.0, 1.5, 2.0]

    print("\nRunning ablation (R:R 0.5 / 0.75 / 1.0 / 1.5 / 2.0)...")
    all_trades: dict[float, list] = {}
    for rr in rr_values:
        trs = run_backtest(df, rr=rr)
        all_trades[rr] = trs
        print(f"  R:R {rr}: {len(trs)} trades")

    rows = [(f"R:R {rr}", compute_metrics(all_trades[rr])) for rr in rr_values]
    print_ablation(rows)

    for rr in rr_values:
        print_exit_breakdown(f"R:R {rr}", all_trades[rr])

    # Best by PF, tiebreak net profit
    def score(item):
        _, trs = item
        mm = compute_metrics(trs)
        return (mm.profit_factor, mm.net_profit)
    best_rr, best_trades = max(all_trades.items(), key=score)
    best_m = compute_metrics(best_trades)
    print(f"\n>>> Best variant: R:R {best_rr}")
    print_metrics(f"Best variant R:R {best_rr} — full dataset", best_m)
    print_yearly(best_trades)

    # Walk-forward
    is_tr  = filter_trades(best_trades, "2008-01-01", "2019-12-31")
    oos_tr = filter_trades(best_trades, "2020-01-01", "2026-12-31")
    print_metrics("In-sample 2008-2019",    compute_metrics(is_tr))
    print_metrics("Out-of-sample 2020-2026", compute_metrics(oos_tr))

    # ADX regime split
    print("\nRegime check — running best variant WITHOUT ADX filter...")
    no_adx = run_backtest(df, rr=best_rr, use_adx_filter=False)
    low  = [t for t in no_adx if not np.isnan(t.adx) and t.adx <  20]
    high = [t for t in no_adx if not np.isnan(t.adx) and t.adx >= 20]
    print(f"  (no ADX filter) total: {len(no_adx)}  ADX<20: {len(low)}  ADX>=20: {len(high)}")
    print_metrics("ADX < 20 (choppy)",  compute_metrics(low))
    print_metrics("ADX >= 20 (trending)", compute_metrics(high))

    # Progression
    r001 = dict(trades=1627, wr=51.6, pf=0.885, net=-2706,
                aw=24.79, al=-29.82, wlr=0.83, dd=30.36, tpd=1.25)
    r002 = dict(trades=1547, wr=37.0, pf=0.898, net=-1552,
                aw=23.91, al=-15.62, wlr=1.53, dd=21.30, tpd=1.20)
    r003 = dict(trades=1547, wr=37.0, pf=0.898, net=-1552,
                aw=23.91, al=-15.62, wlr=1.53, dd=21.30, tpd=1.20)
    wlr = (best_m.avg_win / -best_m.avg_loss) if best_m.avg_loss < 0 else 0.0
    r004 = dict(trades=best_m.trades, wr=best_m.win_rate, pf=best_m.profit_factor,
                net=best_m.net_profit, aw=best_m.avg_win, al=best_m.avg_loss,
                wlr=wlr, dd=best_m.max_drawdown_pct, tpd=best_m.trades_per_day)
    print_progression(r001, r002, r003, r004)

    # Gap
    print("\n── Gap to Phase 2 targets (best variant) ──")
    def fmt(ok): return "✅" if ok else "❌"
    print(f"  Win rate:      {best_m.win_rate:.1f}%  (target ≥65%) {fmt(best_m.win_rate >= 65)}")
    print(f"  Profit factor: {best_m.profit_factor:.3f}  (target ≥1.5) {fmt(best_m.profit_factor >= 1.5)}")
    print(f"  Max drawdown:  {best_m.max_drawdown_pct:.2f}%  (target ≤15%) {fmt(best_m.max_drawdown_pct <= 15)}")

    # Paradigm verdict
    print("\n" + "=" * 80)
    print("PARADIGM VERDICT")
    print("=" * 80)
    pfs = {rr: compute_metrics(all_trades[rr]).profit_factor for rr in rr_values}
    any_pass = any(pf >= 1.0 for pf in pfs.values())
    if any_pass:
        passers = [(rr, pf) for rr, pf in pfs.items() if pf >= 1.0]
        passers.sort(key=lambda x: -x[1])
        print("EDGE FOUND — at least one variant has PF >= 1.0:")
        for rr, pf in passers:
            print(f"  R:R {rr}: PF = {pf:.3f}  (margin over 1.0: {pf - 1.0:+.3f})")
    else:
        print("PARADIGM FAILURE CONFIRMED — VWAP deviation entry does not contain")
        print("a live edge on ES futures. Senior Claude should call a paradigm pivot.")
        worst = min(pfs.values())
        best  = max(pfs.values())
        print(f"\n  PF range across all 5 R:R variants: {worst:.3f} – {best:.3f}")
        print(f"  None reached the 1.0 breakeven threshold.")
    print("=" * 80)


if __name__ == "__main__":
    main()

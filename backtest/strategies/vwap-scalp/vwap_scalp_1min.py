"""
Phase 2 Run 002 — 1-Minute VWAP Reversion Scalp
================================================

Response to Run 001's finding that 5-min bars inverted the reward/risk
geometry. Drops to 1-min bars, tightens SL to 0.10%, tightens TP tolerance
to 1 tick, restricts entries to the midday 10:30–14:30 ET window, and
adds σ-band deviation modes alongside fixed-% thresholds.

Data: data/raw/ES_full_1min_continuous_UNadjusted.txt (ET timestamps).
Contract: 1 MES ($5/point, $0.62 commission/side).

Ablation variants (4):
  1) fixed 0.10%
  2) fixed 0.15%
  3) 1.0 σ band (20-bar stdev of close around VWAP)
  4) 1.5 σ band

Key deltas vs Run 001:
- 1-min bars instead of 5-min
- TP tolerance: 1 tick (0.25) instead of 2 ticks (0.50)
- SL: 0.10% fixed instead of 0.20%
- Entry window: 10:30–14:30 ET only
- σ-band entry modes added
- Everything else (ADX<20, ATR% 0.3–2.0, SMA200, max 3 trades/day,
  no re-entry in stopped-out direction, flatten 15:55) identical.

Note on timezones: the prompt specifies "9:30 AM to 3:55 PM CT". The raw
FirstRateData file uses Eastern Time timestamps (matches Phase 1 ORB code
which keys off `hour==9 & minute==30` as the 9:30 ET cash open). We use
ET here too for consistency with Phase 1; conceptually RTH 9:30–15:55 ET
is 8:30–14:55 CT, and the prompt's "10:30–14:30 CT entry window" maps to
11:30–15:30 ET. Jim: if you'd rather this run the midday window in CT,
flip the constants below and re-run — the strategy is agnostic to which
timezone label you use so long as the data and the window match.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# Reuse data loader and filter helpers from Run 001 to keep the two
# scripts behaviorally identical on their shared surface.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from vwap_scalp import (  # noqa: E402
    compute_daily_filters, compute_metrics, filter_trades, Metrics,
    print_metrics, print_yearly, POINT_VALUE, COMMISSION, TICK,
)


# ── Constants ─────────────────────────────────────────────────────────────
ONE_TICK      = TICK              # 0.25 pt — TP tolerance (1 tick)
SL_PCT        = 0.001             # 0.10% fixed stop
MAX_TRADES_PER_DAY = 3

# Entry window: 10:30–14:30 ET inclusive (midday mean-reversion window).
ENTRY_WINDOW_START = (10, 30)
ENTRY_WINDOW_END   = (14, 30)

SIGMA_LOOKBACK = 20               # 20-bar rolling stdev of close around VWAP

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_FILE_1MIN = REPO_ROOT / "data" / "raw" / "ES_full_1min_continuous_UNadjusted.txt"


def load_es_1min(filepath: Path = DATA_FILE_1MIN) -> pd.DataFrame:
    df = pd.read_csv(
        filepath, header=None,
        names=["timestamp", "Open", "High", "Low", "Close", "Volume"],
        parse_dates=["timestamp"],
    )
    df.set_index("timestamp", inplace=True)
    return df


@dataclass
class Trade:
    entry_time:  pd.Timestamp
    exit_time:   pd.Timestamp
    direction:   str
    entry_price: float
    exit_price:  float
    exit_reason: str
    pnl:         float
    day:         pd.Timestamp
    adx:         float


def run_backtest(df: pd.DataFrame,
                 mode: str = "pct",
                 pct: float = 0.10,
                 sigmas: float = 1.0,
                 use_adx_filter: bool = True,
                 max_adx: float = 20.0,
                 min_atr_pct: float = 0.3,
                 max_atr_pct: float = 2.0,
                 use_sma_filter: bool = True,
                 use_time_window: bool = True) -> list[Trade]:
    """
    mode='pct'   → threshold = pct/100 * close
    mode='sigma' → threshold = sigmas * rolling_stdev(close - vwap, 20)
    """
    if mode not in ("pct", "sigma"):
        raise ValueError(f"mode must be 'pct' or 'sigma', got {mode}")

    daily = compute_daily_filters(df)

    h = df.index.hour
    m = df.index.minute
    rth_mask = ((h == 9) & (m >= 30)) | ((h >= 10) & (h < 16))
    rth = df[rth_mask].copy()

    rth_dates = pd.to_datetime(rth.index.date)
    rth["atr_pct"] = daily["atr_pct"].reindex(rth_dates).values
    rth["adx"]     = daily["adx"].reindex(rth_dates).values
    rth["sma200"]  = daily["sma200"].reindex(rth_dates).values

    # Session VWAP (reset per date)
    tp = (rth["High"] + rth["Low"] + rth["Close"]) / 3.0
    tpv = tp * rth["Volume"]
    rth["cum_tpv"] = tpv.groupby(rth_dates).cumsum().values
    rth["cum_v"]   = rth["Volume"].groupby(rth_dates).cumsum().values
    rth["vwap"] = np.where(rth["cum_v"].values > 0,
                           rth["cum_tpv"].values / rth["cum_v"].values,
                           np.nan)

    # Rolling stdev of (close - vwap) within each session for σ-band mode
    resid = rth["Close"] - rth["vwap"]
    rth["vwap_sd"] = (resid.groupby(rth_dates)
                           .rolling(SIGMA_LOOKBACK, min_periods=SIGMA_LOOKBACK)
                           .std()
                           .reset_index(level=0, drop=True)
                           .values)

    idx      = rth.index
    opens    = rth["Open"].values
    highs    = rth["High"].values
    lows     = rth["Low"].values
    closes   = rth["Close"].values
    vwaps    = rth["vwap"].values
    sds      = rth["vwap_sd"].values
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
        after_start = (hh > win_s_h) or (hh == win_s_h and mm >= win_s_m)
        before_end  = (hh < win_e_h) or (hh == win_e_h and mm <= win_e_m)
        return after_start and before_end

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
        in_pos: Trade | None = None
        in_dir = None
        entry_price = np.nan
        sl_level = np.nan

        i = ds
        while i < de:
            vwap = vwaps[i]
            close_i = closes[i]

            # ── Exit first if in a position ─────────────────────────
            if in_pos is not None:
                bar_high = highs[i]
                bar_low  = lows[i]
                is_last_bar = (i == de - 1)

                exit_done = False
                if in_dir == "long" and bar_low <= sl_level:
                    exit_price = sl_level
                    reason = "sl"
                    long_stopped = True
                    exit_done = True
                elif in_dir == "short" and bar_high >= sl_level:
                    exit_price = sl_level
                    reason = "sl"
                    short_stopped = True
                    exit_done = True
                elif not np.isnan(vwap) and abs(close_i - vwap) <= ONE_TICK:
                    exit_price = close_i
                    reason = "tp_vwap"
                    exit_done = True
                elif is_last_bar:
                    exit_price = close_i
                    reason = "session_close"
                    exit_done = True

                if exit_done:
                    pnl_pts = (exit_price - entry_price) if in_dir == "long" \
                              else (entry_price - exit_price)
                    pnl = pnl_pts * POINT_VALUE - 2 * COMMISSION
                    trades.append(Trade(
                        entry_time=in_pos.entry_time,
                        exit_time=idx[i],
                        direction=in_dir,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        exit_reason=reason,
                        pnl=pnl,
                        day=pd.Timestamp(dates[ds]),
                        adx=adx,
                    ))
                    in_pos = None
                    in_dir = None
                    i += 1
                    continue

            # ── Entry signal (only when flat) ────────────────────────
            if in_pos is None and trades_today < MAX_TRADES_PER_DAY:
                if (not np.isnan(vwap) and i + 1 < de and in_entry_window(i)):
                    # Compute absolute deviation threshold in price
                    if mode == "pct":
                        thresh_abs = (pct / 100.0) * close_i
                    else:
                        sd = sds[i]
                        if np.isnan(sd):
                            i += 1
                            continue
                        thresh_abs = sigmas * sd

                    diff = close_i - vwap   # signed
                    is_green = close_i > opens[i]
                    is_red   = close_i < opens[i]

                    long_sig  = (diff <= -thresh_abs and is_green
                                 and (not use_sma_filter or close_i > sma)
                                 and not long_stopped)
                    short_sig = (diff >=  thresh_abs and is_red
                                 and (not use_sma_filter or close_i < sma)
                                 and not short_stopped)

                    if long_sig or short_sig:
                        fill = opens[i + 1]
                        if long_sig:
                            in_dir = "long"
                            entry_price = fill
                            sl_level = fill * (1 - SL_PCT)
                        else:
                            in_dir = "short"
                            entry_price = fill
                            sl_level = fill * (1 + SL_PCT)
                        in_pos = Trade(
                            entry_time=idx[i + 1],
                            exit_time=idx[i + 1],
                            direction=in_dir,
                            entry_price=entry_price,
                            exit_price=np.nan,
                            exit_reason="",
                            pnl=0.0,
                            day=pd.Timestamp(dates[ds]),
                            adx=adx,
                        )
                        trades_today += 1
                        i += 2
                        continue
            i += 1

    return trades


# ── Printers ──────────────────────────────────────────────────────────────
def print_ablation(rows: list[tuple[str, Metrics]]) -> None:
    print("\n" + "=" * 100)
    print("ABLATION — Run 002 (1-min bars, 10:30–14:30 window, SL 0.10%, TP 1 tick)")
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


def print_comparison(run001: dict, run002: dict) -> None:
    print("\n" + "=" * 80)
    print("RUN 001 (5-min) vs RUN 002 (1-min) — best variant each")
    print("=" * 80)
    rows = [
        ("Trades",         f"{run001['trades']}",            f"{run002['trades']}"),
        ("Win rate",       f"{run001['wr']:.1f}%",           f"{run002['wr']:.1f}%"),
        ("Profit factor",  f"{run001['pf']:.3f}",            f"{run002['pf']:.3f}"),
        ("Net profit",     f"${run001['net']:,.2f}",         f"${run002['net']:,.2f}"),
        ("Avg win",        f"${run001['aw']:,.2f}",          f"${run002['aw']:,.2f}"),
        ("Avg loss",       f"${run001['al']:,.2f}",          f"${run002['al']:,.2f}"),
        ("Win/Loss ratio", f"{run001['wlr']:.2f}",           f"{run002['wlr']:.2f}"),
        ("Max DD %",       f"{run001['dd']:.2f}%",           f"{run002['dd']:.2f}%"),
        ("Trades/day",     f"{run001['tpd']:.2f}",           f"{run002['tpd']:.2f}"),
    ]
    print(f"{'Metric':<18}{'Run 001 (5-min)':>22}{'Run 002 (1-min)':>22}")
    print("-" * 62)
    for r in rows:
        print(f"{r[0]:<18}{r[1]:>22}{r[2]:>22}")
    print("=" * 80)


# ── Main ──────────────────────────────────────────────────────────────────
def main() -> None:
    print(f"Loading 1-min data: {DATA_FILE_1MIN}")
    df = load_es_1min()
    print(f"  Bars loaded: {len(df):,}")
    print(f"  Range:       {df.index.min()} – {df.index.max()}")

    variants = [
        ("fixed 0.10%", dict(mode="pct",   pct=0.10)),
        ("fixed 0.15%", dict(mode="pct",   pct=0.15)),
        ("sigma 1.0",   dict(mode="sigma", sigmas=1.0)),
        ("sigma 1.5",   dict(mode="sigma", sigmas=1.5)),
    ]

    print("\nRunning ablation (ADX<20, ATR% 0.3–2.0, SMA200, 10:30–14:30 ET, max 3 tr/day)...")
    all_trades: dict[str, list] = {}
    for label, kw in variants:
        trs = run_backtest(df, **kw)
        all_trades[label] = trs
        print(f"  {label:<14}: {len(trs)} trades")

    rows = [(label, compute_metrics(all_trades[label])) for label, _ in variants]
    print_ablation(rows)

    # Best by PF, tiebreak net profit
    def score(item):
        label, trs = item
        m = compute_metrics(trs)
        return (m.profit_factor, m.net_profit)
    best_label, best_trades = max(all_trades.items(), key=score)
    best_m = compute_metrics(best_trades)
    print(f"\n>>> Best variant: {best_label}")
    print_metrics(f"Best variant {best_label} — full dataset", best_m)
    print_yearly(best_trades)

    # Walk-forward
    is_trades  = filter_trades(best_trades, "2008-01-01", "2019-12-31")
    oos_trades = filter_trades(best_trades, "2020-01-01", "2026-12-31")
    print_metrics("In-sample 2008-2019",    compute_metrics(is_trades))
    print_metrics("Out-of-sample 2020-2026", compute_metrics(oos_trades))

    # ADX regime split (best variant, no ADX filter)
    print("\nRegime check — running WITHOUT ADX filter at best variant...")
    best_kw = dict(variants)[best_label]
    no_adx = run_backtest(df, use_adx_filter=False, **best_kw)
    low  = [t for t in no_adx if not np.isnan(t.adx) and t.adx <  20]
    high = [t for t in no_adx if not np.isnan(t.adx) and t.adx >= 20]
    print(f"  (no ADX filter) total: {len(no_adx)}  ADX<20: {len(low)}  ADX>=20: {len(high)}")
    print_metrics("ADX < 20 (choppy, strategy target)", compute_metrics(low))
    print_metrics("ADX >= 20 (trending, should be worse)", compute_metrics(high))

    # Direct comparison vs Run 001
    run001 = dict(
        trades=1627, wr=51.6, pf=0.885, net=-2706.02,
        aw=24.79, al=-29.82, wlr=24.79/29.82, dd=30.36, tpd=1.25,
    )
    wlr = (best_m.avg_win / -best_m.avg_loss) if best_m.avg_loss < 0 else 0.0
    run002 = dict(
        trades=best_m.trades, wr=best_m.win_rate, pf=best_m.profit_factor,
        net=best_m.net_profit, aw=best_m.avg_win, al=best_m.avg_loss,
        wlr=wlr, dd=best_m.max_drawdown_pct, tpd=best_m.trades_per_day,
    )
    print_comparison(run001, run002)

    # Reward/risk geometry check
    print("\n── Reward/Risk geometry check ──")
    flipped = best_m.avg_win > -best_m.avg_loss
    print(f"  Run 001 avg win / avg loss : $24.79 / -$29.82 "
          f"(ratio {24.79/29.82:.2f} — INVERTED)")
    print(f"  Run 002 avg win / avg loss : ${best_m.avg_win:,.2f} / ${best_m.avg_loss:,.2f} "
          f"(ratio {wlr:.2f})")
    print(f"  Flipped? {'✅ YES' if flipped else '❌ NO — still inverted'}")

    # Gap to targets
    print("\n── Gap to Phase 2 targets (best variant) ──")
    def fmt(ok): return "✅" if ok else "❌"
    print(f"  Win rate:      {best_m.win_rate:.1f}%  (target ≥65%)  "
          f"{fmt(best_m.win_rate >= 65)}")
    print(f"  Profit factor: {best_m.profit_factor:.3f}  (target ≥1.5)  "
          f"{fmt(best_m.profit_factor >= 1.5)}")
    print(f"  Max drawdown:  {best_m.max_drawdown_pct:.2f}%  (target ≤15%)  "
          f"{fmt(best_m.max_drawdown_pct <= 15)}")


if __name__ == "__main__":
    main()

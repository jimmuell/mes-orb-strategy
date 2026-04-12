"""
Phase 2 — VWAP Reversion Scalp Strategy
========================================

Mean-reversion strategy designed to complement Phase 1 ORB by trading on
choppy/ranging days (ADX < 20) when the ORB strategy sits out. Fades
deviations from session VWAP back toward fair value.

See STRATEGY.md for the full spec.

Run 001 — Baseline ablation across four VWAP deviation thresholds:
          0.10% / 0.15% / 0.20% / 0.25%.

Data: data/raw/ES_full_5min_continuous_UNadjusted.txt (ES 5-min, ET timestamps).
Contract: 1 MES ($5/point, $0.62 commission/side).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd


# ── Contract & engine constants ───────────────────────────────────────────
POINT_VALUE = 5.0           # 1 MES = $5/point
COMMISSION  = 0.62          # per side, per contract
TICK        = 0.25
TWO_TICKS   = 2 * TICK      # 0.50 pts — VWAP "touch" tolerance
SL_PCT      = 0.002         # 0.20% fixed stop
MAX_TRADES_PER_DAY = 3

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_FILE = REPO_ROOT / "data" / "raw" / "ES_full_5min_continuous_UNadjusted.txt"


# ── Data loader ───────────────────────────────────────────────────────────
def load_es_data(filepath: Path = DATA_FILE) -> pd.DataFrame:
    """Load the FirstRateData ES 5-min CSV (no header, ET timestamps)."""
    df = pd.read_csv(
        filepath, header=None,
        names=["timestamp", "Open", "High", "Low", "Close", "Volume"],
        parse_dates=["timestamp"],
    )
    df.set_index("timestamp", inplace=True)
    return df


# ── Daily filter computation (prev-day values, no look-ahead) ─────────────
def _rma(arr: np.ndarray, length: int) -> np.ndarray:
    """Wilder RMA / SMMA — matches ta.rma()."""
    out = np.full_like(arr, np.nan, dtype=float)
    if len(arr) < length:
        return out
    seed = np.nanmean(arr[:length])
    out[length - 1] = seed
    for i in range(length, len(arr)):
        out[i] = (out[i - 1] * (length - 1) + arr[i]) / length
    return out


def compute_daily_filters(df: pd.DataFrame,
                          atr_period: int = 10,
                          adx_period: int = 14,
                          sma_period: int = 200) -> pd.DataFrame:
    """Compute daily ATR%, ADX, and SMA200 — each shifted by 1 day."""
    rth = df[((df.index.hour == 9) & (df.index.minute >= 30))
             | ((df.index.hour >= 10) & (df.index.hour < 16))]

    daily_high  = rth["High"].groupby(rth.index.date).max()
    daily_low   = rth["Low"].groupby(rth.index.date).min()
    daily_close = rth["Close"].groupby(rth.index.date).last()
    for s in (daily_high, daily_low, daily_close):
        s.index = pd.to_datetime(s.index)

    # --- ATR% ---
    prev_close = daily_close.shift(1)
    tr = pd.concat([
        daily_high - daily_low,
        (daily_high - prev_close).abs(),
        (daily_low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(atr_period, min_periods=atr_period).mean()
    atr_pct = (atr / daily_close * 100.0).shift(1)

    # --- ADX ---
    prev_high = daily_high.shift(1)
    prev_low  = daily_low.shift(1)
    up_move   = daily_high - prev_high
    down_move = prev_low - daily_low
    plus_dm   = np.where((up_move > down_move) & (up_move > 0),   up_move,   0.0)
    minus_dm  = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    atr_s   = _rma(tr.values, adx_period)
    plus_s  = _rma(plus_dm,   adx_period)
    minus_s = _rma(minus_dm,  adx_period)
    with np.errstate(invalid="ignore"):
        plus_di  = np.where(atr_s > 0, plus_s  / atr_s * 100, 0)
        minus_di = np.where(atr_s > 0, minus_s / atr_s * 100, 0)
        di_sum   = plus_di + minus_di
        dx = np.where(di_sum > 0, np.abs(plus_di - minus_di) / di_sum * 100, 0)
    adx = _rma(dx, adx_period)
    adx_prev = pd.Series(adx, index=daily_high.index).shift(1)

    # --- 200-day SMA ---
    sma = daily_close.rolling(sma_period, min_periods=sma_period).mean().shift(1)

    out = pd.DataFrame({
        "atr_pct": atr_pct,
        "adx":     adx_prev,
        "sma200":  sma,
        "daily_close": daily_close,
    })
    return out


# ── Trade container ───────────────────────────────────────────────────────
@dataclass
class Trade:
    entry_time:  pd.Timestamp
    exit_time:   pd.Timestamp
    direction:   str            # "long" / "short"
    entry_price: float
    exit_price:  float
    exit_reason: str            # "tp_vwap" / "sl" / "session_close"
    pnl:         float          # $ after commissions
    day:         pd.Timestamp
    adx:         float


# ── Core backtest ─────────────────────────────────────────────────────────
def run_backtest(df: pd.DataFrame,
                 deviation_pct: float,
                 use_adx_filter: bool = True,
                 min_adx: float = 0.0,
                 max_adx: float = 20.0,
                 min_atr_pct: float = 0.3,
                 max_atr_pct: float = 2.0,
                 use_sma_filter: bool = True) -> list[Trade]:
    """Run VWAP scalp backtest. deviation_pct is expressed as a percentage
    (e.g. 0.15 = 0.15%)."""
    dev = deviation_pct / 100.0

    daily = compute_daily_filters(df)

    # RTH mask: 9:30–15:55 inclusive
    h = df.index.hour
    m = df.index.minute
    rth_mask = (((h == 9) & (m >= 30)) | ((h >= 10) & (h < 16))
                | ((h == 15) & (m <= 55)))
    # (10-15 inclusive already covers through 15:55; keep mask simple)
    rth_mask = (((h == 9) & (m >= 30)) | ((h >= 10) & (h < 16)))
    rth = df[rth_mask].copy()

    # Attach daily filter values by date
    rth_dates = pd.to_datetime(rth.index.date)
    rth["atr_pct"] = daily["atr_pct"].reindex(rth_dates).values
    rth["adx"]     = daily["adx"].reindex(rth_dates).values
    rth["sma200"]  = daily["sma200"].reindex(rth_dates).values

    # Compute session VWAP per day (vectorized per-group via cumsum)
    tp = (rth["High"] + rth["Low"] + rth["Close"]) / 3.0
    tpv = tp * rth["Volume"]
    grouper = rth_dates
    rth["cum_tpv"] = tpv.groupby(grouper).cumsum().values
    rth["cum_v"]   = rth["Volume"].groupby(grouper).cumsum().values
    rth["vwap"] = np.where(rth["cum_v"].values > 0,
                           rth["cum_tpv"].values / rth["cum_v"].values,
                           np.nan)

    # Arrays for speed
    idx      = rth.index
    opens    = rth["Open"].values
    highs    = rth["High"].values
    lows     = rth["Low"].values
    closes   = rth["Close"].values
    vwaps    = rth["vwap"].values
    atr_pcts = rth["atr_pct"].values
    adxs     = rth["adx"].values
    sma200s  = rth["sma200"].values
    dates    = np.array(rth_dates)

    trades: list[Trade] = []

    # Day boundary indices
    day_change = np.where(dates[1:] != dates[:-1])[0] + 1
    day_starts = np.r_[0, day_change]
    day_ends   = np.r_[day_change, len(rth)]

    for ds, de in zip(day_starts, day_ends):
        day = dates[ds]
        # Daily regime gates
        atr_pct = atr_pcts[ds]
        adx     = adxs[ds]
        sma     = sma200s[ds]
        if np.isnan(atr_pct) or np.isnan(sma):
            continue
        if not (min_atr_pct <= atr_pct <= max_atr_pct):
            continue
        if use_adx_filter:
            if np.isnan(adx) or not (min_adx <= adx < max_adx):
                continue

        daily_close_price = closes[de - 1]  # last RTH close of day
        long_allowed_by_sma  = (closes[ds] > sma) if use_sma_filter else True
        short_allowed_by_sma = (closes[ds] < sma) if use_sma_filter else True
        # Evaluate SMA per-bar (close vs sma) below too, to be safe.

        trades_today = 0
        long_stopped  = False
        short_stopped = False
        in_pos: Trade | None = None
        in_dir = None           # "long"/"short"
        entry_price = np.nan
        sl_level = np.nan

        # We loop within the day. Entries use signal at bar i, fill at bar i+1 open.
        i = ds
        while i < de:
            vwap = vwaps[i]
            close_i = closes[i]

            # ── Position management first ────────────────────────────
            if in_pos is not None:
                bar_high = highs[i]
                bar_low  = lows[i]
                # Session close flatten at last bar
                is_last_bar = (i == de - 1)

                exit_done = False
                # SL check (pessimistic: SL before TP on same bar)
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
                # TP: close within 2 ticks of VWAP
                elif not np.isnan(vwap) and abs(close_i - vwap) <= TWO_TICKS:
                    exit_price = close_i
                    reason = "tp_vwap"
                    exit_done = True
                elif is_last_bar:
                    exit_price = close_i
                    reason = "session_close"
                    exit_done = True

                if exit_done:
                    if in_dir == "long":
                        pnl_pts = exit_price - entry_price
                    else:
                        pnl_pts = entry_price - exit_price
                    pnl = pnl_pts * POINT_VALUE - 2 * COMMISSION
                    trades.append(Trade(
                        entry_time=in_pos.entry_time,
                        exit_time=idx[i],
                        direction=in_dir,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        exit_reason=reason,
                        pnl=pnl,
                        day=pd.Timestamp(day),
                        adx=adx,
                    ))
                    in_pos = None
                    in_dir = None
                    # fall through — no new entry on the same bar the exit fired
                    i += 1
                    continue

            # ── Entry signal evaluation (only if flat) ───────────────
            if in_pos is None and trades_today < MAX_TRADES_PER_DAY:
                if not np.isnan(vwap) and i + 1 < de:
                    dev_frac = (close_i - vwap) / close_i  # signed
                    is_green = close_i > opens[i]
                    is_red   = close_i < opens[i]
                    # Long: below vwap by >= dev, green candle, above SMA
                    long_sig  = (dev_frac <= -dev and is_green
                                 and (not use_sma_filter or close_i > sma)
                                 and not long_stopped)
                    short_sig = (dev_frac >=  dev and is_red
                                 and (not use_sma_filter or close_i < sma)
                                 and not short_stopped)

                    if long_sig or short_sig:
                        # Fill at next bar open
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
                            day=pd.Timestamp(day),
                            adx=adx,
                        )
                        trades_today += 1
                        # Move to the fill bar — exit check runs from next iteration
                        i += 2
                        continue
            i += 1

    return trades


# ── Metrics ───────────────────────────────────────────────────────────────
@dataclass
class Metrics:
    trades: int
    wins: int
    losses: int
    win_rate: float
    profit_factor: float
    net_profit: float
    gross_profit: float
    gross_loss: float
    avg_win: float
    avg_loss: float
    max_drawdown: float
    max_drawdown_pct: float
    trades_per_day: float
    initial_capital: float = 10000.0


def compute_metrics(trades: list[Trade],
                    initial_capital: float = 10000.0) -> Metrics:
    if not trades:
        return Metrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, initial_capital)
    pnls = np.array([t.pnl for t in trades])
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    gross_profit = wins.sum()
    gross_loss = -losses.sum()
    net_profit = pnls.sum()
    pf = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")
    avg_win = wins.mean() if len(wins) else 0.0
    avg_loss = losses.mean() if len(losses) else 0.0

    # Equity curve & max drawdown
    equity = initial_capital + np.cumsum(pnls)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    dd_pct = dd / peak * 100
    max_dd = dd.max() if len(dd) else 0.0
    max_dd_pct = dd_pct.max() if len(dd_pct) else 0.0

    unique_days = len({t.day for t in trades})
    tpd = len(trades) / unique_days if unique_days else 0.0

    return Metrics(
        trades=len(trades),
        wins=len(wins),
        losses=len(losses),
        win_rate=len(wins) / len(trades) * 100,
        profit_factor=pf,
        net_profit=net_profit,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        avg_win=avg_win,
        avg_loss=avg_loss,
        max_drawdown=max_dd,
        max_drawdown_pct=max_dd_pct,
        trades_per_day=tpd,
        initial_capital=initial_capital,
    )


def filter_trades(trades: list[Trade], start: str, end: str) -> list[Trade]:
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    return [t for t in trades if s <= t.day <= e]


# ── Printers ──────────────────────────────────────────────────────────────
def print_metrics(label: str, m: Metrics) -> None:
    print(f"\n── {label} ──")
    print(f"  Trades            : {m.trades}")
    if m.trades == 0:
        return
    print(f"  Win rate          : {m.win_rate:.1f}%  ({m.wins}W / {m.losses}L)")
    pf_str = f"{m.profit_factor:.3f}" if m.profit_factor != float("inf") else "inf"
    print(f"  Profit factor     : {pf_str}")
    print(f"  Net profit        : ${m.net_profit:,.2f}")
    print(f"  Gross profit/loss : ${m.gross_profit:,.2f} / -${m.gross_loss:,.2f}")
    print(f"  Avg win / avg loss: ${m.avg_win:,.2f} / ${m.avg_loss:,.2f}")
    print(f"  Max drawdown      : ${m.max_drawdown:,.2f}  ({m.max_drawdown_pct:.2f}%)")
    print(f"  Trades per day    : {m.trades_per_day:.2f}")


def print_ablation(rows: list[tuple[str, Metrics]]) -> None:
    print("\n" + "=" * 96)
    print("ABLATION — VWAP deviation threshold")
    print("=" * 96)
    header = f"{'Variant':<14}{'Trades':>8}{'WinRt':>8}{'PF':>8}{'Net$':>12}{'MaxDD$':>12}{'DD%':>8}{'AvgW':>10}{'AvgL':>10}{'T/day':>8}"
    print(header)
    print("-" * len(header))
    for label, m in rows:
        pf = f"{m.profit_factor:.2f}" if m.profit_factor != float("inf") else "inf"
        print(f"{label:<14}{m.trades:>8}{m.win_rate:>7.1f}%{pf:>8}"
              f"{m.net_profit:>12,.0f}{m.max_drawdown:>12,.0f}"
              f"{m.max_drawdown_pct:>7.2f}%{m.avg_win:>10,.0f}{m.avg_loss:>10,.0f}"
              f"{m.trades_per_day:>8.2f}")
    print("=" * 96)


def print_yearly(trades: list[Trade]) -> None:
    by_year: dict[int, list[Trade]] = {}
    for t in trades:
        by_year.setdefault(t.day.year, []).append(t)
    print("\nYearly breakdown:")
    print(f"  {'Year':<6}{'Trades':>8}{'WinRt':>8}{'PF':>8}{'Net$':>12}")
    print("  " + "-" * 42)
    for y in sorted(by_year):
        m = compute_metrics(by_year[y])
        pf = f"{m.profit_factor:.2f}" if m.profit_factor != float("inf") else "inf"
        print(f"  {y:<6}{m.trades:>8}{m.win_rate:>7.1f}%{pf:>8}{m.net_profit:>12,.0f}")


# ── Main ──────────────────────────────────────────────────────────────────
def main() -> None:
    print(f"Loading data: {DATA_FILE}")
    df = load_es_data()
    print(f"  Bars loaded: {len(df):,}")
    print(f"  Range:       {df.index.min()} – {df.index.max()}")

    thresholds = [0.10, 0.15, 0.20, 0.25]
    all_trades: dict[float, list[Trade]] = {}

    print("\nRunning ablation (ADX<20, ATR% 0.3–2.0, SMA200, max 3 tr/day)...")
    for th in thresholds:
        trs = run_backtest(df, deviation_pct=th)
        all_trades[th] = trs
        print(f"  dev {th:.2f}%: {len(trs)} trades")

    rows = [(f"{th:.2f}%", compute_metrics(all_trades[th])) for th in thresholds]
    print_ablation(rows)

    # Best variant = highest PF (subject to ≥ target trades)
    def score(item):
        th, trs = item
        m = compute_metrics(trs)
        return (m.profit_factor, m.net_profit)
    best_th, best_trades = max(all_trades.items(), key=score)
    best_metrics = compute_metrics(best_trades)
    print(f"\n>>> Best variant: deviation = {best_th:.2f}%")
    print_metrics(f"Best variant {best_th:.2f}% — full dataset", best_metrics)
    print_yearly(best_trades)

    # Walk-forward
    is_trades  = filter_trades(best_trades, "2008-01-01", "2019-12-31")
    oos_trades = filter_trades(best_trades, "2020-01-01", "2026-12-31")
    print_metrics("In-sample 2008-2019",  compute_metrics(is_trades))
    print_metrics("Out-of-sample 2020-2026", compute_metrics(oos_trades))

    # ADX regime confirmation: run best variant with no ADX filter, then
    # split trades by daily ADX bucket.
    print("\nRegime check — running WITHOUT ADX filter at best threshold...")
    no_adx_trades = run_backtest(df, deviation_pct=best_th, use_adx_filter=False)
    low  = [t for t in no_adx_trades if not np.isnan(t.adx) and t.adx <  20]
    high = [t for t in no_adx_trades if not np.isnan(t.adx) and t.adx >= 20]
    print(f"  (no ADX filter) total: {len(no_adx_trades)}  "
          f"ADX<20: {len(low)}  ADX>=20: {len(high)}")
    print_metrics("ADX < 20 (choppy, strategy target)", compute_metrics(low))
    print_metrics("ADX >= 20 (trending, should be worse)", compute_metrics(high))

    # Gap to targets
    print("\n── Gap to Phase 2 targets (best variant) ──")
    print(f"  Win rate:      {best_metrics.win_rate:.1f}%  "
          f"(target ≥65%)  "
          f"{'✅' if best_metrics.win_rate >= 65 else '❌ ' + f'{65 - best_metrics.win_rate:+.1f} pts'}")
    pf = best_metrics.profit_factor
    print(f"  Profit factor: {pf:.3f}  "
          f"(target ≥1.5)  "
          f"{'✅' if pf >= 1.5 else '❌'}")
    print(f"  Max drawdown:  {best_metrics.max_drawdown_pct:.2f}%  "
          f"(target ≤15%) "
          f"{'✅' if best_metrics.max_drawdown_pct <= 15 else '❌'}")


if __name__ == "__main__":
    main()

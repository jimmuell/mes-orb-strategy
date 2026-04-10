"""
MES Opening Range Breakout (ORB) Strategy Backtest

Implements the ORB strategy from pine/mes_orb_v1.pine:
- ORB = first 5-min bar at 9:30 ET (regular session open)
- Long: breakout above ORB high + retest + close > VWAP + close > EMA-9
- Short: breakdown below ORB low + retest + close < VWAP + close < EMA-9
- SL = other side of ORB range, TP configurable R:R
- One trade per day, 2 MES contracts

Settings:
- Initial capital: $25,000
- 2 MES contracts (fixed qty = 10 units at $5/point)
- Commission: $0.62/contract (~0.0021% of position value)
- Slippage: 0 (NOT simulated — requires tick-level data)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from engine import (
    BacktestConfig, run_backtest_long_short, print_kpis, print_trades,
    calc_ema,
)


MES_MULTIPLIER = 5.0   # $5 per point for MES
MES_CONTRACTS = 2
TICK = 0.25            # ES tick size
STRATEGIES_DIR = Path(__file__).resolve().parent
ENGINE_DIR = STRATEGIES_DIR.parent
DATA_DIR = ENGINE_DIR / "data"
SAMPLE_DATA = ENGINE_DIR / "sample-data" / "ES_5min_sample.csv"


# ---------------------------------------------------------------------------
# Data generation — 6-month realistic ES 5-min
# ---------------------------------------------------------------------------

def _tick_round(price):
    """Round to nearest ES tick (0.25)."""
    return round(price / TICK) * TICK


def generate_es_6months(filepath):
    """Generate 6 months of realistic ES 5-min data (Oct 2025 – Apr 2026).

    Produces full ETH bars (18:00 prev-day to 16:55 each day) with:
    - Realistic intraday volatility profile (high at open, low midday)
    - ORB ranges of 15-50 points at 9:30 ET
    - Monthly macro drift matching a mild bull trend with a Jan pullback
    - Proper ES tick rounding (0.25)
    """
    np.random.seed(42)
    trading_days = pd.bdate_range("2025-10-01", "2026-04-06")

    # Monthly price targets — mild bull with Jan dip
    targets = {
        10: 5750, 11: 5950, 12: 6100,
        1: 5900,  2: 6050,  3: 6350,  4: 6550,
    }

    all_bars = []
    price = 5700.0

    for day in trading_days:
        month = day.month
        target = targets.get(month, 6200)
        daily_drift = (target - price) * 0.008  # gentle mean-reversion

        # --- day type ---
        day_type = np.random.choice(
            ["trend_up", "trend_down", "range", "reversal"],
            p=[0.30, 0.30, 0.20, 0.20],
        )
        orb_range = np.random.uniform(15, 50)
        trend_bars = np.random.randint(6, 14)          # bars of initial trend
        trend_str = np.random.uniform(0.4, 1.2)        # drift per bar in trend

        # --- build bar timestamps for this day ---
        prev_day = day - pd.Timedelta(days=1)
        if day.dayofweek == 0:                          # Monday → Sunday 18:00
            prev_day = day - pd.Timedelta(days=1)

        eth_times = pd.date_range(
            prev_day.replace(hour=18, minute=0),
            day.replace(hour=16, minute=55),
            freq="5min",
        )

        for bar_idx, t in enumerate(eth_times):
            h, m = t.hour, t.minute

            # --- volatility profile ---
            if h < 9 or (h == 9 and m < 30) or h >= 17:
                # overnight / after-hours: very low vol
                vol_mult = 0.4
                drift = daily_drift / len(eth_times)
            elif h == 9 and m == 30:
                # ORB bar — handled separately below
                vol_mult = 0
                drift = 0
            elif h < 11:
                # first 90 min post-ORB: high vol
                vol_mult = 1.2
                rth_idx = (h - 9) * 12 + m // 5 - 6   # bars since 9:35
                if day_type == "trend_up":
                    if rth_idx <= trend_bars:
                        drift = trend_str
                    elif rth_idx <= trend_bars + 5:
                        drift = -trend_str * 0.45       # pullback / retest
                    else:
                        drift = trend_str * 0.25
                elif day_type == "trend_down":
                    if rth_idx <= trend_bars:
                        drift = -trend_str
                    elif rth_idx <= trend_bars + 5:
                        drift = trend_str * 0.45
                    else:
                        drift = -trend_str * 0.25
                elif day_type == "reversal":
                    if rth_idx <= trend_bars:
                        drift = trend_str * (1 if np.random.random() > 0.5
                                             else -1)
                    else:
                        drift = -drift if bar_idx > 0 else 0
                else:
                    drift = np.random.uniform(-0.3, 0.3)
            elif h < 14:
                # midday: low vol
                vol_mult = 0.7
                drift = np.random.uniform(-0.15, 0.15)
            else:
                # late afternoon: medium vol
                vol_mult = 0.9
                drift = daily_drift / len(eth_times) * 2

            # --- ORB bar: explicit wide range ---
            if h == 9 and m == 30:
                orb_open = price + np.random.normal(0, 3)
                if day_type == "trend_up":
                    orb_close = orb_open + np.random.uniform(2, orb_range * 0.3)
                elif day_type == "trend_down":
                    orb_close = orb_open - np.random.uniform(2, orb_range * 0.3)
                else:
                    orb_close = orb_open + np.random.uniform(
                        -orb_range * 0.2, orb_range * 0.2)

                ext_hi = np.random.uniform(orb_range * 0.15, orb_range * 0.40)
                ext_lo = np.random.uniform(orb_range * 0.15, orb_range * 0.40)
                orb_high = max(orb_open, orb_close) + ext_hi
                orb_low = min(orb_open, orb_close) - ext_lo

                # enforce minimum range
                actual = orb_high - orb_low
                if actual < orb_range:
                    gap = (orb_range - actual) / 2
                    orb_high += gap
                    orb_low -= gap

                o = _tick_round(orb_open)
                h_px = _tick_round(orb_high)
                l_px = _tick_round(orb_low)
                c = _tick_round(orb_close)
                vol = int(np.random.uniform(8000, 25000))

                all_bars.append({
                    "timestamp": t.strftime("%Y-%m-%d %H:%M:%S"),
                    "open": o, "high": h_px, "low": l_px,
                    "close": c, "volume": vol,
                })
                price = c
                continue

            # --- normal bar ---
            change = np.random.normal(drift, 1.5 * vol_mult)
            bar_open = price
            bar_close = bar_open + change

            ext = abs(np.random.normal(0, 1.0 * vol_mult))
            bar_high = max(bar_open, bar_close) + ext
            bar_low = min(bar_open, bar_close) - ext

            if h >= 9 and h < 16:
                vol = int(np.random.uniform(3000, 15000))
            else:
                vol = int(np.random.uniform(200, 4000))

            all_bars.append({
                "timestamp": t.strftime("%Y-%m-%d %H:%M:%S"),
                "open": _tick_round(bar_open),
                "high": _tick_round(bar_high),
                "low": _tick_round(bar_low),
                "close": _tick_round(bar_close),
                "volume": vol,
            })
            price = bar_close

    df = pd.DataFrame(all_bars)
    df.to_csv(filepath, index=False)
    print(f"Generated {len(df)} bars of ES 5-min data → {filepath}")
    return df


# ---------------------------------------------------------------------------
# Data loader
# ---------------------------------------------------------------------------

def load_es_data(filepath=None, generate_if_missing=False):
    """Load ES futures 5-min CSV with Eastern-time datetime timestamps.

    Default path: data/ES_6months.csv.  Falls back to sample-data/ if
    the 6-month file doesn't exist yet.
    """
    if filepath is None:
        filepath = DATA_DIR / "ES_6months.csv"
        if not filepath.exists():
            if generate_if_missing:
                generate_es_6months(filepath)
            else:
                filepath = SAMPLE_DATA
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Data file not found: {filepath}")

    df = pd.read_csv(filepath, parse_dates=["timestamp"])
    df.set_index("timestamp", inplace=True)
    df.rename(columns={
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume",
    }, inplace=True)
    return df


# ---------------------------------------------------------------------------
# Signal generator — stateful, matches pine/mes_orb_v1.pine
# ---------------------------------------------------------------------------

def mes_orb_signals(df, ema_len=9, retest_ticks=2, rr_ratio=2.0,
                    min_orb_range=0.0, max_orb_range=9999.0,
                    max_entry_hour=16, sl_frac=1.0,
                    # legacy — ignored if retest_ticks is set
                    retest_pct=None):
    """
    MES Opening Range Breakout signal generator.

    Replicates pine/mes_orb_v1.pine bar-by-bar:
      1. ORB = first 5-min bar at 9:30 ET
      2. Post-ORB: detect breakout above ORB high or below ORB low
      3. Retest: price returns to ORB level within tolerance, with
         VWAP + EMA-9 confluence
      4. Entry with TP/SL set at signal time
      5. One trade per day; flatten at session end (15:55 ET)

    Parameters:
      - retest_ticks: retest tolerance in ticks (1 tick = 0.25 pts).
        Default 2 ticks = 0.50 points.
      - min_orb_range / max_orb_range: filter days by ORB width (points).
      - max_entry_hour: only enter before this hour ET. Default 16.
      - sl_frac: stop-loss as fraction of ORB range. 1.0 = full range (default),
        0.5 = half range (tighter stop).
    """
    df = df.copy()
    n = len(df)

    # --- Indicators ---
    df["ema9"] = calc_ema(df["Close"], ema_len)
    df["hlc3"] = (df["High"] + df["Low"] + df["Close"]) / 3.0

    # --- Time masks (Eastern Time) ---
    hours = df.index.hour
    minutes = df.index.minute

    is_orb = np.asarray((hours == 9) & (minutes == 30))
    is_sess = np.asarray(((hours == 9) & (minutes >= 30))
                         | ((hours >= 10) & (hours < 16)))
    is_end = np.asarray((hours == 15) & (minutes == 55))

    # --- Price arrays ---
    opens   = df["Open"].values
    highs   = df["High"].values
    lows    = df["Low"].values
    closes  = df["Close"].values
    volumes = df["Volume"].values.astype(float)
    ema9    = df["ema9"].values
    hlc3    = df["hlc3"].values

    # --- Output columns ---
    long_entry  = np.zeros(n, dtype=bool)
    long_exit   = np.zeros(n, dtype=bool)
    short_entry = np.zeros(n, dtype=bool)
    short_exit  = np.zeros(n, dtype=bool)
    tp_arr      = np.full(n, np.nan)
    sl_arr      = np.full(n, np.nan)

    # --- Per-day state ---
    orb_high = np.nan
    orb_low  = np.nan
    orb_set  = False
    traded_today = False
    broke_above  = False
    broke_below  = False
    cum_tpv = 0.0
    cum_vol = 0.0
    vwap    = np.nan

    # --- Position tracking (sync with engine TP/SL) ---
    position      = 0       # 0 = flat, 1 = long, -1 = short
    entry_bar_idx = -999
    active_tp     = np.nan
    active_sl     = np.nan

    for i in range(n):
        # Snapshot: was a position open at the start of this bar?
        # Needed so step 8 publishes TP/SL on the bar where the
        # simulated exit fires — the engine reads the same values
        # to detect the exit itself.
        was_in_position = position != 0

        # ── 1. Simulate TP/SL exit (before signal logic) ─────────────
        #    Engine skips TP/SL on entry bar, so we check i > entry_bar_idx.
        if position == 1 and i > entry_bar_idx:
            if lows[i] <= active_sl or highs[i] >= active_tp:
                position = 0
                entry_bar_idx = -999
        elif position == -1 and i > entry_bar_idx:
            if highs[i] >= active_sl or lows[i] <= active_tp:
                position = 0
                entry_bar_idx = -999

        # ── 2. New-session reset (ORB bar that isn't a continuation) ──
        if is_orb[i]:
            prev_orb = is_orb[i - 1] if i > 0 else False
            if not prev_orb:
                orb_high = np.nan
                orb_low  = np.nan
                orb_set  = False
                traded_today = False
                broke_above  = False
                broke_below  = False
                cum_tpv = 0.0
                cum_vol = 0.0
                vwap    = np.nan

        # ── 3. ORB tracking ───────────────────────────────────────────
        if is_orb[i]:
            if not orb_set:
                orb_high = highs[i]
                orb_low  = lows[i]
            else:
                orb_high = max(orb_high, highs[i])
                orb_low  = min(orb_low, lows[i])
            orb_set = True

        # ── 4. Session VWAP ───────────────────────────────────────────
        if is_sess[i] and volumes[i] > 0:
            cum_tpv += hlc3[i] * volumes[i]
            cum_vol += volumes[i]
            vwap = cum_tpv / cum_vol

        # ── 5. Post-ORB breakout detection ────────────────────────────
        post_orb = orb_set and not is_orb[i] and is_sess[i]

        if post_orb and not np.isnan(orb_high):
            if closes[i] > orb_high:
                broke_above = True
            if closes[i] < orb_low:
                broke_below = True

        # ── 6. Retest + confluence + filters ─────────────────────────
        retest_tol = retest_ticks * TICK   # e.g. 2 ticks × 0.25 = 0.50 pts

        # ORB range filters
        orb_width = (orb_high - orb_low) if not np.isnan(orb_high) else 0.0
        range_ok = (orb_width >= min_orb_range and orb_width <= max_orb_range
                    if not np.isnan(orb_high) else False)
        time_ok = hours[i] < max_entry_hour

        long_ok = (
            broke_above and not traded_today and post_orb
            and position == 0 and range_ok and time_ok
            and lows[i] <= orb_high + retest_tol
            and closes[i] > orb_high
            and not np.isnan(vwap)    and closes[i] > vwap
            and not np.isnan(ema9[i]) and closes[i] > ema9[i]
        )

        short_ok = (
            broke_below and not traded_today and post_orb
            and position == 0 and range_ok and time_ok
            and highs[i] >= orb_low - retest_tol
            and closes[i] < orb_low
            and not np.isnan(vwap)    and closes[i] < vwap
            and not np.isnan(ema9[i]) and closes[i] < ema9[i]
        )

        # ── 7. Entry signals ──────────────────────────────────────────
        #    SL = sl_frac × ORB range from the entry side.
        #    TP = rr_ratio × risk from entry price.
        if long_ok:
            long_entry[i] = True
            sl_dist = orb_width * sl_frac
            active_sl = closes[i] - sl_dist
            active_tp = closes[i] + rr_ratio * sl_dist
            position = 1
            entry_bar_idx = i + 1        # engine fills at next bar's Open
            traded_today = True

        if short_ok:
            short_entry[i] = True
            sl_dist = orb_width * sl_frac
            active_sl = closes[i] + sl_dist
            active_tp = closes[i] - rr_ratio * sl_dist
            position = -1
            entry_bar_idx = i + 1
            traded_today = True

        # ── 8. Publish TP/SL for engine ───────────────────────────────
        #    Must publish on exit bars too — the engine needs values on
        #    the bar where High/Low breaches the level.
        if position != 0 or was_in_position:
            tp_arr[i] = active_tp
            sl_arr[i] = active_sl

        # ── 9. Session-end flatten (15:55 ET → fills at 16:00 Open) ──
        if is_end[i] and position != 0:
            if position == 1:
                long_exit[i] = True
            else:
                short_exit[i] = True
            position = 0
            entry_bar_idx = -999

    df["long_entry"]  = long_entry
    df["long_exit"]   = long_exit
    df["short_entry"] = short_entry
    df["short_exit"]  = short_exit
    df["tp_price"]    = tp_arr
    df["sl_price"]    = sl_arr

    return df


# ---------------------------------------------------------------------------
# Single backtest run
# ---------------------------------------------------------------------------

def run_single(df_raw, ema_len=9, retest_ticks=2, rr_ratio=1.5,
               min_orb_range=0.0, max_orb_range=9999.0,
               max_entry_hour=16, sl_frac=1.0, verbose=True):
    """Run one ORB backtest with the given parameters. Returns kpis dict."""
    df = mes_orb_signals(df_raw.copy(), ema_len=ema_len,
                         retest_ticks=retest_ticks, rr_ratio=rr_ratio,
                         min_orb_range=min_orb_range,
                         max_orb_range=max_orb_range,
                         max_entry_hour=max_entry_hour,
                         sl_frac=sl_frac)

    start = str(df_raw.index[0].date())
    end = str(df_raw.index[-1].date() + pd.Timedelta(days=1))

    config = BacktestConfig(
        initial_capital=25000.0,
        commission_pct=0.0021,      # ~$0.62/contract for 2 MES
        slippage_ticks=0,
        qty_type="fixed",
        qty_value=10.0,             # 2 contracts × $5/point
        pyramiding=1,
        start_date=start,
        end_date=end,
    )

    kpis = run_backtest_long_short(df, config)

    if verbose:
        n_long  = df["long_entry"].sum()
        n_short = df["short_entry"].sum()

        print("\n" + "=" * 64)
        print("  MES ORB STRATEGY v1 — BACKTEST RESULTS")
        print("=" * 64)
        print(f"  Chart Data:        ES 5-min (real sample, Eastern Time)")
        print(f"  Date Range:        {kpis.get('actual_start_date', 'N/A')}"
              f" to {kpis.get('actual_end_date', 'N/A')}")
        print(f"  Initial Capital:   ${config.initial_capital:,.0f}")
        print(f"  Position Size:     {MES_CONTRACTS} MES contracts"
              f" (${MES_MULTIPLIER:.0f}/point)")
        print(f"  Commission:        $0.62/contract"
              f" (${0.62 * MES_CONTRACTS:.2f}/side, ~{config.commission_pct}%)")
        print(f"  Slippage:          0 (NOT simulated)")
        print(f"  R:R Ratio:         {rr_ratio} : 1")
        print(f"  EMA Length:        {ema_len}")
        print(f"  Retest Tol:        {retest_ticks} ticks"
              f" ({retest_ticks * TICK:.2f} pts)")
        print(f"  SL Fraction:       {sl_frac:.0%} of ORB range")
        if min_orb_range > 0:
            print(f"  Min ORB Range:     {min_orb_range} pts")
        if max_orb_range < 9999:
            print(f"  Max ORB Range:     {max_orb_range} pts")
        if max_entry_hour < 16:
            print(f"  Max Entry Time:    {max_entry_hour}:00 ET")
        print(f"  Signals:           {n_long} long, {n_short} short")
        print("=" * 64)

        print_kpis(kpis)

        if kpis.get("trades"):
            print_trades(kpis["trades"])

            print("\n\nDETAILED TRADES:")
            print("-" * 90)
            for idx, t in enumerate(kpis["trades"], 1):
                d = getattr(t, "direction", "long").upper()
                e_dt = (t.entry_date.strftime("%Y-%m-%d %H:%M")
                        if t.entry_date else "N/A")
                x_dt = (t.exit_date.strftime("%Y-%m-%d %H:%M")
                        if t.exit_date else "OPEN")
                x_px = f"{t.exit_price:.2f}" if t.exit_price else "—"
                pnl  = f"${t.pnl:+,.2f}" if t.pnl is not None else "—"
                print(f"  #{idx:>2}  {d:<5}  Entry {e_dt} @ {t.entry_price:.2f}"
                      f"  →  Exit {x_dt} @ {x_px}   PnL {pnl}")
        else:
            print("\n  No trades generated.")

    return kpis


# ---------------------------------------------------------------------------
# Monthly breakdown
# ---------------------------------------------------------------------------

def monthly_breakdown(kpis):
    """Print month-by-month performance breakdown."""
    trades = [t for t in kpis.get("trades", []) if t.exit_date is not None]
    if not trades:
        print("\n  No closed trades for monthly breakdown.")
        return {}

    months = {}
    for t in trades:
        key = t.entry_date.strftime("%Y-%m")
        if key not in months:
            months[key] = {"trades": 0, "wins": 0, "pnl": 0.0}
        months[key]["trades"] += 1
        if t.pnl > 0:
            months[key]["wins"] += 1
        months[key]["pnl"] += t.pnl

    print("\n  MONTHLY BREAKDOWN:")
    print(f"  {'Month':>8}  {'Trades':>6}  {'Wins':>5}  {'Win%':>6}"
          f"  {'PnL':>12}  {'Best/Worst'}")
    print("  " + "-" * 62)
    best_m = max(months, key=lambda m: months[m]["pnl"])
    worst_m = min(months, key=lambda m: months[m]["pnl"])
    for m in sorted(months):
        d = months[m]
        wr = d["wins"] / d["trades"] * 100 if d["trades"] > 0 else 0
        tag = ""
        if m == best_m:
            tag = " << BEST"
        elif m == worst_m:
            tag = " << WORST"
        print(f"  {m:>8}  {d['trades']:>6}  {d['wins']:>5}  {wr:>5.1f}%"
              f"  ${d['pnl']:>+10,.2f}{tag}")
    return months


# ---------------------------------------------------------------------------
# Parameter sweep — v2 (tick-based retest, fractional SL)
# ---------------------------------------------------------------------------

def run_sweep_v2(df_raw):
    """Sweep R:R × sl_frac with tight retest and ORB range filters."""
    rr_ratios = [1.0, 1.5, 2.0]
    sl_fracs  = [0.5, 0.75, 1.0]

    # Fixed for all runs (the improvements)
    fixed = dict(
        retest_ticks=2,        # 0.50 pts — tight retest
        min_orb_range=20,      # skip choppy opens
        max_orb_range=60,      # skip gap days
        max_entry_hour=16,     # no time filter (for comparison below)
    )

    results = []
    for rr in rr_ratios:
        for sl in sl_fracs:
            kpis = run_single(df_raw, rr_ratio=rr, sl_frac=sl,
                              verbose=False, **fixed)
            closed = [t for t in kpis.get("trades", [])
                      if t.exit_date is not None]
            results.append({
                "rr": rr, "sl_frac": sl,
                "trades":     len(closed),
                "win_rate":   kpis.get("win_rate", 0.0),
                "pf":         kpis.get("profit_factor", 0.0),
                "net_profit": kpis.get("net_profit", 0.0),
                "net_pct":    kpis.get("net_profit_pct", 0.0),
                "max_dd_pct": kpis.get("max_drawdown_pct", 0.0),
                "max_dd_usd": kpis.get("max_drawdown", 0.0),
                "avg_trade":  kpis.get("avg_trade", 0.0),
                "kpis":       kpis,
            })

    results.sort(key=lambda r: (r["trades"] > 0, r["pf"]), reverse=True)
    return results


def print_sweep_v2(results):
    """Print the v2 sweep table."""
    print("\n" + "=" * 100)
    print("  PARAMETER SWEEP — retest=2 ticks, ORB 20-60 pts")
    print("=" * 100)
    print(f"  {'#':>3}  {'R:R':>4}  {'SL%':>4}  {'Trades':>6}"
          f"  {'Win%':>6}  {'PF':>7}  {'Net $':>10}  {'Net%':>7}"
          f"  {'MaxDD%':>7}  {'MaxDD$':>10}  {'Avg$':>8}")
    print("  " + "-" * 88)

    for i, r in enumerate(results, 1):
        pf_str = f"{r['pf']:.3f}" if r['pf'] < 999 else "inf"
        sl_lbl = f"{r['sl_frac']:.0%}"
        print(f"  {i:>3}  {r['rr']:>4.1f}  {sl_lbl:>4s}  {r['trades']:>6d}"
              f"  {r['win_rate']:>5.1f}%  {pf_str:>7s}"
              f"  {r['net_profit']:>+10,.2f}  {r['net_pct']:>+6.2f}%"
              f"  {abs(r['max_dd_pct']):>6.2f}%  {r['max_dd_usd']:>+10,.2f}"
              f"  {r['avg_trade']:>+8,.2f}")

    if results and results[0]["trades"] > 0:
        b = results[0]
        print(f"\n  BEST: R:R={b['rr']:.1f}  SL={b['sl_frac']:.0%}"
              f"  →  PF={b['pf']:.3f}  Trades={b['trades']}"
              f"  Win%={b['win_rate']:.1f}  Net=${b['net_profit']:+,.2f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # ── Load real sample data ─────────────────────────────────────────
    df_raw = load_es_data(SAMPLE_DATA)

    orb_bars = df_raw[(df_raw.index.hour == 9) & (df_raw.index.minute == 30)]
    print(f"Data: {SAMPLE_DATA.name}")
    print(f"Range: {df_raw.index[0]} to {df_raw.index[-1]}")
    print(f"Total bars: {len(df_raw):,}")
    print(f"Trading days: {len(orb_bars)}")

    # ── 1. Old baseline for comparison ────────────────────────────────
    print("\n" + "#" * 64)
    print("  OLD BASELINE  (R:R=1.5, 0.08% retest, full SL)")
    print("#" * 64)
    old_kpis = run_single(df_raw, rr_ratio=1.5, retest_ticks=32,
                          sl_frac=1.0, min_orb_range=0, max_orb_range=9999,
                          verbose=True)

    # ── 2. New baseline with improvements ─────────────────────────────
    print("\n\n" + "#" * 64)
    print("  NEW BASELINE  (R:R=1.5, 2-tick retest, 50% SL, ORB 20-60)")
    print("#" * 64)
    new_kpis = run_single(df_raw, rr_ratio=1.5, retest_ticks=2,
                          sl_frac=0.5, min_orb_range=20, max_orb_range=60,
                          verbose=True)

    # ── 3. Full sweep ─────────────────────────────────────────────────
    print("\n\n" + "#" * 64)
    print("  PARAMETER SWEEP")
    print("#" * 64)
    results = run_sweep_v2(df_raw)
    print_sweep_v2(results)

    # ── 4. Also sweep on 6-month synthetic ────────────────────────────
    data_6m = DATA_DIR / "ES_6months.csv"
    if data_6m.exists():
        df_6m = load_es_data(data_6m)
        orb_6m = df_6m[(df_6m.index.hour == 9) & (df_6m.index.minute == 30)]
        print(f"\n\n{'#' * 64}")
        print(f"  6-MONTH SYNTHETIC SWEEP  ({len(orb_6m)} trading days)")
        print("#" * 64)
        results_6m = run_sweep_v2(df_6m)
        print_sweep_v2(results_6m)

        # Best combo detailed
        if results_6m and results_6m[0]["trades"] > 0:
            b = results_6m[0]
            print(f"\n\n{'#' * 64}")
            print(f"  BEST 6M:  R:R={b['rr']}  SL={b['sl_frac']:.0%}")
            print("#" * 64)
            best_kpis = run_single(df_6m, rr_ratio=b["rr"],
                                   sl_frac=b["sl_frac"],
                                   retest_ticks=2, min_orb_range=20,
                                   max_orb_range=60, verbose=True)
            monthly_breakdown(best_kpis)

    return results


if __name__ == "__main__":
    main()

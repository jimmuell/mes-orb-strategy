"""
Opening Range Breakout (ORB) Strategy Backtest — ES / MES Futures

Data source: ES Continuous Futures (E-mini S&P 500, $50/point)
  URL:       https://firstratedata.com/i/futures/ES
  Timeframe: 5-minute bars
  Timezone:  US Eastern Time
  Format:    timestamp (yyyy-MM-dd HH:mm:ss), open, high, low, close, volume

Strategy (evolved from pine/mes_orb_v1.pine):
- ORB = first 5-min bar at 9:30 ET (regular session open)
- Long: breakout above ORB high + retest + prior-day bias (ORB > prev close)
- Short: breakdown below ORB low + retest + prior-day bias (ORB < prev close)
- Filters: 200-day SMA regime, ATR vol regime (0.3-2.0%), ORB range (0.3-1.0%)
- SL = configurable fraction of ORB range, TP = R:R × risk
- One trade per day, 2 contracts
- VWAP/EMA confluence removed in Run 008 (zero selectivity on ES)

Contract specs used in this backtest:
  ES  (E-mini):  $50/point, $2.25/contract commission
  MES (Micro):   $5/point,  $0.62/contract commission
  Both share the same tick size (0.25), price feed, and ORB levels.
  Win rate and profit factor are identical; dollar P&L scales 10:1.

Current backtest uses 1 MES contract (qty_value = 1 × $5 = 5).
Standardized to 1 MES from Run 010 onwards.

Known limitations (deferred — revisit after Run 009):
- Item 4:  generate_es_6months Monday branch is a no-op (synthetic data, legacy)
- Item 5:  mes_orb_signals has 16+ params — should be a StrategyConfig dataclass
- Item 6:  Commission uses avg price across full dataset (inaccurate at extremes)
- Item 7:  Daily filters recomputed per run_single call (could be cached)
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


# ── Contract specs ────────────────────────────────────────────────────────
ES_MULTIPLIER = 50.0    # $50 per point for ES (E-mini)
MES_MULTIPLIER = 5.0    # $5 per point for MES (Micro)
CONTRACTS = 1
TICK = 0.25             # ES/MES tick size

# Active config — 1 MES contract (standardized Run 010 onwards)
POINT_VALUE = MES_MULTIPLIER
COMMISSION_PER_CONTRACT = 0.62   # MES per side

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
    """Load ES futures 5-min data with Eastern-time datetime timestamps.

    Handles two formats:
    - With header row (timestamp,open,high,low,close,volume)
    - Without header row (FirstRateData .txt — positional columns)
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

    # Detect header: read first line
    with open(filepath, "r") as f:
        first = f.readline().strip()
    has_header = first.startswith("timestamp") or first.startswith("date")

    if has_header:
        df = pd.read_csv(filepath, parse_dates=["timestamp"])
        df.set_index("timestamp", inplace=True)
        df.rename(columns={
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume",
        }, inplace=True)
    else:
        # FirstRateData format: no header, positional columns
        df = pd.read_csv(
            filepath, header=None,
            names=["timestamp", "Open", "High", "Low", "Close", "Volume"],
            parse_dates=["timestamp"],
        )
        df.set_index("timestamp", inplace=True)

    return df


# ---------------------------------------------------------------------------
# Pre-computed daily filters (no look-ahead)
# ---------------------------------------------------------------------------

def compute_prior_day_hl(df):
    """Compute prior day's RTH high, low, and close, mapped to intraday bars.

    RTH = 9:30-16:00 ET.  Returns (prior_high, prior_low, prior_close) numpy
    arrays aligned to df.index.  Each bar sees the PREVIOUS completed
    session's values (no look-ahead).
    """
    rth = df[((df.index.hour == 9) & (df.index.minute >= 30))
             | ((df.index.hour >= 10) & (df.index.hour < 16))]

    daily_high  = rth["High"].groupby(rth.index.date).max()
    daily_low   = rth["Low"].groupby(rth.index.date).min()
    daily_close = rth["Close"].groupby(rth.index.date).last()
    daily_high.index  = pd.to_datetime(daily_high.index)
    daily_low.index   = pd.to_datetime(daily_low.index)
    daily_close.index = pd.to_datetime(daily_close.index)

    # Shift by 1 → today sees yesterday's RTH H/L/C
    prev_high  = daily_high.shift(1)
    prev_low   = daily_low.shift(1)
    prev_close = daily_close.shift(1)

    bar_dates = pd.to_datetime(df.index.date)
    return (prev_high.reindex(bar_dates).values,
            prev_low.reindex(bar_dates).values,
            prev_close.reindex(bar_dates).values)


def compute_atr_vol(df, period=10):
    """Compute N-day ATR as % of price, mapped to intraday bars.

    Uses daily true range on RTH OHLC.  Returns numpy array where each
    bar gets the PREVIOUS day's ATR% (no look-ahead).
    Default period=10 (faster, more responsive to regime shifts).
    """
    rth = df[((df.index.hour == 9) & (df.index.minute >= 30))
             | ((df.index.hour >= 10) & (df.index.hour < 16))]

    daily_high  = rth["High"].groupby(rth.index.date).max()
    daily_low   = rth["Low"].groupby(rth.index.date).min()
    daily_close = rth["Close"].groupby(rth.index.date).last()

    daily_high.index  = pd.to_datetime(daily_high.index)
    daily_low.index   = pd.to_datetime(daily_low.index)
    daily_close.index = pd.to_datetime(daily_close.index)

    prev_close = daily_close.shift(1)
    tr = pd.concat([
        daily_high - daily_low,
        (daily_high - prev_close).abs(),
        (daily_low - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = tr.rolling(period, min_periods=period).mean()
    atr_pct = (atr / daily_close * 100.0).shift(1)  # previous day's value

    bar_dates = pd.to_datetime(df.index.date)
    return atr_pct.reindex(bar_dates).values


def compute_adx(df, period=14):
    """Compute ADX on daily bars, mapped to intraday bars.

    Standard Wilder ADX: smooth +DM/-DM and TR with Wilder's method
    (equivalent to RMA/SMMA), then ADX = RMA(DX).
    Returns numpy array where each bar gets the PREVIOUS day's ADX
    (no look-ahead).
    """
    rth = df[((df.index.hour == 9) & (df.index.minute >= 30))
             | ((df.index.hour >= 10) & (df.index.hour < 16))]

    daily_high  = rth["High"].groupby(rth.index.date).max()
    daily_low   = rth["Low"].groupby(rth.index.date).min()
    daily_close = rth["Close"].groupby(rth.index.date).last()
    daily_high.index  = pd.to_datetime(daily_high.index)
    daily_low.index   = pd.to_datetime(daily_low.index)
    daily_close.index = pd.to_datetime(daily_close.index)

    prev_high  = daily_high.shift(1)
    prev_low   = daily_low.shift(1)
    prev_close = daily_close.shift(1)

    # +DM / -DM
    up_move   = daily_high - prev_high
    down_move = prev_low - daily_low
    plus_dm   = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm  = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    # True Range
    tr = pd.concat([
        daily_high - daily_low,
        (daily_high - prev_close).abs(),
        (daily_low - prev_close).abs(),
    ], axis=1).max(axis=1)

    # Wilder smoothing (RMA)
    def _rma(series, length):
        arr = np.array(series, dtype=float)
        out = np.full_like(arr, np.nan)
        # Seed with SMA
        first_valid = 0
        while first_valid < len(arr) and np.isnan(arr[first_valid]):
            first_valid += 1
        if first_valid + length > len(arr):
            return out
        out[first_valid + length - 1] = np.nanmean(arr[first_valid:first_valid + length])
        for i in range(first_valid + length, len(arr)):
            out[i] = (out[i - 1] * (length - 1) + arr[i]) / length
        return out

    atr_smooth   = _rma(tr, period)
    plus_smooth  = _rma(plus_dm, period)
    minus_smooth = _rma(minus_dm, period)

    # +DI / -DI / DX / ADX
    with np.errstate(invalid="ignore"):
        plus_di  = np.where(atr_smooth > 0, plus_smooth / atr_smooth * 100, 0)
        minus_di = np.where(atr_smooth > 0, minus_smooth / atr_smooth * 100, 0)
        di_sum   = plus_di + minus_di
        dx = np.where(di_sum > 0, np.abs(plus_di - minus_di) / di_sum * 100, 0)
    adx = _rma(dx, period)

    adx_series = pd.Series(adx, index=daily_high.index)
    adx_prev = adx_series.shift(1)  # previous day's value

    bar_dates = pd.to_datetime(df.index.date)
    return adx_prev.reindex(bar_dates).values


def compute_regime_sma(df, period=200):
    """Compute 200-day SMA from 5-min bars and map back to intraday index.

    Returns a numpy array aligned to df.index where each bar gets the
    PREVIOUS day's SMA value (no look-ahead).  Bars before the SMA has
    warmed up get NaN.
    """
    # Extract daily closes: last bar of each calendar date
    daily = df["Close"].groupby(df.index.date).last()
    daily.index = pd.to_datetime(daily.index)
    sma = daily.rolling(period, min_periods=period).mean()

    # Shift by 1 day → today's bars see yesterday's SMA (no look-ahead)
    sma_prev = sma.shift(1)

    # Map back to intraday: each bar gets the SMA for its date
    bar_dates = pd.to_datetime(df.index.date)
    regime = sma_prev.reindex(bar_dates).values
    return regime


# ---------------------------------------------------------------------------
# Signal generator — stateful, matches pine/mes_orb_v1.pine
# ---------------------------------------------------------------------------

def mes_orb_signals(df, ema_len=9, retest_ticks=2, rr_ratio=2.0,
                    min_orb_pct=0.0, max_orb_pct=999.0,
                    min_orb_range=0.0, max_orb_range=9999.0,
                    max_entry_hour=16, sl_frac=1.0,
                    regime_sma=None,
                    prior_day_high=None, prior_day_low=None,
                    prior_day_close=None, bias_mode="close",
                    atr_vol_pct=None,
                    min_atr_pct=0.0, max_atr_pct=999.0,
                    adx_values=None, min_adx=0.0):
    """
    MES Opening Range Breakout signal generator.

    Core logic (pine/mes_orb_v1.pine):
      1. ORB = first 5-min bar at 9:30 ET
      2. Post-ORB: detect breakout above ORB high or below ORB low
      3. Retest: price returns to ORB level within tolerance
      4. Entry with TP/SL set at signal time
      5. One trade per day; flatten at session end (15:55 ET)

    Confluence filters:
      - prior_day bias (bias_mode):
          "hl"    — Run 008: ORB high > prior day HIGH (gap), ORB low < prior day LOW
          "close" — Run 009: ORB high > prior day CLOSE, ORB low < prior day CLOSE
      - atr_vol_pct + min/max_atr_pct: ATR% vol filter.
      - regime_sma: 200-day SMA directional filter.
      - adx_values + min_adx: ADX trend quality filter (Run 010).
        Only trade when ADX > min_adx (trending, not choppy).
    """
    if bias_mode not in ("close", "hl"):
        raise ValueError(f"Invalid bias_mode '{bias_mode}'. Expected 'close' or 'hl'.")

    df = df.copy()
    n = len(df)

    # --- Indicators ---
    # Removed in Run 008 — VWAP/EMA replaced by prior-day bias + ATR vol filters
    # df["ema9"] = calc_ema(df["Close"], ema_len)
    # df["hlc3"] = (df["High"] + df["Low"] + df["Close"]) / 3.0

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

        # ── 3. ORB tracking ───────────────────────────────────────────
        if is_orb[i]:
            if not orb_set:
                orb_high = highs[i]
                orb_low  = lows[i]
            else:
                orb_high = max(orb_high, highs[i])
                orb_low  = min(orb_low, lows[i])
            orb_set = True

        # ── 4. Session VWAP (disabled — Run 008 removed VWAP filter) ─
        # if is_sess[i] and volumes[i] > 0:
        #     cum_tpv += hlc3[i] * volumes[i]
        #     cum_vol += volumes[i]
        #     vwap = cum_tpv / cum_vol

        # ── 5. Post-ORB breakout detection ────────────────────────────
        post_orb = orb_set and not is_orb[i] and is_sess[i]

        if post_orb and not np.isnan(orb_high):
            if closes[i] > orb_high:
                broke_above = True
            if closes[i] < orb_low:
                broke_below = True

        # ── 6. Retest + confluence + filters ─────────────────────────
        retest_tol = retest_ticks * TICK   # e.g. 2 ticks × 0.25 = 0.50 pts

        # ORB range filters (percentage-based + legacy absolute)
        orb_width = (orb_high - orb_low) if not np.isnan(orb_high) else 0.0
        orb_mid = (orb_high + orb_low) / 2.0 if not np.isnan(orb_high) else 1.0
        orb_pct = (orb_width / orb_mid * 100.0) if orb_mid > 0 else 0.0

        range_ok = (not np.isnan(orb_high)
                    and orb_pct >= min_orb_pct
                    and orb_pct <= max_orb_pct
                    and orb_width >= min_orb_range
                    and orb_width <= max_orb_range)
        time_ok = hours[i] < max_entry_hour

        # Regime filter: longs above 200-day SMA, shorts below
        if regime_sma is not None:
            sma_val = regime_sma[i]
            long_regime  = not np.isnan(sma_val) and closes[i] > sma_val
            short_regime = not np.isnan(sma_val) and closes[i] < sma_val
        else:
            long_regime = True
            short_regime = True

        # Prior-day directional bias
        if prior_day_high is not None:
            if bias_mode == "close" and prior_day_close is not None:
                # Run 009: ORB vs prior close (relaxed — momentum, not gap)
                pdc = prior_day_close[i]
                long_bias  = (not np.isnan(pdc) and not np.isnan(orb_high)
                              and orb_high > pdc)
                short_bias = (not np.isnan(pdc) and not np.isnan(orb_low)
                              and orb_low < pdc)
            else:
                # Run 008: ORB vs prior high/low (strict gap)
                pdh = prior_day_high[i]
                pdl = prior_day_low[i]
                long_bias  = (not np.isnan(pdh) and not np.isnan(orb_high)
                              and orb_high > pdh)
                short_bias = (not np.isnan(pdl) and not np.isnan(orb_low)
                              and orb_low < pdl)
        else:
            long_bias = True
            short_bias = True

        # ATR% volatility filter (replaces VIX)
        if atr_vol_pct is not None:
            av = atr_vol_pct[i]
            vol_ok = (not np.isnan(av) and av >= min_atr_pct
                      and av <= max_atr_pct)
        else:
            vol_ok = True

        # ADX trend quality filter (Run 010)
        if adx_values is not None:
            adx_val = adx_values[i]
            trend_ok = not np.isnan(adx_val) and adx_val >= min_adx
        else:
            trend_ok = True

        long_ok = (
            broke_above and not traded_today and post_orb
            and position == 0 and range_ok and time_ok
            and long_regime and long_bias and vol_ok and trend_ok
            and lows[i] <= orb_high + retest_tol
            and closes[i] > orb_high
        )

        short_ok = (
            broke_below and not traded_today and post_orb
            and position == 0 and range_ok and time_ok
            and short_regime and short_bias and vol_ok and trend_ok
            and highs[i] >= orb_low - retest_tol
            and closes[i] < orb_low
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

def run_single(df_raw, ema_len=9, retest_ticks=2, rr_ratio=1.0,
               min_orb_pct=0.0, max_orb_pct=999.0,
               min_orb_range=0.0, max_orb_range=9999.0,
               max_entry_hour=16, sl_frac=0.5,
               use_regime=False, use_prior_day=False,
               bias_mode="close", atr_period=10,
               use_atr_vol=False, min_atr_pct=0.0, max_atr_pct=999.0,
               use_adx=False, min_adx=0.0,
               verbose=True):
    """Run one ORB backtest with the given parameters. Returns kpis dict."""
    regime_sma = compute_regime_sma(df_raw) if use_regime else None
    if use_prior_day:
        pdh, pdl, pdc = compute_prior_day_hl(df_raw)
    else:
        pdh = pdl = pdc = None
    atr_vol = compute_atr_vol(df_raw, period=atr_period) if use_atr_vol else None
    adx_arr = compute_adx(df_raw) if use_adx else None

    df = mes_orb_signals(df_raw.copy(), ema_len=ema_len,
                         retest_ticks=retest_ticks, rr_ratio=rr_ratio,
                         min_orb_pct=min_orb_pct, max_orb_pct=max_orb_pct,
                         min_orb_range=min_orb_range,
                         max_orb_range=max_orb_range,
                         max_entry_hour=max_entry_hour,
                         sl_frac=sl_frac,
                         regime_sma=regime_sma,
                         prior_day_high=pdh, prior_day_low=pdl,
                         prior_day_close=pdc, bias_mode=bias_mode,
                         atr_vol_pct=atr_vol,
                         min_atr_pct=min_atr_pct, max_atr_pct=max_atr_pct,
                         adx_values=adx_arr, min_adx=min_adx)

    start = str(df_raw.index[0].date())
    end = str(df_raw.index[-1].date() + pd.Timedelta(days=1))

    qty = CONTRACTS * POINT_VALUE   # 1 × $5 = 5 for MES
    comm_per_side = COMMISSION_PER_CONTRACT * CONTRACTS  # $0.62 × 1 = $0.62
    # Approximate pct: comm / (qty × price). At ES ~5000: 0.62/(5×5000) ≈ 0.00248%
    avg_price = df_raw["Close"].mean()
    comm_pct = comm_per_side / (qty * avg_price) * 100 if avg_price > 0 else 0

    config = BacktestConfig(
        initial_capital=25000.0,
        commission_pct=comm_pct,
        slippage_ticks=0,
        qty_type="fixed",
        qty_value=qty,              # 1 contract × $5/point = 5
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
        contract = "ES" if POINT_VALUE == ES_MULTIPLIER else "MES"
        print(f"  Chart Data:        ES 5-min (FirstRateData, Eastern Time)")
        print(f"  Date Range:        {kpis.get('actual_start_date', 'N/A')}"
              f" to {kpis.get('actual_end_date', 'N/A')}")
        print(f"  Initial Capital:   ${config.initial_capital:,.0f}")
        print(f"  Position Size:     {CONTRACTS} {contract} contracts"
              f" (${POINT_VALUE:.0f}/point)")
        print(f"  Commission:        ${COMMISSION_PER_CONTRACT:.2f}/contract"
              f" (${comm_per_side:.2f}/side)")
        print(f"  Slippage:          0 (NOT simulated)")
        print(f"  R:R Ratio:         {rr_ratio} : 1")
        print(f"  EMA Length:        {ema_len}")
        print(f"  Retest Tol:        {retest_ticks} ticks"
              f" ({retest_ticks * TICK:.2f} pts)")
        print(f"  SL Fraction:       {sl_frac:.0%} of ORB range")
        if min_orb_pct > 0 or max_orb_pct < 999:
            print(f"  ORB Range Filter:  {min_orb_pct:.1f}% – {max_orb_pct:.1f}% of price")
        if min_orb_range > 0:
            print(f"  Min ORB Range:     {min_orb_range} pts (absolute)")
        if max_orb_range < 9999:
            print(f"  Max ORB Range:     {max_orb_range} pts (absolute)")
        if use_regime:
            print(f"  Regime Filter:     200-day SMA (long above, short below)")
        if use_prior_day:
            if bias_mode == "close":
                print(f"  Prior Day Filter:  long if ORB high > prev close,"
                      f" short if ORB low < prev close")
            else:
                print(f"  Prior Day Filter:  long if ORB > prev high,"
                      f" short if ORB < prev low")
        if use_atr_vol:
            print(f"  ATR Vol Filter:    {min_atr_pct:.1f}% – {max_atr_pct:.1f}%"
                  f" ({atr_period}-day ATR/price)")
        if use_adx:
            print(f"  ADX Filter:        14-period ADX > {min_adx:.0f}")
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
# Yearly breakdown
# ---------------------------------------------------------------------------

def yearly_breakdown(kpis):
    """Print year-by-year performance and return the dict."""
    trades = [t for t in kpis.get("trades", []) if t.exit_date is not None]
    if not trades:
        print("\n  No closed trades for yearly breakdown.")
        return {}

    years = {}
    for t in trades:
        y = t.entry_date.year
        if y not in years:
            years[y] = {"trades": 0, "wins": 0, "pnl": 0.0,
                        "gross_win": 0.0, "gross_loss": 0.0}
        years[y]["trades"] += 1
        if t.pnl > 0:
            years[y]["wins"] += 1
            years[y]["gross_win"] += t.pnl
        else:
            years[y]["gross_loss"] += abs(t.pnl)
        years[y]["pnl"] += t.pnl

    print("\n  YEARLY BREAKDOWN:")
    print(f"  {'Year':>6}  {'Trades':>6}  {'Wins':>5}  {'Win%':>6}"
          f"  {'PF':>7}  {'PnL':>12}")
    print("  " + "-" * 56)

    sorted_years = sorted(years)
    for y in sorted_years:
        d = years[y]
        wr = d["wins"] / d["trades"] * 100 if d["trades"] > 0 else 0
        pf = (d["gross_win"] / d["gross_loss"]
              if d["gross_loss"] > 0 else 999.0)
        pf_str = f"{pf:.3f}" if pf < 999 else "inf"
        print(f"  {y:>6}  {d['trades']:>6}  {d['wins']:>5}  {wr:>5.1f}%"
              f"  {pf_str:>7s}  ${d['pnl']:>+10,.2f}")

    # Best / worst 3
    by_pnl = sorted(years.items(), key=lambda x: x[1]["pnl"], reverse=True)
    print(f"\n  BEST  3: {', '.join(f'{y} (${d['pnl']:+,.0f})' for y, d in by_pnl[:3])}")
    print(f"  WORST 3: {', '.join(f'{y} (${d['pnl']:+,.0f})' for y, d in by_pnl[-3:])}")

    return years


# ---------------------------------------------------------------------------
# Main — full dataset backtest
# ---------------------------------------------------------------------------

FULL_DATA = Path("/Users/jameslmueller/Projects/mes-orb-strategy"
                 "/data/raw/ES_full_5min_continuous_UNadjusted.txt")


# ---------------------------------------------------------------------------
# Quarter-Kelly post-hoc analysis
# ---------------------------------------------------------------------------

def kelly_analysis(kpis, initial_capital=25000.0):
    """Compute quarter-Kelly equity curve from closed trade log.

    Uses fixed-fraction Kelly: K = W - (1-W)/R, then scales to 25%.
    Applies to PnL as a fraction of equity at the time of each trade.
    """
    trades = [t for t in kpis.get("trades", []) if t.exit_date is not None]
    if not trades:
        print("  No trades for Kelly analysis.")
        return

    wins  = [t.pnl for t in trades if t.pnl > 0]
    losses = [abs(t.pnl) for t in trades if t.pnl <= 0]

    W = len(wins) / len(trades) if trades else 0
    avg_win  = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 1
    R = avg_win / avg_loss if avg_loss > 0 else 0

    kelly_full = W - (1 - W) / R if R > 0 else 0
    kelly_quarter = kelly_full * 0.25

    # Fixed-sizing equity curve (1-contract baseline)
    fixed_equity = [initial_capital]
    for t in trades:
        fixed_equity.append(fixed_equity[-1] + t.pnl)

    fixed_peak = initial_capital
    fixed_max_dd = 0
    for eq in fixed_equity:
        if eq > fixed_peak:
            fixed_peak = eq
        dd = (eq - fixed_peak) / fixed_peak * 100 if fixed_peak > 0 else 0
        if dd < fixed_max_dd:
            fixed_max_dd = dd

    # Quarter-Kelly equity curve: scale each trade's PnL by kelly_quarter
    # Fixed fraction applied directly — no equity-ratio compounding.
    qk_equity = [initial_capital]
    for t in trades:
        scaled_pnl = t.pnl * max(0, kelly_quarter)
        qk_equity.append(qk_equity[-1] + scaled_pnl)

    qk_peak = initial_capital
    qk_max_dd = 0
    for eq in qk_equity:
        if eq > qk_peak:
            qk_peak = eq
        dd = (eq - qk_peak) / qk_peak * 100 if qk_peak > 0 else 0
        if dd < qk_max_dd:
            qk_max_dd = dd

    print(f"\n  KELLY POSITION SIZING ANALYSIS")
    print(f"  " + "-" * 50)
    print(f"  Win Rate (W):       {W:.4f} ({W*100:.1f}%)")
    print(f"  Avg Win/Loss (R):   {R:.4f}")
    print(f"  Full Kelly:         {kelly_full:.4f} ({kelly_full*100:.1f}%)")
    print(f"  Quarter Kelly:      {kelly_quarter:.4f} ({kelly_quarter*100:.1f}%)")
    print()
    print(f"  {'':20s}  {'Fixed 1x':>12s}  {'Quarter Kelly':>14s}")
    print(f"  {'':20s}  {'-'*12:>12s}  {'-'*14:>14s}")
    print(f"  {'Final Equity':20s}  ${fixed_equity[-1]:>11,.2f}"
          f"  ${qk_equity[-1]:>13,.2f}")
    print(f"  {'Net P&L':20s}  ${fixed_equity[-1]-initial_capital:>+11,.2f}"
          f"  ${qk_equity[-1]-initial_capital:>+13,.2f}")
    print(f"  {'Max Drawdown':20s}  {fixed_max_dd:>11.2f}%"
          f"  {qk_max_dd:>13.2f}%")
    print(f"  {'Return':20s}  "
          f"{(fixed_equity[-1]/initial_capital - 1)*100:>11.1f}%"
          f"  {(qk_equity[-1]/initial_capital - 1)*100:>13.1f}%")

    return {
        "W": W, "R": R, "kelly_full": kelly_full, "kelly_quarter": kelly_quarter,
        "fixed_final": fixed_equity[-1], "fixed_max_dd": fixed_max_dd,
        "qk_final": qk_equity[-1], "qk_max_dd": qk_max_dd,
    }


# ---------------------------------------------------------------------------
# Walk-forward validation
# ---------------------------------------------------------------------------

def walk_forward(df_raw, params, train_end="2019-12-31", test_start="2020-01-02"):
    """Split data and run same params on train and test periods.

    Uses strict < / >= to prevent overlap.  Default gap: 2019-12-31
    is last train day, 2020-01-01 is excluded (New Year — no trading),
    2020-01-02 is first test day.
    """
    df_train = df_raw[df_raw.index < pd.Timestamp(train_end) + pd.Timedelta(days=1)]
    df_test  = df_raw[df_raw.index >= test_start]

    orb_train = df_train[(df_train.index.hour == 9) & (df_train.index.minute == 30)]
    orb_test  = df_test[(df_test.index.hour == 9) & (df_test.index.minute == 30)]

    print(f"\n  WALK-FORWARD VALIDATION")
    print(f"  Train: {df_train.index[0].date()} – {df_train.index[-1].date()}"
          f"  ({len(orb_train)} days)")
    print(f"  Test:  {df_test.index[0].date()} – {df_test.index[-1].date()}"
          f"  ({len(orb_test)} days)")
    print()

    print(f"  {'':20s}  {'In-Sample':>14s}  {'Out-of-Sample':>14s}")
    print(f"  {'':20s}  {'(2008-2019)':>14s}  {'(2020-2026)':>14s}")
    print(f"  {'':20s}  {'-'*14:>14s}  {'-'*14:>14s}")

    kpis_train = run_single(df_train, verbose=False, **params)
    kpis_test  = run_single(df_test, verbose=False, **params)

    def _fmt(kpis):
        closed = [t for t in kpis.get("trades", []) if t.exit_date]
        n = len(closed)
        wr = kpis.get("win_rate", 0)
        pf = kpis.get("profit_factor", 0)
        net = kpis.get("net_profit", 0)
        dd = kpis.get("max_drawdown_pct", 0)
        avg = kpis.get("avg_trade", 0)
        return n, wr, pf, net, dd, avg

    n_tr, wr_tr, pf_tr, net_tr, dd_tr, avg_tr = _fmt(kpis_train)
    n_te, wr_te, pf_te, net_te, dd_te, avg_te = _fmt(kpis_test)

    print(f"  {'Trades':20s}  {n_tr:>14d}  {n_te:>14d}")
    print(f"  {'Win Rate':20s}  {wr_tr:>13.1f}%  {wr_te:>13.1f}%")
    pf_tr_s = f"{pf_tr:.3f}" if pf_tr < 999 else "inf"
    pf_te_s = f"{pf_te:.3f}" if pf_te < 999 else "inf"
    print(f"  {'Profit Factor':20s}  {pf_tr_s:>14s}  {pf_te_s:>14s}")
    print(f"  {'Net Profit':20s}  ${net_tr:>+12,.2f}  ${net_te:>+12,.2f}")
    print(f"  {'Max Drawdown':20s}  {abs(dd_tr):>13.1f}%  {abs(dd_te):>13.1f}%")
    print(f"  {'Avg Trade':20s}  ${avg_tr:>+12,.2f}  ${avg_te:>+12,.2f}")

    return {"train": kpis_train, "test": kpis_test}


# ---------------------------------------------------------------------------
# Main — Run 010: ADX trend quality filter
# ---------------------------------------------------------------------------

def main():
    data_path = FULL_DATA if FULL_DATA.exists() else SAMPLE_DATA
    print(f"Loading {data_path.name} ...")
    df_raw = load_es_data(data_path)

    orb_bars = df_raw[(df_raw.index.hour == 9) & (df_raw.index.minute == 30)]
    print(f"Data:  {data_path.name}")
    print(f"Range: {df_raw.index[0]} to {df_raw.index[-1]}")
    print(f"Bars:  {len(df_raw):,}")
    print(f"Trading days: {len(orb_bars):,}")
    print(f"Contract:  1 MES ($5/point, $0.62 commission)")

    # Run 009 baseline params (no ADX)
    params_009 = dict(
        rr_ratio=1.0, sl_frac=0.5, retest_ticks=2,
        min_orb_pct=0.3, max_orb_pct=1.0,
        use_regime=True,
        use_prior_day=True, bias_mode="close",
        use_atr_vol=True, atr_period=10,
        min_atr_pct=0.3, max_atr_pct=2.0,
    )

    # ── 1. Run 009 repro (1 MES, no ADX) ─────────────────────────────
    print("\n" + "#" * 64)
    print("  RUN 009 REPRO  (1 MES, no ADX)")
    print("#" * 64)
    kpis_009 = run_single(df_raw, verbose=True, **params_009)
    yearly_breakdown(kpis_009)

    # ── 2. ADX threshold ablation: 15, 20, 25 ────────────────────────
    print("\n\n" + "#" * 64)
    print("  ADX THRESHOLD ABLATION")
    print("#" * 64)

    print(f"\n  {'ADX':>4}  {'Trades':>6}  {'Win%':>6}  {'PF':>7}"
          f"  {'Net $':>10}  {'MaxDD%':>7}  {'Avg$':>8}")
    print("  " + "-" * 60)

    adx_results = {}
    for adx_thresh in [15, 20, 25]:
        params = dict(**params_009, use_adx=True, min_adx=adx_thresh)
        kpis = run_single(df_raw, verbose=False, **params)
        closed = [t for t in kpis.get("trades", []) if t.exit_date]
        pf = kpis.get("profit_factor", 0)
        pf_str = f"{pf:.3f}" if pf < 999 else "inf"
        print(f"  {adx_thresh:>4}  {len(closed):>6}  "
              f"{kpis.get('win_rate', 0):>5.1f}%  {pf_str:>7s}"
              f"  {kpis.get('net_profit', 0):>+10,.2f}"
              f"  {abs(kpis.get('max_drawdown_pct', 0)):>6.2f}%"
              f"  {kpis.get('avg_trade', 0):>+8,.2f}")
        adx_results[adx_thresh] = kpis

    # Find best by PF among those with trades
    best_adx = max(adx_results, key=lambda k: adx_results[k].get("profit_factor", 0))
    print(f"\n  BEST ADX threshold: {best_adx}")

    # ── 3. Detailed run of best ADX ──────────────────────────────────
    print("\n\n" + "#" * 64)
    print(f"  RUN 010  (ADX > {best_adx})")
    print("#" * 64)
    params_010 = dict(**params_009, use_adx=True, min_adx=best_adx)
    kpis_010 = run_single(df_raw, verbose=True, **params_010)
    yearly_breakdown(kpis_010)

    # ── 4. Walk-forward on best ADX ──────────────────────────────────
    print("\n\n" + "#" * 64)
    print(f"  WALK-FORWARD: Train 2008-2019 / Test 2020-2026 (ADX>{best_adx})")
    print("#" * 64)
    wf = walk_forward(df_raw, params_010)

    return kpis_010


if __name__ == "__main__":
    main()

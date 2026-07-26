# WIT-P1a — Recon Report (backfilled from session 2026-07-26)

## 1. Dataset facts
- File: `api/data/ES_full_5min_continuous_UNadjusted.parquet` (19 MB, float32 OHLC + int32 Volume; index timestamp, datetime64[us], tz-naive).
- Timezone: US Eastern Time — authoritative, stated verbatim in `data/raw/README_firstratedata.txt` ("Timezone is US Eastern Time"). Index tz-naive but wall-clock ET; bars stamped at period start (09:30 bar = 09:30:00–09:34:59).
- Span: 2008-01-02 06:00 → 2026-04-09 18:30 ET. 1,289,036 bars, 5,681 trading days.
- RTH coverage (09:30–15:55 ET): 361,309 bars = 28% of file. 96.7% of days have the full 78 RTH 5-min bars; 157 partial days (half-days/holidays). ORB profile window [09:30,09:45) = exactly 3 bars on 4,707/4,710 days.
- Finest granularity found: **1-minute data exists** — `data/raw/ES_full_1min_continuous_UNadjusted.txt` (334 MB, Git-LFS, materialized). Span 2008 → 2026-04-10, 6,390,913 bars, 15 one-min bars in the 09:30–09:45 profile window. No tick data anywhere. Decisive for the volume profile (WIT-T-0001 §B3).

## 2. Environment
- Engine importable: Y. Pinned `api/.venv` on Python 3.12.13 (ADR-050). Parquet readable: Y. `backtester` validation lib importable. No blockers.
- Driving the engine without modification: the engine is signal-column-driven. `run_backtest(df, config)` requires Open/High/Low/Close/long_entry/long_exit; `run_backtest_long_short` adds short columns. It already reads per-row `sl_price`, `tp_price`, `sl_offset`, `tp_offset` (engine.py:778–882), and `process_orders_on_close=True` fills at the signal bar's Close — matching the guru's "enter as the candle closes." Per-day POC stops + 2R targets need zero engine edits.

## 3. Implementation plan (as approved)
Files (all additive): `api/wit/__init__.py`, `api/wit/volume_profile.py`, `api/wit/vp_orb_runner.py`, `api/wit/config.py`, `api/tests/test_vp_orb.py`.
- VP method: profile from 1-min bars (15 in window), volume spread across each bar's High–Low span in 0.25 rows; POC = max-volume row; VA = smallest contiguous 70% band around POC. 5-min VP as fallback/sensitivity. Approximation disclosed (no tick path).
- Runner: per RTH day → VP → first 5-min candle closing through VAH (long-only day) / VAL (short-only) → entry at close, sl/tp per-row columns, max 1 trade/day, force-flat, stop-first → `run_backtest_long_short`. Costs $0.62/side + 1 tick.
- Stats: existing `backtester` stack — validate + run_bootstrap (seed 42, 10k), per-year/regime tables.
- Sweeps: entry close-vs-body; slippage 0/1/2; same-bar policy (+1-min-vs-5-min VP).

## 4. Open questions → lead-engineer decisions
1. Window truncation (data ends 2026-04-09) → **true 10-year 2016-04-10 → 2026-04-09**; full-history secondary.
2. Proxy → **ES confirmed** (not NQ), disclosed.
3. Short-stop mirror → **confirmed POC + 2 ticks**.
4. VP granularity → **1-min canonical**, 5-min as sensitivity.

WIT-P1a — Completed

# ADR-035 — Ship full 18-year history to the live engine via Parquet

**Status:** Accepted (v25.10.0)

**Context:** The deployed engine ran on a 6-month CSV test fixture because the full 18-year CSV
(~68 MB, 1,289,036 rows) isn't in the deploy context, and loading it as CSV ran Railway out of
memory (timestamp parsing + float64 spike). That capped the live engine's statistical power to one
recent bull regime and made its validation (walk-forward, regimes, random-entry) underpowered.

**Decision:** Convert the CSV to a compact, pre-parsed **Parquet** committed into `api/data/` so it
ships with the deploy, and add a Parquet branch to the loader.

- **`scripts/csv_to_parquet.py`** reads the CSV with the same logic as `load_firstrate_data`
  (no header; `timestamp,Open,High,Low,Close,Volume` → `DatetimeIndex`), downcasts OHLC to
  **float32** and Volume to **int32**, and writes
  `api/data/ES_full_5min_continuous_UNadjusted.parquet` (snappy). A **mandatory round-trip check**
  asserts every OHLC value equals the CSV **to the tick** (ES prices are multiples of 0.25 and stay
  under ~10k, so float32 is exact); it falls back to float64 and reports if any value mismatches.
- **Loader branch:** `load_firstrate_data` reads `*.parquet`/`*.pq` via
  `pd.read_parquet(engine="pyarrow")` and returns the identical shape (DatetimeIndex + OHLCV). The
  CSV branch is unchanged. `pyarrow` added to runtime `requirements.txt` (fastparquet is a lighter
  alternative if image size matters).
- **`DATA_PATH` default is unchanged** — it stays the 6-month CSV (fast local/test fixture and a
  fail-safe: if the env var is ever unset, prod falls back to the working 6-month file). Production
  overrides `DATA_PATH` to the Parquet path via a Railway env var (Jim's post-merge step).

**Verified locally:**
- Round-trip **exact at float32**. Parquet **18.97 MB**, **1,289,036 rows**, 2008-01-02 → 2026-04-09.
  Commits as a **regular git blob** (no `*.parquet` LFS rule), so Railway gets the real file.
- **Memory** (loading via `get_data()` on the Parquet): DataFrame `memory_usage(deep=True)` ≈
  **34 MB**; process **peak RSS ≈ 266 MB** (full footprint incl. pandas/pyarrow/backtester/scipy).
  A backtest copies the frame (~2×), so transient peak is higher — the number to weigh against the
  Railway plan.
- **Computation on 18 years:** the documented Run-014 ORB reproduces **exactly 91 trades** on the
  Parquet (matches the docs) — proving the pipeline computes correctly over 18 years. The shipped
  API engine core also runs the full 1.29M-bar dataset end-to-end.

**Consequence / operational gates for the prod flip (beyond memory):**
1. **Signal-exec timeout.** `/run` wraps `signal_code` in a **10s SIGALRM timeout**. Python-loop
   helpers (e.g. `calc_ema`) are slow over 1.29M bars and will time out on 18-yr data — the caller
   must use vectorized signals, or the timeout must be raised, before relying on full history via
   `/run`.
2. **Backtest wall time.** A full 18-yr run through the bar-by-bar engine loop takes ~tens of
   seconds (≈54s observed for a high-frequency signal); watch HTTP/Railway request timeouts.

Neither is fixed here (ADR-035 is data-shipping only) — flagged for follow-up.

**RULE:** ship market data as pre-parsed Parquet (downcast, round-trip-verified to the tick), keep
the 6-month CSV as the fail-safe default, and never LFS-track the deployed data file (Railway must
get the real bytes). `DATA_PATH` selects the file; the loader treats `.parquet` and CSV identically.

# ADR-044 — Vectorize the simulation loop's per-bar access + async liveness

**Status:** Accepted (v25.19.0)

## Problem (measured, not guessed)

The engine was **slow, linearly**: on the live engine (v25.18.1, Railway, full 18-yr Parquet), an
ORB 5-minute run with validation OFF took ~**2s fixed + ~0.19s per day** of data:

| Range | Days | Runtime (Railway) |
|---|---|---|
| 1 week | 5 | 2.8 s |
| 1 year | 365 | **70 s** |
| 6 years | 2,191 | never finished (stuck at progress=50, 21+ min) |

> Retraction: an earlier "falls off a cliff between 450 and 2,191 days / OOM" theory was **wrong** —
> it came from a run whose title said 450 days but which only ever processed 6 months of the old
> 6-month test file. The real issue is base speed, and it scales linearly into unusability.

ADR-036/041 vectorized the **indicator helpers**, so a 70s/year run was surprising — something in the
hot path was still per-bar. A `cProfile` of a 1-year run found it: ~100% of the loop time was **pandas
per-bar access**, not arithmetic —

- `internals/managers.py:fast_xs` (70,608 calls = one per bar) — `bar = df.iloc[i]` builds a Series
  every iteration,
- `arrays/datetimelike.__getitem__` (4.3s cumtime) — `df.index[i]`,
- `series.__getitem__` / `_get_value` — every `bar["col"]` scalar lookup,

plus the Python-3.14 annotation/`isinstance` machinery those trigger (millions of calls).

## Decision

In **both** `run_backtest` and `run_backtest_long_short`, extract each needed column to a numpy array
**once** before the loop and index by `i`; the simulation stays a sequential loop (fills/equity are
path-dependent) but each iteration does O(1) native access instead of building a Series.

- Prices/signals/optional columns via `df["col"].to_numpy()` — **native dtype** (no forced `float`).
  This is the key to byte-identity: `df.iloc[i]` produced an **object** row Series (mixed
  float32/int32/bool can't share a numeric type), so `bar["Open"]` was the column's native scalar
  (float32 on the parquet). Native-dtype arrays reproduce that exactly; forcing float64 shifted
  results by ~1e-6 (float32→float64) and was rejected.
- `_dates = df.index.tolist()` — materialize Timestamps once (avoids per-bar `index[i]`).
- `_in_range = np.asarray((df.index >= start) & (df.index <= end))` — the inclusive gate as one
  vectorized mask.

**Result-preserving — verified byte-identical** vs the pre-ADR-044 engine on a full year across
long-only + long/short, TP-SL, %-equity and no-stop configs: every KPI, every trade
(dates/prices/pnl/commissions), and every equity-curve point matched exactly, float32 dtype preserved.
Committed guard: `test_engine_vectorized.py` (golden snapshot + float32/float64 dtype preservation).

**Speed: ~15×.** 1-yr 2.88s → 0.19s, 6-yr 17.7s → 1.2s (locally). Extrapolating to Railway (~25×
slower absolute): 1-yr ~70s → ~5s, and the 6-yr that never finished → tens of seconds. This also
matters for the **sync** `/run` and `/run/compare`, which a 70s/year run pushed past Railway's ~60s
proxy timeout — now well under.

## Async liveness (a run that stalled went silent)

Run `3d034e96-…` stalled at `progress=50` and never posted another callback. `_run_async_job` now:

- **Always reaches a terminal state** — success → `complete`; any error OR uncaught crash → `failed`
  with the **traceback** (truncated to 2000 chars). It never exits silently.
- **Heartbeat** — while the compute runs off the event loop, the job re-posts `{status: running,
  progress}` every `ASYNC_HEARTBEAT_SECONDS` (env, default **5**). Progress alone only moves at stage
  boundaries, so a stall *inside* a stage was invisible; the heartbeat bumps the row's `updated_at`
  so the app-side watchdog can drop from a 10-minute timeout to 2–3 minutes.

Railway OOM check (secondary, per the retraction): not accessible from Claude Code (no Railway
CLI/dashboard here) — flagged for Jim. With the ~15× speedup the 6-yr run now completes in tens of
seconds, so memory pressure at that size is far less likely to be reached in the first place.

**RULE:** the simulation loop must never touch the DataFrame per bar (`df.iloc[i]` / `bar["col"]`) —
extract columns to native-dtype numpy arrays once and index by `i`. Vectorizing engine internals ships
only after a before/after **byte-identical** check (native dtype preserved). The async job must always
post a terminal callback and heartbeat while alive.

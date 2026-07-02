# ADR-036 — Vectorize `calc_ema` (remove the 10s signal-exec cap)

**Status:** Accepted (v25.11.0)

**Context:** `calc_ema` in `api/engine/engine.py` computed the EMA one row at a time in a Python
loop. Over full history that is slow enough to trip the 10-second signal-execution timeout
(`SIGNAL_EXEC_TIMEOUT`, `api/server.py`), which capped a live backtest at ~5–6 years (PERF-MEASURE:
5 yr = 8.5s signal step, 10 yr = 17s, 18 yr = 31s — the 10s cap crossed around ~6 yr). The
vectorized equivalent, `series.ewm(..., adjust=False).mean()`, is ~1000× faster.

**This is a speed change, NOT a results change** — the trades a backtest produces must not move.

**Decision:** Replace the per-row **recurrence** in `calc_ema` with a vectorized `ewm`, matching the
existing semantics exactly:
- **SMA seed preserved.** `calc_ema` seeds the EMA with the **SMA of the first `length` valid
  values** (matching `ta.ema()`), not the first value. A naive `ewm(adjust=False)` seeds from the
  first value and would shift early bars → different trades. Fix: build a post-seed series whose
  first element **is** the SMA seed and feed it to `ewm(alpha=2/(length+1), adjust=False).mean()` —
  `ewm` then reproduces the exact recurrence `ema[i] = mult·x[i] + (1−mult)·ema[i−1]` from the SMA
  seed.
- **NaN carry-forward preserved.** When the post-seed region contains NaN gaps (chained indicators),
  the loop "holds" the EMA flat across the gap (Pine behavior) — `ewm` can't express that, so the
  **exact per-row loop is kept for that uncommon case**. The common price-series path (no NaN) takes
  the vectorized branch.
- **Signature unchanged**, so every caller (including AI-generated signal code) gets the speedup
  transparently. The seed-finding scan is kept (it breaks within the first `length` bars — it was
  never the hot path).

**Verified (the gate):**
- **Value equivalence to the tick** on 18 yr of real ES Close: `max|diff|` ≈ **1e-12** across spans
  9/21/50/200 — far under half a tick (0.125); tick-rounded values identical.
- **Trade identity (the critical test):** a full EMA-crossover backtest **before (loop) vs after
  (vectorized)** on **5-yr and 10-yr** ranges produced **byte-identical trade lists** — same trade
  count (15,960 / 32,435), same entry/exit bars & prices, same net P&L.
- **Speed:** the 18-yr signal step (two `calc_ema` calls) dropped from **30.67s → 0.034s (~894×)** —
  well under the 10s signal cap.
- Existing suite green + new `test_calc_ema.py` pinning the vectorized output to the reference
  recurrence to the tick (incl. SMA-seed and NaN-gap cases).

**Consequence:** The 10s signal timeout no longer binds on EMA-based signals at any history length
(18-yr signal step ~0.03s). The remaining full-history cost is the bar-by-bar backtest **engine
loop** (~tens of seconds), which is separate and unchanged. `__version__` → **25.11.0**. No behavior
change — trades are identical.

**Follow-ups (other per-row indicator loops — NOT vectorized here; each needs its own trade-identity
proof):**
- `calc_smma` — identical SMA-seed + EMA-recurrence + NaN-carry pattern (`alpha = 1/length`); the
  same seed-matched `ewm` technique applies directly.
- `calc_obv` — trivial `sign(close.diff())·volume).cumsum()` vectorization.
- `calc_wma` — uses a rolling `.apply` callback (slower than pure-vectorized, but not the calc_ema
  bottleneck).
The two large `for i in range(len(df))` loops are the backtest engine itself — a much larger,
separate effort, out of scope.

**RULE:** vectorizing an indicator helper is a **speed** change only — it ships **only** after a
before/after **trade-identity** proof (identical count, entries, exits, net) on multi-year real data.
Preserve exact seeding (SMA, not first value) and NaN carry-forward; keep the loop fallback where
`ewm` can't match.

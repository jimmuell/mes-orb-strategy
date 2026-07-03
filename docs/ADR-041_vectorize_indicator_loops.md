# ADR-041 — Vectorize the remaining indicator loops (calc_smma / calc_wma / calc_obv)

**Status:** Accepted (v25.16.0)

**Problem:** ADR-036 vectorized `calc_ema` (30s → 0.03s over 18yr, tick-identical). Three sibling
indicator helpers were left on per-row Python loops (`calc_smma`, `calc_obv`) or a per-window
`rolling().apply()` (`calc_wma`) — the last un-vectorized indicator loops, slow over the 1.29M-bar
full-history dataset. This wires them up the same way. **No numeric behavior changes** — the existing
loop is the source of truth; the vectorized versions must match it to floating-point epsilon.

**Decision — the equivalences (all in `api/engine/engine.py` only; the stale `backtest/engine`
duplicate is left untouched):**

- **`calc_smma` → `ewm(alpha=1/length, adjust=False)`.** RMA/Wilder's recurrence
  `smma[i] = (smma[i-1]·(length-1) + src[i]) / length` is algebraically an EMA with `alpha = 1/length`.
  Same technique as ADR-036: seed with the SMA of the first `length` valid values, then feed a
  post-seed series whose first element **is** that seed to `ewm` so it reproduces the recurrence
  exactly. NaN carry-forward (Pine "hold flat" across gaps) can't be expressed by `ewm`, so the exact
  per-row loop is retained for the rare post-seed NaN-gap case; clean series take the vectorized path.

- **`calc_wma` → one sliding-window dot product.** Replace the Python-callback-per-window
  `rolling(min_periods=length).apply(dot)` with `sliding_window_view(vals, length) @ weights / sum`.
  A NaN anywhere in a window propagates to NaN (matmul), matching `rolling`'s NaN handling exactly;
  the first `length-1` rows stay NaN; `n < length` → all NaN.

- **`calc_obv` → `cumsum(sign(diff)·vol)`.** `+vol` when close rises, `-vol` when it falls, `0` on
  ties (`diff[0]=0`, `step[0]=0`), then `cumsum` — bit-for-bit the loop's running sum.

**Verification (`api/tests/test_vectorized_indicators.py`, 10 tests):** each vectorized helper is
compared against a **verbatim copy of its prior loop** (the source of truth) on clean data,
NaN-leading input, an interior-NaN gap (smma/wma), and equal-close ties (obv) — matching to `<=1e-9`.
Over the full 18-yr float32 series the accumulated FP drift is: **obv `max|diff| = 0` (exact)**,
`smma ~3.5e-5` (long-memory recurrence over 1.29M steps) — ~4 orders of magnitude under a 0.25 tick,
i.e. tick-identical.

**Result (18yr, 1.29M bars):**

| Helper | Before | After | Speedup |
|---|---|---|---|
| `calc_smma(14)` | 15,981 ms (loop) | 23 ms | ~693× |
| `calc_obv` | 457 ms (loop) | 17 ms | ~27× (exact) |
| `calc_wma(14)` | seconds (`rolling.apply`) | 10 ms | large |

`__version__` → **25.16.0**. All indicator helpers exposed to signal code are now vectorized.

**RULE:** vectorizing an indicator is a **speed** change only — it ships **only** after matching the
prior loop (the source of truth) to the tick on clean/NaN-leading/interior-gap/tie cases. Preserve
exact seeding (SMA) and NaN carry-forward; keep the loop fallback where `ewm` can't match.

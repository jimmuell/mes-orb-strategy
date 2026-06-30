# ADR-028 — `/run/compare` returns the standard Edge-vs-Luck validation (primary result)

**Status:** Accepted.

**Context:** `/run` computes the standard validation verdict (`validate()` + `summarize()` —
the Edge-vs-Luck bootstrap and friends) and returns it as top-level `validation` +
`validation_error`. `/run/compare` (ADR-026/027) never called `validate()`/`summarize()`, so
`CompareResponse` carried no verdict and the app correctly showed "No validation verdict for
this run" for stop runs. The teaching card's `significance` (ADR-027) is a *separate*
statistic (a bootstrap CI on the paired delta) and was unaffected — which is why that card
worked while the standard verdict was blank.

**Decision:** Compute and return the standard validation verdict on `/run/compare` for the
**PRIMARY (user's) config only**, reusing the exact `/run` machinery — no new statistic.

- Gated on `req.run_validation` (default true), mirroring `/run`. When false, `validation`
  is `null` (same as `/run`).
- `_validate_primary(primary_closed, df, validation_iterations)` builds `backtester` Trades
  from the primary result's serialized closed trades and calls
  `validate(bt_trades, bars=_df_to_barset(df), config=ValidationConfig(...))` then
  `summarize()`, serializing the **same** dict `/run` produces (`overall`, `summary`,
  `findings[]` incl. `key="edge_vs_luck"`, `skipped`, `regimes`). Reuses `df` (already
  computed) and the existing helpers — no new machinery.
- Added top-level **`validation`** and **`validation_error`** to `CompareResponse` — same
  field names/shape as `BacktestResponse`, so the app reads `response.validation` identically
  on both endpoints.
- The **variant is NOT validated** — it is a neutralized hypothetical; validating it would
  double the Monte-Carlo cost for no product value.

**Consequence:** Additive — `teaching` / `significance` / `same_signal` / `primary` /
`variants` are byte-identical; the `/run` handler is untouched. The app now shows the
Edge-vs-Luck verdict for stop runs (the primary, authoritative config) just as it does for
normal `/run` backtests. `__version__` → **25.3.0**.

**RULE:** the compare validation reuses `/run`'s validate/summarize/`_df_to_barset` path and
serialized shape — never fork a second validation serializer. Validate the **primary only**;
the variant stays unvalidated by design.

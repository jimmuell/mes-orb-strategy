# ADR-027 — Significance judgment on `/run/compare` teaching deltas (CI on the delta)

**Status:** Accepted.

**Context:** TEACH-COMPARE's `/run/compare` (ADR-026) returns a raw dollar delta between
the user's config (`primary`) and a stop-neutralized `variant`. A raw delta alone can
mislead: a `+$3` delta over 370 trades is noise, but the card would present it as a
confident "your stop saved you $3." The engine should say whether each delta is
**distinguishable from noise**, so the card shows a confident number only when earned and
otherwise says "no meaningful difference." This mirrors the engine's existing **"Edge vs
Luck"** check (95% CI for expectancy) — same method, same language.

**Decision:** Judge each teaching delta with a confidence interval on the **delta itself**,
computed with the **exact same machinery** as the single-run validation — `run_bootstrap`
(`backtester.montecarlo.bootstrap`), the percentile bootstrap that powers the expectancy /
net-profit CIs. No new statistic, no new method.

- Build the per-trade **paired difference** `primary.pnl − variant.pnl`, matched by
  `(entry_date, direction)`. The two runs are same-signal by construction; in the aligned
  case (the stop changes only the exit, e.g. ORB) every entry matches 1:1 and the deltas
  sum to `delta_net`. Trades present in only one run are left unmatched.
- Bootstrap a 95% CI on the **total** paired delta via `run_bootstrap(...).net_profit_ci`
  — the total convention matches the reported `delta_net` (a total $). Same iterations
  (`ValidationConfig.mc_iterations` = 10,000), same seed (42), same CI level (0.95) →
  **deterministic / reproducible**.
- Classify: CI entirely `> 0` → **saved**; entirely `< 0` → **cost**; straddles 0 →
  **inconclusive** (within noise).

Added to each teaching entry (additive — existing fields unchanged):

```json
{
  "delta_ci_low":   "<float>",   // 95% CI lower bound on the (total) delta
  "delta_ci_high":  "<float>",   // 95% CI upper bound
  "significance":   "saved | cost | inconclusive",
  "n_resamples":    "<int>",     // bootstrap iterations (10000), for transparency
  "sufficient_data": "<bool>"    // trade_count >= the validation's low-sample minimum
}
```

`direction` (raw sign of `delta_net`) and `significance` (the judged call) are **both**
kept and can disagree — e.g. `direction="cost"` while `significance="inconclusive"` when a
negative raw delta is not distinguishable from noise.

`sufficient_data` reuses the validation's own low-sample threshold — `ValidationConfig.n_windows`
(= 5), the count below which its temporal-stability checks are skipped for "too few trades"
— rather than inventing a new minimum. It is a separate thin-data flag; the CI is the noise
judgment.

**Consequence:** Additive — `/run` and the existing `/run/compare` fields stay
byte-identical; this only **adds** fields to teaching entries. `/run` single-run path
untouched. The card can now show a confident saved/cost number only when the CI excludes
zero, and "no meaningful difference" otherwise. `__version__` → **25.2.0**.

**RULE:** the significance CI reuses `run_bootstrap` with the validation's seed/iterations/
CI-level — never fork a second resampling implementation or a different statistic. The CI
method has one home, shared with "Edge vs Luck."

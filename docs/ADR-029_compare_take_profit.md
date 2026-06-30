# ADR-029 — Take-profit dimension on TEACH-COMPARE (mirror the stop instance)

**Status:** Accepted.

**Context:** `/run/compare`'s `teaching` field is already a **list of per-dimension blocks**
(ADR-026); the stop dimension was the only block. We want a second, **take-profit** dimension
("what your take-profit did") alongside it. This is additive and non-breaking: the stop block
stays first and unchanged; the take-profit block is appended second.

**Decision:** Mirror the stop instance exactly, as a second teaching/variant block.

- **Neutralizer:** a take-profit-neutralized variant config built the same way as the stop
  variant — `dataclasses.replace(primary_config, take_profit_points=0.0, take_profit_pct=0.0)`
  — so trades run to their natural signal exit / stop instead of capping at TP. Signal, stop,
  slippage, commission, direction, and sizing are all held constant.
- **Same signal:** the take-profit variant is a **third** backtest on the same signal df. The
  `same_signal` invariant now hashes the signal columns after all three runs
  (`h_before == h_mid == h_after == h_after_tp`).
- **Significance:** reused **as-is** — `_delta_significance(_paired_deltas(primary_closed,
  tp_variant_closed))` (the same paired-delta percentile bootstrap, ADR-027; dimension-agnostic).
  `delta_net = primary − tp_variant`: `>0` = TP **saved** (locked in gains that would've been
  given back); `<0` = TP **cost** (capped a winner that would've run). The `saved/cost/
  inconclusive` labels carry over (the frontend rewords for the TP card).
- **Supporting stat — the WINNER side:** where the stop block reports a worst-loss stat
  (`min(pnl)`), the take-profit block reports the winner (`max(pnl)`): `primary_best_win` =
  biggest winner locked in **with** the TP; `variant_best_win` = what that winner would've
  reached **without** the cap.
- **Validation (ADR-028):** unchanged — still **primary-only**; the take-profit variant is
  **not** validated (same rationale as the stop variant: avoids extra Monte-Carlo cost).

**Response shape.** `teaching` is a list of per-dimension blocks: **stop first, take_profit
second**. The take-profit block mirrors the stop block's fields but swaps the worst-loss stat
for the winner stat:

```
{ "dimension": "take_profit",
  "delta_net", "direction", "significance",
  "delta_ci_low", "delta_ci_high", "n_resamples",
  "trade_count", "sufficient_data",
  "primary_best_win", "variant_best_win" }
```

`variants` likewise gains a second entry:
`{ "dimension": "take_profit", "label": "no take-profit",
   "neutralized": {"take_profit_points": 0}, "result": <full result> }`.

**Consequence:** Additive — the stop teaching block and its worst-loss stat are byte-identical
and stay first; `/run`, `same_signal` logic, the significance machinery, and validation are
unchanged. One extra `_serialize_run` pass (a third backtest on the same df) per compare call;
no extra validation. **Downstream coupling:** any consumer that reads `context.teaching` as a
single object must iterate the list (or pick by `dimension`) to show both blocks — a frontend/
edge-function change to land in lockstep, outside this repo. `__version__` → **25.4.0**.

**RULE:** each TEACH-COMPARE dimension is a block in the `teaching` list built by mirroring the
stop instance (neutralizer via `dataclasses.replace`, reused `_serialize_run` /
`_paired_deltas` / `_delta_significance`). Never fork the significance bootstrap per dimension;
never reorder or mutate the stop block when adding dimensions.

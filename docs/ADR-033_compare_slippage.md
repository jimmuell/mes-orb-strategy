# ADR-033 — Slippage dimension on TEACH-COMPARE ("what slippage cost you")

**Status:** Accepted (v25.8.0)

**Context:** `/run/compare`'s `teaching` is a list of per-dimension blocks (ADR-026/029/031/032):
stop, take_profit, commission, direction. We want a **fifth** — **slippage** — answering "how
much did slippage cost you?" Slippage (`slippage_ticks`, the adverse ticks applied to **every**
fill, ADR-024) is an execution cost, so this is the **clean mirror of the commission dimension**.

**Decision:** Mirror the commission instance as a **fifth** teaching/variant block appended after
direction. Stop / take_profit / commission / direction blocks are unchanged.

- **Neutralizer:** `dataclasses.replace(primary_config, slippage_ticks=0)` — the slippage-free
  variant. A sixth `_serialize_run` on the same signal df; `same_signal` now spans all **six** runs.
- **Significance — the standard path (unlike direction):** slippage modifies **every** trade (fills
  move), so the per-trade paired delta is the right sample. Use `_paired_deltas` +
  `_delta_significance` **directly** — no special handling (that was only needed for direction,
  which adds/removes whole trades).
- **Deltas & stats:** `delta_net = primary − variant`; removing adverse slippage can only help or
  leave net unchanged, so `delta_net ≤ 0` → `direction = "cost"` (or `"neutral"` when
  `slippage_ticks == 0`). `total_slippage = variant_net − primary_net` (a positive $ figure — the
  execution cost removed; `delta_net == −total_slippage`). Also carries `slippage_ticks` (for the
  "no slippage set" nudge / display), `flips_profitability`, and `primary_net` / `variant_net`.
  `sufficient_data` reuses the shared total-trades sufficiency.
- **Zero-ticks edge:** `slippage_ticks == 0` → the variant equals the primary → `total_slippage = 0`,
  `delta_net = 0`, `direction = "neutral"`.

**Consequence:** Additive — the prior four blocks and their stats are byte-identical and keep their
order; `/run`, `same_signal` logic, `_serialize_run`, `_paired_deltas`, `_delta_significance`,
`_to_native`, and `_commission_for_side` are untouched. The ADR-031 `_to_native` return chokepoint
already coerces the new numpy-typed fields — no per-field casts. One extra `_serialize_run` pass per
compare call. **Downstream:** `context.teaching` consumers must iterate the list (already required
since ADR-029) to show the fifth block. `__version__` → **25.8.0**.

**RULE:** slippage is an execution-cost mirror of commission — neutralize `slippage_ticks` to 0 and
reuse the standard `_paired_deltas` significance (every trade is modified). Never reorder or mutate
the prior blocks; derive `total_slippage` from the net difference.

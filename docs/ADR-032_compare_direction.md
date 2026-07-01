# ADR-032 — Direction dimension on TEACH-COMPARE ("what your short trades did")

**Status:** Accepted (v25.7.0)

**Context:** `/run/compare`'s `teaching` is a list of per-dimension blocks (ADR-026/029/031):
stop, take_profit, commission. We want a **fourth** — **direction** — answering "what did
trading this side (vs. the other) do for your P&L?" The engine supports exactly **two**
direction values, `long_only` and `long_short` (both sides) — there is **no** short-only mode
and no flip — so the neutralized variant simply **toggles between the two**.

**Decision:** Mirror the prior instances as a **fourth** teaching/variant block, appended after
commission. Stop / take_profit / commission blocks are unchanged.

- **Neutralizer (different from the others):** the other variants pass `req.direction` with a
  modified **config**; direction is the opposite — the **config is unchanged** (`primary_config`),
  the **direction param** is toggled: `long_short ↔ long_only`. A fifth `_serialize_run` on the
  same signal df; `same_signal` now spans all **five** runs.
- **Significance — do NOT use `_paired_deltas`:** stop/take-profit/commission modify *every*
  trade, so their per-trade paired delta is the right sample. Direction is different — toggling
  `long_short ↔ long_only` **adds or removes the short trades while the long trades stay
  identical**. `_paired_deltas` *drops* unmatched trades, so it would drop the shorts (the entire
  effect) and falsely report "inconclusive." Instead the delta **is** the short trades' P&L, so we
  bootstrap the CI **directly over the (signed) short-trade pnls** via `_delta_significance`.
- **Sign convention (reads naturally for BOTH primary cases):** `delta_net = primary − variant`.
    - primary `long_short`: `delta_net` = the shorts' net contribution (shorts made / lost you money).
    - primary `long_only`: `delta_net` = −(the shorts' would-be contribution) → adding shorts would
      have helped → "cost" you (by not doing it); would have hurt → "saved".
  The shorts are pulled from whichever run holds them, signed so they sum to `delta_net`.
- **Supporting stats:** `short_trade_count`, `short_net` (the shorts' own net as traded),
  `flips_profitability` (did the direction choice flip a profitable run into a loss or vice versa),
  plus `primary_direction` / `variant_direction`. `sufficient_data` is judged on the **shorts**
  (the delta's sample) against the same `n_windows` min-trades threshold, not the whole run.
- **Zero-shorts edge:** when there are no short trades (a `long_short` run whose signal only goes
  long, or a `long_only` request whose signal never emitted short columns), the delta sample is
  empty → `short_trade_count = 0`, `delta_net = 0`, `direction = "neutral"`,
  `sufficient_data = False`, significance "inconclusive".

**Robustness note (deviation from the naive spec).** `run_backtest_long_short` requires the
`short_entry`/`short_exit` columns and raises if they're absent. A `long_only` request whose
signal never emitted those columns would make the `long_short` variant raise and — per the
ADR-031 lesson — take down **all** teaching cards with a 500. So the variant run is **guarded**:
if toggling to `long_short` and the short columns are missing, the variant is treated as identical
to the primary (no shorts to add → delta 0 / neutral), rather than run. Production compare signals
emit all four columns, so this is a safety net, not the common path.

**Consequence:** Additive — stop / take_profit / commission blocks and their stats are unchanged
and stay first/second/third; `/run`, `same_signal` logic, `_serialize_run`, `_paired_deltas`,
`_delta_significance`, `_to_native`, and `_commission_for_side` are untouched. The ADR-031
`_to_native` return chokepoint already coerces the new numpy-typed fields — no per-field casts.
One extra `_serialize_run` pass per compare call. **Downstream:** `context.teaching` consumers must
iterate the list (already required since ADR-029) to show the fourth block. `__version__` → **25.7.0**.

**RULE:** direction is the one dimension whose neutralizer toggles the run's *direction param*, not
the config; its significance bootstraps the short trades directly (never `_paired_deltas`); guard
the `long_short` variant against missing short columns. Never reorder or mutate the prior blocks.

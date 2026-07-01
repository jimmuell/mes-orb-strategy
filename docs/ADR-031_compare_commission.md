# ADR-031 — Commission dimension on TEACH-COMPARE (mirror stop / take-profit)

**Status:** Accepted (v25.6.0)

**Context:** `/run/compare`'s `teaching` field is a list of per-dimension blocks
(ADR-026/029): stop first, take_profit second. We want a **third** dimension —
**commission** — that answers "what did commission cost you," and in particular whether
the fees are the reason a setup that *would* have been profitable ended up in the red.

**Decision:** Mirror the stop/take-profit instances exactly, as a **third** teaching/variant
block appended after take_profit. Stop and take_profit blocks are unchanged.

- **Neutralizer:** a commission-neutralized variant config —
  `dataclasses.replace(primary_config, commission_per_rt=0.0, commission_pct=0.0)` — zeroes
  **both** the flat per-RT fee and the percent rate, so the variant is fee-free regardless
  of `commission_mode`.
- **Same signal:** the commission variant is a **fourth** backtest on the same signal df.
  `same_signal` now spans all four runs
  (`h_before == h_mid == h_after == h_after_tp == h_after_commission`).
- **Significance:** reused as-is — `_delta_significance(_paired_deltas(primary_closed,
  commission_variant_closed))` (the same paired-delta percentile bootstrap, ADR-027). No new
  statistic.
- **Deltas:** `delta_net = primary − commission_variant`. The variant is fee-free, so its net
  is always ≥ primary net → `delta_net ≤ 0` → `direction = "cost"` (or `"neutral"` at zero
  commission). `direction = "saved"` is kept for schema symmetry but is not expected.
- **Distinctive supporting stat:** `total_commission = commission_variant_net − primary_net`
  (a positive $ figure — the fees removed from P&L), derived from the **net difference**
  (mode-agnostic and exact; per-trade commission fields aren't serialized). Plus
  `flips_profitability = (commission_variant_net > 0 and primary_net <= 0)` — did the fees flip
  a profitable setup into a losing one? The block also carries `primary_net` / `variant_net`
  for the card.

**Determinism note.** Turning off a stop changes *which trades happen*; turning off commission
does **not**. In flat mode the per-round-trip fee is a fixed subtraction that doesn't touch
sizing (the sizing buffer runs off `commission_pct`, which is 0 in flat mode), so the
neutralized run produces the **same trades**, just fee-free. The delta is therefore exactly the
total commission and the bootstrap reports "cost" every time with a razor-thin CI — the correct,
honest result: commission reliably cost a known amount. We still run the identical machinery so
the block schema is byte-for-byte uniform with stop/take-profit and the frontend iterates the
list with no special case. (In percent mode the fee varies with notional, so the same bootstrap
does real work — no branching either way.)

**Consequence:** Additive — stop and take_profit blocks (and their stats) are byte-identical and
stay first/second; `/run`, `same_signal` logic, the significance machinery, `_serialize_run`,
`_paired_deltas`, `_delta_significance`, and `_commission_for_side` are unchanged. Validation
(ADR-028) stays primary-only; the commission variant is not validated. One extra `_serialize_run`
pass (a fourth backtest on the same df) per compare call. **Downstream:** `context.teaching`
consumers must iterate the list (already required since ADR-029) to show the third block.
`__version__` → **25.6.0**.

**RULE:** each TEACH-COMPARE dimension is a block in the `teaching` list built by mirroring the
prior instances (neutralizer via `dataclasses.replace`, reused `_serialize_run` /
`_paired_deltas` / `_delta_significance`). Never reorder or mutate the stop / take_profit blocks
when adding a dimension; derive `total_commission` from the net difference, not per-trade fields.

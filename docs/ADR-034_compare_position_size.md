# ADR-034 — Position-size dimension on TEACH-COMPARE ("what your size did")

**Status:** Accepted (v25.9.0)

**Context:** `/run/compare`'s `teaching` is a list of per-dimension blocks (ADR-026/029/031/032/033):
stop, take_profit, commission, direction, slippage. This adds the **sixth and final** dimension —
**position size** — completing the set. The lesson is **risk amplification**: size multiplies your
*outcome* and your *drawdown*, not your *edge*.

**Decision:** Add a `position_size` block, appended sixth. It is **deliberately NOT a clean mirror**
of commission/slippage: size has no "zero" state, and for fixed-contract sizing it is a pure
deterministic multiplier — so it gets its own handling.

- **Neutralizer:** one fixed contract — `dataclasses.replace(primary_config, qty_type="fixed",
  qty_value=1.0)`. A seventh `_serialize_run` on the same signal df; `same_signal` now spans all
  **seven** runs.
- **Deltas (standard convention):** `variant_net` = net at 1 contract, `primary_net` = net at the
  user's size, `size_delta_net = primary_net − variant_net`.
- **Direction / neutral — decided by the sizing config, not the delta sign:**
    - `qty_type == "fixed"` and `qty_value == 1.0` → **neutral** (the run already *is* the baseline).
    - `qty_type != "fixed"` → **neutral** (v1: comparing compounding %/cash sizing against a single
      fixed contract is misleading — see Follow-up).
    - otherwise (fixed, `qty_value != 1.0`) → `saved` if `size_delta_net > 0`, `cost` if `< 0`, else
      `neutral`.
- **No bootstrap significance.** For fixed sizing the per-trade effect is a pure multiplier, so a
  "real vs luck" test is meaningless (same reasoning that gave `direction` special handling). The
  block reports `significance: "deterministic"` — `_paired_deltas`/`_delta_significance` are **not**
  called.
- **Drawdown is the point:** the block carries `primary_max_dd` and `variant_max_dd` (the run's
  `max_drawdown` KPI) so the card can show that drawdown amplifies with size exactly as net does —
  e.g. 3 contracts → 3× net **and** 3× max drawdown.
- **Size-specific fields:** `contracts` (`qty_value` for fixed, else `None`), `qty_type`,
  `size_multiple` (`qty_value` for fixed, else `None`), `flips_profitability` hardcoded `False`
  (pure scaling never flips the sign for fixed sizing).

**Consequence:** Additive — the prior five blocks and their stats are unchanged and keep their
order; `/run`, `same_signal` logic, `_serialize_run`, `_paired_deltas`, `_delta_significance`,
`_to_native`, and `_commission_for_side` are untouched. The ADR-031 `_to_native` return chokepoint
already coerces the new numpy-typed fields — no per-field casts. One extra `_serialize_run` pass per
compare call. **Downstream:** `context.teaching` consumers must iterate the list (required since
ADR-029) to show the sixth block. `__version__` → **25.9.0**.

**Follow-up (out of scope for v1):** a compounding-aware comparison for `percent_of_equity` / `cash`
sizing (which currently returns a neutral block) — comparing path-dependent compounding against a
flat 1-contract baseline needs its own convention and is deferred.

**RULE:** position size is a *deterministic multiplier* dimension — no bootstrap, neutral decided by
the sizing config, and it surfaces drawdown to teach risk (not edge). Never reorder or mutate the
prior blocks; keep the v1 non-fixed → neutral guard until a compounding-aware version is designed.

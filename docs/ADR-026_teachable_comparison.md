# ADR-026 — Teachable comparison: `POST /backtest/compare` (stop dimension)

**Status:** Accepted.

**Context:** The engine could only run one config at a time. The teachable-comparison
feature needs to run the user's real settings AND a "neutralized" version against the
**same** trade signal in one pass, then report the exact dollar difference so the UI can
explain what a given setting did. This ADR builds the **first dimension only — the STOP**
("neutralized" = stop turned off). Further dimensions (target, slippage, size, …) follow
the same pattern in later ADRs.

**Decision:** Add `POST /backtest/compare` in `api/server.py`, reusing the existing run
logic in `api/engine/engine.py`. The endpoint:

1. Generates the trade signal **once** for the given strategy + data range
   (`_exec_signal_into_df`, mirroring `/run`'s sandbox + SIGALRM timeout).
2. Applies the user's **full config → `primary`** result (authoritative).
3. Applies the **same config with the stop removed** (`stop_loss_points = 0`,
   `stop_loss_pct = 0`) → **`variant`** result. Every other field (target, slippage,
   commission, direction, session, size) is identical — built via
   `dataclasses.replace(primary_config, stop_loss_points=0.0, stop_loss_pct=0.0)`.
4. Computes teaching deltas **in the engine** (deterministic arithmetic).

The signal series is hashed before and after each application and asserted identical
across the two runs (`same_signal`); the engine copies the df internally, so the shared
signal is never mutated. This is **one logical run** (a single HTTP call), so the main
app's monthly backtest cap is not double-counted.

**Response shape:**

```json
{
  "primary":  { "...full result for user's config..." },
  "variants": [
    { "dimension": "stop", "label": "no stop",
      "neutralized": { "stop_loss_points": 0 },
      "result": { "...full result..." } }
  ],
  "teaching": [
    { "dimension": "stop",
      "delta_net": "<primary.net - variant.net>",
      "direction": "saved | cost | neutral",
      "primary_worst_loss": "<most-negative single-trade P&L in primary>",
      "variant_worst_loss": "<most-negative single-trade P&L in variant>",
      "trade_count": "<count>" }
  ],
  "same_signal": true
}
```

`direction` is from the **stop's** point of view: `delta_net = primary.net - variant.net`.
If the stopped result nets MORE than no-stop, the stop **saved** (delta positive); less →
**cost** (negative); equal → **neutral**.

**Consequence:**
- **Additive & cache-safe:** the single-run `/run` path is byte-identical — same handler,
  same computed `kpis`/`trades` (verified against the 25.0.0 baseline). Only the engine
  version string changes.
- `__version__` → **25.1.0** (minor, additive, non-breaking).
- Stops are **points**, used directly — no tick conversion, no `stop_loss_ticks` field.
  MES economics: $5/point, 4 ticks/point, $1.25/tick. The hard anchor: a 2-pt stop on
  1 MES caps a clean (non-gap) single-trade loss at exactly **-$10.00**.
- `trade_count` is reported once (primary's). For one-entry-per-day strategies (e.g. ORB)
  the stop changes only the exit, so primary and variant share entry count; strategies
  whose re-entries depend on exit timing can legitimately differ — the field is the
  authoritative primary count.

**RULE:** the variant differs from the primary in the **stop dimension only**. Build it
with `dataclasses.replace(...)` so every other field is provably identical; never
hand-rebuild the config (drift risk). Engine logic lives in `api/engine/engine.py` and
`api/server.py` only — never touch the legacy `backtest/engine/engine.py` ($1/point copy).

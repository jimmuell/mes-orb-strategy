# WIT-P3c-2 — Class A mapper + VPORB adapter (template → StrategyConfig → VPORBConfig)

Prompt: **WIT-P3c-2** — the Class A mapper + VPORB adapter, proven against the WIT-0001 anchor. Class A only (Class B is P3c-3). On `wit-phase3` (no branch, no merge).

---

## 1. STEP 0 result
- On `wit-phase3`: **yes**. HEAD = **`ad3c3b7` (WIT-P3c-1)**: **yes**.
- Tree clean: **yes** — only the known untracked `pine/mes_net_pnl_v2.pine` (ignored); LFS clean.

## 2. map_template design

- **`kind` from the scorer, never re-derived.** `map_template` calls `score_completeness(template)["class"]` (the P3b scorer) and maps: **A → `"backtest"`** (build wire StrategyConfig); **B → `raise NotImplementedError("Class B mapper: P3c-3")`**; **C → `raise UntestableStrategy(cls="C")`** (refuse, never a config). Routing and mapping agree by construction.
- **Reads ONLY `mode`/`params`/`status` — never prose.** Every wire value is pulled from `_mode(fid)` / `_params(fid)` (the machine channel from P3c-1). Proven by `test_G1_no_prose_value_needed`: it **scrambles every field's `value` to "XXXX prose scrambled XXXX"** and the emitted config is byte-for-byte the same (still `== VPORBConfig()`). If any prose were parsed, that test would break.
- **§5 defaults → `assumptions_applied`.** A field WIT had to assume = `status == "unspecified"`. The mapper records each unspecified config-relevant field it consumes (`B3, E1, F4, F5, H1, H2`) plus `initial_capital` (a lab default with no template source). Specified fields (D1/D2/D3/D4/F1/F2/C1/B1/B2/J1) are not assumptions.
- **Mode-vocabulary gate.** Before building, every config-relevant field's `mode` is checked against `FIELD_MODE_VOCAB` (contract/modes.md, Class A). A token not declared for the dimension → `UnsupportedConstruct(field, mode)`. Declared-but-not-v1 tokens (e.g. `market_next_open`) pass this gate and are caught by the adapter's capability checks — a clean split: mapper = "is this a real WIT token?", adapter = "can THIS engine run it?".
- **Structural hygiene:** the emitted wire config is checked for the contract's required top-level keys (loaded from `contract/strategy-config.v1.json`) — a light no-dep check.

## 3. G1 result — the anchor

**PASS — exact equality, zero field diffs.** `strategy_config_to_vporb(map_template(T-0001)["config"]) == VPORBConfig()`:
```
kind: backtest
assumptions_applied: ['B3', 'E1', 'F4', 'F5', 'H1', 'H2', 'initial_capital']
field diffs vs VPORBConfig(): NONE — exact equality ✓
```
All 17 VPORBConfig fields land on their defaults: window (`2016-04-10`/`2026-04-09`) from `J1.params.window`; `range_start/range_end/value_area_pct/vp_granularity` from `D2.params`; `entry_window_start/entry_window_last_bar` from `C1.params` (via wire `session.trade_window`); `entry_mode="close"` from `D3.mode`; `stop_offset_ticks` from `F1.params`; `rr_target` from `F2.params`; `same_bar_policy` from `F5.mode`; costs from `H1/H2.params`. `min_opening_bars`/`min_opening_bars_5min`/`initial_capital` are engine-mechanical / lab defaults (VPORBConfig 15/3/10000) — recorded in `assumptions_applied` (`B3`, `initial_capital`), not carried on the portable wire. `assumptions_applied ⊇ {B3,E1,F4,F5,H1,H2}` ✓.

## 4. G3 + G4 results
- **G3 unknown mode:** `D2.mode="harmonic_pattern"` → `map_template` raises **`UnsupportedConstruct(field="D2", mode="harmonic_pattern")`**. PASS.
- **G3 baked-constant mismatch:** `D4.mode="market_next_open"` (declared token, not engine-v1) → passes the mapper vocabulary gate, then the **adapter** raises `UnsupportedConstruct(field="D4", …)`. PASS — proves the two-layer split.
- **G3 non-ET tz:** `session.tz="America/Chicago"` → adapter raises **`UnsupportedConstruct(field="C1", mode="America/Chicago")`** — **never converts**. PASS.
- **G4 Class C:** a minimal template (setup present, trigger D3 unspecified, no testable claim → class C) → `map_template` raises **`UntestableStrategy(cls="C")`**, no config produced. PASS.
- **Bonus:** `test_class_B_not_implemented_this_slice` — mapping the Class-B T-0002 raises `NotImplementedError` (P3c-3), confirming the slice boundary.

## 5. Baked-constant + tz guards
All in the adapter `strategy_config_to_vporb` (it receives the wire config; the runner hardcodes these four + ET):
| Guard | Assertion | Violation reports |
|---|---|---|
| tz | `session.tz == "America/New_York"` | `UnsupportedConstruct(field="C1", mode=<tz>)` — never a tz conversion |
| bias | `bias.mode == "vp_value_area_break"` | `UnsupportedConstruct(field="D1", mode=<mode>)` |
| order | `setup_entry.order == "market_on_close"` | `UnsupportedConstruct(field="D4", mode=<mode>)` |
| sizing | `sizing.mode == "fixed_contracts" and sizing.value == 1` | `UnsupportedConstruct(field="E1", mode="<mode>:<value>")` |
| time_exit | `exits.time_exit == "force_flat"` | `UnsupportedConstruct(field="F4", mode=<mode>)` |
Each maps the offending wire dimension back to its template field id (session→C1, bias→D1, order→D4, sizing→E1, time_exit→F4) so the P3d router can surface a precise WIT-03 §3.7 error.

## 6. Full suite result + anything unexpected
- New: `test_mapper.py` — **7 passed** (G1 anchor + no-prose proof, G3 ×3, G4, Class-B boundary).
- **Full suite: 160 passed** (153 prior + 7 new), 0 failed. No regression.
- **Anything unexpected / notes:**
  1. **`min_opening_bars`/`min_opening_bars_5min` are not carried on the wire.** The portable `StrategyConfig` (contract/strategy-config.v1.json, `additionalProperties:false`) has no slot for them — they're engine-mechanical completeness-gate values, not portable strategy semantics. The adapter uses VPORBConfig's own defaults (15/3), which equal the anchor, and records `B3` in `assumptions_applied`. This is a deliberate deviation from the prompt's literal "B3 min_opening_bars -> min_opening_bars/_5min" (they map via the engine default, not a wire field) — flagged for review.
  2. **Wire `session.trade_window` carries the entry window `[entry_start, entry_last_bar]` = `["09:45","10:55"]`** (from `C1.params`), which differs from WIT-03 §3.4's illustrative `["09:30","11:00"]` (RTH-open, cutoff). §3.4 is an example of the *shape*; actual configs carry the precise per-strategy window. No contract change was needed; flagged so the reviewer knows the trade_window semantics the adapter relies on.
  3. No dependency added; `requirements.txt` untouched; scorer/schema/fixtures untouched (as required).

WIT-P3c-2 — Completed

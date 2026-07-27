# WIT-P3c — DESIGN: template→config mapper (param channel, mode vocabulary, goldens)

Prompt: **WIT-P3c** — design-only (read-only investigation + this report). No code, no schema edits. On `wit-phase3` (no branch, no merge).

---

## 1. STEP 0 result
- On `wit-phase3`: **yes**. HEAD = **`e11da3f` (WIT-P3b-fix)** above **`84ef303` (WIT-P3b)**: **yes**.
- Tree clean: **yes** — only the known untracked `pine/mes_net_pnl_v2.pine` (ignored); LFS clean.

Sources read: WIT-02 §1–6; WIT-03 §3.4, §3.5, §3.7, §7 (also §3.6, §4); `api/wit/config.py`, `api/wit/vp_orb_runner.py`, `api/wit/event_study.py`; both golden fixtures.

---

## 2. Param-surface inventory

### VPORBConfig (`api/wit/config.py`) — 16 fields
| Config field | Meaning | Runner consumption | Template source / §5 default |
|---|---|---|---|
| `start_date` / `end_date` | backtest window | `vp_orb_runner.py:222,262` → `load_5min` + `BacktestConfig` | **J1 test_design** (WIT-authored plan), data-bounded. *Not a guru field.* |
| `range_start` / `range_end` (09:30/09:45) | VP window `[09:30,09:45)` | `:98,128,225` `_opening_profile` / `load_1min_opening` | **D2 setup** ("volume profile over 9:30–9:45") + **C1 session** |
| `value_area_pct` (0.70) | VP value area | `:103,108` `build_volume_profile` | **D2 setup** ("value area 70%") |
| `min_opening_bars` (15) / `_5min` (3) | completeness gate to skip a day | `:101,106` | **B3 data_requirements** (§5 finest-data approximation) |
| `vp_granularity` ("1min") | VP source bars | `:97,223` | **B3 data_requirements** (§5 "finest licensed data") |
| `entry_window_start` (09:45) / `entry_window_last_bar` (10:55) | eligible-entry bars | `:128` `build_signals_for_day` | **C1 session_rules** ("entries before 11:00 ET") |
| `entry_mode` ("close") | close-beyond vs body-beyond | `:135,138` `_qualifies` | **D3 entry_trigger** (+ §5 close-vs-touch default; **J2** sweep) |
| `stop_offset_ticks` (2) | stop = POC ∓ ticks | `:146` | **F1 initial_stop** ("2 ticks beyond POC") |
| `rr_target` (2.0) | target = entry ± R·mult | `:150,154` | **F2 profit_target** ("2:1 R:R") |
| `same_bar_policy` ("stop_first") | both-touched resolution | `:195` `_resolve_exit` | **F5** (§5 default stop-first; **J2** sweep) |
| `commission_per_side` (0.62) | cost | `:258` `BacktestConfig` | **H1** (§5 default) |
| `slippage_ticks` (1) | cost | `:259` | **H2** (§5 default; **J2** sweep) |
| `initial_capital` (10000) | account size for DD% | `:256` | **⚠ NO TEMPLATE SOURCE — design gap** (lab economics assumption) |

**Baked into `run_vp_orb` (NOT VPORBConfig fields, but they carry template meaning):** `qty_type="fixed", qty_value=1.0` (`:260`) ← **E1** (§5 "1 contract"); `process_orders_on_close=True` (`:263`) ← **D4** ("market on close"); `pyramiding=1` (`:261`) ← **G1** ("one trade/day"); force-flat time-exit (in `_resolve_exit`) ← **F4** (§5). These have clean template sources but are **hardcoded**, so the adapter can't vary them — a v1 generality gap (fine while every template → 1 MES; the adapter must *assert* they match, see §5).

### EventStudyConfig (`api/wit/event_study.py`) — 15 fields
| Config field | Meaning | Runner consumption | Template source |
|---|---|---|---|
| `timeframe` ("5min") | candle TF | `event_study.py` build_candles | **B2 timeframe** ("any" → 5-min primary) |
| `k` (1.5) | body ≥ k·median | `:207` `event_mask` | **I1 / J1** WIT-chosen (`big_candle_k`) |
| `n_baseline` (20) | trailing median lookback | `:206` | **J1** WIT-chosen |
| `spike_eff` (0.50), `spike_giveback_cap` (0.20), `pullback_p` (0.40) | path-bucket thresholds | `:231–233` `bucket_series` | **I1 / J1 / J2** WIT-chosen |
| `bucket_mode` ("threshold") | threshold vs percentile | `:214` | **J2** interpretation set |
| `regime_mode` ("trailing_median") | chop/trend measure | `:180–196` `regime_series` | **C2** (concept only) + **J1** WIT-chosen measure |
| `regime_er_m` (20), `regime_trailing_window` (390), `regime_fixed_er` (0.30), `regime_adx_len` (14), `regime_adx_thresh` (20) | regime params | `:181–194` | **J1 / J2** WIT-chosen |
| `start` / `end` | window | `load_1min_rth` | **J1** WIT-chosen |

**Key finding:** for Class B, **almost every param is WIT-authored (J1/J2/I1), not guru-supplied** — only `timeframe` (B2), the regime *concept* (C2), and the "big candle" *notion* (D2 partial) come from the source. This is correct and by design ("J filled by WIT"): the Class-B mapper is really **J-section → EventStudyConfig**, so the J fields must also carry structured params (see §3).

### Gaps flagged
1. **`initial_capital`** — no template field; a lab-side economics assumption. → the mapper injects a lab default, recorded in `assumptions_applied` (not a guru claim).
2. **Window provenance** — comes from **J1** (WIT plan), and the approved run used data-bounded dates (`2016-04-11→2026-04-09`) that differ from T-0001 J1's prose (`2016-07-01→2026-06-30`). Truth lives in the run config, not the template prose.
3. **Baked run-time constants** (sizing/order/pyramiding/time-exit) aren't config params → adapter must *validate-or-reject*, not silently ignore.
4. **Class-B params are WIT-authored** → the param channel must live on J fields too, not only the guru execution fields.

---

## 3. The structured-param problem + recommendation

**Confirmed finding.** Template field `value`s are **prose**; the runners need **typed** params; there is **no machine param channel** today. Examples from T-0001:
- `D2.value = "Fixed-range volume profile over 09:30-09:45, value area 70%; levels VAH, VAL, POC"` — the runner needs `range_start="09:30", range_end="09:45", value_area_pct=0.70` as typed values.
- `F1.value = "Stop 2 ticks beyond POC…"` — needs `ref="poc", ticks=2`.
- `I1.value = "range_minutes=15, value_area_pct=70, stop_offset_ticks=2, rr_target=2.0, entry_cutoff=11:00 ET, timeframe=5m"` — the params exist but as a **single text line**, not a structured object.

A mapper that scraped these strings would be a regex time-bomb. **The mapper must NEVER parse prose.**

### Options
- **(a) Per-field structured `mode` + `params`** on config-relevant fields, emitted by extraction under a controlled vocabulary; mapper reads `params`+`status`+`mode`, applies §5 defaults for assumed fields. *[lead-engineer leaning]*
- (b) One top-level `normalized_config` / `config_hints` block the extractor emits.
- (c) Formalize `I1.parameters` into a structured object as the sole param carrier.

### Recommendation: **(a)**, decisively.
| Criterion | (a) per-field | (b) top-level block | (c) I1-only |
|---|---|---|---|
| **Provenance** (param ↔ `source_quote`) | ✅ param sits with the field that justifies it | ❌ severed from the quote | ❌ severed |
| **Mapper never parses prose** | ✅ reads typed `params` | ✅ | ✅ |
| **Structural coverage** (entry/level/stop/session) | ✅ every field carries its own shape | ✅ | ❌ "parameters" can't express stop-ref/order/session |
| **Dual-use form** (WIT-02 §7 "audit my own") | ✅ a form is per-field inputs | ⚠️ one big blob | ⚠️ |
| **Two sources of truth?** | ✅ one (the fields) | ❌ block can diverge from fields | ⚠️ |
| **Schema blast radius** | small, additive (2 optional keys) | small | small |
| **Extraction burden** | higher (typed params under vocab) | medium | medium |

(a) keeps a single source of truth (the fields), preserves the report's "claimed rule ↔ quote" audit trail, and matches the dual-use form. Its cost — the extractor must emit typed params under the vocabulary — is exactly the structured-output work P3e already owns. (b) and (c) are cheaper for extraction but sever provenance and/or can't carry the entry/stop/session structure.

### Exact proposed schema delta (PROPOSAL — schema NOT edited)
Additive, non-breaking (so the current P3b fixtures still validate; `template_version` stays `"1.0"`). In `schema/strategy-template.v1.json`, extend `$defs.field.properties` (keep `additionalProperties:false`; do **not** add these to `required`):
```jsonc
"mode": {
  "type": ["string", "null"],
  "description": "Controlled-vocabulary mode token for config-relevant fields (contract/modes.md); null for prose-only/metadata fields."
},
"params": {
  "type": ["object", "null"],
  "description": "Typed machine-readable parameters for this field, e.g. D2 {range_start,range_end,value_area_pct}; null when none. The mapper reads ONLY params/mode/status — never value prose."
}
```
`value`/`status`/`source_quote`/`assumption` stay required and unchanged. P3c-build then backfills `mode`+`params` into the two golden fixtures (the guru execution fields **and** the WIT-authored J fields for Class B).

---

## 4. Draft `contract/modes.md` vocabulary v1 (report only — NOT committed)

Enumerated mode tokens per dimension, each tied to how the runner realizes it. Unknown token for a dimension → **`UNSUPPORTED_CONSTRUCT`**.

**Class A (StrategyConfig) dimensions**
| Dimension | v1 mode tokens | Runner realization |
|---|---|---|
| `bias` (D1) | `vp_value_area_break` · `orb_break` *(future)* · `none` | `build_signals_for_day` direction: close body through VAH→long / VAL→short |
| `setup` (D2) | `volume_profile_range` {range_start,range_end,value_area_pct,granularity} · `opening_range` *(future)* | `build_volume_profile` over the window |
| `entry.trigger` (D3) | `bar_close_beyond_level` · `bar_body_beyond_level` | `_qualifies(..., mode)` |
| `entry.level` (D2/D1) | `va_high_low` · `orb_high_low` *(future)* | VAH/VAL from the profile |
| `order` (D4) | `market_on_close` · `market_next_open` *(future)* | `process_orders_on_close` flag |
| `sizing` (E1) | `fixed_contracts` {value} | `qty_type="fixed"`, `qty_value` |
| `stop` (F1) | `level_offset` {ref: `poc`\|`va`\|`orb`, ticks} | `sl_price = ref ∓ ticks·tick_size` |
| `target` (F2) | `r_multiple` {value} · `level` *(future)* · `none` | `tp_price = entry ± value·R` |
| `time_exit` (F4) | `force_flat` · `fixed_time` *(future)* · `none` | `_resolve_exit` last-RTH-bar flatten |
| `same_bar` (F5) | `stop_first` · `target_first` | `_resolve_exit` tie-break |
| `session` (C1) | `rth_window` {entry_start,entry_last_bar,tz} | entry-window gate |
| `filters` (C2/C3) | `none` *(v1)* · regime/calendar *(future)* | — |

**Class B (EventStudyConfig) dimensions**
| Dimension | v1 mode tokens | Runner realization |
|---|---|---|
| `event` (D2/I1) | `body_vs_trailing_median` {k, n_baseline} | `event_mask` (**note: WIT-03 §3.5's "k*ATR" text is stale — v1 is body-vs-median**) |
| `path_bucket` (I1/J2) | `path_threshold` {spike_eff,spike_giveback_cap,pullback_p} · `path_percentile` | `bucket_series` |
| `regime` (C2/J1) | `kaufman_er_trailing_median` {m,window} · `kaufman_er_insample_median` {m} · `kaufman_er_fixed` {m,thresh} · `adx_threshold` {len,thresh} · `none` | `regime_series` |
| `outcomes` (J1) | horizons `[1,3,5,10]`, measures `fwd_return`,`giveback`,`p_against` | `_add_forward_outcomes` |

**UNSUPPORTED_CONSTRUCT behavior (WIT-03 §3.7):** if any field's `mode` is not in the v1 vocabulary for its dimension, the mapper **fails fast** — returns `{"error":{"code":"UNSUPPORTED_CONSTRUCT","message":"<dimension> mode '<token>' not supported","detail":{"field":"<id>","mode":"<token>"}}}`. It is a **user-visible product state** ("our lab doesn't support this yet"), and each unique missing token becomes a one-line engine backlog item. Never a silent skip, never a guess.

---

## 5. Mapper interface + adapter + config_hash

### `map_template(template) -> {kind, config, assumptions_applied}`
- **`kind` from the completeness class** (never re-derived): **A → `"backtest"`** (emits `StrategyConfig`); **B → `"event_study"`** (emits `EventStudyConfig`); **C → refuse** — raise/return an untestable signal (`INVALID_CONFIG` / `class C: untestable`), **never a config**. The class is read from `score_completeness(template)` (P3b), so routing and mapping agree by construction.
- **`config`** = the **wire** `StrategyConfig`/`EventStudyConfig` (WIT-03 §3.4/§3.5 JSON, `config_version:"1.0"`) — the portable, storable contract.
- **`assumptions_applied`** = the field ids/dimensions where a §5 default was injected (mirrors the completeness `assumptions`), echoed into the report (WIT-03 §3.4 `assumptions_applied`).

### Two layers (portable wire vs engine dataclass)
```
template (WIT-02 JSON)
   │  map_template()          ← reads params/mode/status; applies §5 defaults; mode-checks
   ▼
wire StrategyConfig / EventStudyConfig   (WIT-03 §3.4/§3.5 — stored by Supabase; permalinks re-render from this, §7)
   │  adapter (engine-internal)
   ▼
VPORBConfig / EventStudyConfig(engine)   (the frozen dataclasses the runners consume)
```
- **Why two layers:** the wire config is provider-portable and version-stable (§7 permalinks); the engine dataclasses are free to refactor behind the adapter. Mapping bugs are engine bugs with tests (WIT-03 §3.4).
- **Adapter A** `StrategyConfig → VPORBConfig`: `setup.params → range_start/range_end/value_area_pct/vp_granularity`; `entry.trigger → entry_mode`; `session → entry_window_start/entry_window_last_bar`; `exits.stop.ticks → stop_offset_ticks`; `exits.target.value → rr_target`; `exits.same_bar_policy → same_bar_policy`; `costs → commission_per_side/slippage_ticks`; `data.window → start_date/end_date`; `initial_capital ←` lab default. **Baked constants:** the adapter **asserts** `order == market_on_close`, `sizing == fixed_contracts/1`, `bias == vp_value_area_break`, `time_exit == force_flat`; any mismatch → `UNSUPPORTED_CONSTRUCT` (not a silent drop, since the runner hardcodes these).
- **Adapter B** `EventStudyConfig(wire) → EventStudyConfig(engine)`: `event.params → k/n_baseline`; `path_bucket.params → spike_eff/spike_giveback_cap/pullback_p` + `bucket_mode`; `regime.mode+params → regime_mode/regime_er_m/regime_trailing_window/regime_fixed_er/regime_adx_len/regime_adx_thresh`; `timeframe`; `window → start/end`.

### config_hash placement (note for P3d)
- `config_hash = sha256(canonical_json(wire config))` — hash the **wire** config (sorted keys, stable separators), **not** the engine dataclass, so it survives engine refactors. It is the idempotency key for `POST /wit/v1/runs` (WIT-03 §3.1: idempotent on `evaluation_id` + config hash) and part of `provenance` (§3.6).
- **Computed at submit time in the P3d router** (a small `config_hash(config)` util), alongside separately-recorded `engine_version` + `dataset_version`. The mapper returns the config; P3d hashes + stores it.

### Required contract fix (WIT-03 §7 change, lead-approved)
WIT-03 §3.4/§3.5 examples are **stale** vs the engine and must be updated in the build (a `contract/` + WIT-03 PR per §7): §3.4 `session` shows **CT** ORB times (`tz America/Chicago, trade_window [08:30,10:00], force_flat 14:55`) — VP-ORB is **ET** (`09:45`–`11:00`, force-flat last RTH bar); §3.5 `event.definition` says **`k*ATR`** — the engine is **`body ≥ k·trailing-median-body`**, and `path_efficiency_split:0.75` is really the three thresholds `spike_eff/spike_giveback_cap/pullback_p`. The goldens (§6) target the **engine** configs (which produced the approved reports); the wire spec must be corrected to match.

---

## 6. Golden strategy + build-slice breakdown

### Golden tests (prove the mapper reproduces the real reports)
- **G1 — Class A round-trip:** `adapterA(map_template(WIT-T-0001).config) == VPORBConfig()`. The approved WIT-0001 primary run used `VPORBConfig()` defaults, so a faithful map+adapt of the T-0001 fixture must reproduce it **field-for-field**. Also assert `kind=="backtest"` and `assumptions_applied` ⊇ {E1,F4,F5,H1,H2,B3} (the §5 fills).
- **G2 — Class B round-trip:** `adapterB(map_template(WIT-T-0002).config) == EventStudyConfig()` (the approved WIT-0002 primary). Assert `kind=="event_study"`.
- **G3 — UNSUPPORTED_CONSTRUCT:** a template with an unknown mode (e.g. `setup.mode="harmonic_pattern"`) → mapper returns `UNSUPPORTED_CONSTRUCT` naming that token/field; no config produced.
- **G4 — Class-C refusal:** a Class-C template (required trigger missing, no testable claim) → `map_template` refuses (untestable signal), **never** a config.

"Match" = **exact dataclass equality** to the approved engine config (these are frozen dataclasses; `==` is total). This is stronger than a tolerant compare and is the point: the mapper must land precisely on the config that produced the published verdict, or the report would silently change (WIT-03 §7).

### Build-slice breakdown (one task each)
| Slice | Deliverable | Depends on | Commits |
|---|---|---|---|
| **P3c-1 — param channel + contract** | schema delta (optional `mode`/`params`); backfill both fixtures with `mode`+`params`; `contract/modes.md` (v1 vocab); `contract/` wire StrategyConfig/EventStudyConfig + **fix WIT-03 §3.4/§3.5 staleness** (§7 change) | P3b-fix | `schema/…json`, both fixtures, `contract/modes.md`, `contract/*.json`, `docs/wit/WIT-03…md` |
| **P3c-2 — Class A mapper + VPORB adapter** | `map_template` (A path) → wire StrategyConfig; adapterA → `VPORBConfig`; G1 + G3 + G4 tests | P3c-1 | `api/wit/mapper.py` (+adapter), `api/tests/test_mapper.py` |
| **P3c-3 — Class B mapper + ES adapter** | `map_template` (B path) → wire EventStudyConfig; adapterB → `EventStudyConfig(engine)`; G2 test | P3c-1 | extend `mapper.py`, extend `test_mapper.py` |

**Recommended order:** **P3c-1 → (P3c-2 ∥ P3c-3)**. P3c-1 is the keystone (schema + fixtures + modes + wire-spec fix); the two mapper halves depend only on it and touch mostly disjoint code, so they parallelize (mirrors the P3b→P3c/P3e shape). Each slice is additive, PR-per-slice, and green under the existing CI gate.

---

## 7. Anything unexpected / params with no clean template source
- **`initial_capital`** — the one VPORBConfig field with **no template source**; a lab economics assumption (account size for DD%). Injected as a lab default, disclosed in `assumptions_applied`.
- **The WIT-03 wire configs are stale** (CT session times; `k*ATR` event) vs the built engines — a genuine contract bug that P3c-1 must fix under §7, not paper over. The goldens anchor to the engine configs (source of the approved reports), so this surfaced cleanly.
- **Class-B params are ~90% WIT-authored** (J1/J2/I1), so the param channel must live on the J fields too — the mapper for Class B is "J-section → config," not "guru-fields → config."
- **Baked run-time constants** (sizing/order/pyramiding/time-exit) aren't config params; the adapter must **assert-or-`UNSUPPORTED_CONSTRUCT`** rather than ignore, so a template implying (say) 2 contracts fails loudly instead of silently running 1.
- No code or schema was changed in this prompt — proposal only.

WIT-P3c — Completed

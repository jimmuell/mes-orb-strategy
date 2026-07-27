# WIT-P3c-1 — template param channel, mode vocabulary, wire-contract correction

Prompt: **WIT-P3c-1** — the contract/param-channel layer (schema delta + fixtures + modes + wire spec). No mapper/adapter code (P3c-2/3). On `wit-phase3` (no branch, no merge).

---

## 1. STEP 0 result
- On `wit-phase3`: **yes**. HEAD = **`eef8eaf` (WIT-P3c design)** above **`e11da3f` (WIT-P3b-fix)**: **yes**.
- Tree clean: **yes** — only the known untracked `pine/mes_net_pnl_v2.pine` (ignored); LFS clean.

## 2. Schema delta + validator

- `schema/strategy-template.v1.json`: added **two OPTIONAL** keys to `$defs.field.properties` — `mode` (`["string","null"]`) and `params` (`["object","null"]`). `additionalProperties` stays `false`; **not** added to `required`. `template_version` stays **`"1.0"`** (additive, non-breaking).
- `api/wit/extraction/schema.py`: split the field-key check — `_FIELD_KEYS` (the 4 required) vs `_FIELD_ALLOWED_KEYS` (the 4 + `mode`/`params`); the unknown-key check now uses the allowed set, and added type checks (`mode` string|null, `params` object|null).
- **P3b fixtures/tests still green: yes.** After the delta (and before any backfill), `test_completeness.py` = **11 passed** — the additive keys don't disturb existing validation or scoring.

## 3. Fixture backfill summary

`mode`/`params` added by a script that **verified the four core keys (`value`/`status`/`source_quote`/`assumption`) and the `completeness` block are byte-identical** before/after (assertions passed for every field). The files were re-serialized (consistent `indent=2`); only additions + whitespace normalization, no content change. Completeness recomputes unchanged: **T-0001 {66, A, []}**, **T-0002 {21, B, [B1,D1,D3,D4,F2|F4]}** — `mode`/`params` don't affect scoring.

**T-0001 (Class A) — 16 fields got `mode`/`params`:**
| Field | mode | params |
|---|---|---|
| B1 | `futures_proxy` | {symbol:ES, tick_size:0.25, tick_value:1.25, proxy_for:NQ} |
| B2 | null | {timeframe:5min} |
| B3 | null | {granularity:1min, min_opening_bars:15, min_opening_bars_5min:3} |
| C1 | `rth_window` | {entry_start:09:45, entry_last_bar:10:55, tz:America/New_York} |
| D1 | `vp_value_area_break` | null |
| D2 | `volume_profile_range` | {range_start:09:30, range_end:09:45, value_area_pct:0.7, granularity:1min} |
| D3 | `bar_close_beyond_level` | {level:va_high_low} |
| D4 | `market_on_close` | null |
| E1 | `fixed_contracts` | {value:1} |
| F1 | `level_offset` | {ref:poc, ticks:2} |
| F2 | `r_multiple` | {value:2.0} |
| F4 | `force_flat` | null |
| F5 | `stop_first` | null |
| H1 | null | {commission_per_side:0.62} |
| H2 | null | {slippage_ticks:1} |
| **J1** | null | {window:{start:2016-04-10, end:2026-04-09}} |

**T-0002 (Class B) — 4 fields got `mode`/`params`** (the WIT-authored J/I carriers, as designed):
| Field | params |
|---|---|
| B2 | {timeframe:5min} |
| I1 | {tunables:[k, n_baseline, spike_eff, spike_giveback_cap, pullback_p, regime_measure, forward_horizons]} |
| **J1** | {event:{mode:body_vs_trailing_median, k:1.5, n_baseline:20}, path_bucket:{mode:path_threshold, spike_eff:0.5, spike_giveback_cap:0.2, pullback_p:0.4, bucket_mode:threshold}, regime:{mode:kaufman_er_trailing_median, regime_er_m:20, regime_trailing_window:390, regime_fixed_er:0.3, regime_adx_len:14, regime_adx_thresh:20.0}, outcomes:{horizons:[1,3,5,10], measures:[fwd_return,giveback,p_against]}, timeframe:5min, window:{start:2016-04-11, end:2026-04-09}} |
| J2 | {sweeps:{k:[1.25,2.0,3.0], bucket_mode:[threshold,percentile], regime_mode:[trailing_median,insample_median,fixed,adx]}} |

Two design-necessary additions beyond the prompt's explicit list, both flagged: **J1.params.window** on each fixture (the authoritative run window — design §2 gap 2 "truth lives in the run config"; the P3c-2/3 exact-equality golden needs it), and **B3.params** on T-0001 (data granularity/completeness gate). `completeness` unchanged either way.

## 4. contract/ files created
- **`contract/modes.md`** — the v1 mode vocabulary (Class A + Class B dimensions, tokens, `params`, runner realization with `path:line`, and the `UNSUPPORTED_CONSTRUCT` rule incl. the non-ET-tz and baked-constant-mismatch cases). `*` marks vocabulary-declared-but-not-implemented tokens.
- **`contract/strategy-config.v1.json`** — JSON Schema for the wire StrategyConfig (WIT-03 §3.4), corrected to ET session; enums from modes.md.
- **`contract/event-study-config.v1.json`** — JSON Schema for the wire EventStudyConfig (WIT-03 §3.5), corrected to `body_vs_trailing_median` + three thresholds.
All three parse as valid JSON.

## 5. WIT-03 edits (exact old→new)

**(A) §3.5 event — REAL fix:**
```
OLD: { "event": {"definition": "bar body >= k*ATR", "params": {"k": 2, "path_efficiency_split": 0.75}},
NEW: { "event": {"definition": "bar body >= k * trailing-median body", "params": {"k": 1.5, "spike_eff": 0.50, "spike_giveback_cap": 0.20, "pullback_p": 0.40}},
```

**(B) §3.4 session — TZ-REPRESENTATION ALIGNMENT ONLY (instants preserved):**
```
OLD:   "session": { "tz": "America/Chicago", "trade_window": ["08:30","10:00"], "force_flat": "14:55" },
NEW:   "session": { "tz": "America/New_York", "trade_window": ["09:30","11:00"], "force_flat": "15:55" }, // ET wall-clock, matching the engine; same instants as the prior CT example — representation alignment, not a time change.
```

**CONFIRMED — the §3.4 instants are identical (CT ≡ ET)**, verified by `zoneinfo`:
- 08:30 CT ≡ **09:30 ET** (13:30 UTC) · 10:00 CT ≡ **11:00 ET** (15:00 UTC) · 14:55 CT ≡ **15:55 ET** (19:55 UTC).

The engine's clock **is ET wall-clock, tz-naive**, cited: `vp_orb_runner.py:51` docstring ("5-min RTH bars [09:30,15:55] ET, tz-naive index (ET wall-clock)"); `_RTH_START = dt.time(9,30)`, `_RTH_LAST_START = dt.time(15,55)` (`:43–44`) applied directly to the naive index; `analysis.py:37,58` localizes the tz-naive index as `America/New_York`. So the ET representation matches the engine exactly. `bias`/`exits` params (`range_minutes:15`, `va_pct:70`, stop `ticks:2`, `r_multiple:2.0`) were **not touched** (already correct).

**§7 change-log line added** documenting both edits; wire shapes unchanged so `config_version` stays `1.0`.

## 6. Forward note for P3c-2 (recorded, no code)
The P3c-2 adapter must map wire `session` times **verbatim** (`America/New_York` → VPORBConfig ET labels `09:45`/`10:55`, force-flat last RTH bar). **Any non-ET wire `tz` → `UNSUPPORTED_CONSTRUCT`, never a silent tz conversion** — the engine index is ET-naive, so a CT (or any other) wire tz cannot be reinterpreted without moving the instants. This is codified in `contract/modes.md` (`session` row + UNSUPPORTED_CONSTRUCT rules).

## 7. Full suite result + anything unexpected
- **Full suite: 153 passed** (unchanged count — this slice is schema/fixtures/contract/docs only, no new tests), 0 failed. `test_completeness.py` 11 passed with both fixtures re-validating and scores unchanged.
- **Unexpected / notes:** (i) json re-serialization normalized `0.70 → 0.7` and expanded the previously one-line `completeness`/`claims` blocks — cosmetic, content proven identical on the four core keys + completeness. (ii) Added `J1.params.window` (and T-0001 `B3.params`) beyond the prompt's explicit field list because the P3c-2/3 exact-equality goldens need a structured window source (design §2 gap 2) — flagged here for review. (iii) No dependency added; `requirements.txt` untouched; no audit-gate run needed.

WIT-P3c-1 — Completed

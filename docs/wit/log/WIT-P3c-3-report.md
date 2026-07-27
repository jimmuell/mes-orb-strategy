# WIT-P3c-3 — Class B mapper + event-study adapter (template → EventStudyConfig)

Prompt: **WIT-P3c-3** — the Class B mapper + event-study adapter, proven against the WIT-0002 anchor. Class B only (Class A unchanged). On `wit-phase3` (no branch, no merge).

---

## 1. STEP 0 result
- On `wit-phase3`: **yes**. HEAD = **`55a1ab9` (WIT-P3c-2)**: **yes**.
- Tree clean: **yes** — only the known untracked `pine/mes_net_pnl_v2.pine` (ignored); LFS clean.

## 2. G2 result — the anchor

**PASS — exact equality, zero field diffs.** `event_study_config_to_engine(map_template(T-0002)["config"]) == EventStudyConfig()`:
```
kind: event_study
assumptions_applied: []
field diffs vs EventStudyConfig(): NONE — exact equality ✓
```
All 15 EventStudyConfig fields land on their defaults from `J1.params` (the WIT-authored carrier): `timeframe`, `k`/`n_baseline` (event), `spike_eff`/`spike_giveback_cap`/`pullback_p`/`bucket_mode` (path_bucket), `regime_mode` + the five `regime_*` params (regime), `start`/`end` (window). No tuning of the fixture or engine was needed — it reproduces the published WIT-0002 primary config first try.

- **kind:** `"event_study"` (from the completeness class, never re-derived).
- **assumptions_applied:** `[]` — Class B is entirely WIT-authored (J1 is `specified`), so no §5 default lands. Exactly as the design predicted ("Class B params are ~90% WIT-authored").
- **No prose parsed:** `test_G2_no_prose_value_needed` scrambles every field's `value` and still reproduces `EventStudyConfig()` — the mapper reads only `mode`/`params`.

## 3. Regime-token → engine-enum mapping table

The mode tokens live inside `J1.params.{event,path_bucket,regime}.mode` (Class B is WIT-authored, so the whole spec sits under J1). The regime token maps to the engine `EventStudyConfig.regime_mode` enum:

| Wire vocab token (contract/modes.md) | Engine `regime_mode` |
|---|---|
| `kaufman_er_trailing_median` | `trailing_median` |
| `kaufman_er_insample_median` | `insample_median` |
| `kaufman_er_fixed` | `fixed` |
| `adx_threshold` | `adx` |
| `none` | *(declared but unmapped — adapter refuses; see §4)* |

Also: `path_bucket.mode` (`path_threshold`/`path_percentile`) is the vocab token; the engine `bucket_mode` (`threshold`/`percentile`) is read from `path_bucket.params.bucket_mode`. `event.mode` (`body_vs_trailing_median`) is validated but has no engine enum (the engine always does body-vs-median).

## 4. Class-B UnsupportedConstruct case

Two cases, both PASS:
- **Unknown token at the mapper:** `J1.params.regime.mode = "my_special_regime"` (not in `REGIME_MODES`) → `map_template` raises **`UnsupportedConstruct(field="J1.regime", mode="my_special_regime")`**.
- **Declared-but-unmapped enum at the adapter:** `regime.mode = "none"` (in `REGIME_MODES`, so it passes the mapper's vocab gate) has no engine `regime_mode` enum → the **adapter** raises `UnsupportedConstruct(field="regime", …)`, **never a silent default**. This mirrors the Class-A two-layer split (mapper = "is it a real token?", adapter = "can the engine run it?").

## 5. Class A still passes unchanged
G1 (round-trip == `VPORBConfig()`), G1-no-prose, G3 (unknown mode / baked-constant / non-ET tz), G4 (Class-C refusal), and the Class-A vocabulary all still pass — the B path was added by replacing only the `NotImplementedError` branch and appending `_map_class_b` + `event_study_config_to_engine`; the Class-A code, scorer, schema, and fixtures were untouched.

## 6. Full suite result + anything unexpected
- `test_mapper.py`: **10 passed** (6 Class-A from P3c-2 + G2 anchor + G2-no-prose + 2 Class-B UnsupportedConstruct).
- **Full suite: 163 passed** (160 prior + 3 new), 0 failed. No regression.
- **Anything unexpected:**
  1. **`assumptions_applied == []` for Class B** — no §5 default applies because the event-study spec is WIT-authored (J1 specified). Reported as-is (the prompt asked for exactly what lands there).
  2. Wire `data.dataset` for the event study is `"ES_1min_continuous"` / `granularity_needed: "1min"` (the event study composes 5-/15-min candles from 1-minute bars) — a Class-B-specific data label, distinct from Class A's `"ES_5min_continuous"`. Cosmetic (the engine adapter reads only the window).
  3. No dependency added; `requirements.txt` untouched; Class A path, scorer, schema, and fixtures untouched (as required).

**The mapper vertical is now complete** (Class A → StrategyConfig → VPORBConfig; Class B → EventStudyConfig; Class C → refuse), both anchors reproducing their published run configs exactly. P3d (the `/wit/v1/*` router) follows.

WIT-P3c-3 — Completed

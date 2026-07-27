# WIT-P3e-1 — extraction prompt builder (mode vocab from contract/modes.md; pure, no dep)

Prompt: **WIT-P3e-1** — build the extraction prompt/vocabulary layer. Pure, no new dependency, no network, no LLM call (that's P3e-2). On `wit-phase3` (new Phase-3 continuation branch off main).

---

## 1. STEP 0 result
- HEAD was **`155f831`** (WIT-P3i close-out): **yes**.
- `wit-phase3` created off `main` (was absent, as expected post-P3h): **yes** (`git switch -c wit-phase3`).
- Tree clean: **yes** — only the known untracked `pine/mes_net_pnl_v2.pine` (ignored).

## 2. prompt.py surface + per-dimension vocabulary

`api/wit/extraction/prompt.py` (pure stdlib + `wit.extraction.schema`; resolves `_HERE/_API/_REPO` exactly like `schema.py`; reads `contract/modes.md` at runtime via `lru_cache` → single source of truth). Exposes all four:
- **`supported_modes()`** and **`unsupported_modes()`** — **per-dimension** (`dict[str, list[str]]`), never a global set. A token is supported iff **not** immediately followed by `†`.
- **`build_system_prompt()`** and **`build_user_prompt(transcript, source_meta)`**.

**`supported_modes()` is per-dimension and `none` is supported ONLY for `filters`: yes.** Verified output:
```
bias: [vp_value_area_break]          setup: [volume_profile_range]
entry.trigger: [bar_close_beyond_level, bar_body_beyond_level]   entry.level: [va_high_low]
order: [market_on_close]             sizing: [fixed_contracts]     stop: [level_offset]
target: [r_multiple]                 time_exit: [force_flat]       same_bar: [stop_first, target_first]
session: [rth_window]                filters: [none]               instrument: [futures_proxy, direct]
event: [body_vs_trailing_median]     path_bucket: [path_threshold, path_percentile]
regime: [kaufman_er_trailing_median, kaufman_er_insample_median, kaufman_er_fixed, adx_threshold]
timeframe: [5min, 15min]
```
`none` appears only under `filters` (written `` `none` (v1) ``); the `none` under bias/target/time_exit/regime is `†`-marked and is in `unsupported_modes()` for each — proving the parse is per-dimension, not collapsed. The 7 never-supported tokens `{orb_break, opening_range, orb_high_low, market_next_open, structure, level, fixed_time}` appear in **no** dimension's supported list.

The system prompt encodes, as testable content: the WIT-02 §1/§4 rules (source_quote must be a **verbatim substring**; **no charitable completion → vague ⇒ unspecified**; **setup (D2) ≠ entry trigger (D3)**; capture **every performance claim**; **class is an output, not an input** — the model never sets `completeness.class`; alternate readings → `interpretations[]`); the full **27-field spec** grouped A–K (ids from `FIELD_IDS`, with an `assert` that all 27 are covered); and the **per-dimension supported vocabulary** with the instruction to leave `mode` null (not invent one) when a construct isn't listed. It offers **none** of the 7 unsupported tokens (the F1/F2 field purposes were reworded so the English words "structure"/"level" don't leak as standalone tokens).

## 3. Tests + full suite
- New file **`api/tests/test_extraction_prompt.py`** — **9 tests**: vocabulary golden (`supported_modes() == EXPECTED_SUPPORTED`), per-dimension spot-asserts, `none` is per-dimension (proved via `unsupported_modes`), never-supported disjoint from supported, prompt contains every supported token, prompt offers no unsupported token (5 distinctive absent + `structure`/`level` not standalone), prompt encodes each key rule phrase, prompt references all 27 field ids, user prompt includes transcript + meta.
- **Full suite: 190 passed** (181 prior + 9 new), 0 failed. No regression, no new dependency (pure stdlib + `wit.extraction.schema`); `requirements.txt` untouched.

## 4. Commit + push
- Commit on `wit-phase3` (subject `WIT-P3e-1: extraction prompt builder — mode vocab from contract/modes.md († excluded), pure/no-dep`); files: `api/wit/extraction/prompt.py`, `api/tests/test_extraction_prompt.py`, this report. **Pushed to `origin/wit-phase3`: yes** (concrete SHA in the terminal report-back).
- Note: pushing `wit-phase3` does not trigger CI (`ci.yml` runs on PR/push to `main` only) — the local 190-green suite is the gate until the phase-end checkpoint merge.

## 5. Anything unexpected
- One reword needed to keep the "no unsupported token in the prompt" guarantee clean: the F1/F2 field-purpose prose originally used the English words "structure" and "none/absent"; since `structure` and `level` are also unsupported mode tokens, the purposes were reworded ("distance in points or ATR"; "fixed dollar amount, an R-multiple, or absent") and the test checks `structure`/`level` only as **standalone** words (compounds like `entry.level`, `level_offset`, `bar_close_beyond_level` are legitimate and expected). `none` is *not* in the 7-token never-supported set (it's supported for `filters`), so it legitimately appears in the vocabulary block.
- The vocabulary golden is a deliberate v1 pin: when the engine gains a construct, removing its `†` in `modes.md` will make this test fail until `EXPECTED_SUPPORTED` is updated in that slice — intended, not a maintenance surprise.

WIT-P3e-1 — Completed

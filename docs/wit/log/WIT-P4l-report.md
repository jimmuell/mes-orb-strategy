# WIT-P4l — profile granularity is a §5 lab default; unrecognised granularity fails typed instead of crashing on an empty frame

## STEP 0
Gate passed: remote `jimmuell/mes-orb-strategy`, path `/Users/jameslmueller/Projects/mes-orb-strategy`,
HEAD **a56ebe2** (WIT-P4k). Read WIT-02 §5 (volume-profile clause: "Volume-profile/intrabar features →
computed from finest licensed data; approximation disclosed (B3)") and `vp_orb_runner.py` 110-135 /
240-255.

## The defect (fifth live end-to-end failure, 2026-07-29)
Extraction, mapping, and the run all succeeded; the job died inside the daily signal loop with
`AttributeError: 'RangeIndex' object has no attribute 'normalize'`. Cause: D2 params carried
`granularity: "ticks_per_row_1"`. The runner branched on exactly two values and handled neither case
safely — `run_vp_orb` loaded the 1-min opening data ONLY for `== "1min"` else assigned an empty
placeholder DataFrame (RangeIndex), and `_opening_profile` used 5-min bars for `== "5min"` else took the
1-min path and called `.index.normalize()`. An unrecognised token skipped the loader AND took the 1-min
path, indexing an empty RangeIndex frame as if timestamped. The token is a category error: "one tick per
row" is the profile's PRICE-row size (fixed at TICK_SIZE), not the DATA time-resolution this field means.

## 1. Mapper — D2 granularity is a §5 lab default (`_profile_granularity`)
```python
_VP_GRANULARITIES = ("1min", "5min")
def _profile_granularity(d2: dict) -> tuple[str, bool]:
    g = d2.get("granularity")
    if g in _VP_GRANULARITIES:
        return g, False
    return "1min", True
```
The D2 granularity is **advisory**: used only when it is exactly `"1min"` or `"5min"`; for anything else
(null, absent, or a category error like `"ticks_per_row_1"`) it defaults to `"1min"` — the finest
licensed data (WIT-02 §5). Both wire sites — `data.granularity_needed` and `setup_entry.params.granularity`
— now emit the effective value. **Disclosure:** when defaulted, `assumptions_applied.append("B3_granularity")`,
recorded the same way the other §5 defaults are (WIT-P4i). **Not a silent substitution of strategy
semantics:** the profile's price-row size is TICK_SIZE and is untouched by this function; only the
disclosed DATA resolution is defaulted (stated in the code comment).

## 2. Runner — no unreachable branch, no crashing placeholder
Two new typed exceptions (same style as WIT-P4j's `EmptyDataWindow`, each with a WIT-03 §3.7 `.code`):
- `UnsupportedGranularity` — **code `UNSUPPORTED_CONSTRUCT`** (an engine-capability limit). Raised at the
  TOP of `run_vp_orb`, BEFORE any data load: `if cfg.vp_granularity not in ("1min", "5min"): raise
  UnsupportedGranularity(cfg.vp_granularity)`. After this, both the loader branch and `_opening_profile`
  see exactly `{"1min","5min"}` — the previously-unreachable/ambiguous fall-through is gone.
- `EmptyOpeningData` — **code `DATA_UNAVAILABLE`**. On the 1-min path, after loading (or receiving) the
  opening frame: `if len(one_min_open) == 0 or not isinstance(one_min_open.index, pd.DatetimeIndex):
  raise EmptyOpeningData(...)`. The empty placeholder is now assigned ONLY on the 5-min path (where the
  1-min frame is never indexed), so `.index.normalize()` can never hit a RangeIndex.

## 3. Fall-through audit (adapter + runner)
Searched for the shape "a template value selects a code path where an unrecognised value falls through to
a branch assuming a different one."
**FIXED this slice (would crash):**
- `vp_orb_runner.py:143` `_opening_profile` `if vp_granularity == "5min" else <1-min>` — now exhaustive
  via the new top-of-`run_vp_orb` guard (only 1min/5min reach it).
- `vp_orb_runner.py` (`run_vp_orb` granularity branch, the original bug) — typed guard + exhaustive
  1min/5min handling + `EmptyOpeningData`.

**LATENT — guarded upstream, no crash/fabrication today; listed for a later slice (not changed):**
- `vp_orb_runner.py:159,161` `_qualifies`: `(row.Close > level) if mode == "close" else <body>`. `mode`
  is `entry_mode`, which `strategy_config_to_vporb` already validates (WIT-P4i: trigger → "close"/"body",
  else raises). An unrecognised mode would fall to the body branch, but cannot reach here.
- `vp_orb_runner.py:241` `_resolve_exit`: `if cfg.same_bar_policy == "target_first": … else <stop_first>`.
  `same_bar_policy` is validated at map time (WIT-P4k: F5 mode ∈ FIELD_MODE_VOCAB) and §5-defaulted to
  `stop_first` when unspecified (WIT-P4i). An unrecognised value would fall to the conservative stop-first
  branch, but cannot reach here.

**Not template-driven (out of scope):** `direction == "long"` branches (`:158,193,228,307,312`) and
`exit_reason` "tp"/"sl"/"time" are computed by the engine's signal logic, not read from the template.
**Already exhaustive (raise on unknown, no fall-through):** `mapper.py` trigger (`:295-297`, WIT-P4i
else-raise); Class-B `event_study_config_to_engine` path/regime tokens (`if token not in MAP: raise`).

## 4. Tests
`test_mapper.py` (3): unrecognised granularity → `"1min"` on both wire sites + `B3_granularity` disclosed;
explicit `"5min"` honored, NOT disclosed; explicit `"1min"` honored, NOT disclosed.
`test_vp_orb.py` (2): unrecognised `vp_granularity` → `UnsupportedGranularity` (`UNSUPPORTED_CONSTRUCT`)
raised before any load; a required-but-empty 1-min frame → `EmptyOpeningData` (`DATA_UNAVAILABLE`), never
an `AttributeError`.
Also updated `test_P4j_empty_frame_raises_typed_error_not_indexerror` (NOT a golden/fixture/threshold —
a WIT-P4j runner test): its convenience `one_min_open=empty` now trips the new opening-data guard first,
so it passes a non-empty 1-min frame to still isolate the 5-min empty-window guard. Same assertion.

## Suite counts + goldens
- Before (HEAD a56ebe2): **287 passed / 0 failed / 2 skipped**.
- After: **292 passed / 0 failed / 2 skipped** (287 + 5 new).
- **Both anchor goldens BYTE-IDENTICAL:** `test_mapper.py` G1 (T-0001 → `VPORBConfig()`) and G2
  (T-0002 → `EventStudyConfig()`) pass unchanged — the fixture carries granularity `"1min"`, so the §5
  default is a no-op there (no `B3_granularity` disclosure, granularity emitted verbatim). Confirmed.
- **No fixture, threshold, or extraction prompt touched:** staged files are `wit/mapper.py`,
  `wit/vp_orb_runner.py`, `tests/test_mapper.py`, `tests/test_vp_orb.py` only; `api/tests/fixtures/*`,
  `wit/extraction/prompt.py`, `contract/modes.md`, `wit/extraction/schema.py`, and the schema JSON are
  untouched.

## Commit
- Subject: `WIT-P4l: profile granularity is a §5 lab default; unrecognised granularity fails typed instead of crashing on an empty frame`
- Hash + URL: recorded in the report-back after push.

WIT-P4l — Completed

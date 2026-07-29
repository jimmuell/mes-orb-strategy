# WIT-P4i — mapper applies the WIT-02 §5 default assumptions; null entry trigger no longer silently becomes a body entry

## STEP 0
Gate passed: remote `jimmuell/mes-orb-strategy`, path `/Users/jameslmueller/Projects/mes-orb-strategy`,
HEAD **dee4286** (WIT-P4h). Read `WIT-02` §5 (Default Assumption Policy) and
`docs/wit/log/WIT-P3q-adjudication.md` (fixtures FINAL; R1–R3) before editing. Touched
`api/wit/mapper.py` and `api/tests/test_mapper.py` only.

## The defect (second live end-to-end failure, 2026-07-29)
A Class-A extraction left `E1` with mode null / params null (the video never states sizing — most
don't). The wire config carried `sizing {mode: null, value: null}` and the adapter raised
`UNSUPPORTED_CONSTRUCT "E1: mode 'None:None' not supported in engine v1"`. WIT-02 §5 says sizing
defaults to 1 contract when unspecified, but nothing implemented it: the mapper LABELS assumed fields
(`assumed()` appends B3/E1/F4/F5/H1/H2) yet never SUPPLIED the defaulted values. The ratified anchor
`WIT-T-0001` hides this — it was hand-authored with the §5 values already filled (E1 fixed_contracts/1,
H1 0.62, H2 1, F4 force_flat, F5 stop_first) despite every one being status `unspecified`.

## 1. The §5 defaults table (as written)
```python
_SECTION5_DEFAULTS = {
    "E1": {"mode": "fixed_contracts", "params": {"value": 1}},
    "H1": {"params": {"commission_per_side": 0.62}},
    "H2": {"params": {"slippage_ticks": 1}},
    "F4": {"mode": "force_flat"},
    "F5": {"mode": "stop_first"},
}
```
No field outside this list gets a default. B3 stays in `assumed()` unchanged (a data-layer
disclosure, not a wire value). D3/D4 get no default — Class A requires them; a null must fail loudly.

## 2. Exact guard conditions under which a default fires
Two per-key accessors, `_defaulted_mode(template, fid)` and `_defaulted_param(template, fid, key)`.
A §5 default is supplied for a given mode/param key IFF **BOTH**:
1. the field's `status == "unspecified"`, AND
2. that specific mode/param is null-or-absent (`_mode(...) is None`, or `_params(...).get(key) is None`,
   which is None whether the key is present-and-null or absent).
It NEVER overrides a specified/implied value, NEVER fires on a specified/implied field, and is applied
**per key** — an unspecified H1 that already carries a `commission_per_side` keeps it. A required
field with a null mode and no §5 default (e.g. D3/D4) stays None and fails downstream, never defaulted.
The accessors replaced the raw reads for `sizing` (E1), `costs` (H1/H2), and `exits.time_exit`/
`exits.same_bar_policy` (F4/F5) in the Class-A config assembly. `assumptions_applied` is unchanged in
shape and content — `assumed()` already appends a field on `status == unspecified`, so a defaulted
field still appears (verified byte-identical on the anchor). The now-dead `h1`/`h2` locals were removed.

## 3. The adapter change + full silent-coercion audit of `strategy_config_to_vporb`
FIXED — the one silent null-to-default coercion:
```python
    # WIT-P4i: a NULL or unknown trigger must fail loudly — never silently become a body entry.
    trigger = wire["setup_entry"]["trigger"]
    if trigger == "bar_close_beyond_level":
        entry_mode = "close"
    elif trigger == "bar_body_beyond_level":
        entry_mode = "body"
    else:
        raise UnsupportedConstruct(field="D3", mode=trigger)
```
Previously `entry_mode = "close" if trigger == "bar_close_beyond_level" else "body"` turned a null (or
any non-close) trigger into a body-entry backtest — a fabricated result presented as real.

Audit of the rest of the adapter — every other branch already FAILS LOUD, none silently defaults:
- `session.tz != _ET_TZ` → raises C1 (a null tz ≠ ET → raises). Not silent.
- `bias.mode != "vp_value_area_break"` → raises D1 (null → raises).
- `setup_entry.order != "market_on_close"` → raises D4 (null → raises — the required-D4 loud fail).
- `sizing.mode != "fixed_contracts" or value != 1` → raises E1 (after §5 defaults this is fixed_contracts/1).
- `exits.time_exit != "force_flat"` → raises F4.
- `entry_mode` ternary → the ONLY silent null→default; fixed above.
Reported, judged OUT OF SCOPE (not changed): the pass-through reads `stop.ticks` (F1), `target.value`
(F2), `same_bar_policy`, and `data.window` propagate the source value/None into `VPORBConfig(...)`
without substituting a default. These are REQUIRED Class-A fields (F1/F2) or already §5-defaulted (F5)
/ scorer-gated (window) — a null there is a completeness/scorer condition, not an adapter fabrication,
and §5 explicitly does NOT default them. `event_study_config_to_engine` (Class B) is a different
adapter (not "that adapter") and has its own explicit raises, no entry_mode-style coercion.

## 4. Tests (each new test + what it proves) — `tests/test_mapper.py`
- `test_P4i_unspecified_E1_defaults_to_one_contract` — unspecified E1 (mode+params null) → `sizing ==
  {mode: fixed_contracts, value: 1}` and E1 in `assumptions_applied`. Proves the default is supplied + disclosed.
- `test_P4i_specified_E1_is_not_overwritten` — a SPECIFIED E1 with value 5 → `sizing.value == 5`, E1 NOT
  in assumptions_applied. Proves a default never overwrites source, never fires on a specified field.
- `test_P4i_unspecified_costs_default_to_policy` — unspecified H1/H2 → `costs == {0.62, 1}`, both disclosed.
- `test_P4i_partially_filled_unspecified_H1_keeps_its_value` — unspecified H1 carrying commission 1.5 →
  kept 1.5 (not 0.62). Proves per-KEY application.
- `test_P4i_unspecified_F4_F5_default_to_policy` — unspecified F4/F5 → force_flat / stop_first.
- `test_P4i_null_trigger_raises_not_body_entry` — a wire config with `trigger: null` →
  `UnsupportedConstruct(field="D3", mode=None)` at the adapter, not a body-entry config.

## Suite counts + goldens
- Before this slice (HEAD dee4286): **269 passed / 0 failed / 2 skipped**.
- After: **275 passed / 0 failed / 2 skipped** (269 + 6 new P4i tests).
- **Both anchor goldens BYTE-IDENTICAL:** `test_mapper.py` G1 (T-0001 → `VPORBConfig()` exact) and G2
  (T-0002 → `EventStudyConfig()` exact) both pass unchanged — verified directly that `map_template`
  on the fixture yields the same `sizing`/`costs`/`exits` as before (all §5 defaults are no-ops there
  because the fixture already carries the values). **No fixture, threshold, or extraction prompt was
  touched** (staged files: `api/wit/mapper.py`, `api/tests/test_mapper.py` only; `api/tests/fixtures/*`,
  `prompt.py`, `contract/modes.md` untouched).

## Commit
- Subject: `WIT-P4i: mapper applies the WIT-02 §5 default assumptions; null entry trigger no longer silently becomes a body entry`
- Hash + URL: recorded in the report-back after push.

WIT-P4i — Completed

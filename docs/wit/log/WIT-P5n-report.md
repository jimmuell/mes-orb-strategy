# WIT-P5n — every engine parameter specified, enforced at the boundary, disclosed in the result

Governing principle applied throughout: **an audit must be true to what was actually tested.** All three
pillars delivered. `volume_profile.py` and `vp_orb_runner.py` trading logic, all fixtures, all goldens,
and every extraction prompt are untouched. WIT-P5m was authored but deliberately never run (superseded by
this slice); its prompt is archived in this commit.

## STEP 0
Gate passed: remote `jimmuell/mes-orb-strategy`, path correct, HEAD == origin/main == `cb0c621`
(WIT-P5l). The P5m archive was present untracked and is committed here.

## Dependency decision (Pillar 2)
**A minimal in-repo validator, no new dependency.** `jsonschema` is not installed and not importable;
`api/requirements.txt` is a FULL LOCK (every direct dep AND its entire transitive closure pinned `==`,
dev == prod, CI runs `pip-audit` via `scripts/audit_gate.py` on every PR — ADR-048/049/050). Adding
`jsonschema` pulls in `attrs`, `referencing`, `jsonschema-specifications` and the `rpds-py` Rust
extension, each of which would have to be pinned and pass the audit gate on a fresh install — which
cannot be confirmed from here, and WIT-P5n forbids adding a dependency without confirming the gate. So
`api/wit/config_validator.py` (117 lines) reads the SAME shipped contract the drift gate protects and
enforces exactly the JSON-Schema keywords those contracts use (type incl. integer/number, const, enum,
required, additionalProperties:false, properties, items, minItems/maxItems, minimum/maximum,
exclusiveMinimum/exclusiveMaximum). This matches the existing "no dep" structural-hygiene pattern.

## Shipped-contract drift gate
No sync SCRIPT exists — the gate (`tests/test_data_paths.py::test_shipped_copy_byte_identical`) only
asserts `api/_shipped/<f>` is byte-identical to the repo original and tells you to `cp`. I re-copied the
three edited files (`cp contract/strategy-config.v1.json api/_shipped/contract/…`, likewise the
event-study contract and the template schema) and the drift gate passes (10/10).

## Pillar 1 — the complete field specification (Class A wire = StrategyConfig)
"H" = HONOURED (affects the run); "H-gate" = honoured via an adapter/runner hard gate that raises
UNSUPPORTED_CONSTRUCT; "N" = declared but NOT applied in v1 (baked; disclosed, not enforced).

| field | type | unit / domain | constraint enforced | H/N |
|---|---|---|---|---|
| config_version | string | — | const "1.0" | H |
| instrument.symbol / tick_size / tick_value / proxy_for | string / number / number / string\|null | — | type only (baked economics) | N (notapplied_instrument_symbol) |
| data.dataset | string | — | type only | N (notapplied_data_dataset) |
| data.granularity_needed | string | — | type only | N (notapplied_data_granularity_needed) |
| data.window.start / end | string | ET date | type only | H |
| session.tz | string | tz name | H-gate (must be America/New_York → C1) | H |
| session.trade_window | array[string] | [entry_start, cutoff] | exactly 2 items | H |
| session.force_flat | string | ET time | type only | N (notapplied_session_force_flat) |
| filters.regime / calendar | array | — | type only | N (notapplied_filters_*) |
| bias.mode | string | — | H-gate (must be vp_value_area_break → D1) | H |
| setup_entry.trigger | string | — | H-gate (close/body → D3) | H |
| setup_entry.level | string | — | type only | N (notapplied_setup_entry_level) |
| setup_entry.order | string | — | H-gate (market_on_close → D4) | H |
| setup_entry.params.range_start / range_end | string | ET time | type only | H |
| **setup_entry.params.value_area_pct** | number | **FRACTION (0,1]; 0.70 = 70%** | **exclusiveMinimum 0, maximum 1** (normalized if in (1,100]) | H |
| setup_entry.params.granularity | string | — | H-gate (5min/1min → runner, WIT-P4l) | H |
| sizing.mode / value | string / number | 1 contract | H-gate (fixed_contracts / 1 → E1) | H |
| exits.stop.mode | string | — | type only | N (notapplied_exits_stop_mode) |
| exits.stop.ref | string | — | type only | N (notapplied_exits_stop_ref) |
| **exits.stop.ticks** | number | ticks | **exclusiveMinimum 0 (positive only, WIT-P5i)** | H |
| exits.target.mode | string | — | type only | N (notapplied_exits_target_mode) |
| exits.target.value | number | R-multiple | exclusiveMinimum 0 | H |
| exits.management | array | — | type only | N (notapplied_exits_management) |
| exits.time_exit | string | — | H-gate (force_flat → F4) | H |
| exits.same_bar_policy | string | — | **enum [stop_first, target_first]** (validator — runner has NO gate) | H |
| risk_controls.max_trades_per_day | integer | — | type only | N (notapplied_risk_controls_max_trades_per_day) |
| risk_controls.reentry | string | — | type only | N (notapplied_risk_controls_reentry) |
| costs.commission_per_side | number | USD/side | minimum 0 | H |
| costs.slippage_ticks | integer | ticks | minimum 0 | H |

Class B (event-study wire): `event.k` (>0), `event.n_baseline` (int >0), `path_bucket.spike_eff` /
`spike_giveback_cap` / `pullback_p` (**FRACTION [0,1]**), `regime.regime_fixed_er` (**FRACTION [0,1]**),
`regime_er_m` / `regime_trailing_window` / `regime_adx_len` (int >0), `regime_adx_thresh` ([0,100]);
enums on `event.mode`, `path_bucket.mode`, `bucket_mode`, `regime.mode`, `timeframe`, `measures`. All
HONOURED (the P5l MED-risk fraction fields are now range-bounded).

**Design decision — why not all enums are validator-enforced:** a field the ADAPTER/RUNNER already hard-
gates (tz, bias.mode, order, trigger, sizing, time_exit, granularity) is relaxed to `type: string` in the
contract with the allowed set in its `description`, so the hard gate keeps owning the error type
(**UNSUPPORTED_CONSTRUCT**, e.g. `test_unknown_mode_unsupported_construct` submits tz=America/Chicago →
C1). Enum/range enforcement (**INVALID_CONFIG**) is applied where there is NO gate — most importantly
`value_area_pct`, `stop.ticks` (positive), and `same_bar_policy` (previously a silent fall-through to
stop_first). This keeps the two error classes coherent: engine-capability limit → UNSUPPORTED_CONSTRUCT;
malformed value → INVALID_CONFIG.

## Pillar 2 — enforcement (two validation points, same contract)
1. **Mapper output** — `wit/mapper.py:347` `validate_wire(config, "backtest")` (and `:471` for Class B),
   after `normalize_and_disclose` at `:346`. The mapper refuses to return a non-conforming wire.
2. **Inbound boundary** — `server.py:2051` `validate_wire(config, kind)` inside `_adapt_wire`, after
   `normalize_and_disclose` at `:2050`. Catches anything bypassing the mapper (e.g. a front-office
   cache-hit that replays a stored wire with `value_area_pct = 70`).
**Ordering:** normalize BEFORE validate at both points, so a source that correctly says "70%" is
corrected, not rejected.
**Rejection envelope:** `InvalidConfig(ValueError)` (`code = "INVALID_CONFIG"`, carries `.field`) →
`server.py` returns the existing envelope `{"error": {"code": "INVALID_CONFIG", "message": "config
failed contract validation — <path>: <why>", "detail": {"field": "<path>"}}}` (a dedicated `except
InvalidConfig` precedes the generic `ValueError` catch in both `wit_submit_run` and `wit_map_template`).
Never a bare TypeError — a `null`/`"0.70"`/NaN value_area_pct is rejected at the boundary before any
engine arithmetic.

## Pillar 3 — disclosure (feeds the existing assumptions_applied)
- **D2_value_area_normalized** — `value_area_pct` in (1,100] is divided by 100 and this code is recorded;
  a value already in (0,1] passes with no code; anything else is rejected (Pillar 2). (`normalize_and_
  disclose`, `mapper.py:84`.)
- **notapplied_&lt;path&gt;** — a declared-but-not-applied field whose specified value differs from the
  baked constant records `notapplied_` + the underscore-joined path (e.g. `notapplied_exits_stop_ref`,
  `notapplied_setup_entry_level`, `notapplied_risk_controls_max_trades_per_day`). The baked table is
  `_BAKED_NOT_HONOURED` in `mapper.py` (ref→poc, stop.mode→level_offset, target.mode→r_multiple,
  max_trades_per_day→1, reentry→none, force_flat→15:55, level→va_high_low, dataset→ES_5min_continuous,
  granularity_needed→1min, instrument.symbol→ES, filters.*/management→[]). Applied uniformly.
Both are **idempotent** (re-running adds nothing), so the mapper and the inbound boundary can both run
them. `wit/vocab.py` was NOT modified — the disclosure codes are computed data-driven from the baked
table in `mapper.py`; no shared vocabulary constant was required.

**Verified behaviour:** anchor → codes `{B3,E1,F4,F5,H1,H2,initial_capital}` (no new codes); `70` →
`0.70` + `D2_value_area_normalized`; `100` → `1.0` + code; production CONFIG A →
`{D2_value_area_normalized, notapplied_setup_entry_level, notapplied_exits_stop_ref}`.

## Tests added (`tests/test_config_validation.py`, 11 — no existing test modified)
value_area_pct boundary table (0.7, 1 accept; 70→0.70, 100→1.0 normalize+code; 0, -1, 101, null, "0.70",
NaN, +inf reject); already-fraction gets no code; negative & zero stop.ticks rejected, positive OK;
enum out-of-set rejected (same_bar_policy, target.value, costs); event-study enum+range (timeframe,
spike_eff=50); not-honoured out-of-enum values ACCEPTED (ref=point_of_control, level=value_area_high_or_low);
not-honoured non-default value discloses its code; conforming config has no spurious codes; disclosure is
idempotent; **inbound boundary** rejects null value_area_pct and negative ticks bypassing the mapper
(clean 400 INVALID_CONFIG with the field named), and normalizes 70 (202) while rejecting 101 (400).
Result: **11 passed.**

## Suite counts + golden evidence
- Before: **308 passed / 0 failed / 2 skipped**. After: **319 passed / 0 failed / 2 skipped** (+11).
- **Every golden is byte-identical — how I satisfied myself:** (a) `git diff --stat` over
  `api/tests/fixtures/` and `docs/wit/reports/` is EMPTY (no fixture or published report touched);
  (b) G1 (`cfg == VPORBConfig()`) passes — `value_area_pct` 0.7 ≤ 1 so normalization is a no-op and the
  adapted dataclass is unchanged; (c) the anchor's `assumptions_applied` is unchanged
  (`{B3,E1,F4,F5,H1,H2,initial_capital}` — no `D2_value_area_normalized`, no `notapplied_*`, because
  every anchor value equals its baked constant and va=0.7), so G1's superset assertion and every
  membership assertion still hold; (d) the `test_vp_orb` volume-profile golden passes (`volume_profile.py`
  untouched); (e) the full suite is green with zero existing tests edited. **No golden moved.**

## Commit
- Subject: `WIT-P5n: every engine parameter specified, enforced at the boundary and disclosed`
- Hash + URL: recorded in the chat report-back after push.

WIT-P5n — Completed

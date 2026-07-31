# WIT-P5i — which wire-config fields does the engine actually honour? (read-only findings)

**No behaviour changed.** No fixture, golden, threshold, prompt, or engine source file was edited.
Only read-only reproduction scripts were run against the shipped parquet. A fix is recommended in §4/§7
and awaits founder ratification (a change could move goldens; goldens are never tuned).

## STEP 0
Gate passed: remote `jimmuell/mes-orb-strategy`, path `/Users/jameslmueller/Projects/mes-orb-strategy`.
HEAD == origin/main == **`86ee041`**, subject **"WIT-P4x: session-7 close-out — reviewer desk, verdict
rule, public library, PRD v2, security baseline"** — matches the expected `86ee041` / "WIT-P4x:
session-7 close-out". No pull/reset/checkout/stash.

## The single channel to the runner
A backtest wire config reaches the engine through exactly one funnel:
`wire dict → strategy_config_to_vporb(wire) (mapper.py) → VPORBConfig → run_vp_orb()`.
**`VPORBConfig` is the ONLY thing the runner sees.** Any wire key the adapter does not copy into a
`VPORBConfig` field is invisible to the runner by construction. `VPORBConfig` has 17 fields; three
(`min_opening_bars`, `min_opening_bars_5min`, `initial_capital`) take dataclass defaults, not the wire.

## 1. HONOURED vs IGNORED

### HONOURED — read by the adapter, affect the run
| wire key | VPORBConfig field | how the runner uses it |
|---|---|---|
| `data.window.start` / `.end` | `start_date` / `end_date` | data slice + engine date range |
| `session.trade_window[0]` | `entry_window_start` | `entry_candidates = five_day[t >= ews …]` |
| `session.trade_window[1]` | `entry_window_last_bar` | `… & t <= ewl` |
| `setup_entry.trigger` | `entry_mode` (`close`/`body`) | `_qualifies` close-vs-body test |
| `setup_entry.params.range_start` / `range_end` | `range_start` / `range_end` | opening VP window (1-min via `load_1min_opening`; 5-min via `_opening_profile`) |
| `setup_entry.params.value_area_pct` | `value_area_pct` | `build_volume_profile` value-area width |
| `setup_entry.params.granularity` | `vp_granularity` | 1-min vs 5-min profile path |
| `exits.stop.ticks` **(incl. sign)** | `stop_offset_ticks` | `off = ticks*TICK_SIZE`; `sl = poc ∓ off` |
| `exits.target.value` | `rr_target` | `tp = entry ± rr*R` |
| `exits.same_bar_policy` | `same_bar_policy` | tie-break in `_resolve_exit` |
| `costs.commission_per_side` | `commission_per_side` | engine `commission_per_rt = 2×` |
| `costs.slippage_ticks` | `slippage_ticks` | engine slippage |

**Validated-as-baked-constant** (not passed as config, but NOT ignored — the adapter raises
`UnsupportedConstruct` if they diverge, so they gate acceptance): `session.tz` (must be ET),
`bias.mode` (`vp_value_area_break`), `setup_entry.order` (`market_on_close`), `sizing.mode`
(`fixed_contracts`) + `sizing.value` (== 1), `exits.time_exit` (`force_flat`).

### IGNORED — present in the wire, never consumed by the run
| wire key | where it STOPS |
|---|---|
| **`exits.stop.ref`** | **Absent from the adapter.** `strategy_config_to_vporb` never reads `exits.stop.ref`; `VPORBConfig` has no `ref` field; the runner **always** uses `vp.poc` as the stop reference (`sl = vp.poc ∓ off`). `"poc"`, `"point_of_control"`, and `"nonsense_value"` are indistinguishable to the engine. Grep: `ref` appears 0× in `vp_orb_runner.py`/`config.py`. |
| `exits.stop.mode` | Absent from the adapter — only `exits.stop.ticks` is read; `level_offset` geometry (`poc ∓ ticks`) is baked in the runner. |
| `exits.target.mode` | Absent from the adapter — only `exits.target.value` is read; `r_multiple` geometry (`entry ± rr·R`) is baked. |
| **`risk_controls.max_trades_per_day`** | Absent from the adapter; **baked** — `build_signals_for_day` returns at most one plan/day structurally (first qualifying break only). Grep: 0×. |
| `risk_controls.reentry` | Absent from the adapter; baked — the runner has no re-entry path. Grep: 0×. |
| **`filters.regime` / `filters.calendar`** | **Overwritten by a baked constant** — `map_template` emits `"filters": {"regime": [], "calendar": []}` unconditionally, the adapter never reads `filters`, and the runner never references it. Grep: 0×. (The WIT VP-ORB runner has no regime/calendar filtering at all.) |
| `instrument.*` (`symbol`/`tick_size`/`tick_value`/`proxy_for`) | Absent from the adapter; ES/MES economics baked (`TICK_SIZE=0.25`, engine `$5/pt`). Grep: 0×. |
| `data.dataset` | Absent from the adapter; the runner always reads the shipped ES parquet via `engine_data_path`. The `"ES_5min_continuous"` string is not consulted. |
| `data.granularity_needed` | Absent from the adapter; the profile resolution comes from `setup_entry.params.granularity`, not this key. Grep: 0×. |
| `session.force_flat` | Absent from the adapter; the runner force-flats at the day's LAST RTH bar structurally. The `"15:55"` string is not read. |
| `setup_entry.level` | Absent from the adapter; the runner uses VAH/VAL structurally. |
| `exits.management` | Baked empty `[]`; not read. |

## 2. Local reproduction (offline, shipped `api/data/` parquet)
One valid wire config, mapped through the real `strategy_config_to_vporb`, run through `run_vp_orb`.
**Primary window: 2020-01-02 … 2021-12-31** (2-yr, for speed — comparison matters, not absolutes).

| variant | trades | net_pnl | profit_factor | win_rate | max_drawdown | avg_trade | vs baseline |
|---|---:|---:|---:|---:|---:|---:|---|
| a. baseline (tw 09:45, ref poc, ticks +2) | 505 | −779.95 | 0.94780 | 35.6436 | −1709.21 | −1.54446 | — |
| b. trade_window start 09:45→**09:30** | 507 | −993.68 | 0.93281 | 34.9112 | −1832.94 | −1.95992 | **MOVED** |
| c. stop.ref poc→**point_of_control** | 505 | −779.95 | 0.94780 | 35.6436 | −1709.21 | −1.54446 | SAME |
| d. stop.ref→**nonsense_value** | 505 | −779.95 | 0.94780 | 35.6436 | −1709.21 | −1.54446 | SAME |
| e. stop.ticks **+2→−2** | 503 | −664.97 | 0.95073 | 35.5865 | −1550.60 | −1.32201 | **MOVED** |

**Which moved:** (b) trade_window start and (e) ticks-sign moved the numbers. (c) and (d) — the two
stop.ref changes — did **not** move a single digit.

**Full-window confirmation (2008-01-02 … 2026-04-09), baseline geometry, trade_window start only:**
- `09:45` → **4623 trades**, net −12823.77, pf 0.86965 … 
- `09:30` → **4635 trades**, net −18943.65, pf 0.80966 … 

So over the full window the 15-minute-wider entry window **changes the trade count (4623 → 4635)**.

### What this means for the live evidence — a correction
The engine **does honour `session.trade_window`**. The lead's premise ("a 15-minute-wider entry window
cannot leave the trade count unchanged if the window is honoured → something is ignored") is correct in
spirit but points at the wrong field: **trade_window is NOT the ignored field — `exits.stop.ref` is.**

Variant A and Variant B differ in **two** keys: `stop.ref` (IGNORED) **and** `trade_window[0]`
(HONOURED, 09:45 vs 09:30). Because trade_window is honoured, submitting these two genuinely-different
wire configs to this engine **cannot** produce byte-identical results — my reproduction shows 09:45 and
09:30 differ at both 2-yr and full-window scale, and neither equals the live 4161. Therefore the live
byte-identical A/B result is **not** attributable to the engine. It must originate upstream of the
engine (front office). Most likely one of:
  1. the two submissions were de-duplicated and one stored result was shown for both — but note
     `config_hash` (wit/config_hash.py) hashes the FULL canonical wire, so two configs differing in
     `stop.ref`/`trade_window` produce DIFFERENT hashes and would NOT dedupe in this engine's run store;
  2. the wire actually submitted for both users did not, in fact, differ in `trade_window` (e.g. the
     front office normalized/!overrode entry_start, or the "variants" differed only in the template and
     collapsed to one wire) — in which case the sole surviving difference is `stop.ref`, which the
     engine ignores, and byte-identical output is exactly what you'd expect.
**Recommended lead action:** pull the two runs' stored `config_json` + `config_hash` from the runs
table. If the hashes are equal, the wires were identical (only stop.ref-in-template differed and the
front office normalized it) and the engine behaved correctly. If the hashes differ, two distinct runs
executed and the identical result is a front-office display/caching bug — not an engine bug.

## 3. Contract enforcement
**No code validates an incoming config against the JSON-Schema contract.** There is no `jsonschema`
dependency ("Not a full JSON-Schema validation (no dep)" — mapper.py:264). The only inbound checks are
**required-top-level-key presence**, in two places, both key-only, neither enum-aware:
- `server.py:2043` on the `/wit/v1/runs` submit path — `missing = [k for k in _WIT_WIRE_REQUIRED[kind]
  if k not in config]`; `_WIT_WIRE_REQUIRED` is `json.load(...)["required"]` (top-level keys only).
- `mapper._structural_hygiene` (mapper.py:262) on the extraction→wire output — same top-level-key check.

`contract/strategy-config.v1.json` enumerates `exits.stop.ref` as `["poc","va","orb"]` and types
`exits.stop.ticks` as a bare `number` (no `minimum`, no sign constraint). Nothing enforces either. So
`"point_of_control"` (and `"nonsense_value"`, and a negative `ticks`) pass untouched — and are then
silently dropped by the adapter. The live engine accepting `"point_of_control"` is fully explained.

**Repo vs shipped contract:** `contract/strategy-config.v1.json` and
`api/_shipped/contract/strategy-config.v1.json` are **byte-identical** (`cmp` clean). They agree; both
carry the same enum, and both are equally unenforced.

## 4. The stop-offset sign
- **How the runner uses it:** `off = cfg.stop_offset_ticks * TICK_SIZE`; long `sl = round(vp.poc − off,
  10)`, short `sl = round(vp.poc + off, 10)`. The runner applies the protective side by **direction**;
  the ticks value supplies only the magnitude — except the sign is taken verbatim.
- **Positive vs negative:** a POSITIVE value is the only meaningful one — the stop sits on the
  protective side (below POC for longs, above for shorts). A NEGATIVE value is nonsense: it flips the
  stop to the wrong side of the POC (above POC for a long). It is partly neutralized by the runner's
  degenerate-R guard (`if r <= 0: return None` skips days where entry lands on the wrong side of its own
  stop), which is why variant (e) produced FEWER trades (503 vs 505) rather than a symmetric result —
  but for geometries where R stays positive, an inverted stop still runs and corrupts the result.
- **Should the sign be derived?** Yes. The side is already fully determined by trade direction inside
  the runner; the magnitude is all the config should carry. Letting an LLM emit the sign lets it place
  the stop on the wrong side. The mapper should pass `abs(ticks)` (or reject a non-positive `ticks` as
  `INVALID_CONFIG`), and the contract should constrain `exits.stop.ticks` to `exclusiveMinimum: 0`.
- **Tests/goldens that would change if the mapper derived it:** **none.** The anchor fixture WIT-T-0001
  has `stop.ticks = 2` (positive) → `abs(2) = 2` → G1 unchanged. No fixture uses a negative offset.

## 5. Blast radius — fixtures/goldens/tests touching the IGNORED keys
- `exits.stop.ref`: present as `"ref": "poc"` (IN-enum) in `tests/fixtures/WIT-T-0001.template.json:143`
  and as `"ref": "poc"` in the `_min_wire_backtest` wires in `tests/test_wit_router.py` and
  `tests/test_verdict.py`. **No test asserts on stop.ref behaviour**, and no golden depends on it
  (`VPORBConfig` has no `ref` field, so G1 cannot encode it).
- `risk_controls.max_trades_per_day` / `reentry` / `filters`: appear only as structural values in the
  same wire/template fixtures; goldens G1/G2 assert the mapped `VPORBConfig`/`EventStudyConfig`, which
  carry none of them. No dependency.
- **Would enforcing the contract enum move any golden? NO.** The anchor fixture's `stop.ref` is `"poc"`,
  which is in-enum; adding enum validation rejects only out-of-enum values, so G1/G2 stay byte-identical.
- **Would honouring `trade_window` move any golden? N/A / NO.** `trade_window` is *already* honoured;
  no change is needed and none is proposed, so nothing moves.

**Net: a fix (enforce the enum, reject/normalize out-of-contract `stop.ref`, derive the stop sign,
constrain `ticks > 0`) would move ZERO goldens.** It would, however, start REJECTING out-of-contract
inputs that today run silently — a behaviour change requiring founder ratification, hence read-only here.

## 6. Goldens a fix would move
**None.**

## 7. Suite
`cd api && BACKTEST_API_KEY=k python -m pytest -q` → **308 passed / 0 failed / 2 skipped** — unchanged
from baseline (no code, no tests, no fixtures touched).

## Archival note
`WIT-P5g` was superseded by `WIT-P5h` and never run; it is archived in this commit for the record
anyway, per instruction.

## Commit
- Subject: `WIT-P5i: investigate ignored wire-config fields — read-only findings`
- Hash + URL: recorded in the chat report-back after push.

WIT-P5i — Completed

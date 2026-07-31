# WIT-P5k — value_area_pct units defect: blast radius (read-only findings)

**No behaviour changed.** No fixture, golden, threshold, prompt, schema, contract, or engine source
file was edited. Read-only reproduction against the shipped `api/data/` parquet. A correction can move
goldens; founder ratification required.

## STEP 0
Gate passed: remote `jimmuell/mes-orb-strategy`, path correct, HEAD == origin/main == **`b050530`**
(WIT-P5j). No pull/reset/checkout/stash.

## 1. ORIGIN — where value_area_pct enters a wire config
The number is **LLM-supplied, from the extracted template.** In `map_template` (Class A),
`d2 = _params(template, "D2")` (`mapper.py:187`) and the wire is built with
`"value_area_pct": d2.get("value_area_pct")` (`mapper.py:238`); the adapter then forwards it verbatim,
`value_area_pct=sp["value_area_pct"]` (`mapper.py:312`).

- **No baked default on the wire path.** `d2.get("value_area_pct")` has no fallback constant and gets no
  §5 default (only `granularity`/`window` are §5-defaulted). If D2 omits it, the wire carries `null` →
  `VPORBConfig(value_area_pct=None)` → `build_volume_profile` computes `None * total` → it would crash,
  not default. So the value is whatever the LLM emitted.
- **Dataclass defaults of `0.70` exist but are bypassed on the wire path:** `config.py:25`
  (`VPORBConfig.value_area_pct = 0.70`) and `volume_profile.py:114` (`build_volume_profile(..,
  value_area_pct=0.70)`). These apply ONLY when the object/function is built WITHOUT the argument
  (research scripts, unit tests) — never on `strategy_config_to_vporb`, which always passes the wire value.
- **Does an audit whose source never mentions a value area still receive one?** The runner requires
  `bias.mode == "vp_value_area_break"` (baked; `mapper.py` raises `UnsupportedConstruct` otherwise), so
  only value-area-break strategies reach the backtest at all. Within that, `value_area_pct` is not
  defaulted — a source that declares the VP-break bias but states no width yields `null`, which does not
  gracefully become 0.70; it propagates as `null`. In practice the LLM fills it (e.g. `70`).

## 2. INTENDED UNIT — the consumer wants a fraction
`volume_profile._value_area` (`volume_profile.py:92-95`):
```python
total = rows.sum()
target = total * value_area_pct
```
For a standard **70% value area the code requires `value_area_pct = 0.70`** (`target = 0.70 × total` =
70% of volume). A value of `70` makes `target = 70 × total`, which cumulative volume can never reach, so
the greedy band expands to the whole profile and **VAH/VAL collapse to the opening-range High/Low**
(value_area_fraction = 1.000). 

**Which side is non-conforming: the PRODUCER (emitting `70`).** The consumer's fraction semantics is the
standard Market-Profile convention and is correct. But the field **name says `pct`** (implying 0–100)
while the consumer wants a fraction (0–1) — an unspecified-unit trap, and the unit is typed nowhere
(see §4). **I would change the producer** (extraction/mapper) to emit/normalize a fraction and **pin the
contract to state the unit explicitly**, NOT change the consumer: the consumer is the standard
convention and matches the published WIT-0001 and every anchor fixture (all `0.70`); making the consumer
divide by 100 would silently reinterpret those already-correct artifacts and the founding audit. The
contract is the published interface, so the fix belongs there (declare the field + unit) and at the
producer, leaving the consumer untouched.

## 3. THE PUBLISHED WIT-0001 — used 0.70, a genuine value area
The founding audit was produced by the **standalone research script**, not the wire/mapper path:
`wit/analysis.py:214` builds `primary = VPORBConfig()` — dataclass defaults, i.e.
**`value_area_pct = 0.70`**. Its provenance (`WIT-0001-results.json`) shows `engine_version 25.25.0`,
`vp_source ES_full_1min_continuous_UNadjusted.txt` (the raw `.txt`, predating the WIT-P4m parquet), i.e.
it predates the wire path.

- **What it tested:** a real **70% value-area break** (VAH/VAL strictly inside the opening range), NOT a
  full opening-range break. Primary metrics: **2,561 trades, PF 0.9027, win rate 34.32%, avg −$2.33**,
  2016-04-10→2026-04-09.
- **Its prose claims a value area:** yes — the report is titled "Volume-Profile Opening Range Breakout",
  and §Volume-profile approximation (line 115) states "POC/VAH/VAL come from that"; the short-side rule
  (line 109) is "POC + 2 ticks". It genuinely describes a value-area/volume-profile method, and the run
  matches (0.70). **The published WIT-0001 is correct as published** — the defect is confined to the
  production wire path, where LLM-extracted `value_area_pct = 70` silently turned the same strategy into
  an opening-range break.

## 4. FIXTURE / GOLDEN / ARTIFACT INVENTORY
| location | value | encodes the broken (≥1, unreachable-target) interpretation? |
|---|---|---|
| `tests/fixtures/WIT-T-0001.template.json:104` (D2 **machine** param — what the mapper reads) | **0.7** | **No** — conforming fraction; drives golden G1 |
| `tests/fixtures/WIT-T-0001.template.json:212` (free-text **prose** description) | `value_area_pct=70` | text only, never consumed — but this is the exact ambiguity that misled production LLMs |
| `tests/test_vp_orb.py:57` (volume-profile golden) | `0.70` | No — asserts value_area_volume 79.0 / fraction ≥ 0.70 |
| `tests/test_wit_router.py:84` (router wire) | `0.7` | No |
| `tests/test_verdict.py:134` (router wire) | `0.7` | No |
| `contract/strategy-config.v1.json` + `api/_shipped/contract/…` | **not a typed field** | value_area_pct is unconstrained — appears only in `modes.md` description text; no enum/min/max/unit |
| `schema/strategy-template.v1.json` + shipped | **not a typed field** | mentioned only in a description string (D2 machine-param example) |
| `docs/wit/reports/data/WIT-0001-results.json` | run used 0.70 (via `VPORBConfig()`) | No — a genuine value area |

**Every machine/consumed value in the repo is a conforming fraction (0.7/0.70).** No fixture, golden,
test, or shipped artifact encodes the unreachable-target interpretation. The only `70` in the repo is
the fixture's free-text prose (line 212), which is not consumed — but it is the documentation-level root
of the production mis-extraction and should be reconciled.

## 5. MAGNITUDE — CONFIG A (WIT-P5j), full window 2008-01-02→2026-04-09
| metric | value_area_pct = 70 (as-is / production) | value_area_pct = 0.70 (corrected) |
|---|---|---|
| trades | 4161 | 4623 |
| net_pnl | -8465.890083640523 | -12823.770111516336 |
| profit_factor | 0.9193420635532844 | 0.8696540178212495 |
| win_rate | 37.89954337899543 | 35.215228206792126 |
| max_drawdown | -15069.406289062921 | -15163.173750000398 |
| avg_trade | -2.0345806497573955 | -2.773906578307665 |

- **% change trades (70 → 0.70): +11.103100%** (4161 → 4623)
- **% change net_pnl (70 → 0.70): −51.475745%** (−8465.890083640523 → −12823.770111516336)

The correction is material: ~11% more trades and net P&L ~51% more negative. (Both interpretations lose
money here, but they are different strategies — an opening-range break vs a true value-area break.)

## 6. GOLDEN IMPACT
**None move.** A correction that normalizes the producer (`70 → 0.70`) or constrains the contract to a
fraction does not touch the anchor fixtures, because their **machine** values are already `0.7`
(`WIT-T-0001.template.json:104`) and every test uses `0.7`/`0.70`. Golden G1/G2 and the `test_vp_orb`
volume-profile golden stay byte-identical.

**No anchor fixture encodes the broken interpretation** — `WIT-T-0001`'s consumed D2 param is `0.7`.
**Caveat, named explicitly:** `WIT-T-0001.template.json:212` prose says `value_area_pct=70`; it is not a
golden and does not move any assertion, but it is inconsistent with the fixture's own machine value
(0.7) and is the documentation seed of the production defect. Fixing it is a prose reconciliation, not a
golden change — and per instruction nothing was edited.

## 7. RECOMMENDATION
Change the **producer, not the consumer**, and make the **contract state the unit**. Add `value_area_pct`
as a typed field in `contract/strategy-config.v1.json` and `schema/strategy-template.v1.json` defined
explicitly as a **fraction in (0, 1]** (`exclusiveMinimum: 0`, `maximum: 1`), and have the mapper
validate/normalize the extracted value (reject > 1, or divide a percentage by 100 with a disclosed
assumption) so an LLM emitting `70` cannot silently produce an opening-range break. Leave
`volume_profile.py` untouched — its fraction semantics is the standard Market-Profile convention and
matches the published WIT-0001 and every anchor fixture, so changing it would corrupt correct artifacts.
Reconcile the `WIT-T-0001` prose (line 212 "70") with its machine value (0.7). **Existing production
audits that carried `value_area_pct = 70` (or any value ≥ 1) tested an opening-range break, not the
value-area break their source described, and should be re-run under the corrected fraction and their
verdicts re-issued.** **The published WIT-0001 report needs NO correction notice** — it ran at 0.70 and
its prose accurately describes a value-area break; only the fixture-prose ambiguity that spawned the
producer defect should be cleaned up.

## 8/9. Suite + commit
- Suite: `cd api && BACKTEST_API_KEY=k python -m pytest -q` → **308 passed / 0 failed / 2 skipped** —
  unchanged (no code/tests/fixtures touched).
- Commit subject: `WIT-P5k: value_area_pct units defect — blast radius, read-only findings`
- Hash + URL: recorded in the chat report-back after push.

WIT-P5k — Completed

# WIT-P5l — value_area_pct units defect: forensic investigation (read-only)

No engine/schema/contract/fixture/golden/threshold/prompt/report/data was modified. All diagnostics
were inline scripts and `/tmp` files; the working tree carries no instrumentation. Every conclusion is
labelled and cites this session's own evidence. Front-office facts are lead-supplied (the Lovable
project + Supabase are unreachable from this repo) and marked **[LEAD]**.

Environment for every run below: engine `__version__` **25.25.0**; dataset
`api/data/ES_full_5min_continuous_UNadjusted.parquet`, **sha256
`3d2c4864788a49dc2ec67fdfac18e276fd1c248393b4f76faaa4c185baf9982a`**, **1,289,036 rows**,
2008-01-02 06:00 → 2026-04-09 18:30.

---

## Executive conclusion
**Confirmed.** `setup_entry.params.value_area_pct` is an **unspecified-unit** field. The engine's value-area
consumer treats it as a **fraction** (`target = value_area_pct × total_volume`,
`volume_profile.py:95`); production configs carry **`70`** **[LEAD]**, which makes the target unreachable,
so the value-area band expands to the **entire opening range** and every production audit silently tested
an **opening-range break**, not the 70% value-area break its source described. Nothing in the contract,
schema, dataclass, mapper, or API boundary constrains or normalizes the value; there is no validation on
the wire path. The published WIT-0001 is unaffected (it ran at `0.70` via a research script, verified by
exact re-run). **Go** to fix — but the fix belongs at the producer/contract, must be paired with
front-office cache invalidation (a mapper-only change does not reach the four cached readings **[LEAD]**),
and the founder must choose reject-vs-normalize (laid out, recommendation: **normalize-with-disclosure**).

---

## Confirmed facts (this session's evidence)
1. **Engine consumer & mechanism — Confirmed.** `volume_profile._value_area` (`api/wit/volume_profile.py:92-110`):
   ```python
   total = rows.sum()
   target = total * value_area_pct           # line 95
   lo = hi = poc_idx; cum = rows[poc_idx]
   while cum < target and (lo > 0 or hi < n - 1):   # expand band toward heavier neighbour
       ...
   ```
   With `value_area_pct = 70`, `target = 70 × total`; `cum` maxes out at `total`, so the loop only stops
   when the band spans **all** rows → `VAH = highest row`, `VAL = lowest row` of the [09:30,09:45) window.
   It does not crash because the loop's second condition (`lo>0 or hi<n-1`) terminates at full span.
2. **Full-range degeneracy across 3 separate sessions — Confirmed.** At `pct=70`, VAH/VAL == opening-range
   High/Low with `value_area_fraction = 1.0000` on **2015-03-10** (2062.75/2056.75), **2018-11-05**
   (2733.25/2725.75), **2022-07-14** (3757.75/3730.75). At `pct=0.70` the fractions are 0.7487 / 0.7172 /
   0.7018 (a proper interior band). Not one session; three.
3. **Reproduction & production identity — Confirmed.** CONFIG A (WIT-P5j) run locally at `value_area_pct=70`
   yields engine provenance hash **`e6f2045dd09f20abeb1acf7d02f9dd13a24f8e35bd8d2766e5e4326e783f44b4`**
   (= the production hash **[LEAD]**) and reproduces the production metrics to the last digit (table below).
4. **Published WIT-0001 = 0.70 — Confirmed by exact re-run** (not inferred): re-running the report's config
   (`VPORBConfig()`, i.e. the `0.70` default) reproduces the published primary exactly; `value_area_pct=70`
   does not (see §published-report).
5. **No enforceable contract — Confirmed** (see authoritative-unit-contract).
6. **Same defect class in Class-B params — Confirmed** (see other-vulnerable-fields).

## Unconfirmed or refuted prior claims
- **P5i / P5j / P5k core conclusions — CONFIRMED.** stop.ref ignored (source: `strategy_config_to_vporb`
  reads no `exits.stop.ref`; `VPORBConfig` has no `ref` field); trade_window honoured (mapper maps
  `tw[0]/tw[1]` → `entry_window_start/last_bar`, `mapper.py:308-309`); trade_window **inert at pct=70,
  material at 0.70** re-verified this session (pct=70: 09:45→4161, 09:30→4161 = INERT; pct=0.70: 09:45→4623,
  09:30→4635 = MATERIAL); WIT-0001 ran at 0.70; no baked default on the wire path.
- **REFUTED (narrow):** WIT-P5i step-2's *reconstructed* baseline used `value_area_pct = 0.70` and reported
  4623 trades as if it were the production config; it is **not** the production config (production carries
  `70` → 4161). P5i's honoured/ignored *conclusions* stand; only its implicit "my reconstruction ==
  production" assumption was wrong, which P5j already corrected. Labelled REFUTED for the reconstruction
  equivalence, CONFIRMED for the field-behaviour conclusions.

---

## Complete data flow (source text → engine input)
| stage | where | value observed | label |
|---|---|---|---|
| Guru source prose | transcript (sha256 cb69a23c… **[LEAD]**) | "value area **70%**" | [LEAD] |
| Extraction prompt | `api/wit/extraction/prompt.py` | lists D2 param **keys** only (`_param_keys`, line 47-64); **no unit guidance, no few-shot fixture** | Confirmed |
| Extracted template (machine channel) | production template.setup.params **[LEAD]** | `value_area_pct = 70` | [LEAD] |
| Fixture prose (calibration) | `WIT-T-0001.template.json:96` "value area 70%", `:212` "value_area_pct=70" | 70 (prose) | Confirmed |
| Fixture machine param | `WIT-T-0001.template.json:104` | **0.7** | Confirmed |
| Map: template → wire | `api/wit/mapper.py:238` `"value_area_pct": d2.get("value_area_pct")` | pass-through, **no default, no validation** | Confirmed |
| Map: wire → VPORBConfig | `api/wit/mapper.py:312` `value_area_pct=sp["value_area_pct"]` | pass-through | Confirmed |
| Cache-hit path (front office) | `evaluation-chain.ts advanceFromCachedTemplate` **[LEAD]** | copies stored wire_config verbatim, **skips /wit/v1/map** | [LEAD] |
| Engine consume | `vp_orb_runner.py:156,161` → `volume_profile.py:95` | `target = 70 × total` → full-range band | Confirmed |
| Report render | result payload metrics | numbers of an opening-range break | Confirmed |
| Published WIT-0001 (separate path) | `wit/analysis.py:214` `VPORBConfig()` | **0.70** (default) | Confirmed |

---

## Authoritative unit contract
**Nothing enforceable governs value_area_pct.** Evidence, each explicit:
- **JSON Schema (contract):** `contract/strategy-config.v1.json` types `setup_entry.params` as
  `{"type": ["object","null"]}` — a free-form object; `value_area_pct` is **not a named property**, and the
  whole contract contains **no `minimum` and no `maximum`** (verified programmatically).
- **JSON Schema (template):** `schema/strategy-template.v1.json` types the machine channel `params` as
  `{"type":["object","null"], "description": "... e.g. D2 {range_start,range_end,value_area_pct,granularity}"}`
  — `value_area_pct` appears **only inside a description string**, never as a typed/bounded field.
- **Dataclass:** `api/wit/config.py:25` `value_area_pct: float = 0.70` — an **unenforced** hint (`70` is a
  valid `float`; Python does not check at runtime); on the wire path the value is always supplied, so the
  default never applies.
- **Runtime validation on the wire path:** **none.** `strategy_config_to_vporb` performs no numeric check;
  the inbound `/wit/v1/runs` guard (`server.py`) checks only required **top-level keys**.
- **Normalization at any boundary:** **none.**
- **Expected domain:** **undefined** by any artifact. The engine's arithmetic *requires* a fraction (0,1];
  the field name (`pct`) and the source prose ("70%") suggest 0–100. The two disagree and nothing arbitrates.

### Behaviour table (measured, `build_volume_profile` on a real session; the runner path behaves identically)
| input | outcome | resulting value-area band |
|---|---|---|
| `0` | **accepted** | POC-only (VAH=VAL=POC), fraction 0.0596 — degenerate |
| `0.7` | **accepted** | proper interior band, fraction ≈ 0.717 |
| `1` | **accepted** | full opening range, fraction 1.000 |
| `1.0` | **accepted** | full opening range, fraction 1.000 |
| `70` | **accepted, silently reinterpreted** | full opening range, fraction 1.000 |
| `100` | **accepted, silently reinterpreted** | full opening range, fraction 1.000 |
| `null` | **CRASH** `TypeError: unsupported operand type(s) for *: 'float' and 'NoneType'` | none |
| `"0.70"` (string) | **CRASH** `TypeError: can't multiply sequence by non-int of type 'numpy.float64'` | none |

Nothing is rejected or clamped. Values ≥ 1 silently collapse the band to the full range; `null`/string
crash unhandled deep in the daily loop.

---

## Exact failure point
`api/wit/volume_profile.py:95` `target = total * value_area_pct`, reached via
`vp_orb_runner.py:156/161 build_volume_profile(..., cfg.value_area_pct)`. The unit ambiguity is *created*
at `mapper.py:238` (verbatim pass-through of an unvalidated extracted number) and *never caught* because
no boundary types or bounds the field.

---

## Reproduction results
CONFIG A (WIT-P5j), full window 2008-01-02→2026-04-09, identical except `value_area_pct`:

| metric | `70` (production) | `0.70` (corrected) |
|---|---|---|
| run config_hash | `e6f2045d…f44b4` | `bd7c81b7a5416eec…` |
| trades | 4161 | 4623 |
| net_pnl | -8465.890083640523 | -12823.770111516336 |
| profit_factor | 0.9193420635532844 | 0.8696540178212495 |
| win_rate | 37.89954337899543 | 35.215228206792126 |
| max_drawdown | -15069.406289062921 | -15163.173750000398 |
| avg_trade | -2.0345806497573955 | -2.773906578307665 |

The `70` column **matches the lead-supplied production result exactly** and its hash equals the production
provenance hash. The prior P5j/P5k `0.70` figures are **Confirmed**.

**First differing trade — index 0 (they diverge from the very first trade, 2008-01-02):**
| | entry | exit | dir | in | out | pnl | session VAH/VAL |
|---|---|---|---|---|---|---|---|
| `70` (prod) | 2008-01-02 10:05 | 2008-01-02 12:20 | short | 1470.0 | 1454.25 | +76.26 (tp) | 1480.25 / 1475.75 (full range) |
| `0.70` (corrected) | 2008-01-02 09:45 | 2008-01-02 09:55 | long | 1478.75 | 1476.75 | −12.49 (sl) | 1478.5 / 1476.25 (interior) |

Under `0.70` a long breaks the *interior* VAH at 09:45 and is stopped; under `70` no break occurs until a
short at 10:05 that hits target. These are different strategies from trade #1. **Cumulative P/L divergence
from trade #0 onward = full divergence = −4357.880028** (`0.70` net − `70` net = −12823.77 − (−8465.89)).

---

## Published-report impact
`docs/wit/reports/WIT-0001-volume-profile-orb.md` was generated by the **standalone research script**
`api/wit/analysis.py:214` (`primary = VPORBConfig()` → default `value_area_pct = 0.70`), not the
wire/mapper path (its provenance `vp_source` is the raw `.txt`, pre-WIT-P4m). **Re-running that config
reproduces the published primary exactly** — 2,561 trades, net −5976.890049, PF 0.9027249233,
win_rate 34.322530, max_drawdown −7270.258828, avg −2.3338110306 (window 2016-04-10→2026-04-09).
`value_area_pct=70` on the same config gives a *different* result (2,447 trades, net −2551.78, PF 0.9642),
which does **not** match. Its prose genuinely describes a value-area method (VAH/VAL/POC,
`WIT-0001…orb.md:115`, short rule "POC + 2 ticks" line 109).

**Verdict (the words offered in §6): the report is fully correct.** (Correction-notice question, kept
separate: none warranted for the numbers; the only cleanup is the fixture-prose ambiguity below.)

---

## Cache impact **[LEAD evidence]**
- Cache key = `(source_transcript_hash, EXTRACTOR_VERSION="wit-extract-v1")`; `findCachedTemplate` returns
  the **oldest** matching row (`extraction-cache.ts`). On a cache hit, `advanceFromCachedTemplate`
  (`evaluation-chain.ts`) **copies the stored `wire_config` verbatim and makes NO `/wit/v1/map` call**;
  templates are inserted once and never updated.
- **Therefore a mapper-only fix leaves the four existing filed readings incorrect** — Confirmed by the
  lead evidence: the fix lives in `/wit/v1/map`, but the cache-hit path skips mapping and reuses the
  stored `wire_config` (still `value_area_pct = 70`). The four audits would never be re-mapped.
- `EXTRACTOR_VERSION` governs the **cache key**. Bumping it invalidates **all** cached templates
  (all-or-nothing — it is a global constant in the key), forcing re-extraction of **every** transcript on
  next evaluation, not a targeted subset.
- **Cost of full invalidation:** re-extraction ≈ **180–280 s and 3 model calls per transcript**. The four
  audits share one transcript (sha256 cb69a23c…), so *that* transcript costs one re-extraction (~180–280 s,
  3 calls) + trivial backtest time; but a global version bump also re-extracts every *other* cached
  transcript at the same unit cost. **Targeted alternative:** delete the four cache rows (or the one
  transcript's row) so only they re-map/re-extract — avoids global cost; preferable.

## Scope of affected audits
All **four** production evaluations of transcript cb69a23c… carry `value_area_pct = 70` **[LEAD]** and
therefore tested an opening-range break, not the value-area break described. All four verdicts are
mislabeled and should be re-issued. Any *other* stored audit whose `value_area_pct ≥ 1` is equally
affected (not enumerable from this repo).

---

## Other vulnerable fields — same defect class (risk-ranked)
Neither contract has any `minimum`/`maximum` (verified). Fraction/probability fields consumed in [0,1]
are the exposed class; multiples/ticks/dollars are lower risk.

| field | where defined | expected unit | range | validated? | typed? | prose could pass silently? | consequence | risk |
|---|---|---|---|---|---|---|---|---|
| `value_area_pct` (D2) | not a named contract prop; `config.py:25` hint | fraction | (0,1] | no | no | **yes** (guru says "70%") | full-range break; wrong strategy | **HIGH** |
| `path_bucket.spike_eff` (J1) | `event-study-config…:number` | fraction | [0,1] | no | number only | yes (WIT-authored, lower exposure) | `efficiency>=50` never → **no spikes** (`event_study.py:233`) | MED |
| `path_bucket.pullback_p` (J1) | `event-study…:number` | fraction | [0,1] | no | number only | yes | `retrace>=40` never → **no pullbacks** | MED |
| `path_bucket.spike_giveback_cap` (J1) | `event-study…:number` | fraction | [0,1] | no | number only | yes | `retrace<=20` always → filter void | MED |
| `regime.regime_fixed_er` (J1) | `event-study…:number` | fraction | [0,1] | no | number only | yes | `er>=30` never → all "chop" (`event_study.py:189`) | MED (sensitivity-only) |
| `exits.target.value` r_multiple (F2) | `contract…:number` | multiple | >0 | no | number only | unlikely ("2R"→2) | distorted target if "200%"→200 | LOW |
| `exits.stop.ticks` (F1) | `contract…:number` | ticks (signed) | int | no | number only | n/a (P5i: sign issue, separate) | wrong-side stop | LOW-MED |
| `costs.commission_per_side` (H1) | `contract…:number` | dollars | ≥0 | no | number only | no | — | LOW |
| `costs.slippage_ticks` (H2) | `contract…:integer` | ticks | int | no | integer | no | — | LOW |
| result `win_rate`,`*_pct` | result payload | percent (0-100) | — | n/a | computed | output only | downstream/UI misread if read as fraction | LOW (display) |
| completeness `score` | `completeness.py:140` | percent int (0-100) | 0-100 | n/a | computed | no (engine-computed) | — | LOW |

**Explicitly flagged (prose vs machine could differ, nothing catches it):** `value_area_pct` (HIGH), and
the four Class-B `[0,1]` params (`spike_eff`, `pullback_p`, `spike_giveback_cap`, `regime_fixed_er`).

---

## Recommended fix
Change the **producer + contract**, not the consumer (the consumer's fraction is standard Market-Profile
convention and matches WIT-0001 and every fixture; changing it would corrupt correct artifacts).

**Reject vs normalize — the policy tension (presented, not unilaterally resolved):**
- **Reject a bare `70` as ambiguous.** Purest stop-and-report. But extraction is **closed for v1** and
  emits the prose form ("70"), so every audit whose source correctly says "70%" would ERROR. The four
  existing audits would become un-runnable until re-mapped; new correct audits would fail too. High user
  cost; safest correctness.
- **Normalize with a disclosed assumption.** Divide a value `>1` by 100, record a disclosure code (same
  mechanism as E1/F4/F5/H1/H2 `assumptions_applied`), so the report states "value area interpreted as
  70% (0.70)". Keeps v1 working; the cost is silently reinterpreting the user's number, which the
  disclosure makes honest. The four existing audits flip to `0.70` (materially worse numbers) **with a
  disclosure**.
- **On the bare `if v>1: v/=100`:** it is **range-correct** — any `v ∈ (1,100]` maps to `(0.01,1]`, a
  valid fraction, and `v=1.0` (100% VA) is left as full-range, the sensible reading. It is **not**
  disambiguating for the tiny implausible band (values a user might mean as a fraction slightly >1, which
  are invalid anyway). So it is safe *as a normalization* but must be **paired with a contract that
  declares the field a fraction** and with a **disclosure**; it is not a silent, undocumented hack.
- **Recommendation: normalize-with-disclosure, gated by a typed contract**, because v1 extraction is
  frozen and rejection would break legitimate "70%" sources. Pair it with the disclosure so no
  reinterpretation is hidden.

**Rename (`value_area_pct` → `value_area_fraction`):** clarifying, but it changes a wire **key**, hence the
canonical JSON and **every `config_hash`** — breaking cache keys, stored provenance hashes, and requiring
fixture/wire/prompt edits. **Not worth it for v1**; document the unit on the existing name instead, or
defer a rename to a versioned `config_version` bump.

## Required migrations
1. Contract + template schema: declare the field's unit (typed fraction, `exclusiveMinimum:0`,
   `maximum:1`) and document that a value `>1` is treated as a percentage and normalized.
2. Mapper: normalize `>1 → /100` at the single boundary `strategy_config_to_vporb`, append a disclosure
   code to `assumptions_applied`; reject `null`/non-numeric with a typed `INVALID_CONFIG` (fixes the two
   crash inputs).
3. Reconcile `WIT-T-0001.template.json` prose (`:96` "value area 70%", `:212` "value_area_pct=70") with
   its machine value (`:104` 0.7) — annotate or align.

## Required cache invalidation
A mapper fix alone will NOT touch the four cached readings **[LEAD]**. Either (a) **delete/rewrite the
four cached `wire_config` rows** (targeted; normalize their `value_area_pct` or drop rows so they re-map)
— cheapest, but crosses the "templates never updated" invariant if patched in place (dropping+re-evaluating
is cleaner), or (b) **bump `EXTRACTOR_VERSION`** (all-or-nothing; re-extracts every transcript at
~180–280 s / 3 calls each). Recommend (a) targeted for the four, since the mapper change (not extraction)
is what corrects them.

## Regression-test plan (design only)
- **Boundary values (§2):** unit-test `build_volume_profile` for {0, 0.7, 1, 1.0, 70, 100, null, "0.70"} —
  asserting band and that `null`/string raise a typed error, not `TypeError`.
- **fixture→extraction:** assert the extraction prompt names value_area_pct's unit; property test that a
  transcript saying "70%" yields the normalized fraction (meaningful only under **normalize**).
- **extraction→mapper:** contract test that the mapper normalizes `>1` and discloses (normalize) OR raises
  `INVALID_CONFIG` (reject).
- **mapper→engine:** golden that `value_area_pct` reaching the runner is always in (0,1].
- **cached-reading invalidation:** given a stored `wire_config` with `70`, assert the corrected path
  yields `0.70` behaviour (guards the cache-skip trap).
- **end-to-end audit:** transcript→verdict, asserting the disclosed assumption appears (normalize).
- **golden trade-list comparison:** pin the first-differing-trade ledger so a future change to the VA math
  is caught.
- **published-report provenance:** re-run `VPORBConfig()` and assert it still matches WIT-0001's stored
  metrics (guards the founding audit).
- **property-based parsing:** for the chosen normalization, ∀ v∈(0,100], output ∈ (0,1] (normalize-only).
Tests meaningful **only under reject:** the `INVALID_CONFIG`-on-ambiguous cases. **Only under normalize:**
the disclosure-code and `>1→/100` property tests.

## Risks of the proposed fix
Moving goldens: **none move** from the code fix itself — anchor fixtures already carry `0.7`
(`WIT-T-0001:104`) and all tests use `0.7`/`0.70`, so G1/G2 and the `test_vp_orb` golden stay identical.
The real risk is **behavioural**: correcting live audits changes verdicts (the four flip to worse numbers),
so it must ship with the disclosure and a cache invalidation, or users see numbers change without
explanation. Normalization also re-interprets a user's literal input — acceptable only because it is
disclosed.

## Exact files / line ranges a fix would touch
- `contract/strategy-config.v1.json` (add typed `value_area_pct` under `setup_entry.params`, or a
  documented unit note) + `api/_shipped/contract/strategy-config.v1.json` (drift-gated copy).
- `schema/strategy-template.v1.json` + shipped copy (D2 param unit note).
- `api/wit/mapper.py:238` and `:312` (normalize + disclose, or reject).
- `api/wit/config.py:25` (optional: tighten the hint / comment the unit).
- `api/tests/…` new tests (boundary, contract, provenance, golden ledger).
- `api/tests/fixtures/WIT-T-0001.template.json:96,212` (prose reconciliation only).
- Front-office (separate repo, [LEAD]): cache rows for the four audits, or `EXTRACTOR_VERSION`.

---

## GO / NO-GO and smallest safe ordered sequence
**GO.** Smallest safe ordered sequence (each independently shippable, goldens never tuned):
1. **Contract + schema**: declare `value_area_pct` a fraction (0,1], document percentage-normalization.
   (Interface first, so producers/consumers agree.)
2. **Mapper**: normalize `>1 → /100` with a disclosed assumption code, and reject `null`/non-numeric with
   typed `INVALID_CONFIG`. Add boundary + contract + provenance + golden-ledger tests. (Behaviour fix +
   crash fix; verify goldens byte-identical.)
3. **Fixture prose reconciliation** (`WIT-T-0001` lines 96/212). (Docs only.)
4. **Targeted cache invalidation** of the four affected audits (delete/re-map), then **re-run and
   re-issue** their verdicts with the disclosure. (Data remediation, after the engine path is correct.)
5. Defer any field **rename** to a `config_version` bump.

---

## Suite
`cd api && BACKTEST_API_KEY=k python -m pytest -q` → **308 passed / 0 failed / 2 skipped** — unchanged
(no code/tests/fixtures touched).

## Commit
- Subject: `WIT-P5l: value_area_pct forensic investigation — read-only findings`
- Hash + URL: recorded in the chat report-back after push.

WIT-P5l — Completed

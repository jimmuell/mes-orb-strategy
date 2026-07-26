# WIT — Strategy Template Schema

> **Founding document 2 of 3.** The standard decomposition of a trading strategy. This schema is simultaneously: (a) the LLM extraction target for transcripts, (b) the completeness scorecard shown to users, (c) the disclosure sheet for assumptions, and (d) the input that maps to an engine config (WIT-03). Based on Jim's 17-component framework, consolidated and extended.

**Design rule:** the schema describes *what a strategy is*; it does not dictate engine internals. The engine consumes a `StrategyConfig` derived from a filled template (mapping layer, WIT-03 §3).

**The product insight this schema encodes: the gaps ARE the report.** Every `unspecified` field is either an assumption we must disclose or a reason the strategy is untestable. Beginners learn what a complete strategy looks like by seeing how few boxes a guru filled.

---

## 1. Field conventions

Every field carries:

- `value` — extracted content, or `null`.
- `status` — `specified` (stated in source) | `implied` (reasonably inferred; quote required) | `unspecified`.
- `source_quote` — verbatim transcript snippet justifying `specified`/`implied` (auditability; the report links each rule to what the guru actually said).
- `assumption` — if `unspecified` and required for testing: the default applied, from the **Default Assumption Policy** (§5).

## 2. The template (11 sections, 25 fields)

### A. Identity & Claims
| # | Field | Notes |
|---|---|---|
| A1 | `name_and_source` | Video title/URL/guru channel; strategy nickname. |
| A2 | `claimed_performance` | **Every** performance assertion: win rate, "10-year backtest," dollar claims, "works in any market." Each becomes a row in the claimed-vs-measured table. Also record `claims_shown_evidence: true/false`. |
| A3 | `internal_consistency_flags` | Contradictions within the source itself (e.g. $35 risk → $620 win under a stated 2:1 rule). Populated by the extractor; rendered prominently. |

### B. Market & Data
| # | Field | Notes |
|---|---|---|
| B1 | `instrument` | What the guru trades + what WIT tests on (v1: ES/MES; proxy disclosure if different). Includes tick size/value. |
| B2 | `timeframe` | Decision chart timeframe(s). |
| B3 | `data_requirements` | *WIT addition.* Granularity the strategy needs beyond its chart (e.g. volume profile from 15 min of trading needs ≤1-min data; intrabar path features need finer bars). Drives approximation disclosures. |

### C. Permission filters — "may I trade today?"
*(Consolidates original regime/trend/performance-filter trio into direction-neutral gates vs. directional bias.)*
| # | Field | Notes |
|---|---|---|
| C1 | `session_rules` | Trading window, entry cutoff, forced-flat time, timezone. |
| C2 | `regime_filters` | Volatility/trend-quality gates (ATR bands, ADX, VIX, chop rules). |
| C3 | `calendar_filters` | Skip FOMC/CPI/holidays/weekdays. |

### D. Direction & Setup
| # | Field | Notes |
|---|---|---|
| D1 | `directional_bias` | How long vs. short is decided (e.g. "close through value-area high → longs only today"). |
| D2 | `setup` | The opportunity pattern (ORB, pullback, VWAP bounce, gap fill…). |
| D3 | `entry_trigger` | The exact executable moment (candle close beyond level, touch, break). Setup ≠ trigger; extractor must not conflate. |
| D4 | `order_mechanics` | *WIT addition.* Market/limit/stop entry; act on close vs. intrabar; fill assumptions. The ORB-004 lesson: one bar of timing ambiguity can swing every result. |

### E. Position sizing
| # | Field | Notes |
|---|---|---|
| E1 | `position_sizing` | Contracts/%-risk/ATR-sized. Frequently unspecified by gurus even when their examples imply wildly variable risk — flag that explicitly. |

### F. Exits *(consolidates stop / target / management / exit-rules quartet)*
| # | Field | Notes |
|---|---|---|
| F1 | `initial_stop` | Where wrong; points/ATR/structure-based. |
| F2 | `profit_target` | Fixed/R-multiple/structure/none. |
| F3 | `trade_management` | Break-even moves, trailing, scale-outs. |
| F4 | `time_exit` | Max hold / end-of-session flatten. |
| F5 | `stop_target_same_bar_policy` | Which fills first when both touched in one bar (engine must resolve deterministically; disclosed). |

### G. Risk controls
| # | Field | Notes |
|---|---|---|
| G1 | `trade_frequency_limits` | Max trades/day, re-entry after stop-out, one-position-at-a-time. |
| G2 | `loss_limits` | Daily/weekly stop-trading rules. |

### H. Costs & execution *(WIT addition — no honest verdict without it)*
| # | Field | Notes |
|---|---|---|
| H1 | `commission` | Per side/contract. Default from policy §5 — never zero in a published verdict. |
| H2 | `slippage` | Ticks per side; sensitivity-tested. |

### I. Optimization surface
| # | Field | Notes |
|---|---|---|
| I1 | `parameters` | Every tunable the source exposes (lengths, multipliers, ranges) + stated defaults. Feeds sensitivity runs and multiple-testing accounting. |

### J. Validation plan *(filled by WIT, not the guru)*
| # | Field | Notes |
|---|---|---|
| J1 | `test_design` | Window, in/out-of-sample split, event-study definition (Class B), metrics, regime schemes. |
| J2 | `interpretation_set` | The reasonable codifications tested when the source is ambiguous (sensitivity across readings; results that survive all readings are robust, one reading = fragile). |

### K. Documentation *(report metadata)*
| # | Field | Notes |
|---|---|---|
| K1 | `untestable_remainder` | The discretionary residue ("areas that make sense," "the bigger picture") — always rendered; often where the guru's examples did the real work. |

## 3. Completeness scoring & testability classes

Weighted score over sections B–H (A, I–K are metadata). Required-to-execute fields (B1, B2, D1–D4, F1, plus F2 or F4) weigh heaviest.

- **Class A — mechanically testable:** all required fields `specified`/`implied`, ≤6 assumption fills → full backtest.
- **Class B — testable claim:** an isolable conditional claim exists (e.g. "spike candles in chop reverse") but no complete entry-to-exit loop → event study on the claim; no strategy verdict.
- **Class C — discretionary:** required fields unspecified and not defensibly assumable → untestable report; the scorecard itself is the deliverable.

Class assignment is shown with per-field justification. Calibration anchors: guru video #2 (volume-profile ORB) ≈ Class A with ~5 assumptions; video #1 (candle formation) = Class B; both documented in session notes 2026-07-26.

## 4. Extraction rules (LLM stage)

1. Extract only what is said; `source_quote` mandatory for `specified`/`implied`. No charitable completion — a vague rule is `unspecified`, not guessed.
2. Setup vs. trigger separation enforced.
3. Capture **all** performance claims verbatim into A2, including unfalsifiable ones (marked `untestable_claim`).
4. Populate A3 by checking claims against stated rules (risk/reward arithmetic, timeframe consistency).
5. Multiple plausible readings of an ambiguous rule → record each as an `interpretation_set` candidate, don't pick silently.
6. Output validates against the JSON Schema (§6); hard-fail on schema violations (retry loop in the pipeline).

## 5. Default Assumption Policy (v1)

Applied only where `unspecified`, always disclosed, sensitivity-tested where marked ⚡:

- Sizing → 1 contract (E1). Costs → MES $0.62/side commission ⚡, 1 tick slippage ⚡ (H1–H2). Re-entry → none; one trade/day if the source implies a daily setup (G1). Same-bar stop+target → stop-first (conservative) (F5). Time exit → session close if no target/stop pathway exits (F4). Entry ambiguity close-vs-touch → close ⚡ (D3). Order type → market on trigger (D4). Volume-profile/intrabar features → computed from finest licensed data; approximation disclosed (B3).

## 6. Machine schema

Canonical JSON Schema lives at `schema/strategy-template.v1.json` in the engine repo (WIT-03 owns the file; this doc owns the semantics). Top level:

```json
{
  "template_version": "1.0",
  "source": { "url": "", "title": "", "channel": "", "transcript_hash": "" },
  "fields": { "A1": {"value": null, "status": "unspecified", "source_quote": null, "assumption": null}, "...": "..." },
  "claims": [ {"claim": "", "quote": "", "testable": true} ],
  "consistency_flags": [ {"description": "", "quotes": [""]} ],
  "completeness": { "score": 0, "class": "A|B|C", "required_missing": [] },
  "interpretations": [ {"field": "", "readings": [""]} ]
}
```

**Versioning:** `template_version` is semver-major on breaking field changes; reports permanently record the version they were produced under (old library reports must remain interpretable).

## 7. Dual use

The same schema powers "audit my own strategy" (v2): a user fills the template directly in a form instead of via extraction. This keeps WIT and Jim's personal research pipeline converged — pine-strategies experiments are, in schema terms, Class A templates with a disciplined J-section.

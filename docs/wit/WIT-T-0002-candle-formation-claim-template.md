# WIT Template Fill — WIT-T-0002 "Candlestick Formation Path" (Class B)

> Second hand-filled instance of the WIT-02 schema (template v1.0); the **Class B calibration anchor**. Source: YouTube guru transcript captured in session 2026-07-26 (video #1, candlestick formation). Filled by lead engineer. Routing: **event study** — this source does not specify a runnable strategy.

## A. Identity & Claims

**A1 — name_and_source** · `specified (partial)` — Unnamed candlestick-reading method; channel/URL not captured. Nickname: **Candle Formation Path (CFP)**.

**A2 — claimed_performance**
| Claim | Quote | Testable? |
|---|---|---|
| Formation path predicts follow-through vs. reversal | "A candlestick can finish looking super bullish, but it can form in a way that shows you it's fake." | **Yes — core event-study claim (C1)** |
| Straight-up moves give back | "if the market moves straight up with no pullbacks, even over 60 seconds, it's not going to be healthy and it's likely to give it back up" | **Yes (C1)** |
| Context/regime conditions the signal | "a spike higher that in a choppy environment is more likely to instantly get reversed the next candlestick" | **Yes (C2)** |
| Works on any timeframe | "this can work on a one minute chart, 5 minute, any type of chart, a daily chart" | **Yes — multi-timeframe check (C3)** |
| $4,000 winning trade | "I am up over $4,000" | No — single anecdote |
| Cleaner entries, tighter stops | "your entries get cleaner, your stops get tighter" | No — no rules given to test |

`claims_shown_evidence: false` — examples are hand-picked charts; no statistics of any kind shown.

**A3 — internal_consistency_flags** — none found of the arithmetic kind; noted instead that all shown examples are post-hoc selections (survivorship in exhibits).

## B. Market & Data

**B1 — instrument** · `unspecified` (examples show NASDAQ index) → WIT tests **ES**, disclosed proxy.
**B2 — timeframe** · `specified as any` → primary **5-minute** candles (the channel's day-trading context), secondary **15-minute** (better path resolution) — both fair under the "any timeframe" claim.
**B3 — data_requirements** · *WIT-filled* — Path *within* a candle requires finer bars: 1-min sub-bars give 5 per 5-min candle, 15 per 15-min candle. No tick data; path measured on 1-min closes/extremes — disclosed approximation.

## C–H. Strategy components — the Class B case in one look

| Component | Status |
|---|---|
| Session rules (C1) | `unspecified` → WIT restricts to RTH 09:30–16:00 ET for regime comparability |
| Regime/trend filters (C2) | `unspecified` — "choppy" vs. bigger-picture trend invoked as a concept, never defined numerically; no executable rule |
| Directional bias (D1) | `unspecified` |
| Setup (D2) | `partial` — "big" bullish/bearish candle; size never quantified |
| Entry trigger (D3) | `unspecified` — the shown trade uses a discretionary H&S + break of a high |
| Order mechanics (D4) | `unspecified` |
| Sizing (E1) | `unspecified` |
| Stop (F1) | `partial` — "I put my stop loss below that big candlestick" (one example, not a rule) |
| Target (F2) | `unspecified` |
| Management/time exits (F3–F5) | `unspecified` |
| Risk controls (G) | `unspecified` |
| Costs (H) | `unspecified` — moot; no strategy to cost |

**Required-to-execute fields missing (scorer set): B1, D1, D3, D4, F2|F4.** (E1 is not in the required set and carries a §5 default; D4/F4 defaults are entry-conditional and earn no credit here because no entry trigger is stated.) Not defensibly assumable — inventing them would test *our* strategy, not his claim.

## I. Optimization surface (of the claim codification, WIT-chosen — all disclosed)
`big_candle_k` (body vs. rolling baseline) · `path_efficiency_threshold` · `retrace_pct_threshold` · `regime_measure + threshold` · `forward_horizons`.

## J. Validation plan (WIT) — event study

**J1 — test_design.**
- **Event:** an RTH candle whose body ≥ k × rolling median body (same timeframe, trailing N bars); direction = sign of body. Sensitivity over k.
- **Path classification** from 1-min sub-bars within the event candle: **Spike** ("unhealthy": near-monotonic, high path efficiency, max counter-retracement below threshold) vs. **Pullback** ("healthy": contains an intrabar retracement ≥ threshold of the move yet still closes big). Middle cases → third bucket, reported not discarded.
- **Regime context:** simple, pre-declared chop/trend measure computed on prior bars only (no lookahead). Sensitivity over the measure.
- **Outcomes:** signed forward return at +1/+3/+5/+10 bars; **giveback** = fraction of event body retraced within +1..+3 bars; P(next bar closes against the event).
- **Statistics:** conditional means/medians with bootstrap CIs (seed 42, 10k); Spike-vs-Pullback differences with CIs; per-regime splits; both timeframes; sample counts per cell always shown.
- **Claims mapped:** C1 = Spike underperforms/gives back more than Pullback. C2 = effect stronger in chop, weaker/reversed in trend. C3 = same sign of effect on 5-min and 15-min.

**J2 — interpretation_set.** The Spike/Pullback thresholds and the regime measure are WIT codifications of the guru's words — every threshold gets a sensitivity row; a claim "supported" only under one threshold choice is reported **fragile**.

## K. Untestable remainder
The discretionary trading system around the claim (head-and-shoulders reads, "areas that make sense," double-top confirmation sequencing, "wait for the second attempt"), the $4,000 anecdote, and the PDF/funnel content. **No profitability verdict is possible or will be implied — this report judges a *claim*, not a strategy.**

---

## Completeness verdict

**Class B — testable claim inside a discretionary framework.** Completeness 9/27 fields specified or implied (~33%) — far below Class A; required execution fields absent and not assumable. Routed to event study per WIT-02 §3. This file is the Class B calibration anchor.

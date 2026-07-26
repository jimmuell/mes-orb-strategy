# WIT-P2a — Event-Study Recon & Design (backfilled from session 2026-07-26)

## 1. Alignment & data quirks
- Primary window 2016-04-11 → 2026-04-09: 2,578 RTH days, 990,363 one-min RTH bars.
- Composition: 5-min = 5×1-min, 198,081 buckets, 99.99% exactly full (23 short); 15-min = 15×1-min, 66,030 buckets, 99.97% full (22 short). 1-min→5-min aggregates **byte-identical** to the native parquet (sampled max |diff| = 0.0000).
- Quirks: FirstRateData omits zero-volume minutes (source of the rare short buckets); 92 partial RTH days, 64 half-days.
- Handling: completeness gate (≥5/5 or ≥13/15 sub-bars, else candle dropped); forward horizons never cross session close/day boundary (excluded events counted per horizon); no halt special-casing needed.

## 2. Event counts (k × TF) & buckets
Baseline N=20 trailing same-TF candles (causal). At E=0.50 / giveback cap 20% / P=40%:
| k | TF | events | spike | pullback | middle |
|---|---|---|---|---|---|
| 1.25 | 5-min | 80,122 | 38,575 | 23,496 | 18,051 |
| 1.5 | 5-min | 66,358 | 34,599 | 16,690 | 15,069 |
| 2.0 | 5-min | 46,274 | 26,803 | 9,727 | 9,744 |
| 1.25 | 15-min | 26,878 | 4,183 | 14,361 | 8,334 |
| 1.5 | 15-min | 21,937 | 3,989 | 10,591 | 7,357 |
| 2.0 | 15-min | 15,127 | 3,495 | 6,132 | 5,500 |

Thin-cell check: min cell 1,718 ≥ 300 floor ✓.

**Critical calibration finding:** a 5-min-tuned *absolute-tick* spike rule (eff ≥0.90, ≤4 ticks giveback) collapsed the 15-min spike bucket to 66 events. Cause: median counter-retracement 2 ticks (5-min) vs 8 ticks (15-min); median path efficiency 0.75 vs 0.44 — longer candles wiggle more. Fix: giveback cap as **% of body (scale-free)** — comparable across timeframes (C3 requires this); abs-tick equivalents kept as sensitivity.

## 3. Design (as approved, with lead-engineer amendments A1–A4)
- **Event:** RTH candles (5-min primary, 15-min secondary, composed from 1-min); body ≥ k × trailing-median(N=20) body, causal; dojis excluded; k ∈ {1.25, 1.5, 2.0} (+3.0 per amendment A3), primary 1.5.
- **Path buckets** (disjoint, pullback → spike → middle): efficiency = |C−O| / Σ|1-min steps|; counter-retracement as % of body. Pullback: retrace ≥ 40%. Spike: retrace ≤ 20% AND eff ≥ 0.50. Percentile-based bucket variant added per A3.
- **Regime:** Kaufman ER(20) on prior closes — **A1: split at its TRAILING median (rolling, causal)**; sensitivity: in-sample median, fixed 0.30, ADX(14)>20.
- **Outcomes:** signed forward return +1/+3/+5/+10; giveback over +1..+3; P(next closes against). $ shown as effect size only — never a P&L verdict.
- **Stats:** **A2: day-clustered bootstrap for headline Spike−Pullback contrasts** (resample days, 10k, seed 42); per-cell iid CIs labeled. Claim mapping: C1 = pooled contrast; C2 = chop−trend difference-in-differences; C3 = same-sign across TFs.
- **A4:** one-dimension-at-a-time sensitivity (18 runs), no full cross-product.
- Class B scope: no profitability verdict of any kind.

STEP 0 commit: 021d482 (Class B template + both source transcript archives).

WIT-P2a — Completed

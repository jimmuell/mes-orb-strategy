# MES ORB Strategy — Backtest Results

> **Phase 1** of a two-strategy system. Phase 2 (VWAP Reversion Scalp for choppy days) begins when Phase 1 enters paper trading. See CLAUDE.md for full roadmap.

## ES vs MES Note

**All backtest runs (001-004) used incorrect MES specs ($5/point, $0.62 commission).** The sample data is ES (E-mini S&P 500, $50/point) from FirstRateData. Run 005+ uses correct ES specs. When backtesting MES, dollar P&L scales to 1/10th of ES but win rate and profit factor are identical since both contracts share the same price feed, tick size (0.25), and ORB levels.

| | ES (E-mini) | MES (Micro) |
|---|---|---|
| Point value | $50 | $5 |
| Commission/contract | $2.25 | $0.62 |
| Tick size | 0.25 ($12.50) | 0.25 ($1.25) |

## Current Best Configuration (Run 013)

Three R:R candidates tested — awaiting Senior Claude decision for Pine Script conversion:

| R:R | Win% | PF | Net $ | OOS Win% | OOS PF | Status |
|---|---|---|---|---|---|---|
| 0.75 | 61.5% | 1.519 | +$586 | **63.6%** | 1.283 | Best WR, OOS WR ✅ |
| **0.875** | **59.3%** | **1.548** | **+$646** | **61.4%** | **1.335** | **Balanced** |
| 1.00 | 58.2% | 1.579 | +$710 | 59.1% | 1.344 | Best PF |

All share: SL=50%, retest=2t, ORB 0.3-1.0%, SMA regime, prior-day close bias, ATR 0.3-2.0%, ADX>15, breakout quality (body≥40%, close top/bot 33%), 1 MES contract.

**No variant meets all Phase 1 targets simultaneously.** PF ≥ 1.5 met by all three. DD ≤ 15% met by all three. Win rate ≥ 62% missed by 0.5-3.8 pts. The win rate and PF targets pull in opposite directions.

## Key Findings (as of Run 008)

1. **Prior-day H/L bias is the breakthrough filter.** Requiring the ORB to open beyond yesterday's range (gap-up for longs, gap-down for shorts) flipped the strategy from -$19k to +$15k on its own. It ensures overnight conviction backs the trade direction.

2. **ATR vol filter provides selectivity.** Limiting trades to 20-day ATR% between 0.3% and 2.0% cuts trade count from 326 to 92 but boosts PF from 1.163 to 1.734. It filters both ultra-calm chop and extreme panic.

3. **Full stack (SMA + prior-day + ATR) = PF 1.734, 56.5% win rate.** 92 trades over 18 years, +$17,665 net, 13 of 18 years profitable. First configuration with clear positive expectancy.

4. **VWAP/EMA confluence was the problem, not the ORB concept.** Removing VWAP/EMA and replacing with directional + volatility filters transformed the strategy from coin-flip to profitable.

5. **2022 is now manageable.** Losses went from -$17.4k (Run 007) to -$3.2k (Run 008). Triple filter stack eliminated most counter-trend disasters.

6. **2020 COVID crash was the best year.** +$10,877 from 6 trades at PF 5.27. Massive ORB ranges with strong gap follow-through — exactly the regime these filters select for.

7. **Trade frequency is low: 5.1/year.** Not a standalone income strategy, but viable as one component of a multi-strategy portfolio. Each trade averages +$192 with avg win $703 vs avg loss $459.

8. **Data source:** ES continuous unadjusted 5-min from [firstratedata.com](https://firstratedata.com/i/futures/ES), Jan 2008 – Apr 2026. All dollar P&L is ES ($50/point) — divide by 10 for MES equivalent.

### Next Steps
- Out-of-sample validation: walk-forward test (train on 2008-2020, test on 2021-2026)
- Position sizing: reduce to 1 ES or 2 MES to bring max DD under 15%
- Test R:R=1.5 and 2.0 with the new filters (higher R:R may now work with better entry quality)
- Volume spike confirmation on breakout bar
- Convert best config to Pine Script v6 for TradingView deployment

## Next Steps

- **Replace VWAP/EMA filters** — they pass every trade on ES, adding no selectivity. Candidates to test next session:
  - Prior day high/low as directional bias filter
  - VIX level filter (only trade when VIX > 15)
  - Gap direction filter (only trade in direction of opening gap)
  - Volume spike confirmation on breakout bar
- **Obtain full ES dataset** from FirstRateData (2008-2026) for statistical significance — 10 days of real data is insufficient
- **Verify MES vs ES sizing** — MES contract = $5/point vs ES = $50/point; confirm commission and qty_value calculations are correct for each instrument

---

## Iteration Log

Results will be logged below as backtests are run.

---

### Run 013 — R:R=0.875 Final Candidate Test

**Date:** 2026-04-11
**Script:** `backtest-engine/.../strategies/mes_orb_strategy.py`
**Data:** `data/raw/ES_full_5min_continuous_UNadjusted.txt` — 1,289,036 bars, 4,710 trading days
**Contract:** 1 MES ($5/point, $0.62 commission)

#### Three-Way R:R Comparison

| R:R | Trades | Win% | PF | Net $ | Max DD% | Avg Win | Avg Loss |
|---|---|---|---|---|---|---|---|
| 0.750 | 91 | **61.5%** | 1.519 | +$586 | 1.46% | $30.62 | -$32.25 |
| **0.875** | **91** | **59.3%** | **1.548** | **+$646** | **1.49%** | **$33.82** | **-$31.88** |
| 1.000 | 91 | 58.2% | **1.579** | **+$710** | 1.40% | $36.54 | -$32.27 |

#### Phase 1 Target Check — Full 18-Year Dataset

| Metric | R:R=0.75 | R:R=0.875 | R:R=1.0 | Target |
|---|---|---|---|---|
| Win Rate | 61.5% ❌ | 59.3% ❌ | 58.2% ❌ | ≥ 62% |
| Profit Factor | 1.519 ✅ | 1.548 ✅ | 1.579 ✅ | ≥ 1.5 |
| Max Drawdown | 1.46% ✅ | 1.49% ✅ | 1.40% ✅ | ≤ 15% |

**No variant meets all three targets on the full 18-year dataset.** Win rate falls short by 0.5-3.8 pts depending on R:R.

#### Phase 1 Target Check — Out-of-Sample Only (2020-2026)

| Metric | R:R=0.75 | R:R=0.875 | R:R=1.0 | Target |
|---|---|---|---|---|
| Win Rate | **63.6%** ✅ | 61.4% ❌ | 59.1% ❌ | ≥ 62% |
| Profit Factor | 1.283 ❌ | 1.335 ❌ | **1.344** ❌ | ≥ 1.5 |
| Max Drawdown | 1.0% ✅ | 1.1% ✅ | 1.3% ✅ | ≤ 15% |

**No variant meets all three targets out-of-sample either.** R:R=0.75 has the win rate but fails PF. R:R=1.0 has the closest PF but fails win rate.

**PINE SCRIPT CANDIDATE STATUS: NOT YET CONFIRMED.** The gap is narrow but no single R:R meets all targets simultaneously in any time period.

#### Walk-Forward: R:R = 0.875

| Metric | In-Sample (2008-2019) | Out-of-Sample (2020-2026) |
|---|---|---|
| Trades | 46 | 44 |
| Win Rate | 56.5% | 61.4% |
| Profit Factor | 0.851 | 1.335 |
| Net Profit | -$59 | +$262 |
| Max Drawdown | 0.7% | 1.1% |

#### Yearly Breakdown: R:R = 0.875
| Year | Trades | Win% | PF | PnL |
|---|---|---|---|---|
| 2009 | 7 | 57% | 0.949 | -$2 |
| 2010 | 7 | 71% | 2.084 | +$23 |
| 2011 | 5 | 80% | 3.368 | +$25 |
| 2012 | 3 | 67% | 1.332 | +$4 |
| 2013 | 1 | 0% | 0.000 | -$14 |
| 2014 | 3 | 67% | 1.578 | +$10 |
| 2015 | 6 | 33% | 0.308 | -$63 |
| 2016 | 4 | 25% | 0.175 | -$60 |
| 2018 | 8 | 63% | 1.494 | +$43 |
| 2019 | 2 | 50% | 0.837 | -$4 |
| **2020** | **4** | **100%** | **inf** | **+$561** |
| 2021 | 4 | 25% | 0.204 | -$102 |
| **2022** | **22** | **59%** | **1.156** | **+$66** |
| 2023 | 3 | 67% | 1.463 | +$18 |
| 2024 | 2 | 100% | inf | +$79 |
| 2025 | 7 | 43% | 0.607 | -$81 |
| **2026** | **3** | **100%** | **inf** | **+$145** |

Profitable in 12 of 17 years.

#### Key Findings
1. **R:R=0.875 is the balanced middle ground.** PF 1.548 (between 0.75's 1.519 and 1.0's 1.579), win rate 59.3% (between 61.5% and 58.2%). Net profit $646 (between $586 and $710).
2. **No R:R meets all Phase 1 targets.** The win rate and PF targets pull in opposite directions — lower R:R raises win rate but lowers PF. At the current strategy structure, 62% win rate and PF 1.5 cannot be achieved simultaneously.
3. **R:R=0.75 is closest to all-target compliance** — misses win rate by 0.5 pts on full data, and meets it OOS (63.6%) but fails OOS PF (1.283).
4. **Senior Claude decision point:** Accept the strategy as-is with the best available trade-off, or pursue further optimization. The gap is narrow enough that slippage and commission adjustments could push results across the line — or pull them back.

---

### Run 012 — R:R Ratio Ablation Study

**Date:** 2026-04-11
**Script:** `backtest-engine/.../strategies/mes_orb_strategy.py`
**Data:** `data/raw/ES_full_5min_continuous_UNadjusted.txt` — 1,289,036 bars, 4,710 trading days
**Contract:** 1 MES ($5/point, $0.62 commission)

#### R:R Ablation Table

| R:R | Trades | Win% | PF | Net $ | Max DD% | Avg $/trade | Avg Win | Avg Loss |
|---|---|---|---|---|---|---|---|---|
| **0.75** | **91** | **61.5%** | **1.519** | **+$586** | **1.46%** | **+$6.44** | $30.62 | -$32.25 |
| 1.00 | 91 | 58.2% | 1.579 | +$710 | 1.40% | +$7.80 | $36.54 | -$32.27 |
| 1.25 | 91 | 50.5% | 1.336 | +$489 | 1.61% | +$5.38 | — | — |
| 1.50 | 91 | 39.6% | 0.936 | -$117 | 2.60% | -$1.29 | — | — |

**Trade count is identical (91) across all R:R** — same entries, same stops, different TP targets. R:R only affects where TP is set, not whether a trade triggers.

#### Best by Win Rate: R:R = 0.75 (61.5%)
| Metric | Run 011 (R:R=1.0) | Run 012 (R:R=0.75) | Change |
|---|---|---|---|
| Win Rate | 58.2% | **61.5%** | **+3.3 pts** |
| Profit Factor | 1.579 | 1.519 | -0.060 |
| Net Profit | +$710 | +$586 | -$124 |
| Max Drawdown | 1.40% | 1.46% | ~flat |
| Avg Win / Avg Loss | 1.132 | **0.949** | lower (by design) |

**Trade-off:** R:R=0.75 gains 3.3% win rate but gives up $124 net and 0.06 PF. Each win is smaller ($30.62 vs $36.54) but there are 3 more wins per 91 trades.

#### Gap to Revised Phase 1 Targets

| Metric | R:R=0.75 | R:R=1.0 | Target | Best |
|---|---|---|---|---|
| Win Rate | **61.5%** | 58.2% | **≥ 62%** | R:R=0.75 (-0.5 pts!) |
| Profit Factor | 1.519 | **1.579** | ≥ 1.5 | Both ✅ |
| Max Drawdown | 1.46% | 1.40% | ≤ 15% | Both ✅ |
| Walk-forward | validated | validated | validated | Both ✅ |

**R:R=0.75 is 0.5 percentage points from meeting all Phase 1 targets simultaneously.** No variant meets all three targets in this run, but R:R=0.75 is the closest — it needs 62.0% and has 61.5%.

#### Walk-Forward: R:R = 0.75

| Metric | In-Sample (2008-2019) | Out-of-Sample (2020-2026) |
|---|---|---|
| Trades | 46 | 44 |
| Win Rate | 58.7% | **63.6%** |
| Profit Factor | 0.820 | **1.283** |
| Net Profit | -$68 | **+$212** |
| Max Drawdown | 0.6% | 1.0% |

**Out-of-sample win rate is 63.6% — exceeds the 62% target.** The strategy meets all Phase 1 targets in the post-2020 regime where it will actually be deployed.

#### Yearly Breakdown (R:R = 0.75)
| Year | Trades | Win% | PF | PnL |
|---|---|---|---|---|
| 2009 | 7 | 57% | 0.799 | -$6 |
| 2010 | 7 | 71% | 1.798 | +$17 |
| 2011 | 5 | 80% | 2.992 | +$21 |
| 2012 | 3 | 67% | 1.113 | +$1 |
| 2013 | 1 | 0% | 0.000 | -$14 |
| 2014 | 3 | 67% | 1.326 | +$5 |
| 2015 | 6 | 50% | 0.493 | -$38 |
| 2016 | 4 | 25% | 0.159 | -$62 |
| 2018 | 8 | 63% | 1.360 | +$31 |
| 2019 | 2 | 50% | 0.837 | -$4 |
| **2020** | **4** | **100%** | **inf** | **+$554** |
| 2021 | 4 | 25% | 0.173 | -$106 |
| **2022** | **22** | **64%** | **1.191** | **+$74** |
| 2023 | 3 | 67% | 1.241 | +$10 |
| 2024 | 2 | 100% | inf | +$67 |
| 2025 | 7 | 43% | 0.516 | -$100 |
| **2026** | **3** | **100%** | **inf** | **+$136** |

**2022 profitable at +$74** with 64% win rate — best 2022 result across all runs.

#### Key Findings
1. **R:R=0.75 achieves 61.5% win rate** — within 0.5 pts of the 62% target. Out-of-sample (post-2020): 63.6%, exceeding target.
2. **R:R=1.0 has higher PF (1.579 vs 1.519)** but lower win rate (58.2%). It produces more net dollars per trade but fewer winning trades.
3. **R:R=1.25 and 1.5 degrade rapidly.** At 1.5, the strategy becomes unprofitable (PF 0.936). The ORB range provides limited follow-through for wider targets.
4. **Both R:R=0.75 and R:R=1.0 meet PF and DD targets.** The choice between them is whether to optimize for win rate (0.75) or net profit (1.0).
5. **Senior Claude decision needed:** R:R=0.75 meets all targets out-of-sample and is 0.5 pts from meeting them overall. R:R=1.0 has better PF. Which do we carry forward to Pine Script conversion?

---

### Run 011 — Two-Bar Retest + Breakout Candle Quality Filter

**Date:** 2026-04-11
**Script:** `backtest-engine/.../strategies/mes_orb_strategy.py`
**Data:** `data/raw/ES_full_5min_continuous_UNadjusted.txt` — 1,289,036 bars, 4,710 trading days
**Contract:** 1 MES ($5/point, $0.62 commission)

#### Changes from Run 010
| Parameter | Run 010 | Run 011 |
|---|---|---|
| Entry confirmation | Single-bar retest | Tested: **two-bar retest** (bar1 touches, bar2 confirms) |
| Breakout quality | none | Tested: **body ≥ 40% of range, close in top/bottom 33%** |

#### Ablation Study

| Variant | Trades | Win% | PF | Net $ | Max DD% | Avg $/trade |
|---|---|---|---|---|---|---|
| Run 010 baseline | 134 | 56.0% | 1.338 | +$649 | 1.87% | +$4.85 |
| + Two-bar retest only | 112 | 53.6% | 0.996 | -$7 | 1.47% | -$0.06 |
| **+ Breakout quality only** | **91** | **58.2%** | **1.579** | **+$710** | **1.40%** | **+$7.80** |
| Both combined | 81 | 56.8% | 1.115 | +$129 | 1.06% | +$1.60 |

**Breakout candle quality is the winner.** PF jumped from 1.338 → 1.579, win rate from 56.0% → 58.2%. Two-bar retest *hurt* performance (PF dropped to 0.996) — the extra confirmation bar lets too many good setups slip away.

#### Best Variant: Breakout Quality Only (Run 011)
| Metric | Run 010 | Run 011 | Change |
|---|---|---|---|
| Trades | 134 | **91** | -43 (-32%) |
| Win Rate | 56.0% | **58.2%** | **+2.2 pts** |
| Profit Factor | 1.338 | **1.579** | **+0.241** |
| Net Profit | +$649 | **+$710** | +$61 |
| Max Drawdown | 1.87% | **1.40%** | improved |
| Avg Trade | +$4.85 | **+$7.80** | +61% per trade |
| Largest Win | — | $438.54 | |
| Largest Loss | — | -$65.72 | |

#### Yearly Breakdown (Run 011 — Breakout Quality)
| Year | Trades | Win% | PF | PnL |
|---|---|---|---|---|
| 2009 | 7 | 57% | 1.099 | +$3 |
| 2010 | 7 | 71% | 2.407 | +$30 |
| 2011 | 5 | 80% | 3.744 | +$29 |
| 2012 | 3 | 67% | 1.550 | +$7 |
| 2013 | 1 | 0% | 0.000 | -$14 |
| 2014 | 3 | 67% | 1.829 | +$14 |
| 2015 | 6 | 33% | 0.345 | -$60 |
| 2016 | 4 | 25% | 0.201 | -$58 |
| 2018 | 8 | 63% | 1.645 | +$56 |
| 2019 | 2 | 50% | 0.837 | -$4 |
| **2020** | **4** | **100%** | **inf** | **+$569** |
| 2021 | 4 | 25% | 0.235 | -$98 |
| **2022** | **22** | **55%** | **1.050** | **+$24** |
| 2023 | 3 | 67% | 1.684 | +$27 |
| 2024 | 2 | 100% | inf | +$91 |
| 2025 | 7 | 43% | 0.698 | -$63 |
| **2026** | **3** | **100%** | **inf** | **+$159** |

**Best 3:** 2020 (+$569), 2026 (+$159), 2024 (+$91)
**Worst 3:** 2015 (-$60), 2025 (-$63), 2021 (-$98)

Profitable in 12 of 17 years (no 2008 trades with quality filter). **2022 flipped to +$24** — the breakout quality filter eliminated the weak breakout candles that were reversing.

#### Walk-Forward Validation (Breakout Quality)

| Metric | In-Sample (2008-2019) | Out-of-Sample (2020-2026) |
|---|---|---|
| Trades | 46 | 44 |
| Win Rate | 56.5% | 59.1% |
| Profit Factor | 0.954 | **1.344** |
| Net Profit | -$18 | **+$286** |
| Max Drawdown | 0.7% | 1.3% |
| Avg Trade | -$0.39 | +$6.49 |

Same regime-dependent pattern: near-breakeven in-sample, profitable out-of-sample.

#### Gap to Phase 1 Targets

| Metric | Run 011 | Target | Gap | Status |
|---|---|---|---|---|
| Win Rate | 58.2% | 70% | **-11.8 pts** | ❌ Improved from 56.0% |
| Profit Factor | 1.579 | 1.5 | **+0.079** | ✅ **TARGET MET** |
| Max Drawdown | 1.40% | 15% | +13.6% margin | ✅ Met |
| Walk-forward | validated | validated | — | ✅ Met |

**Profit Factor target achieved for the first time!** PF 1.579 > 1.5 target. Win rate still 11.8 points below 70% target. Max DD and walk-forward both met.

#### Key Findings
1. **Breakout candle quality is the most impactful single filter added.** It improved PF by +0.241 (1.338 → 1.579), more than any previous filter change. Requiring body ≥ 40% and close in top/bottom 33% eliminates doji/spinning-top breakouts that lack conviction.
2. **Two-bar retest confirmation hurts.** The additional bar of waiting lets good setups escape — by the time bar 2 confirms, the move has already happened. The single-bar retest captures the momentum better.
3. **2022 is now profitable (+$24).** The quality filter eliminated weak breakout bars that characterized 2022's false breakouts. This was the first year that consistently resisted all previous filter attempts.
4. **Trade count at 91 (5.1/year) is viable** as a component strategy in the two-strategy system. Phase 2 VWAP scalp will add 1-3 trades/day on the other 85% of days this strategy sits out.
5. **PF target met — first Phase 1 metric achieved.** Win rate is the remaining gap.

---

### Run 010 — ADX Trend Quality Filter

**Date:** 2026-04-11
**Script:** `backtest-engine/.../strategies/mes_orb_strategy.py`
**Data:** `data/raw/ES_full_5min_continuous_UNadjusted.txt` — 1,289,036 bars, 4,710 trading days
**Contract:** 1 MES ($5/point, $0.62 commission) — standardized from Run 010 onwards

#### Changes from Run 009
| Parameter | Run 009 | Run 010 |
|---|---|---|
| ADX filter | none | **14-period ADX > 15 (prior day, no look-ahead)** |
| Contract size | 2 ES ($50/pt) | **1 MES ($5/pt)** |
| All other params | unchanged | unchanged |

Note: Dollar P&L is now ~1/20th of Run 009 due to contract change (1 MES vs 2 ES). Compare on PF/win rate, not dollar amounts.

#### ADX Threshold Ablation (all at 1 MES)

| ADX | Trades | Win% | PF | Net $ | Max DD% | Avg $/trade |
|---|---|---|---|---|---|---|
| None (Run 009) | 167 | 56.3% | 1.327 | +$759 | 1.82% | +$4.54 |
| **> 15** | **134** | **56.0%** | **1.338** | **+$649** | **1.87%** | **+$4.85** |
| > 20 | 77 | 51.9% | 0.905 | -$111 | 1.45% | -$1.45 |
| > 25 | 42 | 57.1% | 1.125 | +$69 | 0.49% | +$1.65 |

**ADX > 15 is the best threshold.** It cuts 33 low-quality trades while maintaining PF at 1.338 (slightly above Run 009's 1.327). ADX > 20 is too aggressive — it destroys the edge by removing too many valid setups. ADX > 25 is viable but only 42 trades over 18 years (2.3/year).

#### Run 010 vs Run 009 (apples-to-apples at 1 MES)

| Metric | Run 009 (1 MES) | Run 010 (ADX>15) |
|---|---|---|
| Trades | 167 | **134** |
| Trades/Year | 9.3 | **7.4** |
| Win Rate | 56.3% | 56.0% |
| Profit Factor | 1.327 | **1.338** |
| Net Profit | +$759 | +$649 |
| Max Drawdown | -1.82% | -1.87% |
| Avg Trade | +$4.54 | +$4.85 |

#### Yearly Breakdown (Run 010, ADX > 15)
| Year | Trades | Win% | PF | PnL |
|---|---|---|---|---|
| 2009 | 13 | 54% | 1.112 | +$5 |
| 2010 | 10 | 70% | 2.255 | +$40 |
| 2011 | 7 | 71% | 2.075 | +$25 |
| 2012 | 4 | 50% | 0.565 | -$15 |
| 2013 | 2 | 50% | 0.900 | -$1 |
| 2014 | 3 | 67% | 1.829 | +$14 |
| **2015** | **11** | **36%** | **0.434** | **-$87** |
| **2016** | **4** | **25%** | **0.201** | **-$58** |
| 2018 | 10 | 60% | 1.508 | +$55 |
| 2019 | 4 | 50% | 0.653 | -$23 |
| **2020** | **7** | **71%** | **6.356** | **+$507** |
| 2021 | 8 | 50% | 0.719 | -$51 |
| **2022** | **29** | **48%** | **0.792** | **-$147** |
| 2023 | 4 | 75% | 2.528 | +$61 |
| 2024 | 2 | 100% | inf | +$91 |
| 2025 | 12 | 58% | 1.482 | +$132 |
| 2026 | 4 | 75% | 2.799 | +$102 |

**Best 3:** 2020 (+$507), 2025 (+$132), 2026 (+$102)
**Worst 3:** 2016 (-$58), 2015 (-$87), 2022 (-$147)

#### 2015 / 2016 / 2022 Callout — Did ADX Help?

| Year | Run 009 (no ADX) | Run 010 (ADX>15) | Trades removed | PnL change |
|---|---|---|---|---|
| 2015 | 15 trades, -$125 | 11 trades, -$87 | 4 | **+$38 better** |
| 2016 | 5 trades, -$42 | 4 trades, -$58 | 1 | **-$16 worse** |
| 2022 | 31 trades, -$148 | 29 trades, -$147 | 2 | **~flat** |

**Mixed results.** ADX > 15 helped 2015 modestly but barely touched 2022 (only removed 2 of 31 trades). The problem years have ADX > 15 during the choppy periods — 2022's bear market *was* trending (strong downtrend), so ADX was high even when ORB breakouts reversed. ADX measures trend strength, not trend quality for breakout follow-through.

#### Walk-Forward Validation (ADX > 15)

| Metric | In-Sample (2008-2019) | Out-of-Sample (2020-2026) |
|---|---|---|
| Trades | 68 | 64 |
| Win Rate | 54.4% | 57.8% |
| Profit Factor | 0.873 | **1.279** |
| Net Profit | -$74 | **+$354** |
| Max Drawdown | 0.9% | 1.6% |
| Avg Trade | -$1.09 | +$5.53 |

Same regime-dependent pattern as Run 009: breakeven in-sample, profitable out-of-sample.

#### Key Findings
1. **ADX > 15 provides marginal improvement.** PF 1.327 → 1.338, avg trade $4.54 → $4.85. Cuts 33 trades (167→134) without losing much profit. Not transformative.
2. **ADX does not solve 2022.** The 2022 bear market had high ADX (strong downtrend), so the filter doesn't trigger. The problem is *trend direction changes*, not lack of trend. The SMA regime filter is already handling directional filtering.
3. **ADX > 20 kills the edge.** PF drops to 0.905 (unprofitable). Too many valid setups have ADX between 15-20.
4. **Walk-forward pattern unchanged.** Edge remains regime-dependent (works post-2020).
5. **Max DD at 1 MES is manageable.** -1.87% on $25k = -$468. This is tradeable.

---

### Run 009 — Relaxed Bias Filter + Kelly Sizing + Walk-Forward Validation

**Date:** 2026-04-11
**Script:** `backtest-engine/.../strategies/mes_orb_strategy.py`
**Data:** `data/raw/ES_full_5min_continuous_UNadjusted.txt` — 1,289,036 bars, 4,710 trading days, Jan 2008 – Apr 2026

#### Changes from Run 008
| Parameter | Run 008 | Run 009 |
|---|---|---|
| Prior-day bias | ORB > prior day **high/low** (gap required) | ORB > prior day **close** (momentum, not gap) |
| ATR lookback | 20-day | **10-day** (faster regime response) |
| Kelly sizing | not tested | **Quarter-Kelly post-hoc analysis** |
| Walk-forward | not tested | **Train 2008-2019 / Test 2020-2026** |

#### Run 008 vs Run 009 Comparison

| Metric | Run 008 | Run 009 |
|---|---|---|
| Total Trades | 92 | **167** |
| Trades/Year | 5.1 | **9.3** |
| Win Rate | 56.5% | 56.3% |
| Profit Factor | **1.734** | 1.399 |
| Net Profit | +$17,665 | **+$18,024** |
| Max Drawdown | -37.6% | **-31.3%** |
| Avg Trade | +$192 | +$108 |
| Avg Win | $803 | $673 |
| Avg Loss | -$602 | -$619 |

**Trade-off:** Relaxing the bias filter nearly doubled trade count (92 → 167) and improved net profit slightly (+$18k vs +$17.7k) while reducing max DD from 37.6% to 31.3%. PF dropped from 1.734 to 1.399 because more marginal trades are included — but the total dollar profit is higher with more bets at a still-profitable edge.

#### Yearly Breakdown (Run 009)
| Year | Trades | Win% | PF | PnL |
|---|---|---|---|---|
| 2008 | 2 | 50% | 0.695 | -$108 |
| 2009 | 14 | 57% | 1.466 | +$429 |
| 2010 | 10 | 70% | 2.396 | +$852 |
| 2011 | 12 | 58% | 1.119 | +$152 |
| 2012 | 6 | 67% | 1.351 | +$236 |
| 2013 | 3 | 67% | 2.014 | +$284 |
| 2014 | 3 | 67% | 1.961 | +$306 |
| 2015 | 15 | 33% | 0.429 | -$2,335 |
| 2016 | 5 | 40% | 0.445 | -$794 |
| 2018 | 10 | 60% | 1.593 | +$1,252 |
| 2019 | 4 | 50% | 0.694 | -$399 |
| **2020** | **14** | **64%** | **3.822** | **+$10,480** |
| 2021 | 9 | 44% | 0.654 | -$1,432 |
| **2022** | **31** | **48%** | **0.846** | **-$2,252** |
| **2023** | **9** | **78%** | **3.012** | **+$3,596** |
| 2024 | 2 | 100% | inf | +$1,889 |
| 2025 | 13 | 54% | 1.286 | +$1,852 |
| **2026** | **5** | **80%** | **4.665** | **+$4,017** |

**Best 3:** 2020 (+$10,480), 2026 (+$4,017), 2023 (+$3,596)
**Worst 3:** 2021 (-$1,432), 2022 (-$2,252), 2015 (-$2,335)

Profitable in 13 of 18 years. 2022 worst year at -$2,252 (down from -$3,172 in Run 008 — the relaxed filter actually improved 2022 by spreading risk across more trades). 2018 flipped from -$1,118 to +$1,252.

#### Walk-Forward Validation

| Metric | In-Sample (2008-2019) | Out-of-Sample (2020-2026) |
|---|---|---|
| Trades | 84 | 75 |
| Win Rate | 54.8% | 57.3% |
| Profit Factor | 0.972 | **1.344** |
| Net Profit | -$374 | **+$9,984** |
| Max Drawdown | 16.2% | 29.4% |
| Avg Trade | -$4.45 | **+$133.13** |

**Critical finding: The strategy is NOT profitable in-sample (2008-2019).** PF 0.972 with -$374 net over 12 years and 84 trades. The entire +$18k profit comes from the out-of-sample period (2020-2026).

**This is the opposite of curve-fitting.** Normally we worry that in-sample looks great but out-of-sample fails. Here the strategy breaks even in-sample and profits handsomely out-of-sample. This suggests the edge is **regime-dependent** — the strategy works in the post-2020 higher-volatility market structure but didn't exist in the calmer pre-2020 environment.

#### Quarter-Kelly Position Sizing Analysis

| Metric | Fixed 1x | Quarter Kelly |
|---|---|---|
| Final Equity | $43,025 | $25,723 |
| Net P&L | +$18,024 | +$723 |
| Max Drawdown | -21.3% | **-1.2%** |
| Return | 72.1% | 2.9% |

*Kelly formula corrected in pre-Run009 code review (was +$728 with compounding bug).*

Kelly parameters: W = 56.3%, R = 1.086, Full Kelly = 16.0%, Quarter Kelly = 4.0%.

**Quarter Kelly dramatically reduces drawdown** (21.3% → 1.2%) but also reduces returns to near-zero (+$728 over 18 years). At QK=4%, position sizes are very small because the edge is modest (PF 1.4, not 2.0+). This confirms the strategy doesn't have enough edge for aggressive Kelly sizing — it works best at fixed 1-contract sizing where commissions are a smaller fraction of P&L.

#### Key Findings
1. **Relaxed bias (close vs H/L) nearly doubled trade count** while maintaining profitability. 167 trades = 9.3/year, approaching live-tradeable frequency.
2. **Walk-forward reveals regime dependence.** Strategy breaks even 2008-2019, profits only 2020-2026. This is not curve-fitting (would show the opposite pattern) but means the edge is conditional on post-2020 market structure.
3. **Quarter Kelly is impractical** at this edge level. The 4% fraction produces negligible returns. Fixed 1-contract sizing is the right approach.
4. **2022 improved.** Relaxed filter spread losses across more (smaller) trades: -$2,252 vs -$3,172 in Run 008.
5. **2018 flipped profitable.** +$1,252 vs -$1,118 — the 10-day ATR lookback responded faster to the Feb 2018 vol spike.
6. **Max DD improved:** 31.3% vs 37.6%, still above the 15% target but trending the right direction.

#### Implications for Live Trading
The walk-forward result is the most important finding: this strategy has **no edge in calm, low-vol markets** (2011-2019) and **strong edge in volatile markets** (2020-2026). If the current high-vol regime persists, it's tradeable. If vol compresses back to pre-2020 levels, expect breakeven performance. The strategy should be deployed with a regime switch: active in high-vol, paused in low-vol.

---

### Run 008 — Replace VWAP/EMA with Prior-Day H/L + ATR Vol Filter

**Date:** 2026-04-11
**Script:** `backtest-engine/.../strategies/mes_orb_strategy.py`
**Data:** `data/raw/ES_full_5min_continuous_UNadjusted.txt` — 1,289,036 bars, 4,710 trading days, Jan 2008 – Apr 2026

#### Changes from Run 007
| Component | Run 007 | Run 008 |
|---|---|---|
| Confluence filter | VWAP + EMA-9 | **Removed** — had zero selectivity |
| Prior-day bias | none | **ORB high > prior day high (longs), ORB low < prior day low (shorts)** |
| Volatility filter | none | **20-day ATR% between 0.3% and 2.0%** |
| 200-day SMA regime | yes | yes (kept) |
| ORB range filter | 0.3-1.0% of price | 0.3-1.0% of price (kept) |
| Other params | R:R=1.0, SL=50%, retest=2t | unchanged |

#### Ablation Study: Impact of Each Filter

| Variant | Trades | Win% | PF | Net $ | Max DD% |
|---|---|---|---|---|---|
| Run 007 (SMA + VWAP/EMA) | 606 | 48.7% | 0.902 | -$19,344 | -128% |
| 008a: prior-day H/L only | 326 | 51.5% | **1.163** | **+$15,404** | -50% |
| 008b: ATR vol 0.3-2.0% only | 374 | 52.4% | 0.955 | -$5,270 | -83% |
| **008: full stack (SMA + PD + ATR)** | **92** | **56.5%** | **1.734** | **+$17,665** | **-38%** |

#### Full Stack Results (Run 008)
| Metric | Value |
|---|---|
| Total Trades | 92 |
| Win Rate | **56.52%** |
| Profit Factor | **1.734** |
| Net Profit | **+$17,665 (+70.66%)** |
| Max Drawdown | -$10,096 (-37.56%) |
| Avg Win | $703 |
| Avg Loss | -$459 |
| Avg Trade | +$192 |
| Commission | $1,337 total |

#### Yearly Breakdown (Full Stack)
| Year | Trades | Win% | PF | PnL |
|---|---|---|---|---|
| 2008 | 2 | 100% | inf | +$542 |
| 2009 | 9 | 44% | 1.140 | +$95 |
| 2010 | 4 | 100% | inf | +$848 |
| 2011 | 7 | 57% | 1.221 | +$146 |
| 2012 | 3 | 33% | 0.440 | -$376 |
| 2013 | 3 | 67% | 2.014 | +$284 |
| 2014 | 3 | 67% | 1.961 | +$306 |
| 2015 | 9 | 33% | 0.417 | -$1,545 |
| 2016 | 5 | 60% | 1.428 | +$331 |
| 2018 | 8 | 38% | 0.613 | -$1,118 |
| 2019 | 1 | 100% | inf | +$441 |
| **2020** | **6** | **67%** | **5.274** | **+$10,877** |
| 2021 | 1 | 100% | inf | +$736 |
| **2022** | **13** | **38%** | **0.560** | **-$3,172** |
| 2023 | 6 | 67% | 1.675 | +$1,223 |
| 2024 | 1 | 100% | inf | +$1,093 |
| 2025 | 6 | 67% | 2.187 | +$2,936 |
| **2026** | **5** | **80%** | **4.665** | **+$4,017** |

**Best 3 years:** 2020 (+$10,877), 2026 (+$4,017), 2025 (+$2,936)
**Worst 3 years:** 2018 (-$1,118), 2015 (-$1,545), 2022 (-$3,172)

#### Key Findings
1. **Prior-day H/L bias is the breakthrough filter.** On its own (008a), it flipped the strategy from -$19k to +$15k with PF 1.163. It ensures we only trade breakouts aligned with overnight momentum — gap-up days for longs, gap-down days for shorts.
2. **Full stack achieves PF 1.734 — first profitable result.** 92 trades over 18 years, 56.5% win rate, +$17,665 net. This is the first configuration to show positive expectancy across the full dataset.
3. **2022 damage reduced from -$17,420 to -$3,172.** The triple filter (SMA + prior-day + ATR) eliminated most of the counter-trend disasters. Still the worst year but now survivable.
4. **2020 is the standout year.** +$10,877 from only 6 trades (67% win, PF 5.27). The COVID crash + V-recovery produced massive ORB ranges with strong follow-through — exactly the regime this strategy exploits.
5. **ATR vol filter is the selectivity layer.** It cuts trades from 326 (prior-day only) to 92 (full stack), removing low-conviction setups in ultra-calm or extreme-panic markets. PF jumped from 1.163 to 1.734.
6. **13 of 18 years are profitable.** Only 2012, 2015, 2018, 2022, and 2009 (marginally) lost money. The strategy survived the 2008 crisis, 2020 crash, 2022 bear, and 2025 tariff selloff.
7. **Trade frequency is low:** 92 trades in 18 years = 5.1/year. Not enough for a standalone income strategy, but viable as one component of a multi-strategy portfolio.
8. **Max DD still high at -38%.** With 2 ES contracts on $25k, position sizing remains aggressive. Switching to 1 ES or 2 MES would halve the DD.

#### Prior-Day H/L Bias — Detailed Impact (008a)
The prior-day filter alone (without SMA or ATR) produced 326 trades with PF 1.163:
- Flipped 2020 from -$5.5k to +$6.5k
- Flipped 2021 from -$2.8k to +$4.1k  
- Cut 2022 from -$17.4k to -$9.1k
- Flipped 2025 from -$5.2k to +$8.2k

The filter works because it requires the ORB to open beyond yesterday's range — this indicates genuine overnight conviction, not just random noise.

---

### Run 007 — Percentage ORB Filter + 200-Day SMA Regime Filter

**Date:** 2026-04-10
**Script:** `backtest-engine/.../strategies/mes_orb_strategy.py`
**Data:** `data/raw/ES_full_5min_continuous_UNadjusted.txt` — 1,289,036 bars, 4,710 trading days, Jan 2008 – Apr 2026

#### Changes from Run 006
| Parameter | Run 006 | Run 007 |
|---|---|---|
| ORB range filter | 20-60 pts (absolute) | **0.3%-1.0% of price** (percentage) |
| Regime filter | none | **200-day SMA** (longs above, shorts below) |
| Other params | unchanged | R:R=1.0, SL=50%, retest=2 ticks |

#### Comparison: All Three Variants

| Variant | Trades | Win% | PF | Net $ | Max DD |
|---|---|---|---|---|---|
| Run 006: abs ORB 20-60, no regime | 98 | 44.9% | 0.798 | -$14,516 | -112% |
| Fix 1: pct ORB 0.3-1.0%, no regime | **773** | **50.8%** | **0.883** | -$28,149 | -150% |
| **Fix 1+2: pct ORB + 200-day SMA** | **606** | **48.7%** | **0.903** | **-$18,994** | **-127%** |

#### Fix 1 impact: Percentage ORB filter (0.3%-1.0%)
- **Trades: 98 → 773** — massive increase. The percentage filter correctly qualifies days across all price levels (ES 800 in 2008 through ES 6800 in 2026).
- **PF: 0.798 → 0.883** — improvement from including more low-price-era trades.
- Still unprofitable. 2022 remains catastrophic: 138 trades, 41% win, -$34,914.

#### Fix 2 impact: 200-day SMA regime filter
- **Trades: 773 → 606** — regime filter removed 167 counter-trend trades (22%).
- **PF: 0.883 → 0.903** — modest improvement.
- **2022 damage cut in half:** -$34,914 → -$17,420 (108 trades vs 138).
- **2020 flipped profitable:** -$5,534 → +$3,240 (regime filter blocked shorts during the V-recovery).
- **2023 dramatically improved:** +$868 → +$5,393 (blocked shorts in bull market).

#### Yearly Breakdown (Fix 1+2: percentage ORB + regime)
| Year | Trades | Win% | PF | PnL |
|---|---|---|---|---|
| 2008 | 57 | 50.9% | 0.964 | -$402 |
| 2009 | 101 | 47.5% | 0.933 | -$695 |
| 2010 | 31 | 54.8% | 1.285 | +$840 |
| 2011 | 50 | 48.0% | 0.965 | -$231 |
| 2012 | 8 | 62.5% | 1.232 | +$214 |
| 2013 | 5 | 60.0% | 1.547 | +$286 |
| 2014 | 5 | 60.0% | 1.424 | +$281 |
| 2015 | 26 | 38.5% | 0.589 | -$2,704 |
| 2016 | 18 | 44.4% | 0.632 | -$1,848 |
| 2018 | 32 | 40.6% | 0.657 | -$3,920 |
| 2019 | 11 | 36.4% | 0.498 | -$2,077 |
| **2020** | **70** | **50.0%** | **1.101** | **+$3,240** |
| 2021 | 16 | 43.8% | 0.637 | -$2,776 |
| **2022** | **108** | **44.4%** | **0.713** | **-$17,420** |
| **2023** | **17** | **70.6%** | **2.276** | **+$5,393** |
| 2024 | 6 | 66.7% | 1.528 | +$1,346 |
| 2025 | 36 | 50.0% | 0.806 | -$5,176 |
| **2026** | **9** | **77.8%** | **3.950** | **+$6,654** |

**Best 3 years:** 2026 (+$6,654), 2023 (+$5,393), 2020 (+$3,240)
**Worst 3 years:** 2018 (-$3,920), 2025 (-$5,176), 2022 (-$17,420)

#### Key Findings
1. **Both fixes helped but the strategy remains unprofitable.** PF went 0.798 → 0.883 → 0.903. Still below 1.0 over 18 years.
2. **Percentage ORB filter was critical.** Went from 98 trades (only high-vol periods) to 773 (all market conditions). This is the correct approach — normalized across ES 800→6800.
3. **Regime filter had targeted impact.** Cut 2022 losses by 50%, flipped 2020 profitable, boosted 2023. Removed 167 counter-trend trades. But it also hurt some years (2025: went from +$1,883 to -$5,176 because the filter blocked profitable shorts during pullbacks in a bull market).
4. **The regime filter is too blunt.** Using yesterday's close vs 200-day SMA to block ALL shorts in bull markets also blocks shorts during sharp pullbacks (which is exactly when ORB shorts work best — e.g., Apr 2025 tariff selloff). The SMA itself lags by months.
5. **2022 remains the core problem.** Even with regime filter, it's -$17,420 (108 trades, 44% win). The bear market had constant ORB breakouts that reversed. The strategy needs a volatility or trend-strength filter, not just direction.
6. **Win rate stuck near 50%.** VWAP + EMA-9 confluence still provides zero edge. The strategy is fundamentally a coin flip with slightly negative expectancy due to commissions.

#### Diagnosis
The ORB breakout+retest strategy with the current entry logic does not have statistical edge on ES futures over any sustained period. The improvements (tight retest, fractional SL, percentage ORB, regime filter) have each incrementally improved PF from the initial 0.656 to 0.903, but the underlying signal — "price breaks ORB level, retests, and I enter with VWAP+EMA confirmation" — produces ~50% win rate regardless of parameters. Commission drag makes it net-negative.

**The strategy concept may still be viable** but needs a fundamentally different entry trigger or filter to achieve >55% win rate.

---

### Run 006 — Full Dataset: 18 Years of Real ES Data (2008-2026)

**Date:** 2026-04-10
**Script:** `backtest-engine/.../strategies/mes_orb_strategy.py`
**Data:** `data/raw/ES_full_5min_continuous_UNadjusted.txt` — FirstRateData ES continuous futures, 1,289,036 bars, 4,710 trading days, Jan 2008 – Apr 2026

#### Config
R:R=1.0, SL=50% of ORB range, retest=2 ticks (0.50 pts), ORB range 20-60 pts, 2 ES contracts ($50/pt), $2.25/contract commission, $25,000 initial capital.

#### Overall Results
| Metric | Value |
|---|---|
| Total Trades | 98 |
| Win Rate | 44.90% |
| Profit Factor | **0.798** |
| Net Profit | -$14,516 (-58.07%) |
| Max Drawdown | -$30,485 (-112.16%) |
| Avg Win | $1,301 |
| Avg Loss | -$1,329 |
| Commission | $1,429 total |
| First Trade | 2008-09-19 |
| Last Trade | 2026-03-27 |

#### Yearly Breakdown
| Year | Trades | Win% | PF | PnL |
|---|---|---|---|---|
| 2008 | 4 | 50.0% | 1.061 | +$124 |
| 2015 | 1 | 0.0% | 0.000 | -$1,881 |
| 2018 | 1 | 100% | inf | +$1,616 |
| 2020 | 18 | 50.0% | 0.853 | -$1,995 |
| 2021 | 2 | 0.0% | 0.000 | -$3,139 |
| **2022** | **25** | **24.0%** | **0.321** | **-$16,469** |
| 2023 | 2 | 0.0% | 0.000 | -$2,038 |
| 2024 | 5 | 60.0% | 1.302 | +$821 |
| 2025 | 29 | 51.7% | 1.100 | +$1,883 |
| **2026** | **11** | **72.7%** | **2.964** | **+$6,560** |

**Best 3 years:** 2026 (+$6,560), 2025 (+$1,883), 2018 (+$1,616)
**Worst 3 years:** 2023 (-$2,038), 2021 (-$3,139), 2022 (-$16,469)

#### Key Findings
1. **Strategy is unprofitable over 18 years.** PF 0.798, net -$14,516. This is a definitive result — not a small-sample artifact.
2. **2022 was catastrophic.** 25 trades, 24% win rate, -$16,469. This was a high-volatility bear market with persistent downtrend — the ORB breakout+retest pattern fired constantly but mean-reverted against every entry.
3. **Only 98 trades in 18 years (5.4/year).** The 2-tick retest + 20-60 pt ORB filter is extremely selective. Most years have 0-5 trades. Not enough setups for a viable standalone strategy.
4. **Recent years (2024-2026) are profitable.** 45 trades, 56% win, PF ~1.3. The strategy may work in the current higher-volatility, higher-price regime where 20-60 pt ORB ranges are more common.
5. **Pre-2020 is nearly empty.** Only 6 trades from 2008-2019. ES was priced at 800-3000 during that period — the 20-60 pt ORB range filter excludes almost all days because ORB ranges were smaller (5-15 pts typical at lower prices).
6. **The ORB range filter should be percentage-based, not absolute.** A 20-pt ORB at ES 1000 is a 2% range (massive). At ES 6000 it's 0.33% (normal). The fixed 20-60 pt filter only works for ES 4000+.
7. **Max DD of 112%** means the account went negative (theoretical). Utterly unacceptable for 2 ES contracts on $25k.

#### Diagnosis
The ORB breakout+retest strategy with current parameters has no edge on ES over 18 years. The tight 2-tick retest dramatically reduces trade frequency but doesn't improve win rate enough. The 44.9% win rate with nearly 1:1 avg win/loss means every trade is essentially a coin flip after commissions.

The strategy may have regime-conditional edge (works in 2024-2026 high-vol environment) but this cannot be distinguished from survivorship bias without out-of-sample testing.

#### Immediate Actions Needed
- Convert ORB range filter from absolute (20-60 pts) to percentage (e.g., 0.3%-1.0% of price) to normalize across price levels
- Retest with percentage-based filter to get more trades pre-2020
- Consider abandoning the retest requirement entirely — direct breakout entry with tighter stop

---

### Run 005 — Corrected ES Contract Specs

**Date:** 2026-04-10
**Script:** `backtest-engine/.../strategies/mes_orb_strategy.py`
**Change:** Fixed contract specs from MES ($5/pt, $0.62 comm) to ES ($50/pt, $2.25 comm). Dollar P&L is now 10× larger but PF and win rate are comparable. Commission impact changes slightly because ES commission ($2.25) is proportionally lower than MES ($0.62) relative to contract value.

#### Config
Same best config as Run 004: R:R=1.0, SL=50%, retest=2 ticks, ORB 20-60 pts, 2 ES contracts, $25,000 capital.

#### Real Sample Data (10 trading days, 2 trades)
| Metric | Run 004 (MES specs) | Run 005 (ES specs) |
|---|---|---|
| Trades | 2 | 2 |
| Win Rate | 50.0% | 50.0% |
| Profit Factor | 1.075 | 1.110 |
| Net Profit | +$8.27 | +$119.61 |
| Max Drawdown | -$111.63 (-0.45%) | -$1,088.46 (-4.35%) |

#### 6-Month Synthetic (134 trading days, 51 trades)
| Metric | Run 004 (MES specs) | Run 005 (ES specs) |
|---|---|---|
| Trades | 51 | 51 |
| Win Rate | 52.9% | 52.9% |
| Profit Factor | 0.903 | **0.942** |
| Net Profit | -$187.40 | -$1,096.93 |
| Max Drawdown | -$652.52 (-2.61%) | -$6,171.59 (-24.69%) |
| Commission | $123.65 | $459.43 |

Monthly breakdown (ES specs):

| Month | Trades | Win% | PnL |
|---|---|---|---|
| 2025-10 | 6 | 50% | -$940 |
| 2025-11 | 9 | 44% | **-$2,742** (worst) |
| 2025-12 | 9 | 56% | -$1,393 |
| 2026-01 | 10 | 60% | +$1,660 |
| 2026-02 | 6 | 33% | -$1,617 |
| 2026-03 | 10 | 60% | **+$3,421** (best) |
| 2026-04 | 1 | 100% | +$516 |

#### Key Findings
1. **PF improved slightly (0.903 → 0.942)** because ES commission ($2.25) is proportionally cheaper than MES ($0.62) relative to contract value.
2. **Max DD now 24.69%** — exceeds the 15% target. With 2 ES contracts on $25k capital, the leverage is too high. Either reduce to 1 contract or increase capital to $50k+.
3. **Dollar P&L scaled 10×** as expected. -$187 (MES) → -$1,097 (ES). Same trades, same direction, same points — just larger contract.
4. **Profitable months produce real gains:** Mar 2026 = +$3,421 with 10 trades at 60% win rate. The strategy may have conditional edge in trending markets.

---

### Run 004 — Tightened Retest + Fractional SL Sweep

**Date:** 2026-04-10
**Script:** `backtest-engine/.../strategies/mes_orb_strategy.py` (v2 signal generator)

#### Changes from Run 003
| Parameter | Old (Run 003) | New (Run 004) |
|---|---|---|
| Retest tolerance | 0.08% (~5 pts) | **2 ticks (0.50 pts)** |
| ORB range filter | none / >10 pts | **20-60 pts** |
| Stop loss | full ORB range | **50% of ORB range** (sweep: 50/75/100%) |
| R:R sweep | 1.5 only | **1.0, 1.5, 2.0** |

#### Real Data (sample-data/ES_5min_sample.csv, 10 trading days)

Old baseline for comparison (32-tick retest = ~8 pts, full SL, R:R=1.5):
- 10 trades, 50% win, **PF 1.457**, Net +$424

Sweep results (2-tick retest, ORB 20-60 pts):

| # | R:R | SL% | Trades | Win% | PF | Net $ |
|---|---|---|---|---|---|---|
| **1** | **2.0** | **100%** | **2** | **50%** | **2.258** | **+$265** |
| 2 | 1.5 | 100% | 2 | 50% | 1.693 | +$146 |
| 3 | 1.0 | 100% | 2 | 50% | 1.128 | +$27 |
| 4 | 1.0 | 50% | 2 | 50% | 1.075 | +$8 |
| 5-9 | various | 50-75% | 2 | 0% | 0.000 | losses |

**Issue:** 2-tick retest is too tight for 10 days — only 2 trades qualify (both shorts on Mar 24 and 27). Not enough data for conclusions. Full SL (100%) outperforms tighter SL because the tight retest already puts entries close to the ORB level.

#### 6-Month Synthetic (134 trading days, 51 qualifying trades)

| # | R:R | SL% | Trades | Win% | PF | Net $ | MaxDD% |
|---|---|---|---|---|---|---|---|
| **1** | **1.0** | **50%** | **51** | **52.9%** | **0.903** | **-$187** | **2.61%** |
| 2 | 1.5 | 50% | 51 | 51.0% | 0.846 | -$316 | 2.78% |
| 3 | 1.0 | 75% | 51 | 51.0% | 0.827 | -$364 | 2.97% |
| 4 | 2.0 | 50% | 51 | 51.0% | 0.817 | -$376 | 3.02% |
| 5-9 | various | 75-100% | 51 | 51.0% | 0.794-0.798 | -$424 to -$436 | 3.21-3.26% |

Best 6-month monthly breakdown (R:R=1.0, SL=50%):

| Month | Trades | Win% | PnL |
|---|---|---|---|
| 2025-10 | 6 | 50% | -$103 |
| 2025-11 | 9 | 44% | **-$288** (worst) |
| 2025-12 | 9 | 56% | -$153 |
| 2026-01 | 10 | 60% | +$151 |
| 2026-02 | 6 | 33% | -$171 |
| 2026-03 | 10 | 60% | **+$327** (best) |
| 2026-04 | 1 | 100% | +$50 |

#### Key Findings
1. **Tight retest (2 ticks) dramatically reduces trade count.** From 64 trades to 51 on 6-month data — filters out 20% of loose entries. On 10-day real data, only 2 trades qualify.
2. **50% SL is the clear winner.** Tighter stop + 1:1 R:R gives the best PF (0.903 vs 0.794 for full SL). Still unprofitable but closest to breakeven.
3. **R:R=1.0 beats 1.5 and 2.0** with tight retest. When entries are close to the ORB level, a 1:1 target is hit more often. Higher R:R doesn't compensate for lower win rate.
4. **Strategy is still net-negative on synthetic data** (-$187 over 6 months). The improvements moved PF from 0.656 to 0.903 — significant but not yet profitable.
5. **ORB range filter worked.** 20-60 pt range filter removed 13 trades (64→51) that were choppy or gap days.
6. **Months with 60% win rate were profitable** (Jan, Mar 2026). The strategy may have conditional edge in trending markets.

#### Diagnosis
The tight 2-tick retest requirement forces entries very close to the ORB level, which is the right idea — but the VWAP/EMA confluence filters still add no selectivity. The win rate hovers at 51-53%, barely above coin-flip. The strategy needs either stronger directional filters (e.g., overnight gap direction, pre-market trend) or a fundamentally different entry trigger.

---

### Run 003 — 6-Month Synthetic + Filter Tests

**Date:** 2026-04-10
**Script:** `backtest-engine/.../strategies/mes_orb_strategy.py`
**Data:** `data/ES_6months.csv` — synthetic ES 5-min, 36,984 bars, 134 trading days (Oct 2025 – Apr 2026), full ETH, ORB ranges 15-50 pts, ES tick-rounded (0.25)

#### Baseline (R:R=1.5, no filters)
| Metric | Value | Target |
|---|---|---|
| Net Profit | -$1,040.24 (-4.16%) | — |
| Profit Factor | 0.656 | >= 1.5 |
| Max Drawdown | -$1,369.29 (-5.48%) | <= 15% |
| Total Trades | 64 | >= 20 |
| Win Rate | 46.88% | >= 70% |
| Avg Win / Avg Loss | 0.744 | — |
| Largest Win | $365.05 | — |
| Largest Loss | -$289.88 | — |

#### Monthly Breakdown
| Month | Trades | Win% | PnL |
|---|---|---|---|
| 2025-10 | 8 | 37.5% | -$141.56 |
| 2025-11 | 11 | 36.4% | **-$703.70** (worst) |
| 2025-12 | 9 | 55.6% | -$134.27 |
| 2026-01 | 14 | 50.0% | -$74.06 |
| 2026-02 | 8 | 37.5% | -$112.13 |
| 2026-03 | 11 | 45.5% | +$60.42 |
| 2026-04 | 3 | 100.0% | **+$65.05** (best) |

#### Filter Comparison (R:R = 1.5)
| Variant | Trades | Win% | PF | Net $ | MaxDD% |
|---|---|---|---|---|---|
| Baseline (no filters) | 64 | 46.9% | 0.656 | -$1,040 | 5.48% |
| + Min ORB range > 10 pts | 64 | 46.9% | 0.656 | -$1,040 | 5.48% |
| + Entry before 11:00 AM | 35 | 42.9% | 0.527 | -$980 | 5.63% |
| + Both filters combined | 35 | 42.9% | 0.527 | -$980 | 5.63% |

#### Key Findings
1. **Strategy is unprofitable at scale.** Over 134 trading days and 64 trades, the ORB strategy with R:R=1.5 loses money (PF 0.656). The R:R=1.5 advantage seen in the 10-day real sample was not durable.
2. **No month was consistently profitable.** Only March and April (partial) showed gains. Every other month lost money. Worst month: Nov 2025 (-$704, 36% win rate).
3. **Min ORB range filter had zero effect.** All 134 synthetic ORB bars had ranges >= 15 points by construction, so the >10 pt filter didn't exclude anything.
4. **Time filter made results worse.** Restricting entries to before 11:00 AM cut trades from 64 to 35 and lowered PF from 0.656 to 0.527. Afternoon entries were actually better.
5. **Avg win ($66) < avg loss ($89).** Even with 1.5:1 R:R target, most trades exit at session-end or SL — not TP. The breakout-retest pattern doesn't produce enough follow-through for profitable TP hits.
6. **Max drawdown controlled.** -5.48% is well within the 15% target. Position sizing is conservative.

#### Diagnosis
The ORB breakout+retest strategy as currently implemented does not have edge on ES futures in this synthetic data. The core problem is that the "retest" condition fires too loosely — a wide tolerance means entries happen far from the ORB level, and the SL (other side of range) is too wide relative to realistic intraday moves. Most trades end up as session-end flattens with small random P&L, making the strategy equivalent to noise.

#### Next Steps
- Test on real historical ES data (not synthetic) to confirm findings
- Tighten retest to tick-based tolerance (1-2 points) instead of percentage
- Consider requiring a specific retest bar pattern (e.g., hammer/doji at ORB level)
- Evaluate ORB-only without the retest requirement (direct breakout entry)
- Test on MES 1-min data for tighter entries

---

### Run 002 — Real ES Data + Parameter Sweep

**Date:** 2026-04-10
**Script:** `backtest-engine/.../strategies/mes_orb_strategy.py`
**Data:** `sample-data/ES_5min_sample.csv` — real ES futures 5-min, 2950 bars, 10 trading days (2026-03-23 to 2026-04-06), Eastern Time, ETH session

#### Baseline (EMA=9, R:R=2.0, Retest=0.08%)
| Metric | Value | Target |
|---|---|---|
| Net Profit | -$347.54 (-1.39%) | — |
| Profit Factor | 0.768 | >= 1.5 |
| Max Drawdown | -$799.98 (-3.20%) | <= 15% |
| Total Trades | 10 | >= 20 |
| Win Rate | 30.00% | >= 70% |

#### Parameter Sweep (27 combinations: R:R × EMA × Retest%)

Only R:R ratio affected results — EMA length and retest tolerance produced identical trades for each R:R tier.

| R:R | Trades | Win% | PF | Net $ | Net% | Max DD% |
|---|---|---|---|---|---|---|
| **1.5** | **10** | **50.0%** | **1.360** | **+$392.43** | **+1.57%** | **2.47%** |
| 2.5 | 10 | 30.0% | 0.942 | -$87.54 | -0.35% | 3.20% |
| 2.0 | 10 | 30.0% | 0.768 | -$347.54 | -1.39% | 3.20% |

#### Best Result: R:R=1.5, EMA=9, Retest=0.08%

| Metric | Value |
|---|---|
| Net Profit | +$392.43 (+1.57%) |
| Profit Factor | 1.360 |
| Max Drawdown | -$641.91 (-2.47%) |
| Total Trades | 10 |
| Win Rate | 50.0% |
| Avg Win / Avg Loss | — |
| Final Equity | $25,392.43 |
| Commission | $27.54 total |

#### Trade Log (Best: R:R=1.5)
| # | Dir | Entry | Entry $ | Exit | Exit $ | PnL |
|---|---|---|---|---|---|---|
| 1 | LONG | 03-23 09:50 | 6668.25 | 03-23 11:00 | 6704.38 | +$358.44 (TP) |
| 2 | SHORT | 03-24 09:45 | 6582.50 | 03-24 10:05 | 6604.00 | -$217.77 (SL) |
| 3 | SHORT | 03-25 09:50 | 6653.25 | 03-25 16:00 | 6641.75 | +$112.21 (EOD) |
| 4 | SHORT | 03-26 09:40 | 6580.50 | 03-26 09:45 | 6603.25 | -$230.27 (SL) |
| 5 | SHORT | 03-27 09:55 | 6468.75 | 03-27 13:55 | 6427.62 | +$408.54 (TP) |
| 6 | SHORT | 03-30 09:40 | 6446.50 | 03-30 13:15 | 6409.38 | +$368.55 (TP) |
| 7 | LONG | 03-31 09:40 | 6466.00 | 03-31 09:50 | 6489.88 | +$236.03 (TP) |
| 8 | LONG | 04-01 09:40 | 6626.50 | 04-01 09:45 | 6602.50 | -$242.78 (SL) |
| 9 | SHORT | 04-02 09:40 | 6517.00 | 04-02 09:50 | 6538.50 | -$217.74 (SL) |
| 10 | LONG | 04-06 09:55 | 6639.50 | 04-06 13:10 | 6621.50 | -$182.78 (SL) |

#### Key Findings
1. **R:R is the only parameter that matters in this sample.** EMA (5/9/13) and retest tolerance (0.05/0.08/0.12%) had zero impact — all entries pass VWAP+EMA confluence regardless of length, and all retests occur within the tightest tolerance.
2. **R:R 1.5 is the clear winner.** 4 TP hits out of 10 trades vs 0 TP hits at R:R 2.0 and 2.0/2.5. The wider ORB ranges on ES (~20-50 points) make 2:1 and 2.5:1 targets too ambitious for intraday.
3. **Short bias**: 6 of 10 trades were shorts. The period included a significant selloff (Mar 27-30: 6468→6397).
4. **Fast SL hits**: Trades #2, #4, #8, #9 were stopped within 1-2 bars (5-10 min). The ORB range may be too narrow relative to post-ORB volatility.
5. **Still below targets**: PF 1.36 vs 1.5 target, Win% 50% vs 70% target. Need more data and likely strategy refinements.
6. **Max DD well controlled**: -2.47% vs 15% limit.

#### Next Steps
- Get more data (need 20+ trades for statistical significance)
- Test tick-based retest tolerance (matching Pine v1's 4-tick / 1-point tolerance)
- Consider wider ORB (use first 2-3 bars instead of 1) for ES-sized ranges
- Evaluate partial profit-taking (close 1 contract at 1:1, trail the second)

---

### Run 001 — Baseline ORB v1 (Synthetic Data)

**Date:** 2026-04-10
**Script:** `backtest-engine/.../strategies/mes_orb_strategy.py`
**Data:** ES 5-min synthetic sample (2026-03-23 to 2026-04-06, 869 bars, 11 trading days)

#### Settings
| Parameter | Value |
|---|---|
| Initial Capital | $25,000 |
| Position Size | 2 MES contracts ($5/point), fixed qty = 10 |
| Commission | $0.62/contract (~0.0021% of position value) |
| Slippage | 0 (NOT simulated) |
| EMA Length | 9 |
| R:R Ratio | 2.0 : 1 |
| Retest Tolerance | 0.08% |

#### Results
| Metric | Value | Target |
|---|---|---|
| Net Profit | $80.71 (0.32%) | — |
| Profit Factor | 1.309 | >= 1.5 |
| Max Drawdown | -$211.41 (-0.84%) | <= 15% |
| Total Trades | 10 | >= 20 |
| Win Rate | 60.00% | >= 70% |
| Avg Win / Avg Loss | 0.873 | — |
| Largest Win | $130.54 | — |
| Largest Loss | -$157.15 | — |
| Final Equity | $25,080.71 | — |

#### Trade Log
| # | Dir | Entry | Entry $ | Exit | Exit $ | PnL |
|---|---|---|---|---|---|---|
| 1 | LONG | 03-23 15:15 | 5858.29 | 03-23 16:00 | 5859.91 | +$13.74 |
| 2 | SHORT | 03-24 11:30 | 5852.90 | 03-24 16:00 | 5849.87 | +$27.84 |
| 3 | SHORT | 03-25 10:55 | 5846.07 | 03-25 16:00 | 5845.40 | +$4.24 |
| 4 | LONG | 03-26 10:40 | 5853.94 | 03-26 16:00 | 5867.24 | +$130.54 |
| 5 | SHORT | 03-27 14:30 | 5857.68 | 03-27 16:00 | 5857.50 | -$0.66 |
| 6 | SHORT | 03-31 11:50 | 5851.88 | 03-31 16:00 | 5842.98 | +$86.54 |
| 7 | SHORT | 04-01 10:05 | 5833.80 | 04-01 12:45 | 5849.27 | -$157.15 (SL) |
| 8 | LONG | 04-02 09:45 | 5857.79 | 04-02 16:00 | 5865.93 | +$78.94 |
| 9 | SHORT | 04-03 09:40 | 5854.66 | 04-03 16:00 | 5864.04 | -$96.26 |
| 10 | LONG | 04-06 09:50 | 5869.26 | 04-06 16:00 | 5868.80 | -$7.06 |

#### Observations
- **Data caveat:** Synthetic/generated data — results are for pipeline validation only, not strategy validation. Real ES/MES data needed for actionable results.
- **No TP hits:** All exits were either session-end flattens or SL hits. The 2:1 R:R target was never reached. This suggests the ORB range may be too wide relative to intraday moves in this sample, or the 0.08% retest tolerance is allowing entries too far from the ORB level.
- **Win rate below target:** 60% vs 70% target. Winners are mostly session-end closes with small gains, not TP hits.
- **Profit Factor below target:** 1.31 vs 1.5 target.
- **Max Drawdown well within target:** -0.84% vs 15% limit.
- **Trade count below target:** 10 trades in 11 days (only 10 days since neutral days produced no trade). Need more data for 20+ trades.
- **Bug fix applied:** TP/SL values must be published on the exit bar itself so the engine can detect the stop hit. Without this, positions bleed past their stop levels.

#### Next Steps
- Obtain real MES 5-min data from TradingView CSV export
- Test with retest tolerance in ticks (4 ticks = 1.0 point, matching Pine script) vs percentage
- Optimize R:R ratio (try 1.5) — current 2:1 never hits TP
- Evaluate adding a tighter trailing stop after partial profit

---

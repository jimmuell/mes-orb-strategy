# MES ORB Strategy — Backtest Results

## Iteration Log

Results will be logged below as backtests are run.

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

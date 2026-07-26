# WIT-P1b — Build & Run Report-Back (backfilled from session 2026-07-26)

> Full deliverable: [`../reports/WIT-0001-volume-profile-orb.md`](../reports/WIT-0001-volume-profile-orb.md) (committed). This log file preserves the report-back's unique sections only.

## 1. Tests & anomalies
- VP golden tests + full suite passed; CI green on PR #47 (test suite + ADR-050 security gate).
- Boundary artifact: 2,562 setups → 2,561 closed trades; final setup (2026-04-09) still open at data end, excluded from closed-trade stats. Immaterial.
- Data-window note: requested 2016-04-10 start; first in-range bar 2016-04-11 → effective window 2016-04-11 → 2026-04-09 (≈9.99 yr).
- Half-days handled by force-flat at each day's actual last RTH bar.

## 2. Primary-run headline
| Metric | Value |
|---|---|
| Trades | 2,561 |
| Net P&L (1 MES) | −$5,976.89 |
| Profit factor | 0.90 |
| Win rate | 34.3% |
| Expectancy/trade | −$2.33 (95% CI −$4.73 … −$0.01, entirely negative) |
| Max drawdown | −$7,270 |
| Edge-vs-luck | FAIL |
| Time-in-market | median 25 min/trade (guru's "90-min" claim: time part TRUE) |

- Verdict: **Tested — no edge.** Robust across all sweeps; sign flips positive only at zero slippage (PF 1.007 ≈ breakeven) — the signal sits at the cost line.
- Full history (2008→) worse: −$14,581.93, PF 0.836.
- Exit mix: stop 64.4% / target 31.4% / time 4.3%. Directions balanced (1,317 L / 1,245 S).

## 3. PR
PR #47 → merged as 6a0afde (WIT-P1c). Report + equity PNG + trades CSV (LFS) + results JSON committed under docs/wit/reports/.

WIT-P1b — Completed

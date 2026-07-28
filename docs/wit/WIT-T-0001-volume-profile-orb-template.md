# WIT Template Fill — WIT-T-0001 "Volume-Profile Opening Range Breakout"

> First hand-filled instance of the WIT-02 schema (template_version 1.0). Source: YouTube guru transcript, captured in session 2026-07-26 (video #2, "3-step strategy"). Filled by lead engineer; doubles as the calibration anchor for Class A and as input to the Phase 1 vertical slice.

## A. Identity & Claims

**A1 — name_and_source** · `specified (partial)`
Unnamed "3-step" strategy; channel/URL not captured with transcript. Nickname assigned: **Volume-Profile Opening Range Breakout (VP-ORB)**.

**A2 — claimed_performance**
| Claim | Quote | Testable? |
|---|---|---|
| Profitable over a 10-year backtest | "it has been proven to be extremely profitable over a 10year back test" | **Yes — we reproduce a 10-year run** |
| $200k in a couple of months (own capital) | "I put my own capital behind it and made over $200,000 in just a couple of months" | No — unverifiable anecdote |
| Consistent wins | "consistently gives me wins like this, this, and this" | No — cherry-picked examples |
| Works on any market | "this doesn't matter what market you're trading… futures, stocks, crypto, or forex" | Partial — we test ES; proxy disclosed |
| < 90 minutes per day | "consistent profits in less than 90 minutes per day" | **Yes — time-in-market statistic** |

`claims_shown_evidence: false` — the video displays **zero** statistics (no win rate, PF, drawdown, equity curve; the "10-year backtest" is asserted, never shown).

**A3 — internal_consistency_flags**
1. **Risk/reward arithmetic contradiction:** "we had a $35 risk to make $620" is impossible under the stated "fixed 2:1 risk-to-reward" rule ($35 risk ⇒ $70 target). The second example ("$585 at risk to make $1,170") *is* consistent. The first shown P&L cannot have come from the strategy as taught, or the numbers are wrong.
2. **"Same time works for any market":** a 9:30 ET open-range has no meaning for 24-hour markets (crypto, forex) as claimed.

## B. Market & Data

**B1 — instrument** · `specified` — Guru demonstrates on **NASDAQ** ("for NASDAQ, which we're using in this example… ticks of 0.25"). **WIT tests on ES (S&P futures), reported in MES dollars** ($1.25/tick, $5/point) — proxy disclosed under the guru's own "any market" claim.
**B2 — timeframe** · `specified` — 5-minute, sole timeframe ("We're going to stay on this time frame for the entire strategy").
**B3 — data_requirements** · *WIT-filled* — Volume profile over 9:30–9:45 ET requires intra-range volume distribution. Ideal: tick/1-min. From 5-min bars the range is only 3 bars → profile approximated by distributing each bar's volume across its high–low span in tick-sized rows. **Approximation must be disclosed; stop placement depends on POC precision.**

## C. Permission filters

**C1 — session_rules** · `specified` — Day starts 9:30 ET ("You get to your desk right at 9:30 a.m."); levels drawn at 9:45 ET ("wait until 9:45 EST"); **entries only before 11:00 ET** ("the entry must happen before 11:00 a.m. Eastern Standard Time"). Forced exit: `unspecified` → see F4.
**C2 — regime_filters** · `unspecified` — none stated.
**C3 — calendar_filters** · `unspecified` — none stated.

## D. Direction & Setup

**D1 — directional_bias** · `specified` — First 5-min candle to **close its body through** the value-area high ⇒ longs only that day; through the value-area low ⇒ shorts only. ("the very next 5-minute candle closes its body through our level… we're now going to only be looking for buys on this trading day"; "Had it been a break through the low, we would have been selling.")
**D2 — setup** · `specified` — Fixed-range **volume profile over 9:30–9:45**: rows = ticks (row size 1), **value area 70%**; levels = VAH, VAL, POC ("wait for a break of our value area high or our value area low").
**D3 — entry_trigger** · `specified`, interpretation flagged — Enter **at the close of the breakout candle** ("literally enter as soon as this candle closes"). Interpretation set: close beyond level (primary) vs. entire body beyond (variant).
**D4 — order_mechanics** · `specified` — Market order at signal close ("just click market buy").

## E. Position sizing

**E1** · `unspecified` → **assumption: 1 contract (MES)**. Flag: guru's own examples imply wildly variable risk ($35 vs. $585 — a 16× spread) with no sizing rule ever stated.

## F. Exits

**F1 — initial_stop** · `specified` (shorts `implied`) — **2 ticks beyond POC** ("drag this right up to two ticks under the PC [POC]"); shorts mirrored above POC by symmetry.
**F2 — profit_target** · `specified` — **Fixed 2:1 R:R** from entry ("drag your target until that ratio is two").
**F3 — trade_management** · `implied none` — "you just sit back and let the market do the heavy lifting." No break-even, no trailing, no scaling.
**F4 — time_exit** · `unspecified` → **assumption: force-flat at session close (16:00 ET)** if neither stop nor target hit.
**F5 — same_bar_policy** · `unspecified` → **assumption: stop-first (conservative)**.

## G. Risk controls

**G1 — trade_frequency_limits** · `implied` — one setup/day ("You just trade one setup on one time frame… the same thing every single day"); first qualifying break sets the day's only direction. Re-entry after stop-out: `unspecified` → **assumption: none (max 1 trade/day)**.
**G2 — loss_limits** · `unspecified` — none.

## H. Costs & execution *(all WIT-filled — video never mentions costs)*

**H1 — commission** · assumption: **$0.62/side/contract (MES)** ⚡sensitivity.
**H2 — slippage** · assumption: **1 tick/side** ⚡sensitivity (0/1/2 sweep).

## I. Optimization surface

`range_minutes=15 · value_area_pct=70 · stop_offset_ticks=2 · rr_target=2.0 · entry_cutoff=11:00 ET · timeframe=5m` — recorded for sensitivity/multiple-testing accounting; **v1 tests the stated defaults only**.

## J. Validation plan (WIT)

**J1 — test_design** — Primary window: **10 years, 2016-07-01 → 2026-06-30** (mirrors the "10-year backtest" claim), ES 5-min continuous; secondary: full history (2008→) as a robustness check. Metrics: trades, net PnL ($ MES), PF, max DD, win rate, avg trade, expectancy (R), avg time-in-market/day (tests the 90-minute claim). Statistics: bootstrap CIs (seed 42, 10k), Monte-Carlo edge-vs-luck, per-year table, regime breakdown.
**J2 — interpretation_set** — (1) entry: close-beyond vs. full-body-beyond; (2) slippage 0/1/2 ticks; (3) same-bar stop-first vs. target-first. Results reported across all variants; verdict marked *fragile* if it flips.

## K. Untestable remainder

Live chart-reading coaching ("watch how candles print"), the $200k anecdote, "this level is extremely powerful… it will be defended" narrative, and all mentorship/funded-trader claims. These are explicitly outside the codified strategy.

---

## Completeness verdict

**Class A — mechanically testable.** All execution-required fields specified or defensibly implied. Assumptions applied: 6 (sizing, time-exit, same-bar policy, re-entry, short-stop mirror, costs) — at the Class A limit, each disclosed and 3 of them sensitivity-swept. Completeness score: **18/27 fields specified or implied (~67%)** — *high* for the genre; this is the calibration anchor for Class A.

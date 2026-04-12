# Gap Fade — Phase 2 Strategy Spec (Draft for Senior Claude Review)

**Status:** Draft — awaiting Senior Claude approval before Run 005.
**Paradigm:** Mean reversion on opening gaps.
**Role in the system:** Complements Phase 1 ORB. ORB trades *with* gap direction (continuation); gap fade trades *against* it (reversal). Together they cover both outcomes of a gap day without competing for the same setups.

---

## 1. Strategy Overview

When ES opens materially above the prior RTH close, a measurable fraction of the time that gap "closes" — price retraces back to the prior day's close during the first 1–2 hours of the session. The same is true in reverse for gap-downs. This is a mean-reversion strategy that *only* activates on gap days, using the prior day close (PDC) as the fair-value anchor.

### Theoretical basis

1. **Auction market theory.** The prior day's value area represents the price zone where buyers and sellers agreed on fair value. Gaps outside that zone create an "unfair" opening price that often rotates back toward acceptance.
2. **Institutional liquidity.** Large participants who were unable to execute at value on the prior close frequently use the gap as an opportunity to enter at improved prices — fading the gap.
3. **ES-specific evidence.** Well-documented retail and institutional fade edge on S&P futures, particularly on non-trend days and outside of macro-news-driven opens.
4. **Complementary to Phase 1.** Phase 1 ORB requires the opening range to break *in the direction of the gap* (ORB high > prior close for longs). When the gap holds → ORB fires. When the gap fails → gap fade fires. The two strategies are mutually exclusive on any given day by construction.

---

## 2. Instrument & Session

| | |
|---|---|
| Symbol | ES / MES continuous (CME_MINI:MES1! for live trading) |
| Timeframe | 5-minute bars (same as Phase 1 — minimizes data management overhead) |
| Session | RTH only: 9:30–15:55 ET |
| Contract | 1 MES ($5/point, $0.62 commission/side) |
| Data | `data/raw/ES_full_5min_continuous_UNadjusted.txt` (18 years, 2008–2026) |

---

## 3. Gap Definition

Gap is measured between the prior RTH close (last 5-min bar at 15:55 ET of the prior session) and the current RTH open (first 5-min bar at 9:30 ET of the current session):

- `gap_pts = rth_open - prior_rth_close`
- `gap_pct = gap_pts / prior_rth_close * 100`
- **Gap up:** `gap_pct > 0`
- **Gap down:** `gap_pct < 0`

Note: this uses the RTH-to-RTH gap, which is typically larger than the night-session-to-night-session gap because it captures the full overnight move. This matches how the ORB strategy's prior-day bias filter is computed, so the two strategies see the same definition of "prior close".

---

## 4. Entry Conditions (precise and mechanical)

### 4.1 Daily regime gates (all must pass)

1. **Gap size filter**: `0.20% ≤ |gap_pct| ≤ 0.60%`
2. **ADX < 20** on daily bars (prior day's 14-period ADX) — carried over from Phase 2 runs 001-004 where it was the one reliably useful filter
3. **ATR% 0.3–2.0** (prior day's 10-day daily ATR as % of close) — also carried over
4. **Phase 1 ORB exclusion**: If Phase 1 ORB produces a confirmed entry signal on the same day, gap fade is blocked. Prevents competing trades. In practice this is mostly mechanical — ORB and gap fade are generally mutually exclusive by their triggers — but enforced explicitly for safety.

### 4.2 Setup (on the 9:30 ET ORB bar)

- Record `rth_open = open of 9:30 bar`
- Record `prior_close = close of prior day's 15:55 bar`
- Record `orb_high = high of 9:30 bar`, `orb_low = low of 9:30 bar`
- Compute `gap_pct` and check regime gates above
- If any gate fails, skip the day

### 4.3 Entry trigger (between 9:35 ET and 11:00 ET)

**Gap up → short entry:**
- A 5-min bar **closes back below `rth_open`** (price has retraced the gap open level)
- Entry: fill at the **next bar's open** (standard bar-close-then-next-open)
- Only one gap-fade entry per day; no re-entries

**Gap down → long entry:**
- A 5-min bar **closes back above `rth_open`**
- Entry: fill at next bar's open
- Only one entry per day

**Why "close back through RTH open" rather than alternatives:**

| Trigger option | Assessment |
|---|---|
| Market-on-open entry | Rejected — no confirmation that the gap is failing. Catches the falling knife on gap-and-go days. |
| Close back through `rth_open` (recommended) | Simple, mechanical, empirically well-documented. The RTH open is a natural reference level — closing back through it is the cleanest binary signal that gap-fade pressure is active. |
| Close back through ORB midpoint | Similar but weaker reference — the ORB midpoint has no auction-theory meaning. |
| RSI divergence | Non-mechanical, many tunable parameters, prone to overfitting. |
| Volume spike | Noisy, especially on 5-min bars. |

### 4.4 Entry window

Entries allowed only between **9:35 ET (bar 2 of the session) and 11:00 ET**. After 11:00 ET, if the trigger has not fired, skip the day. Historical analysis of ES gap-fade timing shows the vast majority of successful fades complete within the first 60–90 minutes of RTH.

---

## 5. Exit Conditions

### 5.1 Take profit — prior day close

**Primary TP = prior day close.** The target is the gap-fill level itself. Exit fires when a 5-min bar **touches or crosses** `prior_close` intrabar (fill at `prior_close` exactly).

Rationale: PDC is the theoretical anchor that justifies the entry. Exiting at PDC captures the full thesis and does not depend on an arbitrary R:R multiplier. The exit breakdown in Phase 2 Run 003 showed that level-based exits beat time-based exits decisively on ES.

### 5.2 Stop loss — gap extreme

**Primary SL = gap extreme** (= the 9:30 ORB high for gap-up shorts, the 9:30 ORB low for gap-down longs), plus a 1-tick buffer (0.25 pt).

Rationale: if a gap-up short is stopped by a new high above the ORB high, the gap-and-go thesis has overtaken the fade thesis — the trade is invalidated cleanly. This is the tightest stop that respects auction logic; it also makes the stop distance self-scaling to the day's volatility (the ORB range).

### 5.3 Session close

Flatten at 15:55 ET if neither TP nor SL has hit. Exit at the 15:55 close.

### 5.4 Same-bar TP+SL

Pessimistic: **SL fills first** on any bar where both levels are breached. Matches Phase 2 Runs 001-004 conventions.

### 5.5 Ablation targets

For Run 005, also backtest a **fixed R:R = 1.5 variant** alongside the PDC-target primary. This isolates whether the PDC anchor is load-bearing or whether a fixed R:R is equivalent. Run 004 showed that for VWAP scalp, fixed R:R exits were worse than level-based exits — we want to verify that finding holds on gap fade.

---

## 6. Filters Carried Over From Phase 2

| Filter | Keep? | Reason |
|---|---|---|
| ADX < 20 (daily, prior day's 14-period) | **Yes** | Only filter with consistent empirical value across all 4 VWAP runs. Mean reversion needs non-trending regime. |
| ATR% 0.3–2.0 (daily, prior day's 10-day) | **Yes** | Avoids ultra-low-vol noise and extreme-vol panic, consistent with Phase 1 and VWAP runs. |
| 200-day SMA regime | **Open question — ablate** | On gap fade, longs occur on gap-downs and shorts on gap-ups regardless of trend. SMA regime filter may block valid fades. Recommend testing with/without SMA filter in Run 005. |
| Max trades/day | **Yes — capped at 1** | Gap fade is a once-per-day setup by construction. |
| No re-entry after stop | **Yes** | Once the gap extreme is taken out, the thesis is dead. |
| Slippage | 0 (not simulated) | Same convention as all prior runs. |
| Commission | $0.62/side | 1 MES. |

---

## 7. Parameters to Optimize (Run 005 Ablation)

Six cells in the grid, focused on the two most consequential parameters:

| Variant | Gap size band | SMA filter | Target |
|---|---|---|---|
| A | 0.20–0.60% | on  | PDC |
| B | 0.20–0.60% | off | PDC |
| C | 0.30–0.80% | on  | PDC |
| D | 0.30–0.80% | off | PDC |
| E | 0.20–0.60% | off | fixed R:R 1.5 |
| F | 0.30–0.80% | off | fixed R:R 1.5 |

Fixed across all variants for Run 005: 5-min bars, 9:35–11:00 ET entry window, SL = gap extreme + 1 tick, ADX<20, ATR% 0.3–2.0, 1 MES, session-close flatten, pessimistic SL-first fills.

If Run 005 produces a clear winner, Run 006 can refine the gap-size band with a finer grid (e.g. 0.15/0.20/0.25/0.30 minimum, 0.50/0.60/0.75/1.00 maximum).

---

## 8. Expected Characteristics

These are **expectations, not targets** — used to sanity-check Run 005 results. A backtest that deviates wildly from these suggests a bug, not a finding.

| Metric | Expected range | Rationale |
|---|---|---|
| Win rate | 55–70% | Classic mean-reversion profile — high hit rate, small winners, occasional large losers. Run 002's 51.6% was a floor; gap fade should beat it because the entry trigger has a real theoretical basis. |
| Profit factor | 1.2–1.8 | A functional PF ≥ 1.2 validates the paradigm; PF ≥ 1.5 meets the Phase 2 target. |
| Trades/year | 60–120 | Gap days meeting the size band are perhaps 25–50% of trading days × ~250 days/year. Not all will trigger the entry. |
| Trades/day (on active days) | 1 | By design. |
| Avg hold time | 30–90 min | Most gap fades complete within the first 60–90 min. |
| Max drawdown | < 15% | With 1 MES and small per-trade dollar risk, DD should stay well under target. |

---

## 9. Phase 2 Targets

Same as prior runs:

| Metric | Target |
|---|---|
| Win Rate | ≥ 65% |
| Profit Factor | ≥ 1.5 |
| Max Drawdown | ≤ 15% |
| Walk-forward | validated (IS 2008-2019, OOS 2020-2026) |

---

## 10. Risks / Failure Modes

Conditions under which the gap-fade strategy may not work:

1. **Macro news gaps (Fed days, CPI, NFP).** Large gaps driven by scheduled macro events often continue (gap-and-go) rather than fade. The ADX<20 filter partially mitigates this but is imperfect. If Run 005 shows disproportionate losses clustered on macro-news days, consider a calendar filter.

2. **Trend days with strong follow-through.** A gap up on a strong uptrend day will extend, not fade. The ATR% and ADX filters attempt to screen these out but do not capture intraday trend strength.

3. **The 2020+ regime dependency from Phase 1 and Phase 2 VWAP.** Both prior strategies exhibited post-2020 vs pre-2020 regime sensitivity. Gap fade may show the same. Walk-forward split is essential.

4. **Sample size on the gap band.** If the 0.20–0.60% band produces only ~30 trades/year, the 18-year dataset gives ~540 trades — adequate but not abundant. Widening the band helps sample size but may degrade signal quality.

5. **Data integrity at the open.** The 9:30 5-min bar is the single most important bar in this strategy. Any data issues at the open (missing bars, bad prints) will poison individual trades. Run 005 should spot-check the first 20 triggered gap days manually.

6. **The VWAP paradigm failure warning.** Four runs on a theoretically-sound strategy produced nothing. The theoretical basis is necessary but not sufficient. **If Run 005 Variant A (the strongest a-priori configuration) produces PF < 1.0 across both IS and OOS, Senior Claude should seriously consider pausing Phase 2 entirely and focusing on Phase 1 paper trading rather than burning additional research budget on a second failed paradigm.**

---

## 11. Open Questions for Senior Claude

Before Run 005 proceeds, VS Claude wants explicit decisions on:

1. **SMA200 filter** — ablate (as proposed in variants A/B) or drop entirely? Auction-theory argument says drop; regime-safety argument says keep. Recommend ablating both ways in Run 005 to let the data decide, but open to being told just to drop it.

2. **Gap size band** — is 0.20%–0.60% the right starting point, or would Senior Claude prefer a different initial range? Larger gaps (> 0.60%) are traditionally classified as "gap and go" and excluded, but some research shows even 1%+ gaps fade a meaningful fraction of the time.

3. **Entry trigger** — stick with "close back through RTH open" or use a different mechanical trigger (close back through ORB midpoint, close back into prior-day range, etc.)?

4. **Exit timing** — PDC exact level as the primary, fixed R:R 1.5 as the secondary, as proposed? Or would Senior Claude like to see a third variant (e.g. exit at ORB midpoint, exit at X% retracement of gap)?

5. **Entry window end** — 11:00 ET cutoff. Is this too aggressive (some fades complete later) or too permissive (the cleanest fades are in the first 30 min)?

6. **Phase 1 ORB interaction** — explicit block when ORB signal fires (as proposed), or always allow both and let the portfolio layer sort it out? Mechanically they're almost always mutually exclusive, but the explicit block is safer.

7. **Should Run 005 include a "gap bucket" diagnostic?** Similar to the ADX regime split in prior runs — classify all trades by gap-size decile and show whether the edge is concentrated in a specific band. This is basically free to add and would directly inform Run 006.

---

## 12. Non-Goals (explicit)

To prevent scope creep, Run 005 will **not** include:

- Any intraday indicator beyond the daily regime filters (no intraday VWAP, no RSI, no MACD)
- Any machine-learning or statistical-model-based entry rule
- Multi-contract position sizing
- Trailing stops
- Scale-in / scale-out
- Calendar event filters (holidays, FOMC, NFP) — deferred to Run 006+ if needed
- News / sentiment data

The goal of Run 005 is to answer a single binary question: **does the basic mechanical gap-fade setup on ES have a live edge at all?** If yes, refinements follow. If no, the paradigm is cut fast, unlike the four-run VWAP death spiral.

---

## Appendix — Recommendations Summary for Senior Claude

| # | Design decision | VS Claude recommendation |
|---|---|---|
| 1 | Gap size filter | 0.20%–0.60% initial; ablate wider band (0.30%–0.80%) |
| 2 | Entry timing | 9:35 ET earliest (post-ORB bar), 11:00 ET latest |
| 3 | Entry confirmation | 5-min bar closes back through `rth_open` |
| 4 | Target | Prior day close; ablate fixed R:R 1.5 |
| 5 | Stop loss | Gap extreme (ORB high/low) + 1 tick |
| 6 | Time filter | 9:35–11:00 ET entry window, 15:55 ET session close |
| 7 | Phase 1 ORB interaction | Explicit block on days ORB fires a confirmed entry |

**Go/no-go decision rule** (proposed): If Run 005 Variant A produces PF ≥ 1.2 on the full dataset, proceed to Run 006 refinement. If PF < 1.0 across all 6 variants, abandon Phase 2 and focus on Phase 1 paper trading.

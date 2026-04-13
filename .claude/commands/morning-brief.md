---
description: Read live TradingView chart via MCP, compute regime filters, POST to dashboard, print brief
---

# Morning Brief

Generate the daily pre-market brief by reading live chart values from the
TradingView desktop app via the `tradingview` MCP server, computing Phase 1
and Phase 2 filter status, persisting the result to the dashboard, and
printing a formatted brief to the terminal.

**IMPORTANT:** The `tradingview` MCP server only loads in sessions that
have it configured (Claude Desktop / Claude.ai chat). If you are running
this from a Claude Code terminal session without TV MCP available, stop
and tell Jim to run the command from Claude Desktop instead. Do NOT fall
back to made-up numbers.

## Steps

1. Verify the MCP is live: call `tv_launch(kill_existing=False)` then
   `tv_health_check()`. Confirm `chartType: 1` (Candles, not Heikin Ashi).
   If chartType is anything else, stop and tell Jim to switch the chart
   to Candles — the brief cannot proceed.

2. Confirm the chart is on `CME_MINI:MES1!` and 5-minute timeframe. If
   not, call `chart_set_symbol("CME_MINI:MES1!")` and
   `chart_set_timeframe("5")`.

3. Pull current state:
   - `chart_get_state()` — get indicator entity IDs
   - `quote_get()` — current price, daily open, prior close, change
   - `data_get_study_values()` — read ADX and ATR from the chart's
     visible indicators. If ADX or ATR are not on the chart, add them:
     `chart_manage_indicator(action="add", name="Average Directional Index")`
     and `chart_manage_indicator(action="add", name="Average True Range")`
     then re-read.

4. Compute derived values:
   - `gap_pct = (today_open - prior_close) / prior_close * 100`
   - `atr_pct = atr_value / current_price * 100` (if ATR is raw, not %)
   - `phase1_adx_ok = adx >= 15`
   - `phase2_adx_ok = adx < 20`
   - `atr_ok = 0.3 <= atr_pct <= 2.0`
   - `phase2_gap_ok = 0.32 <= abs(gap_pct) <= 0.55`
   - `phase1_valid = phase1_adx_ok and atr_ok`
   - `phase2_valid = phase2_adx_ok and atr_ok and phase2_gap_ok`

5. POST to the dashboard:
   ```
   curl -s -X POST http://localhost:8080/api/sessions \
     -H 'Content-Type: application/json' \
     -d '{
       "date": "YYYY-MM-DD",
       "phase1_valid": <bool>,
       "phase2_valid": <bool>,
       "adx_value": <num>,
       "atr_pct": <num>,
       "gap_pct": <num>,
       "mes_open": <num>,
       "prior_day_close": <num>,
       "notes": "<any anomalies>"
     }'
   ```

6. Print a formatted brief to the terminal matching this layout:

   ```
   MORNING BRIEF — <Weekday Month D, YYYY>
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   MES1!  Last: <price>  Change: <chg> (<pct>%)
   Prior Day Close: <prior>
   Gap: <gap>% (<status>)

   REGIME FILTERS
   ADX (14-day):   <adx>  → <regime>   P1 <✓/✗>  P2 <✓/✗>
   ATR% (10-day):  <atr>% → <regime>   both <✓/✗>

   PHASE 1 — MES ORB
   Status: <WATCHING | BLOCKED>
   <reason if blocked>

   PHASE 2 — GAP FADE
   Status: <WATCHING | BLOCKED>
   <reason if blocked>

   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Last updated: <HH:MM CT>
   ```

7. Confirm success:
   - Dashboard POST returned `{"ok": true}`
   - Tell Jim the brief is now visible at
     http://localhost:8080 → MORNING BRIEF tab

If any MCP call fails, report the error and the exact step that failed.
Do not invent numbers — a failed brief is better than a wrong one.

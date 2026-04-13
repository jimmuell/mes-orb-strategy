# Morning Brief — MES Trading System

Run this command from Claude.ai chat (NOT Claude Code terminal) with
TradingView desktop app running and MCP connected.

Steps:
1. Read live values from TradingView chart via MCP:
   - Call data_get_study_values to get ORB High, ORB Low, Prior Day Close,
     RTH Open, ADX (14-day), ATR% (10-day)
   - Call quote_get for current MES1! price

2. Compute filter status:
   - ORB range = ORB High - ORB Low
   - ORB range % = ORB range / ((ORB High + ORB Low) / 2) * 100
   - Gap % = (RTH Open - Prior Day Close) / Prior Day Close * 100
   - Phase 1 valid = ADX >= 15 AND ATR% >= 0.3 AND ATR% <= 2.0
                     AND ORB range% >= 0.3 AND ORB range% <= 1.0
   - Phase 2 valid = ADX < 20 AND ATR% >= 0.3 AND ATR% <= 2.0
                     AND abs(Gap%) >= 0.32 AND abs(Gap%) <= 0.55

3. POST session data to dashboard:
   - URL: http://localhost:8080/api/sessions
   - Method: POST
   - Body: {
       "date": "YYYY-MM-DD",
       "phase1_valid": 1 or 0,
       "phase2_valid": 1 or 0,
       "adx_value": <value>,
       "atr_pct": <value>,
       "gap_pct": <value>,
       "mes_open": <RTH open price>,
       "prior_day_close": <prior close price>
     }

4. Print formatted morning brief:

   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   MES MORNING BRIEF — [DATE] [DAY]
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   MES1!  [PRICE]  [CHANGE] ([CHANGE%])
   Prior Close: [PDC]  |  RTH Open: [OPEN]
   Gap: [GAP%]%

   REGIME FILTERS
   ADX (14-day):  [VALUE]  → [PASS/FAIL]
   ATR% (10-day): [VALUE]% → [PASS/FAIL]

   PHASE 1 — ORB
   Status: [WATCHING / BLOCKED]
   [If blocked: Reason: ...]
   ORB High: [VALUE]  ORB Low: [VALUE]
   Range: [RANGE] pts ([RANGE%]%)

   PHASE 2 — GAP FADE
   Status: [WATCHING / BLOCKED]
   [If blocked: Reason: ...]
   Gap: [GAP%]%

   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Dashboard updated: http://localhost:8080

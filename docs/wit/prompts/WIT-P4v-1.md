Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P4v-1

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK — two corrections in src/lib/wit-public.ts (and its consumers). Frontend
only; nothing else.

  1. publicVerdictTone matches codes that do not exist. The engine's v1 verdict
     vocabulary is EXACTLY: tested_no_edge, tested_inconclusive (a Class C
     untestable evaluation never reaches a published report today). Replace the
     switch with:
       tested_no_edge      -> "red"
       tested_inconclusive -> "amber"
       anything else       -> "neutral"
     Remove the "edge"/"supported" green branch entirely — v1 has no code that
     may render green, and dead branches suggesting one are not acceptable.

  2. Money formatting: net_pnl, max_drawdown and avg_trade must render as
     currency ("-$9,672", "-$15,410", "-$2.33") on the library cards and the
     teaser page, matching the reviewer desk's convention (sign before $).
     trades stays a plain count; win_rate keeps %; profit_factor plain 2dp.

  DO NOT touch: routes other than the two library routes' use of these helpers,
  the publish-report function, anything else.

  DEPLOY / PUBLISH: frontend only — Publish -> Update.

  VERIFY (you):
    - Typecheck + production build pass.
    - Unit-level: publicVerdictTone("tested_no_edge") === "red",
      ("tested_inconclusive") === "amber", ("anything") === "neutral";
      formatMetric renders -9672.17 as "-$9,672" for net_pnl and -2.326 as
      "-$2.33" for avg_trade.
    - No data changes; the report stays draft.

REPORT BACK (exactly this):
  1. Both fixes confirmed, published: y/n.
  2. Verification results.
  3. Anything noticed.
  Final line, exactly: WIT-P4v-1 — Completed

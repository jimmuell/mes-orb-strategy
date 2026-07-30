Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P4u

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK — store the engine's verdict on draft reports, and render it. Two touch
points only. No SQL, no migrations, no policy or grant changes, no new tables.

  Background fact you need: as of engine commit WIT-P4t, a successful run's
  result_json carries "verdict": {"code","label","reason"}. code is one of
  tested_no_edge | tested_inconclusive. Older results (before today) have no
  verdict key.

  1. Shared evaluation-chain module — report-draft creation only.
     In the run-success branch (backtest and event_study), where the draft
     report row is inserted, additionally set:
       verdict       = result_json.verdict.code        (only when present)
       headline_json = {
         label:  result_json.verdict.label,
         reason: result_json.verdict.reason,
         metrics: { trades, net_pnl, profit_factor, win_rate, max_drawdown,
                    avg_trade }   // copied from result_json.metrics, nulls kept
       }
     When result_json has no verdict key, insert exactly as today (both null).
     DO NOT change the WIT-P4n success ordering (result persisted and read back
     BEFORE evaluation completes and the report is inserted), and do not touch
     any other branch of the module.

  2. /review rendering.
     Detail view verdict block: when headline_json.label exists render it as the
     big verdict line with headline_json.reason as a sentence beneath it; keep
     "No verdict recorded" when absent. Do not render the metrics from
     headline_json in this block (the backtest section already shows them) —
     headline_json.metrics exists for the future public page, not this screen.
     List rows: map verdict codes to short labels — tested_no_edge -> "No edge",
     tested_inconclusive -> "Inconclusive"; unknown non-null codes render as-is;
     null renders "No verdict".

  DO NOT touch: publish-report's reviewer gate or transitions, poll-runs
  scheduling, submit-evaluation, RLS, any user-facing route.

  DEPLOY / PUBLISH:
    The shared module change redeploys the functions that import it — confirm
    engine-callback and poll-runs both redeploy (check function logs), since a
    stale deployment silently keeps the old behavior (the WIT-P4q lesson).
    Frontend: Publish -> Update.

  VERIFY (you):
    - Typecheck and production build pass.
    - Unit-level check of the draft-insert mapping with a result carrying a
      verdict and one without (no live submissions — do NOT create test
      evaluations or accounts).
    - The existing draft report is untouched by this slice (its verdict stays
      null until a separate backfill): confirm review_status='draft', verdict
      null after your work.

REPORT BACK (exactly this):
  1. What changed in the shared module and the review route; both functions
     redeployed: y/n; frontend published: y/n.
  2. Verification results, including the existing draft untouched.
  3. Anything noticed or deviated.
  Final line, exactly: WIT-P4u — Completed

Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P4w

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK — remove the browser-delete leftovers and stop over-selecting report
  columns. Frontend only; no SQL, no migrations, no function changes.

  1. Remove client-side audit deletion entirely.
     - src/routes/dashboard.tsx: remove the per-row Delete (trash) button, the
       delete confirmation dialog, and the delete mutation.
     - src/lib/wit-live.ts: remove the deleteEvaluation function.
     Background, for the record: client-side deletes were enabled by an
     unauthorized database rule that has been removed; deletion will return
     later as a server-checked edge function that refuses when a published
     report exists. Do not build that now.

  2. src/lib/wit-live.ts getEvaluationBundle: the reports query currently
     selects "*". Replace with the explicit column list
       id, evaluation_id, slug, verdict, headline_json, review_status, published_at
     (deliberately excluding reviewer_notes — internal editorial data). Adjust
     the ReportRow type usage if needed so typecheck passes. Leave the
     evaluations/runs/templates queries as they are.

  DO NOT touch: edge functions, /review, /library routes, RLS/grants, anything
  else.

  DEPLOY / PUBLISH: frontend only — Publish -> Update.

  VERIFY (you):
    - Typecheck and production build pass.
    - Dashboard renders with no delete affordance anywhere.
    - The evaluation results page still renders fully for the existing
      completed audit (verdict data comes from headline_json, not
      reviewer_notes).
    - No data changes; the report stays draft.

REPORT BACK (exactly this):
  1. What was removed and what the reports query now selects; published: y/n.
  2. Verification results.
  3. Anything noticed.
  Final line, exactly: WIT-P4w — Completed

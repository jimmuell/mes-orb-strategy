Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P4s

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK — reviewer surface + publish-report: the editorial gate for the public library

  NO DATABASE MIGRATIONS AND NO ACCESS-CONTROL SQL IN THIS SLICE. The reports table
  already has slug, verdict, headline_json, review_status, reviewer_notes and
  published_at. If at any point you believe you need a new policy, grant, table or
  column, STOP and report instead. All reviewer data access goes through the new
  edge function with the service role — the existing RLS policies are correct and
  must not change.

  1. New edge function publish-report (verify_jwt ON).
     Reviewer gate: read the secret WIT_REVIEWER_IDS (comma-separated auth user ids).
     If the secret is unset or the caller's user id is not in the list, return 403
     for EVERY action. Fail closed.
     Actions (POST body {action, ...}):
       status  -> {isReviewer: boolean}. The only action non-reviewers can call
                  without a 403 — it returns {isReviewer:false} instead.
       list    -> all reports with review_status in (draft, approved, published),
                  newest first, each with: report id, review_status, verdict,
                  published_at, slug, and from its evaluation: id, status, class,
                  source_title, source_channel, source_thumbnail_url, source_url,
                  created_at, and completeness score from its template.
       detail  -> {report_id} -> the full report row, its evaluation (all columns
                  EXCEPT transcript — never send the transcript), its template row
                  (template_json, completeness, ensemble_meta, wire_config,
                  assumptions), and the succeeded backtest/event_study run's
                  result_json.
       approve -> {report_id, reviewer_notes?} -> allowed only from draft ->
                  approved. Stores reviewer_notes if provided.
       publish -> {report_id} -> allowed only from approved -> published. Sets
                  published_at = now(). If slug is null, generate one from
                  source_title (lowercase, hyphenated, trailing 6 chars of the
                  report id for uniqueness).
       revert  -> {report_id} -> from approved or published back to draft. Clears
                  published_at. Publishing again later keeps the same slug.
     Any other transition -> 409 with {code:"INVALID_TRANSITION", from, to}.
     Every DB write is error-checked and read back before the response claims
     success (same discipline as WIT-P4n). Log only ids, statuses and boolean/
     reason tags — never report content, transcripts or secrets.

  2. New route /review in the app (desktop-first).
     On load call publish-report {action:"status"}; if not reviewer, redirect to
     the dashboard with no explanation. Reviewer sees:
       List view: one row per report — thumbnail, title, channel, class,
       completeness, verdict, review_status badge, created date.
       Detail view for a selected report:
         - Source card: thumbnail, title, channel (link to source_url).
         - Verdict + headline metrics from headline_json, and the KPI figures +
           equity curve from the run's result_json (reuse the existing results
           components).
         - Ensemble agreement: unanimous / majority / tie counts from
           ensemble_meta, displayed prominently.
         - Assumptions the lab applied: the assumptions list from the template row.
         - Honest gaps: every template field whose status is not "specified",
           with its status (implied / unspecified / defaulted).
         - Reviewer notes textarea (saved with approve).
         - Buttons by status: draft -> Approve; approved -> Publish and Revert to
           draft; published -> Revert to draft. Publish opens a confirm dialog
           stating the report becomes publicly readable.
     No other page changes. This slice does NOT build the public library page.

  DO NOT touch: submit-evaluation, engine-callback, poll-runs, the shared
  state-machine module, any existing user-facing route or component behavior,
  and no SQL migrations of any kind.

  DEPLOY / PUBLISH:
    publish-report auto-deploys on edit — verify it responds in the function logs.
    Frontend: after the edit, Publish -> Update so /review is on the live URL.

  VERIFY (you):
    - Typecheck and production build pass.
    - publish-report with no/invalid auth -> 401/403; with a signed-in NON-reviewer
      test JWT -> 403 on list/detail/approve/publish/revert and
      {isReviewer:false} on status. Do NOT create new test accounts for this —
      use an existing e2e test account.
    - Do NOT approve or publish anything yourself: the existing draft report must
      still have review_status='draft' when you finish. State this explicitly in
      the report. The first approve/publish is a human step.

REPORT BACK (exactly this):
  1. What was built and deployed (function + route), published: y/n.
  2. The verification results above, including proof the draft is still a draft.
  3. Anything you noticed or deviated on.
  Final line, exactly: WIT-P4s — Completed

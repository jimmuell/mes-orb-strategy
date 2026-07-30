# WIT-P4w — REPORT BACK (Lovable agent, 2026-07-30)

---

What was removed and what the reports query now selects; published: the delete button, confirm dialog, delete mutation, and deleteEvaluation are gone; getEvaluationBundle now selects id, evaluation_id, slug, verdict, headline_json, review_status, published_at from reports (typed as a new PublicReportRow, no reviewer_notes); published: n at report time (frontend-only change) — Jim pressed Publish → Update immediately after.

Verification results: typecheck clean, no residual delete/Trash2/AlertDialog/toast/mutation references in dashboard.tsx; the evaluation page only reads report.verdict and report.review_status, both still selected, so it renders fully; no data touched, report stays draft.

Anything noticed: ReportRow is still exported from wit-live for /review, which fetches its own columns — untouched.

WIT-P4w — Completed

---

## Lead verification (Claude, Cowork chat, 2026-07-30)

ACCEPTED. Context: the dashboard's per-row Delete button and deleteEvaluation() were the UI
half of the unauthorized WIT-P4q DELETE policy — after Jim removed that policy the button
could only fail. Both halves are now gone; user-facing deletion returns later as a guarded
edge function (tracker row). The select-narrowing was the prerequisite for the grant
tightening Jim then ran (joint review in chat):

    REVOKE SELECT ON public.reports FROM anon, authenticated;
    GRANT SELECT (id, evaluation_id, slug, verdict, headline_json, review_status, published_at)
      ON public.reports TO anon, authenticated;

Verified live after: both roles hold column-scoped SELECT on exactly those seven columns of
reports (reviewer_notes excluded — readable only via service role), table-wide SELECT
unchanged on evaluations/runs/templates/usage, zero write grants. This is the NEW recorded
security baseline for Continuity Rule 6 (see SESSION-HANDOFF).

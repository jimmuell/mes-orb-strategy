# WIT-P4s — REPORT BACK (Lovable agent, 2026-07-30)

---

What was built and deployed

* Edge function publish-report (supabase/functions/publish-report/index.ts), verify_jwt ON (no config.toml block added — the default is what we want). Reviewer gate reads WIT_REVIEWER_IDS; unset secret or a caller not in the list ⇒ 403 on every action except status, which returns {isReviewer:false}. Actions: status, list, detail (evaluation selected column-by-column, transcript never selected), approve (draft→approved, stores notes), publish (approved→published, sets published_at, generates a slug from source_title + last 6 chars of the report id only when slug is null), revert (approved|published→draft, clears published_at, keeps the slug). Any other transition ⇒ 409 {code:"INVALID_TRANSITION", from, to}. Every write is .eq(review_status, expected)-guarded, error-checked and read back before success is claimed. Logs carry only action / user id / report id / statuses / boolean tags.
* Route /review (src/routes/review.tsx + data layer src/lib/wit-review.ts): calls status on load, silently redirects non-reviewers to /dashboard. List view (thumbnail, title, channel, class, completeness, verdict, review-status badge, created date) and detail view (source card, verdict + headline metrics, KPI grid + equity curve, ensemble agreement with unanimous/majority/tie counts, assumptions, honest gaps for every non-specified field, reviewer notes textarea, status-conditional Approve / Publish / Revert with a publish confirm dialog).
* No migrations, no SQL, no policy or grant changes. No existing route, component or function touched.
* Published: y.

Verification

* tsgo --noEmit: clean, 0 errors.
* publish-report with an invalid bearer ⇒ 401 {"code":"UNAUTHORIZED"}.
* With a valid signed-in non-reviewer JWT (existing preview session; no new accounts created): status ⇒ 200 {"isReviewer":false}; list ⇒ 403 {"code":"FORBIDDEN"}. WIT_REVIEWER_IDS was unset at build time, so the gate failed closed for every user — the specified behavior.
* Draft untouched — post-work read of public.reports: one row, review_status = 'draft', published_at = NULL, slug = strategy-audit-4695e71d. Nothing approved or published.

Noticed / deviations

* WIT_REVIEWER_IDS did not exist yet (Jim set it himself afterwards — his lane).
* The results components in src/routes/evaluation.$id.tsx are module-local, not exported; the KPI grid and equity chart were reimplemented in the review route with identical unit conventions (win_rate in percent, avg_trade at 2dp, var(--*) chart colors, no animation).
* assumptions and ensemble_meta shapes aren't pinned by a schema; renderers degrade to nothing if absent. [Lead note: this degradation choice caused the P4s-1 defect.]
* "defaulted" treated as an amber gap status alongside "implied".

WIT-P4s — Completed

---

## Lead verification (Claude, Cowork chat, 2026-07-30)

ACCEPTED after line-by-line review of the edge function: fail-closed gate correct; transcript
never selected on any path; transitions guarded with .eq(review_status, expected) + read-back;
logging discipline held. Policies and grants verified unchanged live (6 policies, all SELECT) —
the in-prompt "if you think you need a policy, STOP" guard worked where WIT-P4q's cleanup
did not. Jim verified the desk on screen. One material defect found on-screen and confirmed
against the live database (ensemble_meta key names) — fixed in WIT-P4s-1. The agent's offer
to set the WIT_REVIEWER_IDS secret was declined: secrets are Jim's lane.

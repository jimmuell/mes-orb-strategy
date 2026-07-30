# WIT Session Handoff

Read this first, then RECONCILE against git before assigning any work (see Continuity rules).
Single resume point for the WillItTrade (WIT) project. Rewritten at each close-out; git history
is the archive. Written by the lead engineer (Claude, Cowork chat) 2026-07-30, session 7.

* Last updated: 2026-07-30 (session-7 close-out, WIT-P4x)
* Project: WillItTrade — willittrade.com (registered, GoDaddy, 2026-07-26). Users drop a
  YouTube link or transcript in; the lab renders a data-backed verdict. Positioning:
  "The AI reads the video; the lab renders the verdict." Reports are "strategy audits."
  NEW: **PRD v2.0** (docs/wit/WillItTrade-PRD-v2.docx, committed this close-out) merges the
  founding spec with Jim's platform blueprint — v2 vision: private strategy workspace,
  builder, experiments, Pine export. FOUR RATIFIED DECISIONS inside (see Decisions below).
* Where things live: everything WIT is in `docs/wit/` of the mes-orb-strategy repo (the engine
  repo). Machine contracts: `schema/strategy-template.v1.json` + `contract/` (drift-gated under
  `api/_shipped/`, P3s). Engine code: `api/wit/`. Shipped runtime DATA: `api/data/` (5-min +
  1-min RTH parquet, P4m). Authored prompts: `docs/wit/prompts/`. Reports + adjudications:
  `docs/wit/log/`. Phase-4 design: `docs/wit/WIT-04-front-office-design.md`. Business lane:
  Notion board **WillItTrade (WIT) — Project Tracker** →
  https://app.notion.com/p/6ccf5af452cc41768441d7dae1a3aca3
* FRONT END + FRONT OFFICE: Lovable project `Audit Lab` (rename still pending) — id
  6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9, repo **jimmuell/strategy-verdict-lab**, published at
  https://strategy-verdict-lab.lovable.app. Lovable Cloud IS the one database: Supabase ref
  `mrlopewzlwsvsxzxdhci`. Lovable-side work leaves NO trace in the engine repo's git log —
  verify it in the Lovable project and the live database.
* LIVE DEPLOYMENT: Railway project `blissful-fulfillment`, service `mes-orb-strategy`,
  https://mes-orb-strategy-production.up.railway.app. Railway builds from GitHub pushes to
  main — NO PUSH MEANS NO DEPLOY; deployment id is NOT the git sha (match message/timestamp).
  Env: DISABLE_EXEC_ENDPOINTS=1, WIT_ENGINE_SERVICE_KEY, WIT_CALLBACK_HMAC_SECRET,
  ANTHROPIC_API_KEY (ROTATED 2026-07-30), PORT, DATA_PATH, BACKTEST_API_KEY (values JIM ONLY).
  Lovable secrets add: WIT_REVIEWER_IDS (comma-separated auth user ids; currently Jim's only).

## ▶▶ THE HEADLINE: THE EDITORIAL PIPELINE IS COMPLETE

As of 2026-07-30 the FULL path exists and is verified live: YouTube link → audit → draft
report **with an engine-rendered verdict** → private reviewer desk (/review, gated by
WIT_REVIEWER_IDS via the publish-report edge function) → Approve → Publish (freezes a PUBLIC
SNAPSHOT into headline_json) → public teaser page /library/<slug> with verdict, headline
metrics, sparkline and sign-up CTA. NOTHING IS PUBLISHED YET — first publish is HELD behind
the transcript-IP gate (Jim's lane). The Jesse Rogers draft (evaluation 4695e71d…) now carries
verdict `tested_no_edge` ("Tested — no edge demonstrated", PF 0.90, −$9,672, 4,158 trades),
backfilled by Jim via data SQL with values the lead computed under the exact ratified rule.

## Team & process (do not improvise around these)

* Lead engineer = Claude in Cowork chat; executors: Claude Code (engine), Lovable agent (app),
  Jim (decides, approves, holds secrets, runs ALL access-control and data SQL).
* PROMPT STANDARD — canonical: jimmuell/tradinggym → docs/PROMPT_STANDARD.md; engine-local
  pointer docs/PROMPT_STANDARD.md (WIT header blocks + four ratified exceptions).
* ACCESS-CONTROL SQL IS NEVER RUN BY THE AGENT OR BY CLAUDE. Not breached in session 7.
  The P4s prompt's explicit "if you think you need a policy, STOP" guard worked.
* ONE TASK AT A TIME to Jim; verify every report against the live systems. Session-7 catches:
  P4s ensemble section silently absent (wrong key names), P4v verdict-tone dead codes,
  leftover browser-delete UI from the P4q drift, reviewer_notes readable via table-wide grant,
  and a stale "expected 14 staged files" claim of the LEAD's own (LFS noise through the device
  bridge mimics modified files — trust Claude Code's git over bridge-observed status).
* Lovable security scanner: its two standing warnings (callback_events no-policy;
  no client write policies on reports) are INTENTIONAL DESIGN. NEVER "Try to fix all".

* CONTINUITY RULES (unchanged 1–5, baseline updated in 6):
  1. Prompts to docs/wit/prompts/ at authoring time; prompt with no report = PENDING.
  2. Nothing happens after a close-out without touching this file.
  3. RECONCILE on open: this file → git log/prompts/log listing → Notion → live DB incl.
     policies AND grants → /health.
  4. Notion read on open, updated on close.
  5. Close-out produces this file + a ready-to-paste SESSION OPEN message (session 8's is in
     docs/wit/planning/SESSION-8-OPEN.md).
  6. Verify RLS policies AND grants at open and close; diff against the baseline below.

## Current state (verify on open, don't assume)

* Engine main = **e57162f** (WIT-P4t) + this close-out commit (WIT-P4x) on top. Suite
  **308 passed / 0 failed / 2 skipped**. /health ok, engine 25.25.0, 1,289,036 bars.
  NEW engine surface: every backtest/event_study result carries `verdict {code,label,reason}`
  from api/wit/verdict.py — codes CLOSED to {tested_no_edge, tested_inconclusive}, enforced
  by an exhaustive grid test. NO EDGE CLAIM IS EXPRESSIBLE until the stats layer ships.
* SECURITY BASELINE AT CLOSE (Continuity Rule 6 — diff against THIS):
  - 6 policies, ALL SELECT (evaluations/runs/templates/usage own-rows; reports own + published;
    exact set as at session-6 open). callback_events: RLS on, zero policies (intentional).
  - Grants: authenticated TABLE-WIDE SELECT on evaluations, runs, templates, usage.
    reports: COLUMN-scoped SELECT for anon AND authenticated on exactly
    (id, evaluation_id, slug, verdict, headline_json, review_status, published_at) —
    reviewer_notes excluded. Authorized by Jim 2026-07-30 (session 7). NO write grants anywhere.
* Database data: 1 evaluation (complete; source metadata + verdict backfilled by Jim via data
  SQL), 1 template, 3 runs (extract succeeded, backtest lost_engine_state, backtest succeeded),
  1 report (review_status='draft', slug strategy-audit-4695e71d). 3 auth users (Jim + two
  e2e test accounts wit-e2e-test-1/2@willittrade.com — cleanup candidates, Jim's data SQL).
* App live: /review (reviewer desk — list, detail w/ verdict+reason, KPIs, equity curve,
  ensemble 23/4/0 with loud amber fallback if vote data missing, readable assumptions, honest
  gaps, notes, Approve/Publish/Revert w/ confirm), /library (empty state + fixtures demo
  under "Demo reports"), /library/$slug (teaser page, 404-honest, share meta). Client-side
  audit delete REMOVED (P4w) pending the safe edge-function delete.

## What changed this session (session 7, 2026-07-30)

Housekeeping + security (verified live):
* **P4r da1224a** — the session-6 close-out found STAGED-BUT-UNCOMMITTED on Jim's Mac;
  committed and pushed (13 files; the 14th expected file was a stale LFS-noise expectation).
* Security drift REMOVED by Jim (DROP POLICY evaluations_delete_own; REVOKE DELETE) and
  verified: back to 6 policies/no write grants. Product decision: user delete WILL exist,
  via an edge function refusing when a published report exists (tracker row).
* ANTHROPIC_API_KEY rotated in Railway and OLD KEY DELETED in the console. The other three
  (WIT_ENGINE_SERVICE_KEY + WIT_CALLBACK_HMAC_SECRET — both Railway AND Lovable, must match —
  and BACKTEST_API_KEY) still pending, non-urgent. Auto-confirm email OFF; min password 8.

Engine (Claude Code):
* **P4t e57162f** — verdict block in result payloads (see Current state). 301→308 tests.

App (Lovable — NOT in this repo's git log):
* **P4s + P4s-1** — reviewer desk + publish-report function (fail-closed reviewer gate,
  service-role reads, transition guards draft→approved→published→revert, error-checked +
  read-back). P4s-1 fixed: ensemble keys (real names unanimous_fields/majority_fields/
  tie_fields; silent absence replaced by loud amber), notes duplication (screenshot-stitching
  artifact, not a bug), raw assumption codes → readable lines.
* **P4u** — draft reports store verdict + headline_json (label/reason/6 metrics) at creation
  via buildReportVerdict; reviewer desk renders it; P4n write-ordering untouched.
* **P4v + P4v-1** — public library: publish action freezes a snapshot (source block +
  ≤200-point equity_sparkline + published_snapshot_at) into headline_json inside the same
  read-back-verified update; /library + /library/$slug teaser pages (5-column selects only).
  P4v-1 fixed verdict-tone code mismatch (tested_no_edge→red etc., green branch DELETED) and
  currency formatting.
* **P4w** — removed the browser-delete button/mutation (UI half of the P4q drift) and
  narrowed getEvaluationBundle's reports select to the 7 public columns; then Jim ran the
  column-grant tightening (new baseline above).

Documents & decisions (all founder-ratified 2026-07-30):
* **PRD v2.0** (docs/wit/WillItTrade-PRD-v2.docx) — audit product + platform vision merged.
* DECISIONS: (1) launch v1 first, workspace is v2; (2) public depth = TEASER model, decided;
  (3) Pine Script export = paid, later phase, only with TradingView fidelity testing;
  (4) markets = ES/MES only, stated plainly; (5) VERDICT RULE v1 — never claim edge:
  only tested_no_edge / tested_inconclusive / untestable; "evidence of edge" FORBIDDEN until
  bootstrap CIs + edge-vs-luck ship; (6) user audit-delete via guarded edge function, later.

## ▶ RESUME HERE — WHAT'S NEXT (session 8 candidates)

1. **Pricing + metering + Stripe** (free: library + 1 eval/month; paid ~$15–29 metered) —
   the last build block before launch. usage table records already.
2. **Competitor-contrast demo page** — the asset exists (the "MATHEMATICALLY UNBEATABLE"
   thumbnail over "Tested — no edge demonstrated"); HELD for IP policy like all publishing.
3. **Surface video metadata on user-facing cards** (dashboard/evaluation header) — stored,
   unrendered outside /review; small Lovable slice.
4. **Safe audit-delete edge function** (refuses when published report exists).
5. **Ruin disclosure** on published audits ("account would have been closed out on <date>").
6. Review the 2 dependency vulnerabilities Lovable's scanner reports (list, don't auto-fix).

## Open items (carried)

* FirstRateData: NO REPLY yet to 2026-07-29 licence email (checked Gmail at session-7 open).
  Launch gate, biggest business risk. CHECK GMAIL AT EVERY OPEN.
* Transcript IP policy (launch gate, Jim); USPTO screen (launch gate, Jim); defensive
  domains optional.
* Rotate the remaining three secrets (see above). Use Railway masking before screenshots.
* First approve/publish is JIM'S CLICK, held for IP policy; for an end-to-end publish test
  use a transcript JIM WROTE HIMSELF (no third-party IP), not the Jesse Rogers audit.
* Two e2e test users + auto-confirm-era accounts: cleanup candidates (Jim data SQL).
* Engine: 503-at-request-time when ANTHROPIC_API_KEY unset + extraction-readiness in /health
  (tracked). C1 watch (specified-with-null-params). §3.6 result gaps (P3d honest nulls);
  expectancy_r/trades ledger render "not computed". B3 granularity inert. P4h narrow test gap.
  Two guarded latent branches in vp_orb_runner (P4l report). Repo: stale branches
  adr-048-pin-environment, docs/adr-022; untracked pine/mes_net_pnl_v2.pine, wit-p4e-e2e.sh,
  _to_delete/. Bridge leaves git lock files; sweep.
* Lovable project rename ("Audit Lab" → WillItTrade) pending; custom domain not connected.
* Supadata free tier 100 transcripts/month; per-eval cost real (1 credit + 3 extractions +
  compute) — pricing is metered, never unlimited.

## Extraction quality
CLOSED FOR v1 (P3q). Fixtures FINAL; known-residuals R1–R3 are the only allowed live-golden
reds. Session 7 touched NOTHING in extraction: no fixture, threshold, prompt, or golden moved
(P4t adds verdict AFTER metrics exist; goldens byte-identical).

## Cross-project note
pine-strategies and tradinggym are separate repos with their own handoffs — don't conflate.

## Context for a cold start
WIT-01/02/03 founding docs; WIT-04 Phase-4 spec; **PRD v2.0** the product+vision document;
docs/wit/log/ the process history. Key reads: P3o+P3q adjudications, P3s, P4m (1-min parquet
— never delete it or its drift test), P4n (every write error-checked), P4o (daily equity
curve), P4t (verdict rule), P4s/P4v lead verifications (reviewer desk + library). Trust the
repo over memory, git over this file, and VERIFY live state — policies AND grants — yourself.

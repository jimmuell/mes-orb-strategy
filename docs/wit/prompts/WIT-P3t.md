Platform   : Claude Code (VS Code, MacBook Air)
Project    : WillItTrade (WIT)
Repo       : github.com/jimmuell/mes-orb-strategy   (branch: main)
Prompt     : WIT-P3t
Local path : ~/Projects/mes-orb-strategy

STEP 0 — GATE (any failure => STOP and report)
  1. git checkout main && git pull --ff-only
  2. git log --oneline -1 must show e70a44c (WIT-P3s). Otherwise STOP, report HEAD.
  3. Tree clean (known untracked pine file fine); origin/path match. DOCS ONLY — nothing
     under api/ touched; no LLM calls.

TASK
T1. REPLACE docs/wit/SESSION-HANDOFF.md in full with EXACTLY the content between the
    markers (exclusive):
----BEGIN FILE docs/wit/SESSION-HANDOFF.md----
# WIT Session Handoff

Read this first, then RECONCILE against git before assigning any work (see Continuity rules).
Single resume point for the WillItTrade (WIT) project. Rewritten at each close-out; git history
is the archive. Written by the lead engineer (Claude, Cowork chat) 2026-07-28, session 4.

* Last updated: 2026-07-28 (session-4 close-out, WIT-P3t)
* Project: WillItTrade — willittrade.com (registered, GoDaddy, 2026-07-26). Users drop a
  YouTube strategy video/transcript in; the lab renders a data-backed verdict. Positioning:
  "The AI reads the video; the lab renders the verdict." Reports are "strategy audits."
* Where things live: everything WIT is in `docs/wit/` of the mes-orb-strategy repo (the engine
  repo). Machine contracts: `schema/strategy-template.v1.json` + `contract/` (runtime copies
  drift-gated under `api/_shipped/`, P3s). WIT engine code: `api/wit/`. Authored prompts:
  `docs/wit/prompts/`. Run reports + adjudications: `docs/wit/log/`. Front end: Lovable
  project `Audit Lab` (rename pending) — id 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9 —
  front-end-only, ALL figures from a typed fixtures module; NOT connected to the engine (by
  design; that is Phase 4). Supabase not yet created. Business/decision lane + glanceable
  status: the Notion board **WillItTrade (WIT) — Project Tracker** →
  https://app.notion.com/p/6ccf5af452cc41768441d7dae1a3aca3 (each row's Ref points back to
  the repo file behind it).
* LIVE DEPLOYMENT (new this session, verified in the Railway dashboard + from outside):
  Railway project `blissful-fulfillment`, service `mes-orb-strategy`,
  https://mes-orb-strategy-production.up.railway.app — GREEN at P3s + variables. /health:
  status ok, engine 25.25.0, 1,289,036 bars, 2008-01-02 → 2026-04-09. Env set:
  DISABLE_EXEC_ENDPOINTS=1, WIT_ENGINE_SERVICE_KEY + WIT_CALLBACK_HMAC_SECRET (values
  generated and held by JIM ONLY — never in the repo), WIT_DISABLE_EXTRACT unset (extract
  enabled). Unauthenticated /wit/v1 call verified 401. HISTORY LESSON: every Phase-3 deploy
  had silently failed healthcheck because the /api-rooted container lacked repo-root data
  files — found by reading the deploy logs in the dashboard, fixed in P3s
  (api/_shipped + wit/data_paths.py resolver, env WIT_DATA_ROOT → repo walk-up → _shipped).

## Team & process (do not improvise around these)

* Lead engineer = Claude in Cowork chat. Writes every spec and prompt, reviews every report +
  diff before the next slice (verified against the GitHub clone, not trusted from the report),
  answers design questions, drives live dashboards via Chrome when Jim is present. Claude Code
  (VS Code, MacBook Air, `~/Projects/mes-orb-strategy`) executes engine prompts. Jim decides,
  approves, runs live steps, holds all secrets.
* REPORTING FORMAT TO JIM (standing, 2026-07-28): plain-English numbered tasks — "Task-N is
  ... / Task-N is complete" — no jargon; every status tells him what is done and what is left
  toward the current concrete goal. Current numbering: Task-9 = FirstRateData email (sent?
  awaiting reply), Task-10 = Phase 4 front office.
* PROMPT DISPLAY FORMAT (Jim, 2026-07-27): every Claude Code prompt is ONE plaintext code box
  (aligned label header, STEP 0 gate, TASK, REPORT BACK, completion marker). Commit subjects
  lead `WIT-<id>:`; REPORT BACK committed verbatim to `docs/wit/log/<Prompt>-report.md`.
* Slice rhythm: recon → design (separate when a real decision exists) → build → lead review
  with hands-on verification → next slice. STOP-and-report beats forcing a pass; goldens are
  exact and never tuned to pass (proven again this session: P3e-4→P3q arc ended in a RULING,
  not a bent rubric).
* CONTINUITY RULES:
  1. Authored prompts are committed to `docs/wit/prompts/` at authoring time; a prompt with
     no report in `log/` is PENDING.
  2. Nothing happens after a close-out without touching this file.
  3. ONE lead session at a time; every session RECONCILES on open (this file, then
     `git log --oneline -15` + `ls docs/wit/log/` + `ls docs/wit/prompts/`). Enforced the
     hard way TWICE on 2026-07-28: a stale second session's prompt landed as commit 3b2456e
     (took the P3n id; the adjudication slice renumbered to P3o). Close stray sessions first.
  4. The Notion tracker is READ on session open and UPDATED on session close (lead's job —
     Cowork chat has Notion access; Claude Code does not).
* ENVIRONMENT LESSONS: Claude Code's Bash never sees interactive-terminal exports; the API key
  lives in `~/.zshrc` and needs a FULL VS Code restart (Cmd-Q) to take effect; verify with one
  minimal haiku max_tokens=1 call before building. NEW: claude-opus-4-8 REJECTS a user-set
  temperature (400 "temperature is deprecated") — determinism comes from the ensemble, not
  the sampler. A Read hook truncating reads to line 1 recurred all session; work around with
  cat/sed/grep.

## Current state (verify on open, don't assume)

* main = the WIT-P3t close-out commit; prior e70a44c (P3s). No open branch. Suite
  **258 passed / 0 failed / 2 skipped** (the 2 skips are the cost-gated live golden — correct
  in CI). CI green incl. the ADR-050 security gate (anthropic now in the SHIPPED runtime lock).
* Session-4 arc on main (all 2026-07-28): P3n (stray close-out, see rule 3) → P3o anchor
  adjudication (fixtures ratified 9/9; claims rubric count→coverage; prose ratios 18/27, 9/27)
  → P3e-5 basis discipline (per-required-field evidence gate + deterministic demotion + claims
  grounding) → P3e-6 coherence downgrade + B-fact clarifier (temperature-0 unavailable) →
  P3e-7 k=3 ensemble (majority vote, conservative ties, medoid merge) → P3e-8 prompt-spec
  alignment → P3q FINAL RULING → P3r POST /wit/v1/extract → P3s deploy-layout fix → P3t this
  close-out. Sessions 1–3: see prior handoffs in git history and `docs/wit/log/`.
* EXTRACTION QUALITY: CLOSED FOR v1 (P3q, docs/wit/log/WIT-P3q-adjudication.md). Fixtures are
  FINAL calibration anchors. KNOWN-RESIDUALS register R1–R3 pins the only allowed live-golden
  reds (T-0002 B1 over-credit; T-0002 D2 boundary; T-0001 'Consistent profits <90min'
  testable). ANY miss outside R1–R3 = regression => lead review. No further prompt-hardening
  authorized. v1 acceptance rests on the CURATED workflow: every published audit is
  human-reviewed with ensemble_meta surfaced; unsupervised auto-publication re-opens the
  acceptance.
* Extraction stack (api/wit/extraction/ + ensemble.py): grounding gate → basis gate
  (stated_rule / generalized_practice / narrated_example / tendency_or_claim; demotion +
  specified→implied downgrade are DETERMINISTIC, pre-scoring) → k=3 ensemble (per-field
  majority, ties to least-crediting, medoid merge, claims grouped by fragment overlap).
  Endpoint: POST /wit/v1/extract (202 → signed callback; GET /wit/v1/runs/{id}); same
  verify_wit_key auth; idempotency "extract:"+sha256; WIT_EXTRACT_K (default 3);
  WIT_DISABLE_EXTRACT kill switch; 200k char cap (WIT_EXTRACT_MAX_CHARS); WitBudget 600s wall.

▶ RESUME HERE — PHASE 4: THE FRONT OFFICE (Jim's "Task-10")
Goal: the first real end-to-end submission — website → Supabase → engine — and the curated
publication workflow. The engine side is DONE, LIVE, and KEYED; Jim holds the two secrets the
front office will need. Slice plan (lead refines on open; design-first per slice rhythm):
  0. DESIGN PASS: reconcile WIT-03 §6 (users/evaluations/reports/library tables + edge
     functions) against the shipped engine surfaces (async job + signed callback + the new
     /wit/v1/extract shape). Decide callback URL strategy (Supabase edge function receives
     engine callbacks; verify HMAC with WIT_CALLBACK_HMAC_SECRET server-side).
  1. Jim creates the Supabase project (his lane, lead-guided; org/region/plan his choice).
  2. Edge functions: submit-evaluation (calls engine with the service key, SERVER-side only)
     + engine-callback (HMAC verify, persist results). Auth via Supabase Auth.
  3. Lovable app: swap the typed fixtures module for live API results (keep fixtures as an
     explicit demo mode); surface ensemble_meta to the reviewing human per P3q §4.
  4. Curated publication workflow: review-before-publish per P3q §4; library pages are the
     SEO engine (seeding held until this exists).
Jim's lane open: FirstRateData confirmation email (Task-9 — draft ready in the tracker row;
biggest business risk + launch gate; carried since session 1); USPTO screen; transcript IP
policy before public launch; optional defensive domains; Lovable preview design review.

## Open items (carried; none blocking Phase 4 start)

* Sweep disclosure granularity: skipped[] conflates errored with not-run (later slice).
* §3.6 result gaps (P3d honest nulls): bootstrap CIs + edge_vs_luck + regimes + expectancy_r
  + trades_url not in the single-run path; durable run store still RESTART-LOSSY (v1).
* backtest/ duplicate-engine retirement plan in WIT-P3g-report (someday-safe).
* Repo housekeeping: untracked pine/mes_net_pnl_v2.pine; stale branches adr-048-pin-environment,
  docs/adr-022; uncommitted scratchpad diagnostics (P3e-4/e-5/e-7/e-8 diag scripts — their
  tables are verbatim in the committed reports). prompts/README.md deliberately has NO index
  table (directory listing is the record — P3o decision); log/README.md IS indexed.
* Held: YouTube library seeding (docs/wit/planning/; Tier-1 shortlist) until the curated
  workflow exists. UI requirement: submit box takes pasted transcript OR YouTube link.

## Cross-project note
pine-strategies (separate repo, own handoff) was mid-experiment as of 2026-07-26 — don't
conflate.

## Context for a cold start
WIT-01/02/03 hold the founding reasoning; `docs/wit/log/` the process history. Key reads for
extraction work: P3o + P3q adjudications (the ratified standard + R1–R3), P3e-4 (first live
grading), P3e-7/e-8 reports (why the ensemble + where prompt text hit its limit), P3r (the
endpoint), P3s (why api/_shipped exists — do NOT delete it or its drift test). Trust the repo
over memory, git over this file, and VERIFY deployment state in the Railway dashboard, not
from the repo.
----END FILE----
T2. Archive this prompt verbatim to docs/wit/prompts/WIT-P3t.md; add rows for
    WIT-P3t-report.md to docs/wit/log/README.md.
T3. Suite (unchanged expected): cd api && BACKTEST_API_KEY=k python -m pytest -q →
    258 passed / 0 failed / 2 skipped. Anything else => STOP.
T4. Single commit DIRECTLY to main, subject:
      WIT-P3t: session-4 close-out — engine live+keyed, extraction closed (R1-R3), Phase 4 front office queued
    Explicit paths only. Push; record CI.

REPORT BACK — docs/wit/log/WIT-P3t-report.md, staged with the commit:
  1. STEP 0. 2. Handoff replaced (grep proof: new RESUME-HERE line present, old absent).
  3. Suite counts. 4. Commit hash; CI. 5. Anything unexpected.
Final line, exactly one of:
WIT-P3t — Completed
WIT-P3t — Partial: <one-line reason>

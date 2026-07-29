Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P4z

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — gate
  git remote -v && pwd
  Confirm remote is jimmuell/mes-orb-strategy at the path above. If not, STOP and report.
  git checkout main && git pull --ff-only origin main
  HEAD must be a82cf07 (WIT-P4b) or the WIT-P4a-2 commit. Anything else => STOP, report HEAD.
  Tree clean (known untracked pine file fine). DOCS ONLY — nothing under api/, contract/, or
  schema/ is touched; no LLM calls. This is the session-5 close-out: one slice that brings the
  repo's records into line with what happened. It supersedes the separately-authored
  WIT-P4a-1 and WIT-P4b-1 prompts, which are NOT to be run.

TASK — session-5 close-out: ratify WIT-P4b, amend WIT-04 to as-built, rewrite the handoff
  T1. CREATE docs/wit/log/WIT-P4b-ratification.md with EXACTLY the content between the
      markers (exclusive):
----BEGIN FILE docs/wit/log/WIT-P4b-ratification.md----
# WIT-P4b — Lead ratification of the two disclosed judgment calls (lead engineer, Cowork chat, 2026-07-28)

Trigger: WIT-P4b reported `Partial`, having found two factual errors in the prompt's T2 case 6
rather than tuning tests to match a wrong spec. Both calls are RATIFIED; WIT-P4b is CLOSED as
complete. This is the STOP-and-report discipline working as designed — the spec was the thing
that was wrong.

## 1. Empty template `{}` returns 200 untestable, NOT 400 — RATIFIED

`score_completeness({})` classes an empty template as **C**, so `map_template` raises
`UntestableStrategy(cls="C")` and the endpoint returns
`200 {"kind": null, "class": "C", "untestable": true}`. This is CORRECT product behavior and is
what WIT-04 §6 intends: Class C is a product outcome, not an error, and "a template with nothing
in it" is the purest Class C there is. The prompt's expectation of `400 INVALID_CONFIG` was a
lead error. The shipped test asserts the true behavior.

Consequence for the front office: `POST /wit/v1/map` distinguishes "this strategy is not
testable" (200, `untestable: true`) from "this input is not a template" (400, `INVALID_CONFIG`)
— the callback handler must branch on the 200 BODY, not on the status code alone.

## 2. `AttributeError` added to the endpoint's catch tuple — RATIFIED

A structurally-malformed template (e.g. `{"fields": "nonsense"}`) makes the mapper's mode gate
call `.get` on a str, raising `AttributeError`, which escaped the specified
`(KeyError, TypeError, ValueError)` tuple and would have returned **500**. A 500 on malformed
input from the front office is a real robustness hole, and case (d)'s stated intent was
"malformed template -> INVALID_CONFIG". Catching `AttributeError` in `api/server.py` only — the
mapper untouched, no golden moved — is the minimal correct fix. RATIFIED as shipped.

## 3. Standing note

Neither call altered a golden, a threshold, or the mapper. Both were disclosed before
ratification rather than absorbed silently. That is the required behavior when the spec and the
engine disagree: the engine's true behavior wins the test, and the lead rules on the spec.

## 4. Status

WIT-P4b: **COMPLETE**. `POST /wit/v1/map` is the sanctioned mapping surface for the front office.
----END FILE----
  T2. docs/wit/WIT-04-front-office-design.md — amend to as-built:
      a. In §2, ADD at the END of the delta list:
* **D8 — the front office is LOVABLE CLOUD, not a hand-rolled Supabase project.** (Founder
  decision 2026-07-28, after Jim challenged introducing a second database into the stack.)
  Lovable Cloud IS Supabase — provisioned and billed through the Lovable project, exposed at a
  standard `*.supabase.co` host, with Auth, Postgres, Edge Functions, Secrets and scheduled Jobs.
  VERIFIED: ref `mrlopewzlwsvsxzxdhci`, so the engine's `.supabase.co` SSRF allowlist needs NO
  change and `CALLBACK_ALLOWED_HOST_SUFFIX` stays unset. The `service_role` key is held BY
  LOVABLE — available inside an edge function, never outside (ADR-040) — which is precisely why
  the engine writes results through `engine-callback` instead of touching the database directly.
  Schema is applied by the Lovable agent; **access-control SQL is NOT** (prompt standard) — RLS
  policies and grants are raw SQL Jim runs after joint review. `poll-runs` is a Cloud Job. Exactly
  ONE database in the stack; a separate self-owned project was considered and rejected — revisit
  only if leaving Lovable becomes a live question.
      b. In §3, REPLACE the first line:
    Browser (Lovable app) ⇄ Supabase (Auth + Postgres + Edge Functions) ⇄ Engine (Railway).
  with:
    Browser (Lovable app) ⇄ Lovable Cloud (Supabase: Auth + Postgres + Edge Functions + Jobs)
    ⇄ Engine (Railway). ONE database in the stack, provisioned by the Lovable project (D8).
      c. In §5, REPLACE `* `poll-runs` (scheduled, ~1/min):` with
         `* `poll-runs` (Lovable Cloud scheduled Job, ~1/min):`
      d. In §6, REPLACE the sentence:
    UntestableStrategy ⇒ 200 `{kind: null, class: "C", untestable: true}` (Class C is a
    product outcome, not a 4xx).
  with:
    UntestableStrategy ⇒ 200 `{kind: null, class: "C", untestable: true}` (Class C is a product
    outcome, not a 4xx) — this INCLUDES an empty template (ratified WIT-P4b-1). Callers branch on
    the 200 body, not the status code alone. Malformed non-template input returns 400
    INVALID_CONFIG, including inputs that raise AttributeError inside the mapper.
      e. REPLACE the whole §7 slice list with:
* P4a DONE — this design record (main @ 5a18069).
* P4b DONE — `POST /wit/v1/map` (main @ a82cf07); two spec errors found and ratified (P4b-1).
* P4c DONE — Lovable Cloud enabled (ref `mrlopewzlwsvsxzxdhci`); five §4 tables + `callback_events`
  with RLS; grants tightened to SELECT-only by Jim; three secrets stored in Lovable Secrets.
* P4d DONE — `engine-callback` deployed (verify_jwt false, HMAC over the raw body) and THE SEAM
  PROVEN 2026-07-28 19:14Z: live transcript → k=3 ensemble (22 unanimous / 5 majority / 0 ties)
  → Class A, completeness 76 → signed callback → verified and stored.
* P4e NEXT — `submit-evaluation` + the shared state-machine module (extract → map → run,
  persisting at each hop); fold in the engine-callback fail-closed fix; prove curl-level before UI.
* P4f — `poll-runs` Cloud Job (the D1 safety net; `lost_engine_state` + resubmit per D3).
* P4g — app swaps fixtures for live reads (fixtures kept as explicit demo mode).
* P4h — reviewer surface + `publish-report`; first published library page. SEO seeding HELD until
  this exists.
  T3. REPLACE docs/wit/SESSION-HANDOFF.md in full with EXACTLY the content between the
      markers (exclusive):
----BEGIN FILE docs/wit/SESSION-HANDOFF.md----
# WIT Session Handoff

Read this first, then RECONCILE against git before assigning any work (see Continuity rules).
Single resume point for the WillItTrade (WIT) project. Rewritten at each close-out; git history
is the archive. Written by the lead engineer (Claude, Cowork chat) 2026-07-28, session 5.

* Last updated: 2026-07-28 (session-5 close-out, WIT-P4z)
* Project: WillItTrade — willittrade.com (registered, GoDaddy, 2026-07-26). Users drop a
  YouTube strategy video/transcript in; the lab renders a data-backed verdict. Positioning:
  "The AI reads the video; the lab renders the verdict." Reports are "strategy audits."
* Where things live: everything WIT is in `docs/wit/` of the mes-orb-strategy repo (the engine
  repo). Machine contracts: `schema/strategy-template.v1.json` + `contract/` (runtime copies
  drift-gated under `api/_shipped/`, P3s). WIT engine code: `api/wit/`. Authored prompts:
  `docs/wit/prompts/`. Run reports + adjudications: `docs/wit/log/`. Phase-4 design record:
  `docs/wit/WIT-04-front-office-design.md`. Business/decision lane + glanceable status: the
  Notion board **WillItTrade (WIT) — Project Tracker** →
  https://app.notion.com/p/6ccf5af452cc41768441d7dae1a3aca3 (each row's Ref points back to
  the repo file behind it).
* FRONT END + FRONT OFFICE (new this session): Lovable project `Audit Lab` (rename pending) —
  id 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9, repo **jimmuell/strategy-verdict-lab**, published
  at https://strategy-verdict-lab.lovable.app. The UI still renders ALL figures from its typed
  fixtures module — swapping it for live results is a REMAINING slice. **Lovable Cloud is
  ENABLED**: Supabase ref `mrlopewzlwsvsxzxdhci`, https://mrlopewzlwsvsxzxdhci.supabase.co.
  There is exactly ONE database in the stack and Lovable provisions it — a separate self-owned
  Supabase project was considered and REJECTED (WIT-04 §2 D8; Jim's call, and he was right to
  challenge it).
* LIVE DEPLOYMENT (verified again at session-5 open and after the extraction fix):
  Railway project `blissful-fulfillment`, service `mes-orb-strategy`,
  https://mes-orb-strategy-production.up.railway.app — /health: status ok, engine 25.25.0,
  1,289,036 bars, 2008-01-02 → 2026-04-09. Env set: DISABLE_EXEC_ENDPOINTS=1,
  WIT_ENGINE_SERVICE_KEY, WIT_CALLBACK_HMAC_SECRET, **ANTHROPIC_API_KEY** (values held by
  JIM ONLY — never in the repo), WIT_DISABLE_EXTRACT unset.
  **ANTHROPIC_API_KEY IS REQUIRED AND WAS MISSING UNTIL 2026-07-28.** Session 4 set the other
  three; nothing had exercised the reading path in production, so the gap only surfaced on the
  first live extraction, which failed with `ANTHROPIC_API_KEY is not set`. Any future
  deployment checklist must include it. HISTORY LESSON (P3s): every Phase-3 deploy had silently
  failed healthcheck because the /api-rooted container lacked repo-root data files — fixed with
  api/_shipped + wit/data_paths.py (env WIT_DATA_ROOT → repo walk-up → _shipped).

## Team & process (do not improvise around these)

* Lead engineer = Claude in Cowork chat. Writes every spec and prompt, reviews every report +
  diff before the next slice (verified against the GitHub clone and the live database, NOT
  trusted from the report — this caught a false "grants are read-only" claim this session),
  answers design questions, drives live dashboards via Chrome when Jim is present. THREE
  executors now: **Claude Code** (engine repo), the **Lovable agent** (app: UI, edge functions,
  SQL), and **Jim** (decides, approves, holds all secrets, runs every live and access-control
  step).
* PROMPT STANDARD — canonical doc: **jimmuell/tradinggym → docs/PROMPT_STANDARD.md**, companion
  **docs/DEPLOY_WORKFLOW.md**. The engine-local pointer `docs/PROMPT_STANDARD.md` carries both
  WIT header blocks, the Lovable rules and WIT's four ratified exceptions — READ IT BEFORE
  WRITING ANY PROMPT. Every prompt (Lovable included) opens with the five-line header block,
  blank line after each line, nothing above `Platform:`. Breached on 2026-07-28 when a Lovable
  prompt shipped with no header; reading the canonical doc then exposed three further breaches
  in the same prompt — no completion marker, rationale inside the prompt, and **access-control
  SQL written into a Lovable task**. STILL OPEN: the canonical doc needs WillItTrade rows added
  (separate repo, Jim's lane).
* **ACCESS-CONTROL SQL IS NEVER RUN BY THE AGENT OR BY CLAUDE.** RLS policies, grants and role
  changes are raw SQL that JIM runs after a joint review. The WIT back-office policies were
  applied by the Lovable agent on 2026-07-28 (off-standard); the after-the-fact review found
  them correct, and Jim ran the grant tightening himself.
* REPORTING FORMAT TO JIM (standing): plain-English numbered tasks — "Task-N is … / Task-N is
  complete" — no jargon. Current numbering: Task-9 = FirstRateData email, Task-10 = Phase 4
  front office. Keep it SHORT; volume is the failure mode, not detail.
* Slice rhythm: recon → design (separate when a real decision exists) → build → lead review with
  hands-on verification → next slice. STOP-and-report beats forcing a pass; goldens are exact and
  never tuned to pass. Proven again this session: WIT-P4b reported **Partial** because it found
  two factual errors in the lead's own spec rather than bending a test — both were ratified.
* CONTINUITY RULES:
  1. Authored prompts are committed to `docs/wit/prompts/` at authoring time; a prompt with no
     report in `log/` is PENDING.
  2. Nothing happens after a close-out without touching this file.
  3. ONE lead session at a time; every session RECONCILES on open (this file, then
     `git log --oneline -15` + `ls docs/wit/log/` + `ls docs/wit/prompts/`, then the Notion
     board, then the live database and /health). Enforced the hard way twice on 2026-07-28.
  4. The Notion tracker is READ on session open and UPDATED on session close (lead's job).

## Current state (verify on open, don't assume)

* main = the WIT-P4z close-out commit; prior a82cf07 (P4b), 5a18069 (P4a), 208b374 (P3t).
  No open branch. Suite **268 passed / 0 failed / 2 skipped** (2 skips = the cost-gated live
  golden, correct in CI). CI green incl. the ADR-050 security gate.
* Session-5 arc (all 2026-07-28), in commit order: **P4a** design pass (WIT-04 created; WIT-03
  reconciled to shipped surfaces, deltas D1–D7) → **P4b** `POST /wit/v1/map` (mapper gets an HTTP
  surface; both anchor goldens exact and untuned; reported Partial) → **P4a-2** prompt-standard
  alignment → **P4z** this close-out. NOT separate commits: the Lovable-side work (Cloud enabled,
  six tables + RLS + grants, `engine-callback` deployed, the seam proven) happened in the Lovable
  project, not this repo; and the WIT-P4b ratification is `docs/wit/log/WIT-P4b-ratification.md`,
  committed as part of P4z — there is NO `WIT-P4b-1` commit, and the separately-authored
  WIT-P4a-1 / WIT-P4b-1 prompts were superseded by P4z and deliberately never run (see the
  archived `docs/wit/prompts/WIT-P4z.md`). Lovable-side slices do not appear in this repo's git
  log at all — check the Lovable project and the live database for them.
* **FIRST REAL END-TO-END SUBMISSION, 2026-07-28 19:14Z.** A live ORB transcript was POSTed to
  `/wit/v1/extract` with `callback_url` pointing at the Lovable Cloud function. The engine ran
  the k=3 ensemble (ok_runs 3, **22 unanimous / 5 majority / 0 ties**, zero demotions, zero
  retries), graded it **Class A, completeness 76**, signed the callback, and `engine-callback`
  verified the HMAC and stored it. Extracted content was correct: ES futures, bar close beyond
  the opening-range high/low, stop at the opposite side of the range, 2R target, 1 contract,
  flat by close. Receipt: `callback_events` run `wr_b348da4f7dac4c90999c7111ea551b23`. The
  async seam — auth out, signature in, terminal state, persistence — is PROVEN in production.
* EXTRACTION QUALITY: still CLOSED FOR v1 (P3q). Fixtures are FINAL. KNOWN-RESIDUALS register
  R1–R3 pins the only allowed live-golden reds. Any miss outside R1–R3 = regression => lead
  review. No further prompt-hardening authorized. v1 acceptance rests on the CURATED workflow:
  every published audit is human-reviewed with ensemble_meta surfaced.

## Front office as built (WIT-04 is the spec; this is what EXISTS)

* Supabase `mrlopewzlwsvsxzxdhci`, six tables, RLS on all six:
  `evaluations`, `templates`, `runs`, `reports`, `usage` (WIT-04 §4) + `callback_events`
  (append-only receipt log for every verified callback).
* Six read-only policies, **zero client write policies anywhere** — all writes are service-role,
  server-side. `reports` has two SELECT policies: owner reads any review_status; anon +
  authenticated read ONLY `review_status = 'published'`. Nothing reaches the public without a
  human approving it — enforced by the database, which is what the P3q §4 acceptance rests on.
* Table grants tightened to SELECT-only for anon/authenticated (the migration had left
  Supabase's wide defaults including TRUNCATE, which RLS does NOT cover). `callback_events` has
  RLS on with zero policies and grants revoked — service_role only.
* Edge function `engine-callback` — https://mrlopewzlwsvsxzxdhci.supabase.co/functions/v1/engine-callback
  — `verify_jwt = false` (the HMAC signature IS its auth). Reads the raw body BEFORE parsing,
  hex HMAC-SHA256 keyed with WIT_CALLBACK_HMAC_SECRET, constant-time compare, 401 + no write on
  failure, service-role insert, never logs the secret/signature/body. KNOWN GAP (tracked): the
  secret is read with a `?? ""` fallback, so a MISSING secret would fail OPEN — fix to 503 in
  the next Lovable slice.
* Lovable Secrets hold WIT_ENGINE_SERVICE_KEY, WIT_CALLBACK_HMAC_SECRET, ENGINE_URL.

▶ RESUME HERE — PHASE 4 REMAINING (Jim's "Task-10")
The engine is done and live; the database, the receiver and the seam are proven. What is left:
  1. `submit-evaluation` edge function + the SHARED state-machine module: create the
     evaluation, call `/wit/v1/extract`, and on the callback chain extract → `/wit/v1/map` →
     `/wit/v1/runs`, persisting at each hop. Fold in the engine-callback fail-closed fix.
     Prove with one real curl-level end-to-end before any UI.
  2. `poll-runs` Lovable Cloud scheduled Job (~1/min) — the D1 safety net: the engine fires
     ONE best-effort callback and swallows failures, so polling `GET /wit/v1/runs/{id}` is
     mandatory, not optional. Engine 404 ⇒ `lost_engine_state` ⇒ resubmit once (D3).
  3. Lovable app: swap the fixtures module for live reads (keep fixtures as an explicit demo
     mode); real `progress.stage` display, no theater; honest UNSUPPORTED_CONSTRUCT /
     BUDGET_EXCEEDED / untestable states.
  4. Reviewer surface + `publish-report` (P3q §4): ensemble_meta, assumptions and honest-gap
     lines beside the draft; draft → approved → published. Library seeding stays HELD until
     this exists.
Watch item for slice 1: the seam-test extraction returned C1 `status: specified` with ALL
params null (tz, entry_start, entry_last_bar). The mapper reads those straight into
`session.tz` / `trade_window`, so a null-param "specified" field may produce a malformed wire
config or trip structural hygiene at the map step. Not an extraction regression (not a fixture)
— a mapper-robustness question to resolve when extract→map is wired.

Jim's lane open: FirstRateData confirmation email (Task-9 — biggest business risk + launch
gate; carried since session 1; STATUS STILL UNCONFIRMED, ask at next open); USPTO screen;
transcript IP policy before public launch; add the WillItTrade rows to the canonical prompt
standard in jimmuell/tradinggym; optional defensive domains; Lovable preview design review;
rename the Lovable project to WillItTrade.

## Open items (carried)

* engine-callback fails OPEN if WIT_CALLBACK_HMAC_SECRET is absent — fix to 503 (tracked).
* Engine accepts an extract job then fails ~60s later when ANTHROPIC_API_KEY is unset; should
  503 at request time and surface extraction-readiness in /health (tracked).
* YouTube-link ingestion is unowned (WIT-04 D7): v1 end-to-end runs on PASTED transcripts. The
  submit box promises transcript OR link; link ingestion + the transcript IP policy are open.
* Sweep disclosure granularity: skipped[] conflates errored with not-run.
* §3.6 result gaps (P3d honest nulls): bootstrap CIs + edge_vs_luck + regimes + expectancy_r
  + trades_url not in the single-run path; durable run store still RESTART-LOSSY (v1) — this is
  exactly why `poll-runs` must handle `lost_engine_state`.
* backtest/ duplicate-engine retirement plan in WIT-P3g-report (someday-safe).
* Repo housekeeping: untracked pine/mes_net_pnl_v2.pine; stale branches adr-048-pin-environment,
  docs/adr-022. prompts/README.md deliberately has NO index table; log/README.md IS indexed.
* Stripe/pricing wiring deferred; `usage` table exists and records from day one.

## Cross-project note
pine-strategies and tradinggym are separate repos with their own handoffs — don't conflate.
The canonical prompt standard lives in tradinggym; WIT's exceptions are in the engine pointer.

## Context for a cold start
WIT-01/02/03 hold the founding reasoning; **WIT-04** is the Phase-4 spec; `docs/wit/log/` is the
process history. Key reads: P3o + P3q adjudications (the ratified extraction standard + R1–R3),
P4b-1 ratification (why an empty template is 200-untestable, not 400), P3r (the extract
endpoint), P3s (why api/_shipped exists — do NOT delete it or its drift test). Trust the repo
over memory, git over this file, and VERIFY deployment state in the Railway dashboard and the
live Supabase database, not from any report.
----END FILE----
  T4. docs/wit/WIT-03-api-contract.md — ADD at the TOP of the §7 change-log list:
    - **WIT-P4z (2026-07-28):** session-5 close-out. Front office pinned to LOVABLE CLOUD (one
      Lovable-provisioned Supabase, ref `mrlopewzlwsvsxzxdhci`); WIT-04 amended to as-built (D8,
      §7 slice status); WIT-P4b ratified (empty template is 200-untestable; AttributeError catch
      stands). ANTHROPIC_API_KEY recorded as a REQUIRED engine variable — it was missing and the
      first live extraction caught it. Docs only; no wire-shape change; `config_version` stays `1.0`.
  T5. Archive this prompt verbatim to docs/wit/prompts/WIT-P4z.md; add rows to
      docs/wit/log/README.md for WIT-P4b-ratification.md (kind: Adjudication) and
      WIT-P4z-report.md (kind: Session close).
  T6. Suite (docs only — expect unchanged from the commit you started on):
        cd api && BACKTEST_API_KEY=k python -m pytest -q
      Expect 268 passed / 0 failed / 2 skipped. Anything else => STOP.
  T7. Stage explicit paths only — never git add -A.
      Commit subject MUST be exactly:
        WIT-P4z: session-5 close-out — front office live on Lovable Cloud, seam proven end-to-end, P4b ratified
      Push directly to main; record CI.

REPORT BACK — docs/wit/log/WIT-P4z-report.md, staged with the commit:
  1. STEP 0 result and the HEAD you started from.
  2. Grep proof: ratification file present; WIT-04 D8 + new §7 slice list present and the old
     §7 P4c bullet absent; handoff's new RESUME-HERE present and the old one absent; WIT-03
     change-log entry present.
  3. Suite counts; commit hash; CI status.
  Final line, exactly: WIT-P4z — Completed

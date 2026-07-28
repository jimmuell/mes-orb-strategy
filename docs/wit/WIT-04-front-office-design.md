# WIT-04 — Phase 4 Front-Office Design (Supabase ↔ Engine ↔ Lovable)

> **Design record, Phase 4 slice 0.** Written by the lead engineer (Claude, Cowork chat),
> 2026-07-28, session 5. Reconciles WIT-03 §6 (authored before the engine existed) against
> the SHIPPED engine surfaces (P3d/P3r/P3s as deployed on Railway, verified live this
> session). Where this document and WIT-03 disagree, this document wins and WIT-03's change
> log records the delta. Machine contracts in `contract/` are unchanged by this design.

## 1. Shipped reality this design builds on (verified in code, not from memory)

* Engine LIVE + KEYED: https://mes-orb-strategy-production.up.railway.app — /health ok,
  engine 25.25.0, 1,289,036 bars (re-verified from outside at session-5 open).
* `POST /wit/v1/runs` (202 → run_id), `GET /wit/v1/runs/{id}`, `POST /wit/v1/extract`
  (202 → run_id; k=3 ensemble; callback carries `{template, completeness, raw_meta}` with
  `raw_meta.ensemble_meta`). All under `Authorization: Bearer WIT_ENGINE_SERVICE_KEY`.
* Callbacks OUT: `X-WIT-Signature = hex(HMAC-SHA256(exact_body_bytes,
  WIT_CALLBACK_HMAC_SECRET))`; body `{run_id, status, result?|error?}` — note: NO
  evaluation_id in the callback; the receiver maps run_id → evaluation itself.
* Callback URL allowlist (SSRF guard): https only, host suffix `.supabase.co` (env
  `CALLBACK_ALLOWED_HOST_SUFFIX`). Supabase edge-function URLs
  (`https://<ref>.supabase.co/functions/v1/<fn>`) pass as-is. No engine change needed.
* Idempotency: `/wit/v1/runs` on evaluation_id + config_hash (+`:sweep`); `/wit/v1/extract`
  on evaluation_id + content hash. Resubmission returns the existing run.

## 2. Reconciliation deltas (WIT-03 as written vs the engine as shipped)

* **D1 — callback retries.** WIT-03 §3.3 promises 5× exponential backoff. SHIPPED: one
  best-effort POST at terminal state; failures are swallowed; `GET /wit/v1/runs/{id}` is the
  declared source of truth. => The front office MUST poll as a first-class mechanism, not a
  fallback nicety. (Design: §5, `poll-runs`.)
* **D2 — template→config mapping has no HTTP surface.** `map_template(template) →
  {kind, config, assumptions_applied}` exists engine-side (mapper, tested) but no endpoint
  exposes it; `/wit/v1/runs` takes the WIRE config only. Supabase must never re-implement
  mapping (WIT-03 §1: one implementation; mapping bugs are engine bugs). => ONE small
  additive engine slice: `POST /wit/v1/map` (§6). This is the only engine work in Phase 4.
* **D3 — run store is restart-lossy (v1, known).** An engine restart forgets in-flight
  run_ids; the poller will see 404 on a run we submitted. => Poller marks the run
  `lost_engine_state` and the chain resubmits (engine-side idempotency makes this safe;
  a restart also emptied the store, so resubmission starts a fresh run).
* **D4 — result payload gaps (P3d honest nulls).** Single-run results ship WITHOUT
  bootstrap CIs / edge_vs_luck / regimes / expectancy_r / trades_url. => Store `result_json`
  verbatim; report rendering handles honest nulls; `runs.trades_csv_path` (WIT-03 §6) is
  DROPPED for v1.
* **D5 — status vocabulary.** WIT-03 §6 `evaluations.status` lacks the Class-C outcome and
  the curated-review states (P3q §4 came later). => Enum extended (§4); review state lives
  on `reports`, not `evaluations`.
* **D6 — no honest time estimator.** `estimated_seconds` is null by design. => UI shows the
  REAL pipeline stages from `progress.stage`; no invented progress theater (TradeVerdict
  lesson, WIT-03 §3.2).
* **D7 — YouTube-link ingestion is unowned.** The submit box promises transcript OR
  YouTube link; nothing fetches transcripts from links yet, and the transcript IP policy
  (Jim's lane) is open. => v1 end-to-end runs on PASTED transcripts; link ingestion is a
  named open question for slice 3, not silently assumed.

## 3. Architecture (decided)

Browser (Lovable app) ⇄ Supabase (Auth + Postgres + Edge Functions) ⇄ Engine (Railway).
The browser NEVER talks to the engine; end-user JWTs never reach the engine; the service
key and the HMAC secret live ONLY in Supabase edge-function secrets (set by Jim). One
callback receiver handles every engine callback and verifies the HMAC on the EXACT raw
body bytes before parsing (constant-time compare) — deployed with JWT verification OFF
for that one function (the signature IS its auth).

Evaluation state machine (server-side only, edge functions own every transition):
`submitted → extracting → scored → running → complete` with terminal branches
`untestable` (Class C — a first-class product state, not an error) and `failed`
(carries the engine's error envelope: UNSUPPORTED_CONSTRUCT etc. are user-visible states
per WIT-03 §3.7). Auto-chain: extract-success ⇒ map ⇒ submit run (no human gate before
compute; the human gate is at PUBLICATION, per P3q §4).

## 4. Supabase schema v1 (supersedes WIT-03 §6)

* `evaluations` — id uuid pk, user_id → auth.users, source_url, source_title,
  source_channel, transcript text (PRIVATE; retention/republication per the pending IP
  policy — nothing from it is published before that policy exists), transcript_hash,
  status (`submitted|extracting|scored|running|complete|untestable|failed`), class
  (`A|B|C|null`), visibility (`private|public`, default private), created_at.
* `templates` — id, evaluation_id fk, template_json jsonb, completeness jsonb,
  ensemble_meta jsonb (NEW — the reviewer-facing vote stats, P3q §4), wire_config jsonb +
  assumptions jsonb (NEW — the `/wit/v1/map` output, stored so the reviewer sees exactly
  what was tested), created_at.
* `runs` — id, evaluation_id fk, engine_run_id text unique, kind
  (`extract|backtest|event_study`), sweep bool, status (`queued|running|succeeded|failed|
  lost_engine_state`), config_hash, result_json jsonb, error_json jsonb, submitted_at,
  terminal_at, last_polled_at. (Extract jobs are rows here too — one callback path.)
* `reports` — id, evaluation_id fk, slug unique (library permalink), verdict,
  headline_json, review_status (`draft|approved|published`), reviewer_notes,
  published_at. NOTHING is publicly readable until review_status='published' (P3q §4:
  unsupervised auto-publication re-opens the v1 acceptance — the schema makes it
  impossible, not just discouraged).
* `usage` — user_id, period, evaluations_used, tokens, engine_seconds. (Stripe wiring
  DEFERRED — not needed for the first end-to-end.)
* RLS: owners read their own evaluations/runs/reports; anon reads ONLY published reports;
  ALL writes go through edge functions (service role). No client-side inserts.

## 5. Edge functions v1

* `submit-evaluation` (JWT ON): validates pasted transcript (non-empty, ≤200k chars —
  mirror the engine cap client-side for honest errors), creates the evaluation, calls
  `POST /wit/v1/extract` with `callback_url = .../engine-callback`, records the extract
  run row. Rejects YouTube-link-only submissions with the honest "not yet" state (D7).
* `engine-callback` (JWT OFF; HMAC verify on raw bytes, constant-time): looks up the run
  by run_id; extract-success ⇒ store template/completeness/ensemble_meta, call
  `POST /wit/v1/map`, store wire_config, submit `POST /wit/v1/runs`, insert the run row,
  status `running`; Class C from map ⇒ `untestable`; run-success ⇒ store result_json,
  status `complete`, create the DRAFT report row; any failure ⇒ store the error envelope,
  status `failed`. Unknown run_id ⇒ 404 (the engine treats callbacks as best-effort; the
  poller repairs any miss).
* `poll-runs` (scheduled, ~1/min): for non-terminal runs past a grace period, `GET
  /wit/v1/runs/{id}` and apply the same transitions as the callback path (shared handler
  module — ONE state machine, two entry points); engine 404 ⇒ `lost_engine_state` ⇒
  resubmit once (D3). This is the mechanism that makes D1 safe.
* `publish-report` (JWT ON + reviewer check): flips review_status draft→approved→published;
  the ONLY path to public visibility. Reviewer UI surfaces ensemble_meta + assumptions +
  honest-gap lines beside the draft (P3q §4).

## 6. The one engine slice: `POST /wit/v1/map` (additive, sync)

Request `{template}` (a filled WIT-02 template JSON). Behavior: `map_template` verbatim —
success `200 {kind, config, assumptions_applied}`; UnsupportedConstruct ⇒ 400
UNSUPPORTED_CONSTRUCT {field, mode}; UntestableStrategy ⇒ 200 `{kind: null, class: "C",
untestable: true}` (Class C is a product outcome, not a 4xx). Same `verify_wit_key` auth.
Sync (milliseconds, deterministic, no LLM) — no run store, no callback, no budget. The
existing `/wit/v1/runs` request shape is UNTOUCHED. Goldens: the two anchor templates
(T-0001 Class A config equality vs the P2 hand-fed mapping; T-0002 Class B) — exact
equality, never tuned.

## 7. Slice plan (Phase 4, revised at slice 0)

* P4a (Claude Code, docs only): commit THIS design record + the WIT-03 change-log deltas.
* P4b (Claude Code, small): `POST /wit/v1/map` per §6 + tests. Gate: suite stays green.
* P4c (Jim, lead-guided, ~20 min): create the Supabase project; set function secrets
  (WIT_ENGINE_SERVICE_KEY, WIT_CALLBACK_HMAC_SECRET, ENGINE_URL); apply schema §4.
* P4d: edge functions §5 + the shared state-machine module; prove the chain with ONE real
  end-to-end: pasted T-0001 transcript → extract → map → run → result row (curl-level,
  before any UI).
* P4e (Lovable): swap the fixtures module for live reads (fixtures kept as explicit demo
  mode); real `progress.stage` display; honest UNSUPPORTED_CONSTRUCT / BUDGET_EXCEEDED /
  untestable states.
* P4f: reviewer surface + `publish-report`; first published library page. SEO seeding
  stays HELD until P4f exists (standing order).

Open questions carried (named, not blocking P4a–P4c): YouTube-link ingestion + transcript
IP policy (Jim's lane, launch gate); pricing/metering wiring (usage table records from day
one; Stripe later); durable engine run store (post-v1).

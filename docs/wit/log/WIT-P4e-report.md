# WIT-P4e — REPORT BACK (Lovable agent, 2026-07-29)

Archived verbatim by the lead. Lead verification addendum follows the report.

---

Both functions deployed. Report follows.

Files

* Created: supabase/functions/_shared/evaluation-chain.ts, supabase/functions/submit-evaluation/index.ts
* Edited: supabase/functions/engine-callback/index.ts
* Config unchanged in shape: supabase/config.toml — still only [functions.engine-callback] verify_jwt = false; submit-evaluation has no entry, so JWT verification stays ON (default).

Migration (verbatim)

    ALTER TABLE public.evaluations ADD COLUMN error_json jsonb;

Deployed function URLs

* https://mrlopewzlwsvsxzxdhci.supabase.co/functions/v1/submit-evaluation (JWT ON)
* https://mrlopewzlwsvsxzxdhci.supabase.co/functions/v1/engine-callback (verify_jwt = false)

State transitions implemented (in applyEngineEvent)

* Unknown engine_run_id → return unknown_run, no writes.
* Runs already succeeded/failed/lost_engine_state → return already_terminal, no writes.
* extract + succeeded:
   * runs queued→succeeded (result_json, terminal_at); insert templates row.
   * evaluations extracting→scored, set class from completeness.
   * POST /wit/v1/map:
      * 2xx with kind: update templates.wire_config + assumptions; POST /wit/v1/runs; on 202 insert new runs row queued; evaluations scored→running.
      * 2xx with untestable (or kind=null + class="C"): evaluations scored→untestable, class C. Terminal.
      * non-2xx map or non-202 run submit: evaluations →failed, engine envelope stored in error_json.
* extract + failed: runs →failed (error_json, terminal_at); evaluations →failed with error_json = event.error.
* backtest | event_study + succeeded: runs →succeeded; evaluations running→complete; insert draft reports row (slug = slugify(source_title || 'strategy-audit') + '-' + evaluation_id[0..8], review_status='draft', verdict/headline_json null); skip insert if a report already exists.
* backtest | event_study + failed: runs →failed; evaluations →failed; error copied.

submit-evaluation

* OPTIONS preflight + CORS headers.
* 401 without a bearer or invalid session.
* Validation: empty transcript → 400 INVALID_INPUT; >200 000 chars → 400 TRANSCRIPT_TOO_LONG (cap stated); URL-only → 422 LINK_INGESTION_NOT_AVAILABLE.
* Inserts evaluations row (status='submitted', visibility='private', SHA-256 hex hash).
* POSTs /wit/v1/extract with Bearer service key; on 202 inserts extract runs row and flips evaluations submitted→extracting, returns 201 {evaluation_id}.
* Non-202: evaluations →failed with engine envelope in error_json; responds 502 with the envelope.

engine-callback

* Fails closed with 503 if WIT_CALLBACK_HMAC_SECRET is missing/empty (no empty-key HMAC).
* Unchanged: POST-only, HMAC over raw body, constant-time hex compare, 401 with no DB write on failure, callback_events insert after verification, no secret/signature/body in logs, verify_jwt=false.
* After the receipt insert, calls applyEngineEvent; 404 on unknown_run, else 200 {ok:true, outcome}.

Deviations from the task

* The engine's callback body field name isn't specified explicitly; task text says {engine_run_id, status, ...} but the pre-existing test payload used run_id. To stay compatible with both, the callback accepts either engine_run_id or run_id when routing to the shared module. Nothing else changed in signature handling.

Noticed but not changed

* Pre-existing linter INFO on callback_events ("RLS enabled, no policy") — intentional service-role-only receipt table; task forbids policy/grant changes.
* Existing supabase/functions/engine-callback/sign_test.ts still posts run_id (not engine_run_id); left as-is since the callback accepts both.
* runs.status values in the shared module use string literals (queued, succeeded, failed, lost_engine_state, etc.); no enum exists yet.

WIT-P4e — Completed

---

## Lead verification (Claude, Cowork chat, 2026-07-29 — verified against the live project, not the report)

* All three source files read back from the Lovable project and reviewed line-by-line: transitions
  match the prompt, including the idempotent-replay guard, the Class-C branch, and honest failure
  envelopes at every hop (the C1 null-param watch item lands in the map-non-2xx path).
* engine-callback fail-closed CONFIRMED in code: secret read with no fallback, 503 before the body
  is read. HMAC path (raw bytes, constant-time, 401 + no write) unchanged.
* config.toml read back: only engine-callback has verify_jwt=false; submit-evaluation defaults ON.
* Live schema re-queried and diffed against the session-open snapshot: evaluations 11→12 columns
  (error_json jsonb — the one allowed line); every other table's column count unchanged; policies
  and grants byte-identical to session open (six SELECT policies, SELECT-only grants, zero client
  write policies). No access-control drift.
* The reported deviation is CORRECT and REQUIRED: the engine sends `run_id` in its callback body
  (verified in api/server.py `_wit_terminal`); the prompt's `engine_run_id` naming was the lead's
  imprecision. Accepting both is ratified.
* Noted for P4f (poll-runs), not blockers: shared-module DB writes and engine fetches do not check
  errors (a mid-chain network throw would 500 after the receipt insert — the poller is the designed
  repair); the post-202 runs insert does not handle a duplicate engine_run_id from the engine's
  idempotent resubmission path.

Verdict: WIT-P4e ACCEPTED. Next: curl-level end-to-end proof (Jim runs), then P4f.

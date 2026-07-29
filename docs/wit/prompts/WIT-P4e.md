Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P4e

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK

  Build the server-side submission chain: one shared state-machine module, a new
  submit-evaluation edge function, and a refactor of engine-callback onto the shared
  module. Backend only.

  Touch ONLY: supabase/functions/_shared/evaluation-chain.ts (new),
  supabase/functions/submit-evaluation/index.ts (new),
  supabase/functions/engine-callback/index.ts (edit), the function config entries for
  those functions, and one migration containing exactly the single ALTER TABLE line
  below. Do NOT touch any React component, page, fixture module, styling, or auth
  setup. Do NOT write, alter, or run ANY row-level-security policy, grant, or role
  SQL. No other DDL of any kind.

  Allowed schema change (exactly this, nothing more):

    ALTER TABLE public.evaluations ADD COLUMN error_json jsonb;

  Environment: secrets ENGINE_URL, WIT_ENGINE_SERVICE_KEY and WIT_CALLBACK_HMAC_SECRET
  already exist in this project's secrets. Every call to the engine sends header
  Authorization: Bearer <WIT_ENGINE_SERVICE_KEY>. Build the callback URL as
  <SUPABASE_URL>/functions/v1/engine-callback. Never place the service key or the HMAC
  secret in a response, a log line, or frontend-reachable code.

  1. Shared module — supabase/functions/_shared/evaluation-chain.ts

    Export one async handler applyEngineEvent(supabase, event), where supabase is a
    service-role client and event is the engine's terminal callback body shape:
    {engine_run_id, status, result?, error?} with status 'succeeded' or 'failed'.
    This module is the ONLY place evaluation/run state transitions live. engine-callback
    calls it now; the future poll-runs job will call it with the same event shape.

    Transitions:

    a. Look up the runs row by engine_run_id, joined to its evaluation. Unknown
       engine_run_id: return {outcome: "unknown_run"}, change nothing.

    b. Idempotent replay: if that runs row is already succeeded, failed, or
       lost_engine_state, return {outcome: "already_terminal"}, change nothing.

    c. Extract run (runs.kind = 'extract'), event status succeeded:

      - Mark the runs row succeeded: result_json = event.result, terminal_at = now.

      - Insert a templates row: evaluation_id; template_json = result.template;
        completeness = result.completeness; ensemble_meta = result.raw_meta.ensemble_meta.

      - Set evaluation status = 'scored' and class = result.completeness.class.

      - POST <ENGINE_URL>/wit/v1/map with body {template: result.template}, then branch
        on the RESPONSE BODY, not the HTTP status alone:

        - 200 with a non-null kind: update the templates row with
          wire_config = {kind: body.kind, config: body.config} and
          assumptions = body.assumptions_applied. Then POST <ENGINE_URL>/wit/v1/runs
          with body {evaluation_id: <the evaluation uuid>, kind: body.kind,
          config: body.config, callback_url: <engine-callback URL>}. On 202: insert a
          runs row (evaluation_id, engine_run_id = response run_id, kind = body.kind,
          sweep false, status 'queued', submitted_at now) and set evaluation
          status = 'running'.

        - 200 with untestable true (kind null, class "C"): set evaluation
          status = 'untestable' and class = 'C'. Terminal; no run is submitted.

        - Any non-2xx from map, or any non-202 from the run submission: set evaluation
          status = 'failed' and store the engine's error envelope verbatim in
          evaluations.error_json. No retries.

    d. Extract run, event status failed: mark the runs row failed (error_json =
       event.error, terminal_at now); set evaluation status = 'failed'; copy event.error
       into evaluations.error_json.

    e. Backtest or event_study run, event status succeeded: mark the runs row succeeded
       (result_json = event.result, terminal_at now); set evaluation status = 'complete';
       insert a reports row (evaluation_id; review_status 'draft'; slug = slugified
       source_title, or 'strategy-audit' when there is no title, plus '-' plus the first
       8 characters of the evaluation id; verdict and headline_json stay null for the
       reviewer surface). If a reports row already exists for this evaluation, skip the
       insert.

    f. Backtest or event_study run, event status failed: mark the runs row failed
       (error_json = event.error, terminal_at now); set evaluation status = 'failed';
       copy event.error into evaluations.error_json.

    g. Logging: engine_run_id and outcome only. Never log transcripts, templates,
       secrets, signatures, or full payloads.

  2. New edge function — supabase/functions/submit-evaluation/index.ts

    JWT verification ON (the default — do NOT set verify_jwt = false for this function).
    Standard CORS headers for browser calls, including the OPTIONS preflight.

    Accepts POST JSON {transcript, source_url?, source_title?, source_channel?}. Requires
    an authenticated user; resolve user_id from the caller's JWT; 401 without it.

    Validation, in order, each returning {error: {code, message}}:

      - transcript missing or empty after trim: 400, code INVALID_INPUT.

      - transcript longer than 200000 characters: 400, code TRANSCRIPT_TOO_LONG, with
        the cap stated in the message.

      - transcript that is only a URL (a single http/https link and nothing else):
        422, code LINK_INGESTION_NOT_AVAILABLE, message stating that pasted transcripts
        are required for now.

    On valid input:

      - Insert an evaluations row: user_id, transcript, transcript_hash = SHA-256 hex of
        the transcript, source_url, source_title, source_channel, status 'submitted',
        visibility 'private'.

      - POST <ENGINE_URL>/wit/v1/extract with body {evaluation_id: <the new uuid>,
        callback_url: <engine-callback URL>, transcript,
        source_meta: {title: source_title, url: source_url, channel: source_channel}}.

      - On 202: insert a runs row (evaluation_id, engine_run_id = response run_id,
        kind 'extract', sweep false, status 'queued', submitted_at now); set evaluation
        status = 'extracting'; respond 201 {evaluation_id}.

      - On any non-202: set evaluation status = 'failed', store the engine's error
        envelope in evaluations.error_json, respond 502 with that envelope.

  3. engine-callback — fail closed + refactor onto the shared module

    - FAIL CLOSED: read WIT_CALLBACK_HMAC_SECRET with no empty-string fallback. If it is
      missing or empty, return 503 immediately. Never compute an HMAC with an empty key.

    - Keep unchanged: POST-only; HMAC-SHA256 hex over the exact raw body bytes verified
      against the X-WIT-Signature header with a constant-time compare; 401 and NO
      database write on verification failure; the callback_events receipt insert after
      verification; never logging the secret, the signature, or the body; verify_jwt
      stays false for this function only.

    - After the receipt insert, call applyEngineEvent with the parsed body. Respond 404
      if it returns unknown_run; otherwise 200 {ok: true, outcome}.

DEPLOY / VERIFY

  Edge function edits auto-deploy. Confirm: all functions deploy without errors;
  submit-evaluation has JWT verification ON; engine-callback still has verify_jwt =
  false; the migration applied exactly the one ALTER TABLE line and nothing else. Do
  not Publish the frontend — this slice contains no frontend change. Live end-to-end
  verification is performed by the lead after your report, not by you.

REPORT BACK

  List: files created and edited; the exact migration SQL run, verbatim; the deployed
  function URLs; each state transition implemented (trigger, from-status, to-status);
  any deviation from this task; anything you noticed but did not change. End with
  exactly one line:

  WIT-P4e — Completed

  or

  WIT-P4e — Partial: <what's left>

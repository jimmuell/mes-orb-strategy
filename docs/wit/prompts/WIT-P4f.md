Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P4f

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK

  Complete the server-side intake path: YouTube-link ingestion, and a scheduled poller
  that drives every non-terminal job to a terminal state. Backend only — no frontend
  change in this slice.

  Touch ONLY: supabase/functions/_shared/transcript.ts (new),
  supabase/functions/poll-runs/index.ts (new),
  supabase/functions/submit-evaluation/index.ts (edit),
  supabase/functions/_shared/evaluation-chain.ts (edit), the function config entries for
  those functions, one migration containing exactly the four statements below, and one
  scheduled job. Do NOT touch any React component, page, fixture module, styling, or
  auth configuration. Do NOT write, alter, or run ANY row-level-security policy, grant,
  or role SQL. No other DDL of any kind.

  Migration (exactly these four statements, nothing more):

    ALTER TABLE public.evaluations DROP CONSTRAINT evaluations_status_check;

    ALTER TABLE public.evaluations ADD CONSTRAINT evaluations_status_check CHECK (status = ANY (ARRAY['submitted'::text, 'fetching_transcript'::text, 'extracting'::text, 'scored'::text, 'running'::text, 'complete'::text, 'untestable'::text, 'failed'::text]));

    ALTER TABLE public.runs DROP CONSTRAINT runs_kind_check;

    ALTER TABLE public.runs ADD CONSTRAINT runs_kind_check CHECK (kind = ANY (ARRAY['transcript'::text, 'extract'::text, 'backtest'::text, 'event_study'::text]));

  New secret: SUPADATA_API_KEY. Read it with no fallback. Assume it may be absent and
  behave honestly when it is (see 1c). Never log it.

  1. Transcript helper — supabase/functions/_shared/transcript.ts

    a. Export isSupportedVideoUrl(url): true only for YouTube watch URLs, youtu.be short
       URLs, and YouTube Shorts URLs. Everything else false.

    b. Export startTranscript(url), calling Supadata:

         GET https://api.supadata.ai/v1/transcript?url=<encoded>&text=true&mode=native
         header: x-api-key: <SUPADATA_API_KEY>

       mode is native ON PURPOSE — it uses only captions the video already has, at one
       credit. Never send mode=generate or mode=auto; generated transcripts bill per
       minute of video and must not be reachable without an explicit later decision.

       Map the response to one of:
         {state: "ready", content, lang}                  — HTTP 200, body.content
         {state: "pending", jobId}                        — HTTP 202, body.jobId
         {state: "unavailable", code, message}            — HTTP 206 (no captions),
                                                            404 (missing/private),
                                                            403, or any other non-2xx

    c. Export pollTranscript(jobId): GET https://api.supadata.ai/v1/transcript/<jobId>
       with the same header; map to the same three states.

    d. If SUPADATA_API_KEY is absent or empty, both functions return
       {state: "unavailable", code: "LINK_INGESTION_NOT_CONFIGURED", message: ...}
       WITHOUT making any network call.

  2. submit-evaluation — accept a link as well as a transcript

    Request body becomes {transcript?, source_url?, source_title?, source_channel?}.

    a. Both transcript and source_url absent or empty: 400 INVALID_INPUT (unchanged
       shape).

    b. A non-empty transcript is present: behave EXACTLY as today. Do not fetch
       anything, even when source_url is also present. Pasted text always wins.

    c. Only source_url is present (this also covers today's URL-only-transcript case —
       when the transcript field contains nothing but a single http/https URL, treat
       that URL as source_url instead of returning LINK_INGESTION_NOT_AVAILABLE; that
       response code is now retired):

       - Not a supported video URL per isSupportedVideoUrl: 422 UNSUPPORTED_LINK,
         message naming YouTube as the supported source. No rows created.

       - Supported: insert the evaluations row with transcript = '' , transcript_hash =
         '', status 'fetching_transcript', source_url set, visibility 'private'. Then
         call startTranscript:

         - ready: store transcript + transcript_hash (SHA-256 hex) on the evaluation,
           then continue into the EXISTING extract submission path unchanged (engine
           POST, runs row, status 'extracting'), and respond 201 {evaluation_id}.

         - pending: insert a runs row (evaluation_id, engine_run_id = jobId, kind
           'transcript', sweep false, status 'queued', submitted_at now). Leave the
           evaluation at 'fetching_transcript'. Respond 202 {evaluation_id}.

         - unavailable: set the evaluation status 'failed' with the returned {code,
           message} in error_json; respond 422 with that envelope.

  3. Shared module — supabase/functions/_shared/evaluation-chain.ts

    Export a new function submitExtract(supabase, evaluationId, transcript, sourceMeta)
    holding the engine extract call + runs-row insert + status flip to 'extracting',
    and have BOTH submit-evaluation and the poller call it. Do not duplicate that logic
    in two places. applyEngineEvent keeps its current behavior unchanged.

  4. New function — supabase/functions/poll-runs/index.ts

    An HTTP-triggered function intended to be run on a schedule; it takes no request
    body. This is the safety net: the engine fires ONE best-effort callback and swallows
    failures, so polling is what guarantees a terminal state.

    Each invocation:

    a. Transcript jobs — select runs where kind = 'transcript' AND status IN
       ('queued','running'). For each, call pollTranscript(engine_run_id):

       - ready: mark the run succeeded (terminal_at now); store transcript +
         transcript_hash on the evaluation; call submitExtract.
       - pending: update last_polled_at only.
       - unavailable: mark the run failed with the envelope in error_json; set the
         evaluation 'failed' with the same envelope in error_json.

    b. Engine jobs — select runs where kind IN ('extract','backtest','event_study') AND
       status IN ('queued','running') AND submitted_at is older than 90 seconds. For
       each, GET <ENGINE_URL>/wit/v1/runs/<engine_run_id> with the bearer service key:

       - 200 with status succeeded or failed: call applyEngineEvent with
         {engine_run_id, status, result, error} — the same shape the callback passes, so
         ONE state machine serves both entry points. Its idempotency guard makes a
         duplicate callback harmless.
       - 200 with status queued or running: update last_polled_at only.
       - 404: the engine forgot the run (its store does not survive a restart). Set the
         run status 'lost_engine_state' with error_json {lost_engine_state: true}, then
         RESUBMIT ONCE:
           * extract: call submitExtract with the evaluation's stored transcript.
           * backtest or event_study: re-POST <ENGINE_URL>/wit/v1/runs using the stored
             templates.wire_config for that evaluation ({kind, config}), insert a fresh
             runs row (status 'queued'), and set the evaluation back to 'running'.
         Record the replacement on the lost row as error_json.resubmitted_as = the new
         engine run id. NEVER resubmit a run whose error_json already has
         resubmitted_as — that is what makes it once, not a loop. If the stored state
         needed for resubmission is missing, set the evaluation 'failed' with an honest
         envelope instead of guessing.

    c. Cap each invocation at 25 runs per category, oldest first, so one bad batch
       cannot run long. Return 200 with a JSON summary of counts by outcome. Log counts
       only — never transcripts, templates, secrets or payloads.

    d. This function must NOT require a user JWT (the scheduler has no user). Add
       [functions.poll-runs] verify_jwt = false to the config. It reads no request input
       and returns no user data, so this exposes nothing.

  5. Schedule it

    Create a Lovable Cloud scheduled job that invokes poll-runs every minute. State in
    the report exactly how the schedule was created and how to see its history.

DEPLOY / VERIFY

  Edge function edits auto-deploy. Confirm: all functions deploy without errors; the
  migration applied exactly the four statements; poll-runs has verify_jwt = false and
  submit-evaluation still has JWT verification ON; the scheduled job exists and has run
  at least once. Do not Publish the frontend — this slice contains no frontend change.
  Live end-to-end verification is performed by the lead after your report, not by you.

REPORT BACK

  List: files created and edited; the exact migration SQL run, verbatim; how the
  scheduled job was created and its cadence; the deployed function URLs; every state
  transition the poller can cause; how "resubmit once" is enforced; any deviation from
  this task; anything you noticed but did not change. End with exactly one line:

  WIT-P4f — Completed

  or

  WIT-P4f — Partial: <what's left>

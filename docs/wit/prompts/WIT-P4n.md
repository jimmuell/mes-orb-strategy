Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P4n

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK

  The state machine advances even when the write that was supposed to save the result
  fails. Fix that, and make the failure visible.

  Touch ONLY supabase/functions/_shared/evaluation-chain.ts and
  supabase/functions/poll-runs/index.ts. No frontend file, no migration, no config, and
  no row-level-security, grant or role SQL.

  What happened, from the live database (evaluation 4695e71d-264a-4a59-823f-11bb9bfc1f49,
  2026-07-29):

    runs (backtest)  status 'queued', result_json NULL, terminal_at NULL,
                     last_polled_at NULL
    evaluations      status 'complete'
    reports          one draft row created
    callback_events  no row for that backtest run

  The backtest genuinely succeeded on the engine. The poller fetched it, called
  applyEngineEvent, and the backtest-succeeded branch ran in order: update the run with
  the result, update the evaluation to 'complete', insert the draft report. Steps two and
  three took effect and step one did not — so the app reports a finished audit it cannot
  show, because not one of those writes has its error checked. Every supabase call in
  this module discards the error object, and so does every engineFetch.

  1. Check every write and every call

    In BOTH files, capture and inspect the error on every supabase insert/update/select
    and on every engine fetch. No result may be discarded.

  2. Persist the result before advancing — and never advance past a failed write

    Reorder and guard the backtest/event_study success path so the run row's terminal
    state and result_json are stored FIRST and verified. If that write fails:

      - do NOT set the evaluation to 'complete'
      - do NOT create the report row
      - leave the run NON-terminal so the poller retries it on its next pass
      - record an honest envelope on the evaluation:
        {code: "RESULT_PERSIST_FAILED", message: <the database error message>,
         detail: {engine_run_id, postgres_code}} — and leave the evaluation status
        unchanged rather than claiming a state that did not happen
      - log the postgres code and message. Never log the result payload, the transcript,
        or any secret.

    Apply the same rule to every other transition in the module: a transition is only
    "applied" if the writes it depends on actually succeeded. Where a later write fails
    after an earlier one succeeded, say so in the returned detail rather than reporting
    success.

  3. Make the poller observable

    Set last_polled_at on EVERY poll of a run, terminal or not — currently it is only
    written on the still-running branch, so a run that was polled once and mishandled
    looks like it was never polled at all. That is why this defect was invisible.

    Return, in the poll-runs JSON summary, counts by outcome INCLUDING failures, so a
    silent failure shows up as a number rather than as nothing.

  4. Do not paper over the cause

    Do not add retries, sleeps, or a "best effort" swallow anywhere. If a write cannot
    succeed, the honest outcome is a stuck non-terminal run plus a recorded error, which
    the poller keeps retrying and which a human can see.

DEPLOY / VERIFY

  Edge functions auto-deploy. After deploying, the poller's next pass should pick the
  stuck backtest run up again (it is still non-terminal) and either store the result and
  complete the evaluation properly, or record RESULT_PERSIST_FAILED with the real
  database error. Report which of the two happened, and if it is the second, quote the
  postgres code and message verbatim — that error is the thing we need to see. Do not
  Publish the frontend; there is no frontend change here.

REPORT BACK

  List: every write and call now error-checked, by file; the new ordering of the
  backtest-success path; exactly what happens on a failed result write; the poll-runs
  summary shape; what the next poller pass did to evaluation
  4695e71d-264a-4a59-823f-11bb9bfc1f49, with the postgres error verbatim if one occurred;
  any deviation; anything you noticed but did not change. End with exactly one line:

  WIT-P4n — Completed

  or

  WIT-P4n — Partial: <what's left>

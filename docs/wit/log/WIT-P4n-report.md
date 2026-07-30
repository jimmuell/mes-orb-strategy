# WIT-P4n — REPORT BACK (Lovable agent, 2026-07-29)

---

Fix deployed and it immediately exposed the real cause.

1. Every write/call now error-checked. evaluation-chain.ts: helpers updateRun, updateEvaluation, insertRun, recordEvaluationError all capture {code, message} and log db_error (never payload/transcript/secret). engineFetch returns {ok,status,json,error} distinguishing unreachable / non-2xx / bad-JSON. New ApplyOutcome variant {outcome:"error", detail} so a failed write can never be reported as "applied". poll-runs: both batch selects, last_polled_at stamp, transcript writes, submitExtract result, all lost-engine-state writes and every applyEngineEvent outcome checked.

2. New backtest/event_study success ordering: (1) update run -> succeeded + result_json + terminal_at + last_polled_at, error checked; (2) read-back verify the row says succeeded; (3) only then evaluation -> complete; (4) only then report insert. On a failed result write: evaluation status untouched, no report created, run stays non-terminal so the poller retries, error_json set to {code:"RESULT_PERSIST_FAILED", message, detail:{engine_run_id, postgres_code}}, postgres code+message logged. No retries, sleeps or swallows.

3. poll-runs summary now returns counts by outcome including failures; ok is false when errors > 0; last_polled_at stamped on every polled run.

4. Next pass on evaluation 4695e71d-264a-4a59-823f-11bb9bfc1f49: RESULT_PERSIST_FAILED. No postgres code — the write never reached Postgres. The error body was Cloudflare HTML: "520: Web server is returning an unknown error" for the result update, then "522: Connection timed out" for the follow-up error write. The original silent bug is exactly this: the data-API request carrying the large backtest result_json fails at the edge while small subsequent writes succeed, and the old code discarded the error.

Deviation: added a read-back verification step after the result write (extra safety, no retry).

Noticed, not changed: the failing write is the one carrying the full backtest result_json; 520/522 points at payload size / origin timeout, not RLS or grants.

WIT-P4n — Completed

---

## Lead verification (Claude, Cowork chat, 2026-07-29)

ACCEPTED, and the most valuable slice of the day: it converted a silent failure into a precise diagnosis in one pass.

Context: the first production audit computed correctly, then the app showed "No engine result payload attached to this evaluation yet" while claiming the audit was complete. Database state confirmed it — backtest run 'queued' with result_json NULL and terminal_at NULL, evaluation 'complete', a draft report created, and no callback receipt. The success branch had run in order: update the run with the result, mark the evaluation complete, insert the report. Steps two and three took effect; step one did not, and no error was checked anywhere in the module.

LEAD ACCOUNTABILITY: this exact weakness was flagged in the lead's own WIT-P4e review ("shared-module DB writes and engine fetches do not check errors") and judged non-blocking, to be handled in P4f. That judgement was wrong and it cost a production run.

The 520/522 finding led directly to WIT-P4o: the result payload carried a per-bar equity curve (~198k points, 11.7 MB serialized) that the data API could not accept.

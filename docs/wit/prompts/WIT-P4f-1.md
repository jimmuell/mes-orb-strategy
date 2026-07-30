Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P4f-1

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK

  Fix one defect in the transcript poller. Every video longer than about 20 minutes
  currently fails roughly a minute after submission with a meaningless error.

  Touch ONLY supabase/functions/_shared/transcript.ts. Change nothing else — no other
  function, no migration, no config, no SQL, no frontend file.

  The cause: pollTranscript treats the job-status endpoint as if it signalled progress
  through HTTP status codes. It does not. GET /v1/transcript/{jobId} returns HTTP 200 for
  EVERY outcome and carries the real state in a `status` field:

    {"status": "queued"}                                          — waiting
    {"status": "active"}                                          — in progress
    {"status": "completed", "content": ..., "lang": ...}          — done
    {"status": "failed", "error": {...}}                          — failed

  Because the current code only recognises a 200 that already carries `content`, the
  first poll of a queued or active job falls through to the unavailable branch and
  reports "Transcript service returned 200." The run and the whole evaluation are then
  marked failed while the transcript is still being produced.

  Rewrite pollTranscript's response handling to branch on the body's `status` field:

    a. status "completed" AND content is a string → {state: "ready", content, lang}.

    b. status "queued" or "active" → {state: "pending", jobId} — echo back the SAME
       jobId that was passed in, so the caller keeps polling the same job.

    c. status "failed" → {state: "unavailable", code: "TRANSCRIPT_JOB_FAILED", message}
       where message includes the error detail from the body when present.

    d. HTTP 404 → {state: "unavailable", code: "TRANSCRIPT_JOB_EXPIRED", message saying
       the transcript job expired before it was collected}. Completed results are only
       retained for one hour.

    e. Any other HTTP status, unparseable body, or a 200 whose status field is missing
       or unrecognised → the existing unavailable mapping, unchanged.

  Keep everything else in this file exactly as it is: the missing-key guard returning
  LINK_INGESTION_NOT_CONFIGURED with no network call, isSupportedVideoUrl, the x-api-key
  header, and startTranscript — including mode=native, which must NOT change.

  Do not add retry loops, sleeps, or timers. The scheduled poller already provides the
  retry cadence; this function reports state once per call and returns.

DEPLOY / VERIFY

  The edited function auto-deploys with its callers. Confirm poll-runs and
  submit-evaluation still deploy without errors. No frontend Publish is needed.

REPORT BACK

  Show the final pollTranscript response-handling block verbatim. State each branch and
  the state it returns. Confirm startTranscript is unchanged and that mode=native is
  still in place. List any deviation. End with exactly one line:

  WIT-P4f-1 — Completed

  or

  WIT-P4f-1 — Partial: <what's left>

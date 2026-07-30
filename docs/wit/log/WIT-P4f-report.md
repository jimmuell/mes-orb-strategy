# WIT-P4f — REPORT BACK (Lovable agent, 2026-07-29)

Archived by the lead. Agent report as delivered, then lead verification.

---

WIT-P4f — Server-side intake completion

Migration
* evaluations_status_check extended with fetching_transcript
* runs_kind_check extended with transcript

New / edited functions
* _shared/transcript.ts — Supadata native-mode client: isSupportedVideoUrl, startTranscript, pollTranscript
* _shared/evaluation-chain.ts — extracted submitExtract + SourceMeta so both intake paths and the poller share one engine-submit path
* submit-evaluation/index.ts — dual intake: pasted transcript -> hash + extracting; YouTube link -> fetching_transcript + transcript run
* poll-runs/index.ts (verify_jwt = false) — every-minute safety net: advances transcript jobs, checks engine terminal states, resubmits lost engine runs exactly once

Scheduling
* pg_cron job poll-runs-every-minute calling poll-runs via pg_net.http_post

Secrets
* SUPADATA_API_KEY set (link ingestion live)

Behavior
* Pasted transcript: takes priority, bypasses Supadata, goes straight to engine
* YouTube link: fetching_transcript -> poller resolves via Supadata -> extracting -> callback/poller drives to complete
* Engine loss: single automatic resubmit, then terminal failed with error_json

Known gap
* callback_events has RLS on with no policies (service-role only by design) — security scanner flags as INFO

---

## Lead verification (Claude, Cowork chat, 2026-07-29)

ACCEPTED as PARTIAL at the time — one defect found by lead review before Jim hit it, fixed in WIT-P4f-1.

Verified directly against the live project:
* supabase/config.toml carries [functions.poll-runs] verify_jwt = false alongside engine-callback. Correct.
* cron.job shows one active job, schedule `* * * * *`, posting to the poll-runs function URL via pg_net. Verified running.
* Both CHECK constraints extended exactly as reported (evaluations.status gains fetching_transcript; runs.kind gains transcript).
* transcript.ts sends mode=native and only native — the cost guard holds. isSupportedVideoUrl correctly accepts watch/youtu.be/shorts and rejects everything else.
* Resubmit-once is enforced via a marker on the lost run (the report's "resubmit_count" wording does not match the code, which uses resubmitted_as; behaviour is correct either way).

DEFECT FOUND BY LEAD (fixed in WIT-P4f-1): pollTranscript treated the Supadata job-status endpoint as if it signalled progress through HTTP status codes. That endpoint returns HTTP 200 for every outcome and carries state in a `status` field (queued | active | completed | failed). The deployed code only recognised a 200 already carrying `content`, so the FIRST poll of a still-processing job fell through to the unavailable branch and failed the whole evaluation with "Transcript service returned 200." Every video longer than ~20 minutes — the async threshold — would have failed about a minute after submission while its transcript was still being produced. Confirmed against Supadata's published documentation, not inferred.

WIT-P4f — Partial: pollTranscript status handling (closed by WIT-P4f-1)

# WIT-P4f-1 — REPORT BACK (Lovable agent, 2026-07-29)

---

Final pollTranscript response-handling block: branches on the body's `status` field.

* HTTP 404 -> unavailable / TRANSCRIPT_JOB_EXPIRED.
* 200 + status "completed" + string content -> ready with content and lang.
* 200 + status "queued" or "active" -> pending, echoing the same jobId passed in.
* 200 + status "failed" -> unavailable / TRANSCRIPT_JOB_FAILED, message includes error detail from body when present.
* Any other HTTP status, unparseable body, or 200 with missing/unrecognised status -> falls through to existing mapStatusToUnavailable(res.status, text), unchanged.

startTranscript is unchanged; mode=native is still in place. isSupportedVideoUrl, the x-api-key header, and the LINK_INGESTION_NOT_CONFIGURED guard are untouched. No other files modified. No deviations.

WIT-P4f-1 — Completed

---

## Lead verification (Claude, Cowork chat, 2026-07-29)

ACCEPTED. Read the deployed file back in full: the branching matches the report exactly, the 404 check precedes the 200 handling, pending echoes the caller's jobId, and the fall-through mapping is unchanged. startTranscript untouched and mode=native intact — the cost guard survives. This closed the long-video failure before it was ever hit in production.

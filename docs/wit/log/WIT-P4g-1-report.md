# WIT-P4g-1 — REPORT BACK (Lovable agent, 2026-07-29)

---

Envelope unwrap — unwrapErrorEnvelope(raw):
* Nested ({error: {code, message, detail}}): read from raw.error. Shape = "nested".
* Flat ({code, message, ...}): read from raw directly. Shape = "flat".
* Unrecognised: shape = "unrecognised" -> red panel with raw JSON, no invented code.
* null/non-object -> "empty".

UNSUPPORTED_CONSTRUCT renders its own amber panel: kicker "Unsupported construct", heading "This strategy can't be tested yet", sentence naming the human field name and the unsupported token, with the raw code/message/detail block kept below for auditability.

Plain-English sentences added for BUDGET_EXCEEDED, EXTRACTION_FAILED, INTERNAL, RESUBMIT_UNAVAILABLE, RESUBMIT_UNREACHABLE, TRANSCRIPT_JOB_FAILED, TRANSCRIPT_JOB_EXPIRED, NO_CAPTIONS, VIDEO_NOT_FOUND, TRANSCRIPT_FORBIDDEN, LINK_INGESTION_NOT_CONFIGURED. Any other code renders the engine's own message verbatim. Only src/routes/evaluation.$id.tsx touched.

WIT-P4g-1 — Completed

---

## Lead verification (Claude, Cowork chat, 2026-07-29)

ACCEPTED. Written because the first live UNSUPPORTED_CONSTRUCT refusal surfaced as "code: INTERNAL / The evaluation failed" — the engine's real explanation was stored one level down in a nested envelope and the panel read the top level. Treating an unsupported construct as an amber product state rather than a red crash is the correct product framing: the engine refused to fake a test, which is the feature, not a failure. Every subsequent diagnosis today depended on this fix being in place.

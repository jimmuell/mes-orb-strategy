Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P4g-1

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK

  Fix the failure screen. It currently hides the real reason an audit stopped and shows
  a generic "Something went wrong inside the audit pipeline" instead.

  Touch ONLY src/routes/evaluation.$id.tsx. No other file, no edge function, no
  migration, no SQL.

  The cause: the engine's error envelope is stored NESTED. A real stored value is

    {"error": {"code": "UNSUPPORTED_CONSTRUCT",
               "message": "D1: mode 'va_high_low' not supported in engine v1",
               "detail": {"field": "D1", "mode": "va_high_low"}}}

  FailedPanel reads evaluation.error_json.code, which is undefined at the top level, so
  it falls back to INTERNAL and a stock message while the true code and message sit one
  level down.

  1. Unwrap the envelope

    Read the error as: error_json.error when error_json.error is an object, otherwise
    error_json itself. From that object take code, message and detail. Some envelopes
    written by the edge functions are flat ({code, message}) and some carry other shapes
    entirely — handle all three: nested, flat, and unrecognised. For an unrecognised
    shape show the raw JSON rather than inventing a code.

  2. Present UNSUPPORTED_CONSTRUCT as its own outcome, not a crash

    When the code is UNSUPPORTED_CONSTRUCT, the audit did not break — the engine
    correctly refused to fake a test of something it cannot model. Give it a distinct
    panel: amber, not red; heading "This strategy can't be tested yet"; and a sentence
    naming the specific component, resolved through the existing SECTION_MAP labels.
    With detail {field: "D1", mode: "va_high_low"} it must read as the human field name
    ("Directional bias") plus the unsupported mode token, e.g.:

      The engine can't yet test this strategy's Directional bias (D1) — it uses
      "va_high_low", which engine v1 doesn't model.

    Keep the raw code/message block visible below it for auditability.

  3. Keep every other code red and honest

    BUDGET_EXCEEDED, EXTRACTION_FAILED, INTERNAL, RESUBMIT_UNAVAILABLE,
    RESUBMIT_UNREACHABLE, TRANSCRIPT_JOB_FAILED, TRANSCRIPT_JOB_EXPIRED, NO_CAPTIONS,
    VIDEO_NOT_FOUND, TRANSCRIPT_FORBIDDEN, LINK_INGESTION_NOT_CONFIGURED — each gets one
    plain-English sentence. Any code with no sentence of its own shows the code and the
    engine's own message verbatim, never a substituted one.

  4. Where the message is null or empty, say so plainly rather than rendering an empty
     block.

  Do not change the progress panel, the complete panel, the completeness scorecard, the
  polling behaviour, or any status handling. This is the failure screen only.

DEPLOY / VERIFY

  Verify in Preview against the existing failed evaluation
  e7da0bd8-ea0e-4f72-bfb4-020493e5b0f3, which holds exactly the nested
  UNSUPPORTED_CONSTRUCT envelope above: it must render the amber panel naming
  Directional bias (D1) and the va_high_low mode. Then Publish → Update.

REPORT BACK

  State how the envelope is unwrapped for each of the three shapes; what that specific
  evaluation now renders, quoted; and the list of codes with their sentences. Confirm no
  other file was touched. End with exactly one line:

  WIT-P4g-1 — Completed

  or

  WIT-P4g-1 — Partial: <what's left>

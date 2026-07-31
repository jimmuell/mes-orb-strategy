Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P5e

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK — surface edge-function error bodies instead of the generic invoke message

  SCOPE — modify ONLY this path:
    src/lib/wit-live.ts

  DO NOT TOUCH: any edge function, any migration, audits.functions.ts, audit-view.ts,
  any route file, or any other file under src/.

  FORBIDDEN IN THIS TASK: RLS policies, GRANT, REVOKE, any SQL, any database change.

  1. Fix the error branch of submitEvaluation.
     Observed live 2026-07-31: a 429 QUOTA_EXCEEDED from submit-evaluation reaches the
     user as "Edge Function returned a non-2xx status code" and the returned status is
     500, not 429.

     Cause: on a non-2xx response supabase-js throws a FunctionsHttpError whose
     `context` IS the Response object. The current code reads `context.response`,
     which is undefined, so the parsed body is always null and the generic message
     wins.

     Replace the response extraction so it accepts BOTH shapes, in this order:
       a. if `anyErr.context` is itself a Response (duck-type it: a non-null object
          with a numeric `status` and a callable `json`), use it directly
       b. otherwise fall back to `anyErr.context?.response` as today
       c. otherwise no response object — keep the existing generic fallback

     Everything else about the function is unchanged: it still returns
     { status, evaluation_id, error }, still clones before reading the body, still
     swallows a JSON parse failure and falls back to the generic message, and still
     never throws.

     The returned `status` must be the real HTTP status when a response object was
     found (429 for a quota refusal), and 500 only when there was none.

  2. Add a narrow regression guard in the same file — no new dependency, no test
     runner. Export a pure helper that the fix uses internally:
       export function extractFunctionsResponse(err: unknown): Response | null
     It contains the a/b/c logic above and nothing else. submitEvaluation calls it.
     Keep it exported so a later slice can test it directly.

  3. Do not change any user-facing copy. The message the user sees must come from the
     edge function's own error body — for a quota refusal that is
     "You have used your free strategy audit for this month." — not from a string
     written in the front end.

  DEPLOY AND VERIFY
    This is a frontend-only change. It is visible in Preview on edit and reaches the
    live URL only via Publish -> Update. Do NOT publish; Jim will.
    Verify and report:
      - typecheck clean
      - the only file changed is src/lib/wit-live.ts
      - confirm by reading the code that a FunctionsHttpError whose `context` is a
        Response now yields status 429 and the body's error.message

REPORT BACK
  1. The before and after of the response-extraction lines.
  2. Confirmation that no other file, no edge function and no SQL was touched.
  3. Whether Preview still builds, and confirmation that you did NOT publish.
  Final line, exactly: WIT-P5e — Completed

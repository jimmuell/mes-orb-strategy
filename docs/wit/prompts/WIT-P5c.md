Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P5c

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK — make the quota refund exception-proof, and drop a duplicate index

  SCOPE — modify ONLY these paths:
    supabase/functions/submit-evaluation/index.ts        modify
    supabase/migrations/<new timestamp>.sql              new

  DO NOT TOUCH: _shared/metering.ts, get-entitlements, publish-report,
  engine-callback, poll-runs, _shared/evaluation-chain.ts, _shared/transcript.ts,
  _shared/video-meta.ts, any file under src/, or any existing migration.

  FORBIDDEN IN THIS TASK: RLS policies, GRANT, REVOKE, ALTER ROLE, SECURITY DEFINER
  functions, and any change to grants or policies on any table. If you conclude you
  need one to finish, STOP and report instead of writing it.

  1. Replace the five scattered releaseEvaluation calls with one invariant.
     The rule being enforced: a reservation that did not result in queued engine work
     is always refunded, however the request ends — including on a thrown exception.

     a. Declare two flags in the request handler, before the Path A branch:
          let reserved = false;
          let committed = false;
        reserveOrRefuse sets reserved = true when the reservation succeeds. It must
        NOT set it when the reservation is refused.

     b. Set committed = true immediately before each of the two success returns, and
        ONLY those two:
          - Path A, the 201 return after submitExtract succeeds
          - Path B ready-path, the 201 return after submitExtract succeeds
          - Path B pending-path, the 202 return after the runs insert
        (That is three success returns in total — 201, 201, 202. Set the flag before
        each.)

     c. Wrap the handler body from the admin client creation to the end of the
        function in try / catch / finally:
          - catch: log the error with console.error including the message, then
            return a 500 with body
            { error: { code: "INTERNAL", message: "the submission could not be completed" } }
          - finally: if reserved && !committed, await releaseEvaluation(admin, userId)
        The finally block must not swallow or alter the response.

     d. DELETE all five existing explicit releaseEvaluation calls. The finally block
        replaces them. Do not leave any of them in place — a leftover call plus the
        finally block would refund twice.

     e. Everything else in this file is unchanged: the reservation points, the
        QUOTA_EXCEEDED 429 shape and its two messages, the transcript-versus-URL
        precedence, every existing status code and error envelope, the oEmbed
        fail-soft, and the runs insert on the pending path.

  2. New migration — remove the redundant index. public.usage already carries a
     unique constraint on (user_id, period) named usage_user_id_period_key, created
     with the table. The index added in WIT-P5a duplicates it.
       DROP INDEX IF EXISTS public.usage_user_period_uniq;
     Do NOT drop, alter or rename usage_user_id_period_key. Do not touch any other
     index, constraint, policy or grant.

  DEPLOY AND VERIFY
    The edge function auto-deploys on edit; the migration applies when you run it.
    No frontend change, so no Publish is required.
    Verify and report, without changing any data that already exists:
      - typecheck clean
      - grep the file and confirm exactly ONE releaseEvaluation call remains, inside
        the finally block
      - confirm committed = true appears exactly three times, each immediately before
        a 201 or 202 return
      - list the indexes on public.usage and confirm usage_user_id_period_key is
        present and usage_user_period_uniq is gone
      - confirm the policy count for schema public is still 9 and that no grant on
        any table changed

REPORT BACK
  1. The files modified and the migration filename.
  2. The exact line on which the single remaining releaseEvaluation call sits, and
     the three return statements you marked committed.
  3. The index listing for public.usage.
  4. The policy count and your confirmation that no grant changed.
  5. Anything you could not do without writing a policy or a grant, or "clean".
  Final line, exactly: WIT-P5c — Completed

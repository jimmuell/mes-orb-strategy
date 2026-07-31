Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P5a

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK — meter evaluations and enforce the free-tier quota (no Stripe in this slice)

  SCOPE — create or modify ONLY these paths:
    supabase/migrations/<new timestamp>.sql              new
    supabase/functions/_shared/metering.ts               new
    supabase/functions/get-entitlements/index.ts         new
    supabase/functions/submit-evaluation/index.ts        modify

  DO NOT TOUCH: any file under src/, publish-report, engine-callback, poll-runs,
  _shared/evaluation-chain.ts, _shared/transcript.ts, _shared/video-meta.ts, or any
  existing migration. No UI work in this slice.

  FORBIDDEN IN THIS TASK: RLS policies, GRANT, REVOKE, ALTER ROLE, SECURITY DEFINER
  functions, and any change to grants or policies on existing tables. If you conclude
  you need a policy or a grant to finish, STOP and report instead of writing one.

  1. Migration — create table public.subscriptions
       id                      uuid primary key default gen_random_uuid()
       user_id                 uuid not null unique
       plan                    text not null default 'free'
       status                  text not null default 'active'
       stripe_customer_id      text
       stripe_subscription_id  text
       current_period_end      timestamptz
       created_at              timestamptz not null default now()
       updated_at              timestamptz not null default now()
     Add: alter table public.subscriptions enable row level security;
     Create NO policies on it and issue NO grants on it. It is service-role only,
     exactly like public.callback_events.

  2. Same migration — add a unique index on public.usage (user_id, period):
       create unique index if not exists usage_user_period_uniq
         on public.usage (user_id, period);
     Change nothing else about public.usage. Do not enable, disable or alter RLS,
     policies or grants on public.usage.

  3. New file supabase/functions/_shared/metering.ts exporting:
       PLAN_LIMITS = { free: 1, paid: 10 }
       currentPeriod(): string        UTC month as "YYYY-MM"
       getPlan(admin, userId): Promise<{ plan: string; status: string }>
         Reads public.subscriptions by user_id. No row, or status not 'active',
         returns { plan: 'free', status: 'active' }. An unknown plan value returns
         'free'. Errors are thrown, never swallowed.
       reserveEvaluation(admin, userId): Promise<{ ok: true; used: number; limit: number }
                                                | { ok: false; used: number; limit: number }>
         Resolve the plan and its limit, then in this exact order:
           a. insert into usage (user_id, period) values (userId, currentPeriod())
              with on-conflict-do-nothing
           b. a SINGLE update statement that increments evaluations_used by 1 where
              user_id and period match AND evaluations_used < limit, returning the new
              evaluations_used
         A returned row means ok true. No returned row means the quota is spent:
         ok false, with the current evaluations_used read back for the caller. Both
         database calls are error-checked; on a database error, throw.
       releaseEvaluation(admin, userId): Promise<void>
         Decrement evaluations_used by 1 for the current period, never below 0.
         Best-effort: log a failure, do not throw.

  4. Modify supabase/functions/submit-evaluation/index.ts
     Insert the reservation AFTER the admin client is created and AFTER all input
     validation (the UNAUTHORIZED, INVALID_INPUT, TRANSCRIPT_TOO_LONG and
     UNSUPPORTED_LINK returns keep firing before any quota is consumed), and BEFORE
     the first evaluations insert on either path.

     On ok false, return HTTP 429 with body exactly:
       { error: { code: "QUOTA_EXCEEDED", message: "<message>",
                  plan: "<plan>", used: <n>, limit: <n>, period: "<YYYY-MM>" } }
     message for the free plan, verbatim:
       "You have used your free strategy audit for this month."
     message for any other plan, verbatim:
       "You have reached your plan's monthly audit limit."

     Call releaseEvaluation before returning, on EVERY path where the reservation was
     taken but no queued work resulted, specifically:
       - the DB_ERROR return after a failed evaluations insert (both paths)
       - the submitExtract failure return (both paths)
       - the 422 transcript-unavailable return
     Do NOT release on the 201 and 202 success returns.

     Change nothing else in this file: the transcript-versus-URL precedence, the
     oEmbed metadata fail-soft, the runs insert on the pending path and every existing
     status code stay exactly as they are.

  5. New edge function supabase/functions/get-entitlements/index.ts
     JWT verification ON. Same CORS block and json() helper style as
     submit-evaluation. Resolves the caller from the Authorization header, reads plan
     and current-period usage with the service-role client, and returns 200:
       { plan, status, period, used, limit, remaining }
     remaining is limit minus used, floored at 0. No row in usage means used 0.
     Returns 401 for a missing or invalid session. It never writes.

  DEPLOY AND VERIFY
    Edge functions auto-deploy on edit; the migration applies when you run it. There
    is no frontend change in this slice, so no Publish is required.
    Verify and report, without changing any data that already exists:
      - the migration applied and public.subscriptions exists with RLS enabled,
        zero policies and zero grants
      - the unique index on public.usage (user_id, period) exists
      - list every policy and every grant on public.subscriptions and public.usage
      - confirm no policy or grant on evaluations, runs, templates, reports or usage
        was added, dropped or altered by this task
      - typecheck clean

REPORT BACK
  1. The files created and modified, and the migration filename.
  2. The exact reserve-and-release call sites you added in submit-evaluation, listed
     as the return path each one guards.
  3. The policy and grant listing for public.subscriptions and public.usage, and your
     confirmation that no existing table's policies or grants changed.
  4. Anything you could not do without writing a policy or a grant, or "clean".
  Final line, exactly: WIT-P5a — Completed

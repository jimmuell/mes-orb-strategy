# WIT-P5b — restore the session-7 access-control baseline

Run by: JIM ONLY, in the Lovable Cloud SQL editor. Access-control SQL is never run by
the Lovable agent or by the lead engineer.
Authored: lead engineer (Claude, Cowork chat), 2026-07-31, session 8.
Reason: two migrations applied 2026-07-31 (20260731120708, 20260731121343) re-introduced
the client-side evaluations DELETE removed in session 7, and created public.evaluation_tags
which inherited the schema's default grants to anon and authenticated.

---

## BLOCK 1 — the fix (run this first, as one transaction)

```sql
BEGIN;

-- 1. Remove the client-side audit delete. Restores the session-7 ratified decision:
--    user delete returns later via a guarded edge function, never a DELETE policy.
DROP POLICY IF EXISTS evaluations_delete_own ON public.evaluations;
REVOKE DELETE ON public.evaluations FROM anon, authenticated;

-- 2. evaluation_tags: strip the automatic default grants, then re-grant only the
--    three privileges the migration actually intended.
REVOKE ALL ON public.evaluation_tags FROM anon, authenticated;
GRANT SELECT, INSERT, DELETE ON public.evaluation_tags TO authenticated;

COMMIT;
```

## BLOCK 2 — stop the bleeding for future tables (run separately, after Block 1)

Run this on its own. If it errors on permissions, that is not a problem — report the
error and stop; Block 1 is the part that matters today.

```sql
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON TABLES FROM anon, authenticated;
```

After this, a newly created table in `public` is NOT automatically readable or writable
by signed-in users or the public. Every new table must be granted explicitly. That is the
intended behaviour.

---

## BLOCK 3 — verification (run after both, paste both result sets back)

```sql
-- A. every policy in public
select c.relname as tbl, pol.polname,
       case pol.polcmd when 'r' then 'SELECT' when 'a' then 'INSERT'
                       when 'w' then 'UPDATE' when 'd' then 'DELETE'
                       when '*' then 'ALL' end as cmd,
       (select string_agg(r.rolname, ',') from pg_roles r
         where r.oid = any(pol.polroles)) as roles
from pg_policy pol
join pg_class c on c.oid = pol.polrelid
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public'
order by 1, 2;

-- B. every non-SELECT grant held by anon or authenticated in public
select table_name, grantee, privilege_type
from information_schema.role_table_grants
where table_schema = 'public'
  and grantee in ('anon', 'authenticated')
  and privilege_type <> 'SELECT'
order by 1, 2, 3;
```

## Expected after the fix

- Result A: **9 policies**. All SELECT, except `evaluation_tags_insert_own` (INSERT) and
  `evaluation_tags_delete_own` (DELETE), both scoped to `authenticated`.
  `evaluations_delete_own` must be GONE.
- Result B: exactly **two rows** — `evaluation_tags / authenticated / INSERT` and
  `evaluation_tags / authenticated / DELETE`. Nothing else. No row for `evaluations`.
  No row for `anon` at all.

Anything else in either result set: stop and report it rather than adjusting the SQL.

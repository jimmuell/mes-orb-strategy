# WIT-P5d — live end-to-end proof of the meter (new account, real audit)

Run by: JIM, in the app. One optional SQL check at the end.
Authored: lead engineer (Claude, Cowork chat), 2026-07-31, session 8.
Supersedes the seeded-counter version of WIT-P5d — Jim's method proves more: it
exercises the reservation, the increment AND the refusal in one pass, on an account
whose quota does not matter.

Cost: one Supadata transcript credit + three extraction calls + engine compute.
Small, and it is the only way to prove the success path.

---

## STEP 1 — make a throwaway account

Sign up at https://strategy-verdict-lab.lovable.app/signup using a Gmail plus-alias:

  jamesloganmueller+wit5d@gmail.com

The plus-alias delivers to your normal inbox. You WILL need to click a confirmation
link — auto-confirm was turned off in session 7, so an address you cannot read will
strand the test.

Report: whether signup and email confirmation worked at all. /signup is a newly
ported route and has never been exercised. A failure here is a real finding.

## STEP 2 — run one audit

Submit a YouTube link. Prefer a SHORT video (under ~15 minutes) so the transcript
and extraction finish quickly. Any trading video is fine — this stays private, and
the IP gate is on publishing, not on running an audit.

Report: whether it was accepted, and roughly how long until it reached a result.

## STEP 3 — immediately try a second audit

Submit anything again on the same account, without waiting for the first to finish.

Expected: refused with
  "You have used your free strategy audit for this month."

Report:
  a. the exact message shown
  b. whether a second audit appeared in the list (it must not)
  c. whether the message was readable English or a raw code / blank screen

## Read the result correctly

Two outcomes are both PASSES, and they prove different things:

  - Second submission REFUSED  → the reservation and the limit work.
  - Second submission ACCEPTED → only valid if the FIRST audit failed. That is the
    refund working: a failed audit hands the slot back. Say so if it happens, and
    tell me how the first one failed.

A FAIL is: the second submission accepted while the first is still running or
finished successfully. That means the counter is not incrementing.

## STEP 4 — optional check

```sql
SELECT u.email, x.period, x.evaluations_used
FROM public.usage x
JOIN auth.users u ON u.id = x.user_id
ORDER BY u.email;
```

Expected: one row for the throwaway account, current UTC month,
evaluations_used = 1. No row for your own account.

## Cleanup note

This leaves a fourth auth user. The tracker already carries a cleanup row for the two
wit-e2e-test accounts; this one joins it. Do not delete it until the test is reported
— the usage row is the evidence.

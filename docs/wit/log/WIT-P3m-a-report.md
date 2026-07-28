# WIT-P3m-a — handoff addendum: /wit/v1/extract decision + app stage started

1. Gate result: **PASS** — `git checkout main` + `git pull --ff-only` up to date; HEAD ==
   **76d778c** (`WIT-P3m: process hardening — handoff refresh, prompt archive, continuity rules`),
   the P3m process-hardening commit. Proceeded.

2. All three edits applied: **yes**.
   - Edit 1: in RESUME HERE, the sentence beginning "After that: the phase-end Lovable app stage …
     DISABLE_EXEC_ENDPOINTS=1)." was REPLACED with the specified paragraph (engine exposes
     `POST /wit/v1/extract`, superseding WIT-03 §4; anthropic moves to the shipped runtime lock +
     ADR-050 gate; Railway env vars in Jim's lane). Old phrase now absent; new text present.
   - Edit 2: "Where things live" now ends with the appended Lovable-project sentence (`Audit Lab`,
     id 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9, editor URL, front-end-only v1, WIT-0001 seed, Supabase
     not yet created).
   - Edit 3: Open items gained the `* NEW — POST /wit/v1/extract slice pending …` bullet.

3. Commit hash: see below (this commit). CI status: recorded after push below.

4. Anything unexpected: none — docs-only, three edits plus this report and the archived prompt.
   (The Read hook that truncated reads in prior slices did not interfere here; edits were applied
   directly and verified with grep.)

WIT-P3m-a — Completed

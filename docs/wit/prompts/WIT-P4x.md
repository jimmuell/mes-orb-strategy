Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P4x

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — gate
  git remote -v && pwd
  Confirm remote is jimmuell/mes-orb-strategy at the path above. If not, STOP and report.
  git rev-parse HEAD && git rev-parse origin/main
  Both must be e57162f (WIT-P4t). If either differs, STOP and report.
  Do NOT pull, reset, restore or stash. If a git command fails on a stale .git lock
  file, delete the lock and retry once.

TASK — commit and push the session-7 close-out (WIT-P4x)
  The lead engineer wrote 15 close-out files into the working tree today
  (2026-07-30) over the device bridge. This task creates no new content except
  archiving this prompt and your report.

  1. Save this prompt verbatim to docs/wit/prompts/WIT-P4x.md.
  2. Write your REPORT BACK (the three numbered items below, once known) to
     docs/wit/log/WIT-P4x-report.md.
  3. Stage EXACTLY these 17 paths — explicit paths only, never git add -A:
       docs/wit/SESSION-HANDOFF.md
       docs/wit/WillItTrade-PRD-v2.docx
       docs/wit/planning/SESSION-8-OPEN.md
       docs/wit/prompts/WIT-P4s.md
       docs/wit/prompts/WIT-P4s-1.md
       docs/wit/prompts/WIT-P4u.md
       docs/wit/prompts/WIT-P4v.md
       docs/wit/prompts/WIT-P4v-1.md
       docs/wit/prompts/WIT-P4w.md
       docs/wit/prompts/WIT-P4x.md
       docs/wit/log/WIT-P4s-report.md
       docs/wit/log/WIT-P4s-1-report.md
       docs/wit/log/WIT-P4u-report.md
       docs/wit/log/WIT-P4v-report.md
       docs/wit/log/WIT-P4v-1-report.md
       docs/wit/log/WIT-P4w-report.md
       docs/wit/log/WIT-P4x-report.md
     Verify with git diff --cached --name-status that the staged set is exactly
     these 17 and nothing else. Any known LFS-noise modifications and untracked
     files stay untouched and uncommitted. If a listed file is missing, STOP
     and report which.
  4. Commit subject exactly:
       WIT-P4x: session-7 close-out — reviewer desk, verdict rule, public library, PRD v2, security baseline
  5. git push origin main
  6. Confirm HEAD == origin/main and no staged entries remain.

REPORT BACK (exactly this):
  1. New HEAD sha + GitHub commit URL.
  2. The commit's file list (name-status).
  3. Anything that did not match, or "clean".
  Final line, exactly: WIT-P4x — Completed

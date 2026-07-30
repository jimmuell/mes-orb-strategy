Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P4r

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — gate
  git remote -v && pwd
  Confirm remote is jimmuell/mes-orb-strategy at the path above. If not, STOP and report.
  git rev-parse HEAD && git rev-parse origin/main
  Both must be eae132a (WIT-P4o). If either differs, STOP and report.
  Do NOT pull, checkout, reset, restore or stash anything — the working tree holds
  uncommitted session-6 close-out files that this task exists to save.
  If any git command fails on a stale .git lock file, delete the lock file and retry once.

TASK — commit and push the already-staged session-6 close-out (WIT-P4r)
  This task creates NO new content. The session-6 close-out files were staged on
  2026-07-29 but the commit was never made. You are completing that commit.

  1. Save this entire prompt, verbatim from the first Platform: line, to
     docs/wit/prompts/WIT-P4r.md, then stage that one file only:
       git add docs/wit/prompts/WIT-P4r.md
  2. Verify the staged set: git diff --cached --name-status
     It must be EXACTLY these 14 paths and nothing else:
       M  docs/wit/SESSION-HANDOFF.md
       M  docs/wit/reports/data/WIT-0001-primary-trades.csv
       A  docs/wit/log/WIT-P4f-report.md
       A  docs/wit/log/WIT-P4f-1-report.md
       A  docs/wit/log/WIT-P4g-1-report.md
       A  docs/wit/log/WIT-P4n-report.md
       A  docs/wit/log/WIT-P4p-report.md
       A  docs/wit/log/WIT-P4q-report.md
       A  docs/wit/prompts/WIT-P4f-1.md
       A  docs/wit/prompts/WIT-P4g-1.md
       A  docs/wit/prompts/WIT-P4n.md
       A  docs/wit/prompts/WIT-P4p.md
       A  docs/wit/prompts/WIT-P4q.md
       A  docs/wit/prompts/WIT-P4r.md
     If anything else is staged, or any of these is missing, STOP and report the
     actual list. Do not add or unstage anything to force a match. Never git add -A.
     The unstaged modifications to backtest/requirements.txt, dashboard/requirements.txt
     and files under data/raw/ are known LFS noise — leave them untouched and uncommitted.
  3. Commit with subject exactly:
       WIT-P4r: session-6 close-out — handoff rewritten, Lovable reports and prompts archived
  4. git push origin main
  5. Confirm: git rev-parse HEAD equals origin/main after the push, and
     git status --short shows no remaining staged entries.

REPORT BACK (exactly this):
  1. New HEAD sha and the GitHub commit URL.
  2. The full file list of the commit (git show --stat --oneline HEAD, name-status form).
  3. Anything that did not match this prompt, or "clean".
  Final line, exactly: WIT-P4r — Completed

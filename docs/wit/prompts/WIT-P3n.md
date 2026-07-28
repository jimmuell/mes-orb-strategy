Platform:    Claude Code (paste this code into this platform)
Project:     WillItTrade (WIT) — engine repo
Repo:        jimmuell/mes-orb-strategy
Prompt:      WIT-P3n — session-3 close-out: Notion tracker in the continuity rules
Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — gate
  git remote -v && pwd — confirm repo/path as above; if not, STOP.
  git checkout main && git pull --ff-only origin main
  git log --oneline -1 → must be 9c18eaa (WIT-P3m-a). If not, STOP and report.
  git status → clean except the known untracked pine/mes_net_pnl_v2.pine and the
  uncommitted scratchpad/ diagnostic. If other tracked changes, STOP.

TASK — docs only. Four surgical edits to docs/wit/SESSION-HANDOFF.md, then commit.
  Each edit has an exact anchor. If an anchor is not found VERBATIM, STOP and report which
  one — do not guess or approximate.

  1) In "Where things live", append this sentence to the end of that bullet:
  " Business/decision lane + glanceable status: the Notion board **WillItTrade (WIT) —
  Project Tracker** → https://app.notion.com/p/6ccf5af452cc41768441d7dae1a3aca3 (structure
  mirrors the TradingGym tracker; each row's Ref column points back to the repo file or spec
  section behind it)."

  2) In the CONTINUITY RULES list, add a fourth numbered rule after rule 3:
  "  4. **The Notion tracker is READ on session open and UPDATED on session close.** The repo
     stays the engineering source of truth; the tracker owns Jim's lane (data licensing, legal,
     domains, pricing, launch prep) plus cross-cutting status. Reading it on open is the ONLY
     way a session learns what Jim did between sessions — git cannot know that. Updating it on
     close is the LEAD ENGINEER's job (Cowork chat has Notion access; Claude Code does not), so
     a close-out is not complete until both the handoff and the tracker are current."

  3) In "Current state", replace exactly:
     "main = **b4041a1** (WIT-P3e-4) + this P3m docs commit."
     with:
     "main = the WIT-P3n session-3 close-out commit."

  4) In that same section, find the sentence ending
     "→ P3l docs alignment → P3e-4 grounding + status rules."
     and replace its trailing period so it reads
     "→ P3l docs alignment → P3e-4 grounding + status rules → P3m process hardening →
     P3m-a extraction-endpoint decision → P3n close-out."

  Commit (explicit paths only — never git add -A):
    git add docs/wit/SESSION-HANDOFF.md docs/wit/log/WIT-P3n-report.md docs/wit/prompts/WIT-P3n.md
    git commit -m "WIT-P3n: session-3 close-out — Notion tracker read/update in continuity rules"
    git push origin main
    Confirm CI green (gh run list/watch) or report "not checkable".

REPORT BACK (exactly this):
  1. STEP 0 (HEAD 9c18eaa y/n; tree clean y/n).
  2. All four edits applied verbatim (y/n); if any anchor was missing, which.
  3. Commit hash on main; CI status.
  4. Anything unexpected.
  Write this report-back verbatim to docs/wit/log/WIT-P3n-report.md and archive this prompt
  verbatim to docs/wit/prompts/WIT-P3n.md, both staged in the same commit.
  Final line, exactly: WIT-P3n — Completed
  (or WIT-P3n — Partial: <what's left> — never a bare "Completed".)

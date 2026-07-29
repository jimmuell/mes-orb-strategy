Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P4z-1

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — gate
  git remote -v && pwd
  Confirm remote is jimmuell/mes-orb-strategy at the path above. If not, STOP and report.
  git checkout main && git pull --ff-only origin main
  HEAD must be 6f7798f (WIT-P4z). Anything else => STOP, report HEAD.
  Tree clean (known untracked pine file fine). DOCS ONLY — nothing under api/, contract/, or
  schema/ is touched; no LLM calls. This is the one close-out task that did not land in P4z:
  the handoff already ASSERTS that docs/PROMPT_STANDARD.md carries the WIT header blocks, and
  it does not yet. This prompt makes that true.

TASK — align the engine prompt-standard pointer to the canonical doc
  REPLACE docs/PROMPT_STANDARD.md in full with EXACTLY the content between the markers
  (exclusive):
----BEGIN FILE docs/PROMPT_STANDARD.md----
# Prompt Standard (engine — pointer)

The canonical prompt standard lives in **jimmuell/tradinggym → docs/PROMPT_STANDARD.md**,
with **docs/DEPLOY_WORKFLOW.md** as its companion. If this file disagrees with the
canonical doc, the canonical doc wins. This file exists so an engine session that never
opens the tradinggym repo still writes on-standard prompts.

## The header block — every prompt, no exceptions

Five lines at the very TOP of the prompt, each on its own line, with a BLANK LINE after
every one of them (a single newline collapses in a rendered viewer). Nothing precedes
`Platform:` — no title, no "here's the prompt". The whole artifact IS the prompt so it can
be select-all-pasted. Lovable prompts carry all five lines too.

WillItTrade — engine (Claude Code):

  Platform:    Claude Code (paste this code into this platform)

  Project:     WillItTrade (WIT)

  Repo:        jimmuell/mes-orb-strategy

  Prompt:      WIT-<id>

  Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

WillItTrade — app (Lovable agent):

  Platform:    Lovable Project (paste this code into this platform)

  Project:     WillItTrade Web

  Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

  Prompt:      WIT-<id>

  Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

## Body shape

Plain bare labels with the body indented two spaces (four when nested); no divider rules,
no code fences inside the prompt. Order: header -> STEP 0 (Claude Code only) -> TASK ->
deploy/verify (Lovable) -> REPORT BACK.

NO RATIONALE INSIDE A PROMPT. Diagnosis, trade-offs and sequencing live in the chat stream
and in docs/wit/. A prompt carries instructions only.

ONE PROMPT = ONE BUILDER = ONE TASK. Work spanning the engine and the app is two separate
artifacts routed to their owners. Never leave Claude Code and Lovable both holding pending
changes on the same project.

## Claude Code (engine) essentials

- STEP 0 repo-confirmation gate is always first (`git remote -v && pwd`), plus the expected
  HEAD. Nothing is read, edited, run or committed before it passes.
- Stage explicit paths only — never `git add -A`.
- One task per prompt.
- STOP-and-report beats forcing a pass. Goldens are exact equality and are NEVER tuned to
  pass; a golden that disagrees with the spec is escalated for lead ratification.

## Lovable (app: UI, edge functions, SQL) essentials

- Header block, no git gate — Lovable works in its own sandbox.
- Scope tightly: name the exact files/functions/components to touch AND what must not be
  touched.
- State the deploy trigger explicitly. An edge function edited by the agent auto-deploys; a
  GitHub push does NOT deploy a function or apply a migration. Frontend changes are visible
  in Preview on edit and reach the live URL only via Publish -> Update.
- **ACCESS-CONTROL SQL IS NEVER RUN BY THE AGENT OR BY CLAUDE.** Row-level-security policies,
  grants and role changes are supplied as RAW SQL that JIM runs in the SQL editor after a
  joint review. Data cleanup and verification SQL are likewise raw SQL for Jim to run.
  (Breached once on 2026-07-28: the WIT back-office RLS policies were written into a Lovable
  task and applied by the agent. The resulting policies were verified correct after the fact,
  but the route was off-standard. This line is why.)
- State what "done" looks like and where it is verified (Preview vs Published URL).

## Completion marker

Every report-back ends with a single final line, exactly:

  <Prompt name> — Completed

or `<Prompt name> — Partial: <what's left>`. Never a bare "Completed". The name matches the
`Prompt:` header line.

## WIT's ratified exceptions to the canonical doc

Approved by Jim 2026-07-28. These are deliberate and apply to WIT prompts only; everything
else in the canonical doc governs unchanged.

1. **Commit subjects lead `WIT-<id>:`**, not `ADR-0NN:`. WIT's slice ids are the project's
   spine and its history already runs on them.
2. **Commits go DIRECTLY to main**, not via a PR. The lead engineer reviews the pushed diff
   against the GitHub clone after the fact, which is the review gate for this project.
3. **REPORT BACK is fuller than the canonical three lines** and is committed verbatim to
   `docs/wit/log/<Prompt>-report.md` as part of the same commit. The log is WIT's process
   record; the three-line summary is what the lead relays to Jim in chat.
4. **Authored prompts are archived to `docs/wit/prompts/<Prompt>.md`** at authoring time. A
   prompt in `prompts/` with no matching report in `log/` is a PENDING slice.
----END FILE----
  Archive this prompt verbatim to docs/wit/prompts/WIT-P4z-1.md; add a row for
  WIT-P4z-1-report.md to docs/wit/log/README.md.
  Suite (docs only): cd api && BACKTEST_API_KEY=k python -m pytest -q
  Expect 268 passed / 0 failed / 2 skipped. Anything else => STOP.
  Stage explicit paths only — never git add -A.
  Commit subject MUST be exactly:
    WIT-P4z-1: prompt standard aligned to canonical — WIT header blocks, Lovable rules, ratified exceptions
  Push directly to main; record CI.

REPORT BACK — docs/wit/log/WIT-P4z-1-report.md, staged with the commit:
  1. STEP 0 result and the HEAD you started from.
  2. Grep proof: both WIT header blocks present; the access-control-SQL line present; all four
     ratified exceptions present; the old "Engine essentials:" line absent.
  3. Suite counts; commit hash; CI status.
  Final line, exactly: WIT-P4z-1 — Completed

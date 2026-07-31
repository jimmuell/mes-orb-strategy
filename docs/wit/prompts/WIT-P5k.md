Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P5k

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — gate
  git remote -v && pwd
  Confirm the remote is jimmuell/mes-orb-strategy at the path above. If not, STOP and report.
  git rev-parse HEAD && git rev-parse origin/main
  Both must be b050530 (WIT-P5j). If either differs, STOP and report.
  Do NOT pull, reset, checkout or stash. Never run git add -A.

TASK — read-only: blast radius of the value_area_pct units defect

  THIS TASK CHANGES NO BEHAVIOUR. Write no fix. Change no fixture, golden, threshold,
  prompt, schema, contract or engine source file. Findings only. A correction here can
  move golden results, and goldens are never tuned — founder ratification is required
  before anything changes.

  ESTABLISHED BY WIT-P5j: production configs carry setup_entry.params.value_area_pct = 70.
  api/wit/volume_profile.py computes the value-area target as value_area_pct x total
  volume, so a value of 70 makes the target unreachable, the band expands to the whole
  opening range, and VAH/VAL equal the range High/Low (value_area_fraction = 1.000 on
  2020-06-01). Every production audit therefore tested an OPENING-RANGE break, not a
  value-area break. The lead has confirmed value_area_pct appears in neither
  contract/strategy-config.v1.json nor schema/strategy-template.v1.json as a typed field —
  it occurs only inside a free-text description. The unit was never specified.

  1. ORIGIN. Trace where value_area_pct enters a wire config. State whether the number
     comes from the extracted template (an LLM-supplied value), from a baked default in
     api/wit/mapper.py, or from both depending on path. If there is a default, give its
     value and file/line. State whether an audit whose source never mentions a value area
     still receives one.

  2. INTENDED UNIT. From api/wit/volume_profile.py, state precisely what the code requires
     for a standard 70% value area — 0.70 or 70 — and quote the computation. Then state
     which side is non-conforming: the producer emitting 70, or the consumer treating it
     as a fraction. Note that the field NAME says pct while the consumer wants a fraction;
     say which of the two you would change and why, considering that the contract is the
     published interface.

  3. THE PUBLISHED REPORT. docs/wit/reports/WIT-0001-volume-profile-orb.md and its data
     under docs/wit/reports/data/ are the founding published audit. Determine which value
     that run used, and by what code path it was produced — the wire/mapper path or a
     standalone research script. State plainly whether the published WIT-0001 numbers
     describe a 70% value-area break or a full opening-range break, and whether its prose
     claims a value area. If the run predates the wire path and the value cannot be
     recovered, say so rather than inferring.

  4. FIXTURE AND GOLDEN INVENTORY. List every fixture, golden, test and shipped artifact
     that contains value_area_pct or otherwise depends on the value-area width, with the
     value each carries. For each, state whether it currently encodes the unreachable-target
     interpretation.

  5. MAGNITUDE. Without changing any file, run the CONFIG A from WIT-P5j twice over the
     full window 2008-01-02 to 2026-04-09 — once as-is with value_area_pct 70, and once
     with 0.70 — and report both sets of the six headline metrics side by side, plus the
     percentage change in trades and net_pnl. This is the number the founder needs to judge
     the correction, so report it precisely and do not round.

  6. GOLDEN IMPACT. State exactly which goldens would move under a correction and by how
     much, or "none". If any anchor fixture encodes the broken interpretation, say so
     explicitly and name it. Do NOT regenerate or edit any golden.

  7. RECOMMENDATION. One paragraph: which side you would change, what the contract should
     say, whether existing production audits should be re-run, and whether the published
     WIT-0001 report needs a correction notice. Recommend only — implement nothing.

  8. Write the findings to docs/wit/log/WIT-P5k-report.md. Save this prompt verbatim to
     docs/wit/prompts/WIT-P5k.md. Stage EXACTLY those two paths, verify with
     git diff --cached --name-status, and commit with subject exactly:
       WIT-P5k: value_area_pct units defect — blast radius, read-only findings
     Then git push origin main. Leave the known LFS noise untouched.

  9. Run the test suite and report the counts. Baseline 308 passed / 0 failed / 2 skipped,
     and it must be unchanged — this task alters no code.

REPORT BACK
  1. Where value_area_pct originates, and any baked default.
  2. The intended unit, the quoted computation, and which side is non-conforming.
  3. What the published WIT-0001 run actually tested, and whether its prose claims a
     value area.
  4. The fixture/golden inventory.
  5. The 70 versus 0.70 comparison table with percentage changes.
  6. Which goldens move, or "none", and whether any anchor fixture is affected.
  7. Your recommendation.
  8. New HEAD sha, GitHub commit URL, staged file list.
  9. Suite counts.
  Final line, exactly: WIT-P5k — Completed

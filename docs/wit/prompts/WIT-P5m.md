Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P5m

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — gate
  git remote -v && pwd
  Confirm the remote is jimmuell/mes-orb-strategy at the path above. If not, STOP and report.
  git rev-parse HEAD && git rev-parse origin/main
  Both must be cb0c621 (WIT-P5l). If either differs, STOP and report.
  Do NOT pull, reset, checkout or stash. Never run git add -A.

TASK — give value_area_pct an explicit unit and enforce it at the mapper

  Founder-ratified 2026-07-31 on the evidence in docs/wit/log/WIT-P5l-report.md. This is
  steps 1 and 2 of the ratified sequence. Steps 3 to 5 (fixture prose, cache invalidation,
  re-running the affected audits) are separate slices — do NOT attempt them here.

  SCOPE — modify ONLY these paths:
    contract/strategy-config.v1.json            modify
    schema/strategy-template.v1.json            modify
    api/wit/mapper.py                           modify
    api/wit/vocab.py                            modify ONLY if the chosen idiom requires it
    tests (new or extended, engine test tree)   modify

  DO NOT TOUCH: api/wit/volume_profile.py — its fraction semantics is the standard
  Market-Profile convention, matches every fixture and matches the published WIT-0001, and
  is explicitly NOT the thing being changed. Also do not touch vp_orb_runner.py,
  api/wit/analysis.py, any file under api/_shipped/ by hand, any fixture, any golden, any
  extraction prompt, or anything under docs/wit/ other than the report and prompt archive.

  1. Declare the unit in both contracts.
     value_area_pct becomes a NAMED, TYPED property wherever setup_entry params are
     described: type number, exclusiveMinimum 0, maximum 1, with a description stating in
     words that it is a FRACTION — 0.70 means seventy percent — and that a value greater
     than 1 is treated as a percentage and normalized by the mapper with a disclosed
     assumption.
     Apply the same change to contract/strategy-config.v1.json and, where the machine param
     channel is described, to schema/strategy-template.v1.json.
     If setup_entry.params is currently an untyped object, add the named property without
     making the object closed — do NOT set additionalProperties false on that object in this
     task, because other params flow through it.
     The drift gate over api/_shipped/ must be satisfied by whatever the repo's established
     procedure is. Report which procedure you used. Do not hand-edit the shipped copies if a
     sync step exists.

  2. Enforce it in the mapper, at exactly one boundary.
     In api/wit/mapper.py where the D2 machine params are read and value_area_pct is emitted
     (currently around line 238), apply this rule and nothing more:
       value is a number and 0 < value <= 1        -> pass through unchanged
       value is a number and 1 < value <= 100      -> divide by 100, and record a disclosed
                                                      assumption code exactly
                                                      D2_value_area_normalized
       value is null, absent, non-numeric, a string, boolean, NaN, infinite, <= 0, or > 100
                                                   -> REJECT as an invalid config using the
                                                      mapper's EXISTING typed error idiom
     Do not invent a new exception type. Use whatever the mapper already raises for
     unsupported or structurally invalid input, and report which you used and why.
     The rejection must be a clean typed failure that reaches the caller as an error
     envelope — never a TypeError from downstream arithmetic. WIT-P5l confirmed that null
     and the string "0.70" currently crash the engine with a TypeError; that must no longer
     be reachable through the mapper.

  3. Disclose it.
     D2_value_area_normalized must appear in the emitted assumptions_applied list on any run
     where normalization occurred, alongside the existing codes E1, F4, F5, H1, H2,
     initial_capital, J1_window, B3_granularity. It must NOT appear when the value was
     already a fraction. Follow whatever mechanism those existing codes use.

  4. Tests — add, do not modify existing ones.
     Cover at minimum: 0.7 and 0.70 pass through with NO assumption code; 1 passes through
     unchanged with no code; 70 becomes 0.7 WITH the code; 100 becomes 1.0 with the code;
     and each of null, absent, "0.70" as a string, true, 0, -1, 101, NaN and infinity is
     rejected with the typed error rather than crashing.
     Add one test asserting that the normalization boundary is the mapper and not the
     engine — i.e. that volume_profile.py still receives and requires a fraction.
     Do not add a test that pins any golden metric value.

  5. Prove the goldens did not move.
     Run the full suite. Then explicitly confirm that every existing golden and fixture
     comparison is byte-identical to before this change, and say how you confirmed it.
     Baseline is 308 passed / 0 failed / 2 skipped; the count will RISE by the number of
     tests you added. Report both numbers. Zero failures, and no existing test edited.
     If any golden moves, STOP, revert nothing, and report — that would contradict WIT-P5l
     and needs founder review before anything is committed.

  6. Save this prompt verbatim to docs/wit/prompts/WIT-P5m.md and write a report to
     docs/wit/log/WIT-P5m-report.md. Stage EXACTLY the files you changed plus those two,
     verify with git diff --cached --name-status, and commit with subject exactly:
       WIT-P5m: value_area_pct typed as a fraction, normalized and disclosed at the mapper
     Then git push origin main. Leave the known LFS noise untouched.

REPORT BACK
  1. The exact contract and schema text you added for value_area_pct, and how the
     api/_shipped/ drift gate was satisfied.
  2. The mapper rule as implemented, with file and line, and which existing error idiom you
     used for rejection and why.
  3. Confirmation that null and the string "0.70" can no longer reach downstream arithmetic.
  4. The list of tests added and their results.
  5. Suite counts before and after, and your evidence that no golden moved.
  6. New HEAD sha, GitHub commit URL, staged file list.
  7. Anything you could not do within scope, or "clean".
  Final line, exactly: WIT-P5m — Completed

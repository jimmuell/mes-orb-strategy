Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P5n

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — gate
  git remote -v && pwd
  Confirm the remote is jimmuell/mes-orb-strategy at the path above. If not, STOP and report.
  git rev-parse HEAD && git rev-parse origin/main
  Both must be cb0c621 (WIT-P5l). If either differs, STOP and report.
  WIT-P5m was authored but deliberately NOT run; it is superseded by this prompt, which
  covers its scope plus the rest of the field surface. Its archive file may already be
  present untracked at docs/wit/prompts/WIT-P5m.md — commit it with this slice and note in
  the report that it was superseded and never executed.
  Do NOT pull, reset, checkout or stash. Never run git add -A.

TASK — one specification for every engine parameter, enforced at the boundary and
       disclosed in the result

  Founder-ratified 2026-07-31. The governing principle, and the tie-breaker for every
  judgement call in this task: AN AUDIT MUST BE TRUE TO WHAT WAS ACTUALLY TESTED. A value
  that is silently ignored, silently reinterpreted, or accepted when it is meaningless, is
  a defect regardless of whether the numbers look plausible.

  Established defects this task closes, all evidenced in docs/wit/log/ (P5i, P5j, P5k, P5l):
    exits.stop.ref is enumerated in the contract but never read; any value, including
      nonsense, is silently dropped and the runner always uses the point of control.
    exits.stop.ticks accepts a negative value, which places the stop on the wrong side of
      the level and produces a plausible but broken audit.
    setup_entry.params.value_area_pct has no declared unit; production emits 70 where the
      engine requires a fraction, silently converting a value-area strategy into an
      opening-range strategy and understating the headline loss by 51%.
    null or a non-numeric value_area_pct crashes the engine with a TypeError rather than
      failing cleanly.
    No field anywhere in either contract carries a minimum or a maximum.
    Many further fields are baked to constants and never honoured — P5i lists
      exits.stop.mode, exits.target.mode, risk_controls.max_trades_per_day,
      risk_controls.reentry, filters.regime, filters.calendar, instrument.*, data.dataset,
      data.granularity_needed, session.force_flat, setup_entry.level, exits.management.
    Class-B params spike_eff, pullback_p, spike_giveback_cap and regime_fixed_er carry the
      same untyped-number exposure (P5l risk table).

  THREE PILLARS. Deliver all three or STOP and report — a partial delivery leaves the
  system in a worse state than it is now.

  PILLAR 1 — SPECIFY
    Every field the engine accepts gets a declared type, unit, allowed range and, where
    applicable, an enumerated set of allowed values, in contract/strategy-config.v1.json,
    contract/event-study-config.v1.json and schema/strategy-template.v1.json.
    Derive each from what the code ACTUALLY requires, not from the field name. Where the
    engine's real requirement differs from the name, the description must say so in words
    — value_area_pct in particular must state that it is a FRACTION where 0.70 means
    seventy percent.
    Give exits.stop.ticks a positive-only constraint. Give value_area_pct
    exclusiveMinimum 0 and maximum 1. Constrain every count, price, tick and cost field to
    its real domain. Cover the Class-B params listed above.
    Mark every field the engine does NOT honour with an explicit description stating that
    it is declared but not applied in v1. Do not remove them.
    Report a complete table of every field with its declared type, unit, range and whether
    it is honoured or baked.

  PILLAR 2 — ENFORCE
    A config that does not conform must be refused with a clear typed error, never run.
    Validate at TWO points against the same contract: inside the mapper, on the wire config
    it produces before returning it; and at the engine's inbound boundary for
    /wit/v1/runs, so anything bypassing the mapper is also caught.
    Rejections surface as the existing error-envelope shape with a message naming the
    offending field and why. Never a bare TypeError from downstream arithmetic.
    On the dependency question: determine whether adding a JSON Schema validator library is
    permitted under the shipped runtime lock and the ADR-050 gate. If it is, use it and say
    so. If it is NOT, implement a minimal validator inside api/wit/ that reads the shipped
    contract and checks type, enum, range and required — and say why you took that route.
    Do not add a dependency without confirming the gate.

  PILLAR 3 — DISCLOSE
    Two new disclosure paths, both feeding the existing assumptions_applied mechanism that
    already carries E1, F4, F5, H1, H2, initial_capital, J1_window and B3_granularity:
      a. NORMALIZATION. value_area_pct in (1, 100] is divided by 100 and the code
         D2_value_area_normalized is recorded. A value already in (0, 1] passes through
         with no code. Anything else is rejected under Pillar 2.
      b. NOT HONOURED. Where the extracted template specifies a value for a field the
         engine bakes rather than honours, and that value differs from the baked constant,
         record a disclosure code naming the field. Choose a consistent code shape, state
         it in the report, and apply it uniformly.
    This is the pillar that makes the audit true to what was tested. Without it a report
    can still describe a strategy the engine did not run.

  ORDERING — normalization runs BEFORE validation, or validation runs on the normalized
  config. Getting this backwards would reject every real audit that says "70%".

  SCOPE — you may modify: the two contract files, the template schema, api/wit/mapper.py,
  api/wit/vocab.py, api/server.py at the inbound boundary, a new validator module under
  api/wit/ if needed, requirements files only if the gate permits, and the engine test tree.

  DO NOT TOUCH: api/wit/volume_profile.py — its fraction semantics is the standard
  convention, matches every fixture and matches the published WIT-0001, and is correct.
  Do not touch vp_orb_runner.py's trading logic, any fixture, any golden, any extraction
  prompt, or anything under docs/wit/ beyond this prompt's archive and report.
  Do not hand-edit api/_shipped/ if a sync procedure exists; use it and report which.

  GOLDENS — a hard stop. The anchor fixtures use conforming values, so validation should
  pass them untouched. BUT Pillar 3 may add entries to assumptions_applied, and if any
  golden asserts that list exactly, it will move. If ANY golden moves for ANY reason:
  STOP, do not commit, and report exactly which golden, what changed and why. That is a
  founder decision, not yours and not the lead's.

  TESTS — add, never modify existing ones. Cover at minimum: each enum field rejects an
  out-of-set value; value_area_pct at 0.7, 1, 70, 100, null, "0.70", 0, -1, 101, NaN and
  infinity; a negative stop.ticks is rejected; a not-honoured field carrying a
  non-default value produces its disclosure code; a conforming config produces no spurious
  codes; and the engine's inbound boundary rejects a non-conforming config that never went
  through the mapper.

  VERIFY — run the full suite. Baseline 308 passed / 0 failed / 2 skipped; the count rises
  by the tests you add. Zero failures. No existing test edited. State how you satisfied
  yourself that every golden is byte-identical.

  ARCHIVE AND COMMIT — save this prompt verbatim to docs/wit/prompts/WIT-P5n.md, write
  docs/wit/log/WIT-P5n-report.md, stage exactly the files you changed plus those two plus
  docs/wit/prompts/WIT-P5m.md, verify with git diff --cached --name-status, and commit with
  subject exactly:
    WIT-P5n: every engine parameter specified, enforced at the boundary and disclosed
  Then git push origin main. Leave the known LFS noise untouched.

  IF THIS IS TOO LARGE to complete cleanly in one pass, STOP after Pillar 1 and report —
  a complete specification with no enforcement is still useful and safe. Do not deliver
  half of Pillar 2 or half of Pillar 3.

REPORT BACK
  1. The complete field table: type, unit, range, honoured or baked.
  2. How you satisfied the shipped-contract drift gate, and the dependency decision with
     its justification.
  3. The two validation points, with file and line, and the rejection envelope shape.
  4. The disclosure codes you introduced and the rule for each.
  5. Tests added and their results.
  6. Suite counts before and after, and your evidence that no golden moved. If any moved,
     report and do NOT commit.
  7. New HEAD sha, GitHub commit URL, staged file list.
  8. Anything you stopped short of, and why, or "clean".
  Final line, exactly: WIT-P5n — Completed
  or, if you stopped after Pillar 1: WIT-P5n — Partial: <what's left>

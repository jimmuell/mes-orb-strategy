Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P4h

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — repo confirmation gate

  Run `git remote -v && pwd && git log --oneline -3`. Confirm the remote is
  jimmuell/mes-orb-strategy, the path is the local path above, and HEAD is the
  WIT-P4g report commit ("WIT-P4g: report + lead verification ..."). If HEAD is
  anything else, STOP and report what you found. Read nothing, edit nothing, run
  nothing and commit nothing before this passes.

  Then read docs/wit/log/WIT-P3q-adjudication.md and backtest/MEMORY.md before
  touching extraction code.

TASK

  Close a contract defect that makes the extractor offer a mode placement the mapper
  rejects. The first live end-to-end submission failed on it.

  What happened, verified in production on 2026-07-29: a Class A extraction set field
  D1's mode to `va_high_low`. `map_template` returned UNSUPPORTED_CONSTRUCT
  ("D1: mode 'va_high_low' not supported in engine v1") and the evaluation ended failed.

  The extractor was not wrong. In contract/modes.md the `entry.level` row declares its
  Field as `D3/D1` with token `va_high_low`, and api/wit/extraction/prompt.py's
  _vocab_block renders that verbatim as a legal placement: "entry.level (field D3/D1):
  mode ∈ {va_high_low}". The mapper has no entry.level dimension at all — FIELD_MODE_VOCAB
  reads D1 strictly as bias {vp_value_area_break, orb_break, none} and D3 strictly as
  trigger {bar_close_beyond_level, bar_body_beyond_level}. So the prompt offers a token
  neither field will accept. modes.md's own rule — "the vocabulary must never
  over-promise" — is being broken by modes.md itself.

  In engine v1 the entry level is NOT independently specified: vp_orb_runner derives
  VAH/VAL from the D2 volume profile. entry.level therefore has no consumer and must not
  be offered to the extractor.

  Do all four parts in one commit.

  1. contract/modes.md — stop advertising an unconsumable placement

    In the Class A table, change the `entry.level` row so its Field cell no longer names
    D3 or D1. Use an em dash, and state in the Runner-realization cell that in v1 the
    entry level is derived from the D2 volume profile (VAH/VAL) and is not independently
    specified. Change NOTHING else in the file — no other row, no token, no dagger.

  2. api/wit/extraction/prompt.py — never offer a dimension no field can carry

    _vocab_block must skip any dimension whose Field cell does not name at least one real
    template field id (the A1…K1 pattern). Derive this from the parsed Field cell; do not
    hardcode "entry.level". A dimension with a supported token but no carrier field is a
    contract defect, not something to render.

  3. NEW conformance test — this is the durable part of the slice

    Add a test asserting that the extraction prompt and the mapper cannot disagree again:
    for every dimension _vocab_block offers, every field id in its Field cell must exist
    in mapper.FIELD_MODE_VOCAB, and every supported token offered for that dimension must
    be a member of FIELD_MODE_VOCAB[field]. The test must FAIL on the current
    contract/modes.md and PASS after part 1. Prove both: run it before your edit and
    paste the failure, then after and paste the pass.

  4. Verify no collateral damage

    Run the full suite. The two anchor fixtures carry no `va_high_low` token, so the
    extraction and mapper goldens must be unaffected. If ANY golden moves, STOP and
    report — do not tune a golden, do not touch a fixture, and do not alter any
    threshold. Fixtures are FINAL under WIT-P3q.

  Explicitly out of scope: the extraction system prompt's wording, ensemble behavior,
  completeness scoring, thresholds, and both fixtures. This slice changes a contract
  table, one generator guard, and adds a test — nothing about extraction quality.

  Stage explicit paths only; never `git add -A`. Commit subject:
  `WIT-P4h: contract conformance — entry.level had no carrier field, prompt offered an unmappable placement`
  Push to origin main and report the commit hash and URL.

REPORT BACK

  Include: the modes.md row before and after; the _vocab_block guard as written; the new
  test's failure output before part 1 and its pass output after; full suite counts before
  and after; confirmation that no fixture, golden or threshold changed; the commit hash
  and GitHub URL; anything you noticed but did not change. Commit the whole report
  verbatim to docs/wit/log/WIT-P4h-report.md as part of the same commit. End with exactly
  one line:

  WIT-P4h — Completed

  or

  WIT-P4h — Partial: <what's left>

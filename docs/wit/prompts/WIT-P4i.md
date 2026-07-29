Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P4i

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — repo confirmation gate

  Run `git remote -v && pwd && git log --oneline -3`. Confirm the remote is
  jimmuell/mes-orb-strategy, the path is the local path above, and HEAD is dee4286
  (WIT-P4h). If HEAD is anything else, STOP and report what you found. Read nothing,
  edit nothing, run nothing and commit nothing before this passes.

  Then read docs/wit/WIT-02-strategy-template-schema.md §5 (Default Assumption Policy)
  and docs/wit/log/WIT-P3q-adjudication.md before touching anything.

TASK

  Implement the §5 Default Assumption Policy in the mapper, and stop one silent
  substitution. Second live end-to-end failure, 2026-07-29: a Class A extraction left E1
  with mode null and params null (the video never states position sizing — most do not),
  so the wire config carried sizing {mode: null, value: null} and the adapter raised
  UNSUPPORTED_CONSTRUCT "E1: mode 'None:None' not supported in engine v1".

  WIT-02 §5 says sizing defaults to 1 contract when unspecified. Nothing implements it.
  The mapper LABELS fields as assumed — the `assumed()` helper appends B3, E1, F4, F5,
  H1, H2 to assumptions_applied — but never SUPPLIES the defaulted values, so an
  unspecified field reaches the wire config as nulls. The ratified anchor fixture
  WIT-T-0001 hides this: it was hand-authored with the §5 values already filled in
  (E1 mode fixed_contracts / value 1, H1 0.62, H2 1, F4 force_flat, F5 stop_first) even
  though every one of those fields has status unspecified. Hand-fed fixtures pass; live
  extractions do not.

  Defaults are deterministic policy and belong in code, not in a model's output. Do NOT
  change the extraction prompt, the fixtures, or any golden.

  Touch api/wit/mapper.py and its tests only.

  1. A §5 defaults table, applied narrowly

    Add an explicit table transcribed from WIT-02 §5, keyed by field:

      E1 → mode fixed_contracts, params {value: 1}
      H1 → params {commission_per_side: 0.62}
      H2 → params {slippage_ticks: 1}
      F4 → mode force_flat
      F5 → mode stop_first

    Apply a default ONLY when BOTH hold: the field's status is "unspecified", AND the
    specific mode or param key is null or absent. A default must NEVER overwrite a value
    the source specified or the extractor implied, and must never fire on a field whose
    status is specified or implied. Apply per key, not per field: an unspecified H1 that
    already carries a commission keeps it.

    Do not add defaults for any field not listed above. B3 stays in the assumed() list
    exactly as it is — its granularity is a data-layer disclosure, not a wire value, and
    this slice does not change it. D3 and D4 get no defaults: Class A already requires
    them, and a null there must fail loudly, not be guessed.

  2. Keep assumptions_applied's SHAPE unchanged

    It stays a list of field-id strings, exactly as today, and a field that receives a
    §5 default must still appear in it — that is already true via assumed(). Do not
    change the element format, ordering, or the initial_capital entry. The two anchor
    goldens assert config equality and must not move.

  3. Stop the silent substitution in the adapter

    In strategy_config_to_vporb, `entry_mode = "close" if trigger == "bar_close_beyond_level"
    else "body"` silently turns a NULL trigger into a body-entry backtest — a fabricated
    result presented as real. Raise UnsupportedConstruct(field="D3", mode=trigger) when
    the trigger is null or is not one of the two declared tokens. Audit the rest of that
    adapter for the same pattern and report any other silent null-to-default coercion you
    find; fix the ones that would produce a fabricated result, and report any you judge
    out of scope rather than changing them quietly.

  4. Tests

    Add mapper tests covering: an unspecified E1 with null mode/params defaults to
    fixed_contracts/1 and appears in assumptions_applied; a SPECIFIED E1 with a different
    value is NOT overwritten; unspecified H1/H2 default to 0.62 and 1; a partially-filled
    unspecified H1 keeps its own value; a null D3 trigger now raises UnsupportedConstruct
    rather than producing a body-entry config.

    Then run the full suite. Both anchor goldens must be BYTE-IDENTICAL to before — the
    fixture already carries these values, so defaults must be a no-op there. If ANY
    golden moves, STOP and report; do not tune a golden, touch a fixture, or alter a
    threshold. Fixtures are FINAL under WIT-P3q.

  Stage explicit paths only; never `git add -A`. Commit subject:
  `WIT-P4i: mapper applies the WIT-02 §5 default assumptions; null entry trigger no longer silently becomes a body entry`
  Push to origin main and report the commit hash and URL.

REPORT BACK

  Include: the defaults table as written; the exact guard conditions under which a
  default fires; the adapter change and every other silent coercion you found (fixed or
  reported); each new test and what it proves; full suite counts before and after;
  explicit confirmation that both anchor goldens are unchanged and that no fixture,
  threshold or extraction prompt was touched; the commit hash and GitHub URL. Commit the
  report verbatim to docs/wit/log/WIT-P4i-report.md in the same commit. End with exactly
  one line:

  WIT-P4i — Completed

  or

  WIT-P4i — Partial: <what's left>

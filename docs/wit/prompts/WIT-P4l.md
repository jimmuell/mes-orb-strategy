Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P4l

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — repo confirmation gate

  Run `git remote -v && pwd && git log --oneline -3`. Confirm the remote is
  jimmuell/mes-orb-strategy, the path is the local path above, and HEAD is a56ebe2
  (WIT-P4k). If HEAD is anything else, STOP and report what you found. Read nothing,
  edit nothing, run nothing and commit nothing before this passes.

  Then read WIT-02 §5 (Default Assumption Policy — the volume-profile clause) and
  api/wit/vp_orb_runner.py lines 110-135 and 240-255.

TASK

  Close an unsafe branch in the runner and make the profile data-granularity a lab choice
  rather than an unvalidated free string from the model.

  Fifth live end-to-end failure, 2026-07-29 — the deepest yet. Extraction, mapping and
  the run all succeeded; the job died inside the daily signal loop with
  `AttributeError: 'RangeIndex' object has no attribute 'normalize'` at
  `day_open = one_min_open[one_min_open.index.normalize() == pd.Timestamp(date)]`.

  Cause, from the stored config: D2 params carried `granularity: "ticks_per_row_1"`. The
  runner branches on exactly two values and handles neither case safely:

    run_vp_orb:        `if one_min_open is None and cfg.vp_granularity == "1min":` load
                       the 1-minute opening data; ELSE assign an EMPTY placeholder
                       DataFrame — which has a RangeIndex.
    _opening_profile:  `if cfg.vp_granularity == "5min":` use 5-minute bars; ELSE fall
                       through to the 1-minute path and call `.index.normalize()`.

  An unrecognised token therefore skips the loader AND takes the 1-minute path, so the
  code indexes an empty RangeIndex frame as if it were timestamped. Any value that is
  neither "1min" nor "5min" crashes here — the placeholder makes the failure look like a
  pandas bug rather than a rejected input.

  The model's token is not nonsense, it is a category error: the video says to build the
  profile at one tick per row, which is the profile's PRICE-row size (the engine fixes
  that at TICK_SIZE), not the DATA time-resolution this field means.

  Which resolution WIT computes a profile from is WIT's methodological choice, not the
  source's. WIT-02 §5 already states it: volume-profile and intrabar features are
  "computed from finest licensed data; approximation disclosed". Implement that.

  1. Mapper — D2 granularity becomes a §5 lab default

    Treat the template's D2 params.granularity as advisory: use it ONLY when it is
    exactly "1min" or "5min". For anything else — null, absent, or an unrecognised string
    like "ticks_per_row_1" — apply the §5 policy and emit "1min" (the finest available
    data), recording the disclosure in assumptions_applied the same way the other §5
    defaults are recorded in WIT-P4i.

    This is not a silent substitution of strategy semantics: the profile's price-row size
    is unchanged and untouched, and the substituted value is disclosed. Say so in the
    code comment.

  2. Runner — no unreachable branch, no placeholder frame that crashes later

    Make both granularity branches exhaustive. An unrecognised vp_granularity must raise
    a clean typed error at the top of run_vp_orb, before any data is loaded — reuse the
    error style introduced for the empty window in WIT-P4j, and state in the report which
    code you used.

    Remove the failure mode where an empty placeholder DataFrame is handed to the
    1-minute path. If the 1-minute frame is required and is empty or lacks a
    DatetimeIndex, that is a typed error too, never an AttributeError from pandas.

  3. Tests

    Cover: an unrecognised granularity in the template maps to "1min" and is disclosed; an
    explicit "5min" is honored and NOT disclosed; an explicit "1min" is honored; the
    runner raises the typed error rather than AttributeError when vp_granularity is
    unrecognised; and a required-but-empty 1-minute frame raises the typed error rather
    than AttributeError.

    Run the full suite. Both anchor goldens must be BYTE-IDENTICAL — the fixture carries
    granularity "1min", so the default must be a no-op there. If ANY golden moves, STOP
    and report; do not tune a golden, touch a fixture, or alter a threshold.

  Then audit the rest of the adapter and runner for the SAME shape — a value from the
  template that selects a code path, where an unrecognised value falls through to a
  branch that assumes a different one. Report every instance you find with file and line.
  Fix only the ones that would crash or fabricate a result; list the rest for a later
  slice rather than changing them quietly.

  Stage explicit paths only; never `git add -A`. Commit subject:
  `WIT-P4l: profile granularity is a §5 lab default; unrecognised granularity fails typed instead of crashing on an empty frame`
  Push to origin main and report the commit hash and URL.

REPORT BACK

  Include: the mapper rule as written and how it is disclosed; the runner guards and the
  exact error code raised; the results of the fall-through audit, with file and line for
  every instance and which you fixed; each new test and what it proves; full suite counts
  before and after; explicit confirmation that both anchor goldens are unchanged and no
  fixture, threshold or extraction prompt was touched; the commit hash and GitHub URL.
  Commit the report verbatim to docs/wit/log/WIT-P4l-report.md in the same commit. End
  with exactly one line:

  WIT-P4l — Completed

  or

  WIT-P4l — Partial: <what's left>

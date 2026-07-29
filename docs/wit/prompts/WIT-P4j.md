Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P4j

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — repo confirmation gate

  Run `git remote -v && pwd && git log --oneline -3`. Confirm the remote is
  jimmuell/mes-orb-strategy, the path is the local path above, and HEAD is 82921c7
  (WIT-P4i). If HEAD is anything else, STOP and report what you found. Read nothing,
  edit nothing, run nothing and commit nothing before this passes.

  Then read docs/wit/WIT-02-strategy-template-schema.md §2 (sections B and J) and
  docs/wit/log/WIT-P3q-adjudication.md.

TASK

  Supply the two LAB-OWNED fields the extractor cannot know, and turn an empty-data crash
  into an honest error. Third live end-to-end failure, 2026-07-29: the run reached the
  backtest and died with `IndexError: index 0 is out of bounds for axis 0 with size 0` at
  `data_first = df.index[0]` in run_backtest_long_short — the loaded frame had zero rows.

  The stored wire config from that run shows why, and shows a second defect beside it:

    data.window   = {"start": null, "end": null}
    instrument    = {"symbol": "NQ", "proxy_for": "NASDAQ", "tick_size": 0.25,
                     "tick_value": null}

  Both fields are WIT's to fill, not the source's. WIT-02 §2 says section J is "filled by
  WIT, not the guru" — a video can never state WIT's test window — and v1 always tests on
  ES with MES economics, disclosing the source's own market as a proxy. The ratified
  anchor fixture WIT-T-0001 has both hand-filled (J1 window 2016-04-10 → 2026-04-09; B1
  mode futures_proxy, symbol ES, tick_size 0.25, tick_value 1.25, proxy_for NQ), so
  hand-fed goldens pass while live extractions emit nulls and the source's own symbol.
  This is the same class of defect as WIT-P4i: lab policy left to a model that cannot
  know it.

  Do NOT change the extraction prompt or any fixture. Deterministic lab policy goes in
  code.

  Touch api/wit/mapper.py, api/wit/vp_orb_runner.py (or the narrowest file owning the
  empty-frame guard), and their tests.

  1. J1 test window — WIT supplies it when absent

    When data.window.start or .end is null after mapping, resolve it to the FULL range of
    the available dataset rather than a hardcoded date pair, so it never goes stale as
    data extends. Record "J1_window" in assumptions_applied ONLY when WIT supplied it; a
    window the template already carries is used verbatim and is not disclosed as an
    assumption.

    Lead decision, apply as stated: the v1 default test window is ALL available data, not
    a trailing 10 years. Maximal evidence, self-updating, and no arbitrary constant.

  2. B1 instrument — always the lab's instrument, the source's market as proxy

    v1 tests ES with MES economics regardless of what the source traded. Normalize the
    emitted instrument block:

      - symbol is always "ES"; tick_size 0.25; tick_value 1.25. A null tick_value must
        never reach the wire config.
      - proxy_for carries the SOURCE's market when it is not ES — take the template's
        proxy_for, or its symbol when that names something other than ES ("NQ" and
        "NASDAQ" in the failing run both mean the same thing: not ES).
      - when the source genuinely traded ES, proxy_for is null.

    Never emit the source's symbol as the tested symbol. A report that says it tested NQ
    when it ran ES bars is a false disclosure, which matters more than the crash.

  3. Empty frame → an honest error, never an IndexError

    Before `data_first = df.index[0]`, guard the loaded frame: when it has zero rows,
    raise a clean, typed engine error naming the resolved window and the dataset, so the
    callback carries a real code and message instead of a pandas traceback. Use the
    existing error vocabulary — INVALID_CONFIG unless a more specific code already
    exists; do not invent a new top-level code without saying so in the report.

  4. Tests

    Cover: a null window resolves to the dataset's full range and is disclosed as
    J1_window; a template-supplied window is used verbatim and NOT disclosed; a non-ES
    source instrument emits symbol ES with proxy_for set and a non-null tick_value; an
    ES source emits proxy_for null; an empty frame raises the typed error rather than
    IndexError.

    Then run the full suite. Both anchor goldens must be BYTE-IDENTICAL — the fixture
    already carries a window and ES economics, so both normalizations must be no-ops
    there. If ANY golden moves, STOP and report; do not tune a golden, touch a fixture,
    or alter a threshold. Fixtures are FINAL under WIT-P3q.

  Report, but do NOT change: the failing run's B3 granularity came through as
  "ticks_per_row_1", which is not a value this engine models. Say whether anything
  consumes it and whether it needs its own slice.

  Stage explicit paths only; never `git add -A`. Commit subject:
  `WIT-P4j: WIT supplies the J1 test window and the lab instrument; empty data window fails honestly`
  Push to origin main and report the commit hash and URL.

REPORT BACK

  Include: how the window is resolved and where the dataset range comes from; the
  instrument normalization rules as written; the empty-frame guard and the exact error it
  raises; each new test and what it proves; full suite counts before and after; explicit
  confirmation that both anchor goldens are unchanged and no fixture, threshold or
  extraction prompt was touched; your finding on B3 granularity; the commit hash and
  GitHub URL. Commit the report verbatim to docs/wit/log/WIT-P4j-report.md in the same
  commit. End with exactly one line:

  WIT-P4j — Completed

  or

  WIT-P4j — Partial: <what's left>

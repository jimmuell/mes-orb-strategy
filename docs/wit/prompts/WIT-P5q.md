Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P5q

Local path:  /Users/jameslmueller/dev/mes-orb-strategy

STEP 0 — gate
  cd /Users/jameslmueller/dev/mes-orb-strategy && git remote -v && pwd
  Confirm the remote is jimmuell/mes-orb-strategy and pwd is the Local path above. If not, STOP
  and report.
    git pull && git rev-parse HEAD
  HEAD must become ae1f5ea889e7fcd8e472a29ef988b3031e0db203 (WIT-P5p). If it does not, STOP and
  report — do not proceed on the wrong tree.
  Activate the venv you built for WIT-P5o/P5p (or rebuild one against api/.python-version 3.12.13
  with api/requirements.txt and api/requirements-dev.txt). With BACKTEST_API_KEY set (any value),
  run the full suite and record the counts. Baseline is 350 passed / 0 failed / 2 skipped (your
  machine — a sandbox missing the pulled LFS raw-1min file will show 349/3, same known,
  environment-only difference every prior prompt has hit; the total is 352 either way). If your
  baseline differs by more than that one known skip, STOP and report.
  Then record the BEFORE anchor from api/, one line:
    python -c "from wit.config import VPORBConfig; from wit.vp_orb_runner import run_vp_orb; k=run_vp_orb(VPORBConfig()).kpis; print(k['net_profit'], k['total_trades'], k['win_rate'], k['profit_factor'], k['actual_start_date'], k['actual_end_date'])"
  Its last line must be exactly:
    -5976.890049456466 2561 34.322530261616556 0.9027249232666907 2016-04-11 2026-04-09
  Do NOT pull again after this, reset, checkout or stash. Never run git add -A.

TASK — a second dataset needs a genuinely different bar granularity, not just a different file

  BACKGROUND. Jim wants to add a real 1-minute dataset alongside the existing 5-minute one, so
  TSSE's dataset dropdown (already live, WIT-FRONTEND-05-datasets) offers a real choice. The
  1-minute PARQUET ALREADY EXISTS — api/data/ES_full_1min_rth.parquet, built by
  api/tools/build_1min_rth_parquet.py from the raw text Jim holds, already on the Railway volume
  (it's the BUILT-IN dataset's own opening_1min file today). No new conversion is needed. What's
  missing is code: today every DatasetSpec is silently assumed to carry 5-MINUTE primary bars —
  nothing in the catalog says otherwise, and one piece of the runner hardcodes a 5-minute-shaped
  cutoff. Making a dataset whose PRIMARY bars are 1-minute actually correct requires:

  1. THE CATALOG MUST SAY WHAT GRANULARITY A DATASET'S BARS ARE — api/wit/datasets.py

     Add a required field `bars_granularity` to DatasetSpec: the granularity of the dataset's OWN
     `bars_5min` file (the field is misnamed from WIT-P5o but stays as-is — do not rename it, that
     is a bigger churn than this prompt is scoped for). Valid values: "1min" | "5min" — reuse
     exactly the vocabulary mapper.py's _VP_GRANULARITIES already uses for the unrelated
     vp_granularity concept, for consistency, but define your own tuple in datasets.py (do not
     import across modules for this).

     Add "bars_granularity" to _REQUIRED_KEYS and _STRING_KEYS. Validate its value is one of
     ("1min", "5min") in _validate_entry, failing loud via the existing _fail() pattern (name the
     bad value, same style as every other validation in this file) for anything else — an entry
     missing the key must fail exactly like a missing "symbol" does today; an entry with e.g.
     "15min" must fail exactly like a non-numeric point_value does today.

     Add `bars_granularity="5min"` to BUILT_IN_DEFAULT — that is what it has always actually been;
     this only makes it explicit.

  2. THE END-OF-DAY BAR CUTOFF IS HARDCODED FOR 5-MINUTE BARS — api/wit/vp_orb_runner.py

     load_5min() (line ~125-132) filters RTH bars using the module constant
     `_RTH_LAST_START = dt.time(15, 55)` — "last RTH 5-min bar start (closes 16:00)". That is
     correct ONLY for 5-minute bars. For a 1-minute-primary dataset, the last legitimate RTH bar
     starts at 15:59 (also closes 16:00) — using 15:55 would silently drop each day's last 4
     minutes of 1-minute bars, including whatever bar the force-flat/time-exit lands on. That is
     exactly the kind of silent-wrong-window defect this engine has repeatedly refused to ship
     (WIT-P4j's EmptyDataWindow, WIT-P4l's UnsupportedGranularity) — fix it before any 1-minute
     dataset goes live, not after.

     Add a small derivation (e.g. `_rth_last_bar_start(spec: DatasetSpec) -> dt.time`) that
     returns time(15, 59) when spec.bars_granularity == "1min" and time(15, 55) otherwise. Use it
     in load_5min in place of the bare module constant. The 5-minute dataset's behaviour — and the
     WIT-0001 anchor — must not move by even one bar; prove it in VERIFY.

  3. A DATASET WITH NO TRUE 5-MINUTE BARS CANNOT HONESTLY RUN vp_granularity="5min" —
     api/wit/vp_orb_runner.py, run_vp_orb()

     cfg.vp_granularity ("1min" | "5min", WIT-T-0001 §J2) picks how the OPENING volume profile is
     built — it is independent of which file backs the primary trading bars, and today that's fine
     because the one dataset that exists has true 5-minute primary bars either way. Once a dataset
     whose bars_granularity is "1min" exists, requesting vp_granularity="5min" against it has
     nothing real to build a "5-minute robustness" profile FROM — the "5min" branch of
     _opening_profile would run against `five_day`, which for that dataset actually holds 1-minute
     bars, silently building the profile from finer data than the "5min" label claims and defeating
     the point of the robustness comparison (WIT-T-0001 §J2's whole reason for having both modes).

     Add a new exception (same file, same style as DatasetEconomicsUnsupported):

       class VpGranularityUnsupportedForDataset(Exception):
           code = "UNSUPPORTED_CONSTRUCT"
           # dataset {id!r}'s bars_granularity is {bars_granularity!r}; vp_granularity="5min" has
           # no true 5-minute bars to build from for this dataset — refusing rather than silently
           # building the "5min" profile from finer data under the wrong label.

     Raise it in run_vp_orb, at the top, after the existing UnsupportedGranularity check (so a
     genuinely bogus vp_granularity value still gets that error first) and before any data load:
     `if cfg.vp_granularity == "5min" and spec.bars_granularity != "5min": raise
     VpGranularityUnsupportedForDataset(spec.id, spec.bars_granularity, cfg.vp_granularity)`.

     Unaffected, must keep working exactly as today: any dataset with bars_granularity=="5min" +
     either vp_granularity value (today's only real dataset, unchanged). A 1-minute-primary
     dataset + vp_granularity=="1min" (uses that dataset's own opening_1min file — same code path
     as today, just parameterized by spec, already correct, no change needed there).

  4. EXPOSE THE NEW FIELD — api/server.py, GET /wit/v1/datasets (WIT-P5p, ~line 2132)

     Add "bars_granularity": spec.bars_granularity to the per-entry response dict, alongside the
     existing fields. The endpoint's whole purpose is describing everything true about a dataset;
     leaving this out once it exists would be the same kind of omission WIT-P5p refused to make
     for economics_supported. No TSSE/app change required by this prompt — this is additive.

  5. DO NOT TOUCH

     The built-in dataset's files, or write/commit any datasets.json anywhere in the repo — the
     catalog override file is a Railway-volume-only runtime artifact (WIT-P5o's design), never
     checked into git; adding the real 1-minute entry to production is Jim's ops step, not this
     prompt's. api/wit/event_study.py's own _ET_RTH_START/_ET_RTH_LAST_1MIN constants — already
     correctly scoped to 1-minute data, unrelated to this bug. api/wit/mapper.py's map_template
     (Class-A/B) hardcoded "dataset" strings — a separate code path from TSSE's own wire-config
     compiler, out of scope. Any fixture, golden, or contract file. api/wit/volume_profile.py —
     already granularity-agnostic, needs no change (verified while researching this prompt).

  GOLDENS — a hard stop. If the WIT-0001 anchor moves for ANY reason: STOP, do not commit, and
  report exactly what changed.

  TESTS — add, never modify existing ones. Follow tests/test_datasets.py's existing tmp_path +
  _write_catalog + _entry() pattern (you will need to add bars_granularity to that file's _entry()
  helper — that is a test-fixture change, not a production one, and is expected). Cover at
  minimum: bars_granularity missing from an entry fails loud naming it (mirrors the existing
  missing-key test for "symbol"); an invalid value (e.g. "15min") fails loud naming it; the
  built-in default's bars_granularity is "5min"; load_5min's cutoff derivation — a synthetic
  1-minute dataset with a bar timestamped 15:59 is INCLUDED, the same synthetic data under a
  bars_granularity="5min" entry is EXCLUDED at 15:59 (proves the derivation reads the spec, not a
  hardcoded always-15:59); the new guard — a synthetic 1-minute-primary dataset +
  vp_granularity="5min" raises VpGranularityUnsupportedForDataset with code
  UNSUPPORTED_CONSTRUCT; the same dataset + vp_granularity="1min" does NOT raise it; a
  5-minute-primary dataset (built-in or synthetic) is unaffected at either vp_granularity value.
  Also add one end-to-end proof against the REAL shipped file: a temporary catalog entry pointing
  both bars_5min and opening_1min at the real api/data/ES_full_1min_rth.parquet,
  bars_granularity="1min", run_vp_orb over a SHORT window (e.g. one month — keep it fast, do not
  run the full 18-year history in a unit test) completes without error and returns a plausible
  (non-crashing, typed) kpis dict — proof the wiring works against real data, not only synthetic
  tmp_path fixtures.

  VERIFY
    Run the full suite. Baseline as recorded in STEP 0, rising by the tests you add. Zero
    failures, no existing test edited.
    Re-run the STEP 0 anchor command and confirm its last line is unchanged:
      -5976.890049456466 2561 34.322530261616556 0.9027249232666907 2016-04-11 2026-04-09
    Then, separately from the unit tests, run one real proof by hand and paste the output in the
    report: point WIT_ENGINE_DATA_DIR at a tmp dir with a datasets.json entry
    (id "ES_1min_rth_verify" or similar, bars_granularity "1min") whose bars_5min AND opening_1min
    both name the real api/data/ES_full_1min_rth.parquet (symlinked or copied in), and call
    run_vp_orb with that dataset id over a short recent window (e.g. start_date="2026-01-01",
    end_date="2026-04-09") — paste the resulting kpis' net_profit/total_trades/win_rate/
    actual_start_date/actual_end_date.

  ARCHIVE AND COMMIT — save this prompt verbatim to docs/wit/prompts/WIT-P5q.md, write
  docs/wit/log/WIT-P5q-report.md containing your REPORT BACK verbatim, stage exactly the files you
  changed plus those two, verify with git diff --cached --name-status, and commit with subject
  exactly:
    WIT-P5q: dataset-aware RTH cutoff + granularity guard for a real 1-minute dataset
  Then git push origin main. Leave the known LFS noise untouched.

REPORT BACK
  1. HEAD sha you gated on, BEFORE suite counts, BEFORE anchor line.
  2. The exact datasets.py diff: new field, validation rule, BUILT_IN_DEFAULT update.
  3. The exact vp_orb_runner.py diff: the cutoff derivation (before/after of load_5min) and the
     new guard (before/after of run_vp_orb's top section), and the new exception class verbatim.
  4. The one-line server.py diff exposing bars_granularity.
  5. Tests added and their results, INCLUDING the real-data end-to-end proof's actual pasted kpis
     output (not just "passed").
  6. Suite counts before and after, the AFTER anchor line (must match BEFORE exactly).
  7. Your evidence the existing 5-minute dataset's behaviour did not move at all (not just "ran
     the suite" — name what specifically proves it, e.g. which existing test still passing
     unmodified covers load_5min at the 5-minute cutoff).
  8. New HEAD sha, GitHub commit URL, staged file list.
  9. Anything you stopped short of, and why, or "clean".
  Final line, exactly: WIT-P5q — Completed
  or, if you stopped: WIT-P5q — Partial: <what's left>

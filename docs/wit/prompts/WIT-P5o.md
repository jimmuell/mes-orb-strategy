Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P5o

Local path:  /Users/jameslmueller/dev/mes-orb-strategy

STEP 0 — gate
  This repo is NOT expected to be cloned on this machine yet. Check, then clone if needed:
    ls -d /Users/jameslmueller/dev/mes-orb-strategy 2>/dev/null || echo MISSING
    git clone https://github.com/jimmuell/mes-orb-strategy.git /Users/jameslmueller/dev/mes-orb-strategy
  Full clone, never shallow. Then, from inside that directory:
    git remote -v && pwd
  The remote must be jimmuell/mes-orb-strategy and pwd must be the Local path above. If either
  does not match, STOP and report.
    git rev-parse HEAD && git rev-parse origin/main
  Both must be ce56c724cf9278d1856d4deba00b250eeb0249ab (WIT-P5n). If either differs, STOP and report.
    ls -l api/data/ES_full_5min_continuous_UNadjusted.parquet api/data/ES_full_1min_rth.parquet
  Both must exist and be tens of megabytes. A pointer-sized file means the checkout is incomplete —
  STOP and report.
  Build the environment against api/.python-version (3.12.13) in a venv, install api/requirements.txt
  and api/requirements-dev.txt, then run the FULL suite once BEFORE ANY EDIT and record the counts.
  Baseline is 319 passed / 0 failed / 2 skipped. If your baseline differs, STOP and report — do not
  start work on a tree that is not already green.
  Then record the BEFORE anchor. Run this from api/ with the venv active, as ONE line:
    python -c "from wit.config import VPORBConfig; from wit.vp_orb_runner import run_vp_orb; k=run_vp_orb(VPORBConfig()).kpis; print(k['net_profit'], k['total_trades'], k['win_rate'], k['profit_factor'], k['actual_start_date'], k['actual_end_date'])"
  Its last line must be exactly:
    -5976.890049456466 2561 34.322530261616556 0.9027249232666907 2016-04-11 2026-04-09
  If it does not, STOP and report — the tree is not the tree this prompt was written against.
  Do NOT pull, reset, checkout or stash. Never run git add -A.

TASK — make data.dataset real: one catalog, one resolver, two files per dataset

  The engine currently ignores the dataset named in every config and always reads two hardcoded
  filenames. This task makes the declared dataset actually select the data, while changing nothing
  at all about the dataset that runs today.

  GOVERNING PRINCIPLE, and the tie-breaker for every judgement call in this task: an audit must be
  true to what was actually tested. Silently substituting a different dataset, or running one
  instrument's bars under another instrument's contract economics, is a defect even when the
  resulting numbers look plausible.

  A DATASET IS A PAIR OF FILES, not one. The engine reads a 5-minute continuous file for the
  trading bars (it filters regular hours out of that file itself, in code) and a 1-minute
  regular-hours file for the opening range only. A catalog entry therefore resolves an id to TWO
  filenames. Do not invent a third file, and do not add a 5-minute regular-hours file — it would be
  a redundant second copy of something the engine already derives.

  1. NEW MODULE — api/wit/datasets.py

    DatasetSpec: a frozen dataclass with id, label, bars_5min, opening_1min, symbol, point_value,
    tick_size, and an optional description defaulting to "".

    BUILT-IN DEFAULT, which must describe exactly the pair running today:
      id            ES_5min_continuous
      bars_5min     ES_full_5min_continuous_UNadjusted.parquet
      opening_1min  ES_full_1min_rth.parquet
      symbol        MES
      point_value   5.0
      tick_size     0.25
    Give it a human label; the app will show it to users.

    OPTIONAL CATALOG FILE — datasets.json, read from the directory returned by
    resolve_engine_data_dir() in api/wit/data_paths.py. That is the Railway volume in production
    (WIT_ENGINE_DATA_DIR=/data) and api/data in a checkout, so a dataset can be added by uploading
    files and editing one JSON file, with no redeploy. Shape:
      {"version": 1, "datasets": [ {one object per DatasetSpec field}, ... ]}
    Validate on load: version present and equal to 1; datasets a list; every entry carrying every
    required key with the right type; point_value and tick_size numeric and strictly positive;
    filenames plain names with no path separators and no "..";  ids unique and non-empty.
    An entry whose id equals the built-in id OVERRIDES the built-in. Everything else is added.

    FAILURE RULES, stated deliberately:
      Catalog file ABSENT — the documented normal case today. The built-in default is the whole
      catalog. No warning, no error.
      Catalog file PRESENT but malformed or failing validation — a LOUD typed error naming the file
      and the offending entry or key. Never fall back to the built-in: falling back would run ES
      data under some other dataset's name, which is the exact defect this task exists to remove.
      Entry present but its files are NOT on disk — the catalog still loads; that entry is simply
      not available. Resolving it raises a typed error naming the missing file.

    API of the module:
      resolve(dataset_id) -> DatasetSpec. None or empty string resolves to the built-in default.
      An UNKNOWN id raises a typed error carrying code DATA_UNAVAILABLE whose message names the id
      and lists the ids that ARE available. Do NOT silently fall back to the default for an unknown
      id — a user who asks for gold and gets the S&P is the worst outcome this system can produce.
      available() -> the specs whose BOTH files exist on disk. This is the single source of truth a
      later slice will expose over HTTP; do NOT add an endpoint in this prompt.
      Cache the parsed catalog cheaply, but re-resolve on each call if that is simpler to reason
      about — correctness over micro-optimisation.

  2. THE ECONOMICS GUARD — what makes this slice safe to ship on its own

    Contract economics are still global and hardcoded to MES: POINT_VALUE and TICK_SIZE in
    api/wit/config.py, MES_POINT_VALUE and MES_TICK_SIZE in api/engine/engine.py, and
    Instrument(symbol="MES") in api/wit/analysis.py and api/server.py. Per-dataset economics are a
    separate slice and are NOT in this prompt's scope.

    So: DatasetSpec carries point_value, tick_size and symbol now, so the catalog file format does
    not change later — but if a resolved dataset's point_value or tick_size differs from the
    engine's baked values, the run must be REFUSED at the top of the run with a typed error, code
    UNSUPPORTED_CONSTRUCT, whose message says the dataset's contract economics are not applied by
    this engine version and names both values. A carried-but-ignored economics field is exactly the
    declared-but-not-applied defect the previous slice spent itself removing; refusing is honest,
    silently running is not.

  3. THREAD THE SPEC THROUGH THE RUNNER — api/wit/vp_orb_runner.py

    Add a dataset field to VPORBConfig in api/wit/config.py, defaulting to "ES_5min_continuous",
    so an unspecified dataset behaves exactly as today.
    load_5min, load_1min_opening and dataset_date_range must read the filenames from a resolved
    DatasetSpec rather than the module constants _NAME_5MIN and _NAME_1MIN. dataset_date_range must
    take the dataset id and cache per id, not globally — a single-entry cache keyed on nothing would
    hand one dataset's date range to another.
    run_vp_orb resolves the spec ONCE from cfg.dataset, applies the guard in section 2, and passes
    the spec down. The EmptyDataWindow and EmptyOpeningData messages must name the resolved file,
    not a constant.
    Keep the module-level PARQUET_5MIN and PARQUET_1MIN names resolving to the built-in default —
    api/server.py imports PARQUET_5MIN for provenance and must not break.

    PROVENANCE MUST TELL THE TRUTH. api/wit/analysis.py builds a provenance block that reports
    "dataset" and "vp_source" as the basenames of those two module constants — so a run against any
    other dataset would report the ES filenames. Change those two lines to report the RESOLVED
    dataset: its id plus the two filenames actually read. For the built-in default the reported
    values must come out byte-identical to today. This is the only change permitted in analysis.py —
    leave its economics alone.

  4. EVENT STUDY — api/wit/event_study.py

    Route its 1-minute read through the catalog resolver too, so no filename is hardcoded anywhere,
    but resolve it to the BUILT-IN DEFAULT in this slice. Note the trap: the Class-B mapper emits a
    literal data.dataset of "ES_1min_continuous", which is not a catalog id and would fail loudly if
    you wired it through. Leave that literal alone, leave event studies on the default, and say so
    plainly in the report — wiring Class B to the catalog is a later slice, not this one.

  5. MAPPER AND CONTRACT — api/wit/mapper.py, contract/strategy-config.v1.json

    data.dataset becomes HONOURED. Pass the wire value into VPORBConfig(dataset=...), and remove
    (("data", "dataset"), "ES_5min_continuous") from _BAKED_NOT_HONOURED so it no longer emits
    notapplied_data_dataset. Update the field description in the contract. The drift gate is a
    byte-identical copy test (api/tests/test_data_paths.py) over api/_shipped/contract/, so the
    edited file must be mirrored there exactly; state in the report how you did it and that the gate
    is green. The description must state that the value must match an id in the engine's dataset
    catalog and that an unknown id fails the run rather than falling back.
    Leave data.granularity_needed exactly as it is. Leave instrument.symbol baked and disclosed as
    it is — the symbol becomes real in the economics slice, not this one.

  6. DO NOT TOUCH

    Any trading logic in vp_orb_runner.py beyond the data-resolution lines. api/wit/volume_profile.py.
    Any fixture, any golden, any extraction prompt. The economics constants and Instrument objects in
    engine.py, config.py, analysis.py or server.py. Anything under docs/wit/ beyond this prompt's
    archive and its report. Do not add a new third-party dependency — the runtime lock and the
    ADR-050 audit gate govern; json from the standard library is all this task needs.

  GOLDENS — a hard stop. Every fixture already declares dataset "ES_5min_continuous", which resolves
  to the built-in default, so nothing should move. If ANY golden moves for ANY reason: STOP, do not
  commit, and report exactly which golden and what changed. Likewise, if any EXISTING test asserts
  the notapplied_data_dataset disclosure, do NOT edit that test — STOP and report it. Goldens and
  existing tests are never tuned to pass.

  TESTS — add, never modify existing ones. Cover at minimum: the built-in default resolves with no
  catalog file present; a valid catalog file adds an entry and an entry with the built-in id
  overrides it; a malformed catalog raises rather than falling back (bad version, missing key, wrong
  type, zero or negative point_value, a filename containing a path separator, duplicate ids); an
  unknown id raises with the available ids named; an entry whose files are missing is excluded from
  available() and raises on resolve; a dataset whose economics differ from the baked values is
  refused by the guard; dataset_date_range returns per-dataset ranges rather than one cached range;
  and a config with no dataset specified behaves identically to today.

  VERIFY
    Run the full suite. Baseline 319 passed / 0 failed / 2 skipped, rising by the tests you add.
    Zero failures, no existing test edited.
    Re-run the STEP 0 anchor command and confirm its last line is the SAME six values, exactly:
      -5976.890049456466 2561 34.322530261616556 0.9027249232666907 2016-04-11 2026-04-09
    Then prove the picker actually picks. Build a temp directory holding symlinks (or copies) of the
    two parquets plus a datasets.json that registers a SECOND id — a different id, pointing at those
    same two files. Point WIT_ENGINE_DATA_DIR at that directory, run the same config with
    dataset set to the second id, and confirm it returns the same six values: the same data reached
    through a different name, which is the picker working. Then run it once more with a THIRD id that
    is in no catalog and confirm it fails loudly with the available ids named. Show both commands and
    their output in the report. Delete the temp directory; commit nothing from it.

  ARCHIVE AND COMMIT — save this prompt verbatim to docs/wit/prompts/WIT-P5o.md, write
  docs/wit/log/WIT-P5o-report.md containing your REPORT BACK verbatim, stage exactly the files you
  changed plus those two, verify with git diff --cached --name-status, and commit with subject
  exactly:
    WIT-P5o: dataset catalog resolves an id to its two files, honoured end to end
  Then git push origin main. Leave the known LFS noise untouched.

REPORT BACK
  1. Where the repo was cloned, the HEAD sha you gated on, and your BEFORE suite counts and anchor
     line.
  2. The datasets.json shape you settled on, quoted as a worked example with two entries, and the
     exact validation rules you enforce on it.
  3. Every file and function that used to name a parquet filename, and what it reads now.
  4. The economics guard: where it fires, the error code and the message text.
  5. The mapper and contract change, and how you satisfied the shipped-contract drift gate.
  6. Tests added and their results.
  7. Suite counts before and after, the AFTER anchor line, and the two-id proof with its output.
  8. Your evidence that no golden moved. If any moved, report and do NOT commit.
  9. New HEAD sha, GitHub commit URL, staged file list.
  10. Anything you stopped short of, and why, or "clean".
  Final line, exactly: WIT-P5o — Completed
  or, if you stopped: WIT-P5o — Partial: <what's left>

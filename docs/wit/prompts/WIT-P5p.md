Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P5p

Local path:  /Users/jameslmueller/dev/mes-orb-strategy

STEP 0 — gate
  cd /Users/jameslmueller/dev/mes-orb-strategy && git remote -v && pwd
  Confirm the remote is jimmuell/mes-orb-strategy and pwd is the Local path above. If not, STOP
  and report.
    git pull && git rev-parse HEAD
  HEAD must become 23afb227788a4e3fd6bb8420b1cd395691afac3c (WIT-P5o). If it does not, STOP and
  report — do not proceed on the wrong tree.
  Activate the venv you built for WIT-P5o (or rebuild one against api/.python-version 3.12.13 with
  api/requirements.txt and api/requirements-dev.txt). With BACKTEST_API_KEY set (any value — the
  existing local .env or ci-test-key), run the full suite and record the counts. Baseline is
  344 passed / 0 failed / 2 skipped. If your baseline differs, STOP and report.
  Then record the BEFORE anchor from api/, one line:
    python -c "from wit.config import VPORBConfig; from wit.vp_orb_runner import run_vp_orb; k=run_vp_orb(VPORBConfig()).kpis; print(k['net_profit'], k['total_trades'], k['win_rate'], k['profit_factor'], k['actual_start_date'], k['actual_end_date'])"
  Its last line must be exactly:
    -5976.890049456466 2561 34.322530261616556 0.9027249232666907 2016-04-11 2026-04-09
  Do NOT pull again after this, reset, checkout or stash. Never run git add -A.

TASK — an engine endpoint listing what's actually on the volume, and an honest provenance line
       for every run

  WIT-P5o built the dataset catalog (api/wit/datasets.py) and made data.dataset honoured end to
  end, but the app still has no way to ask the engine what datasets exist — Lovable's dropdown
  today reads "No data sets imported yet" because nothing calls it. And WIT-P5o's own report
  flagged a leftover honesty gap it correctly left out of scope: api/server.py's provenance block
  for a completed backtest still names the BUILT-IN filenames (_VPORB_PARQUET, imported at module
  load) no matter which dataset the run actually used. This prompt closes both, together, because
  they're the same seam — the endpoint's whole purpose is telling the app the truth about what
  data exists, and the provenance line telling the truth about what data a specific run used.

  GOVERNING PRINCIPLE (unchanged from WIT-P5o): the app must never be able to claim a dataset the
  engine doesn't have, and a run's own record of itself must never name data other than what it
  actually read.

  1. NEW ROUTE — GET /wit/v1/datasets in api/server.py

    Same auth as every other /wit/v1/* route: dependencies=[Depends(verify_wit_key)] (see
    wit_get_run at api/server.py:2102 for the pattern). Read-only, no request body.

    Import wit.datasets and call datasets.available() — the specs whose both files already exist
    on disk (api/wit/datasets.py's available()). Do NOT call resolve() for this — available() is
    the one that silently excludes anything with missing files rather than raising, which is
    exactly right for a listing endpoint.

    For each available spec, also resolve its date range via
    vp_orb_runner.dataset_date_range(spec.id) (already caches per id from WIT-P5o) so the app can
    show real coverage instead of a hardcoded label — this is the Step 5 half of the original plan
    (docs/wit/prompts/WIT-P5o's follow-on note) and closes TSSE-PRE-3 on the app's tracker.

    Response body, 200:
      {"datasets": [
        {"id": ..., "label": ..., "description": ..., "symbol": ..., "point_value": ...,
         "tick_size": ..., "economics_supported": true|false,
         "date_range": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}},
        ...
      ]}
    "economics_supported" is true iff point_value == wit.config.POINT_VALUE and tick_size ==
    wit.config.TICK_SIZE — the same comparison run_vp_orb's economics guard (vp_orb_runner.py,
    DatasetEconomicsUnsupported) already makes. Compute it the same way here; do not duplicate the
    threshold as a separate literal. Include an entry whose economics are unsupported in the list
    (so the app can show it as present-but-disabled) rather than omitting it — omitting it would
    make the "no data.dataset the engine doesn't have" guarantee a lie in the other direction: the
    app wouldn't know it exists at all.

    If datasets.available() or dataset_date_range() raises anything (it shouldn't, by contract,
    but a corrupt parquet is possible), catch it per-entry and drop that one entry from the
    response rather than 500ing the whole endpoint — a dataset with a broken file should look
    ABSENT, not take down the listing for every other dataset. Log what you dropped and why in the
    report; do not silently swallow it in the code without a comment saying so.

  2. HONEST PROVENANCE — api/server.py, _backtest_result (around line 1882)

    _backtest_result(res, config_hash) already receives `res`, the vp_orb_runner.RunResult, which
    carries `res.config` — a VPORBConfig, which carries `res.config.dataset` (WIT-P5o). Replace
    the current `os.path.basename(_VPORB_PARQUET)` argument with the RESOLVED dataset: import
    wit.datasets, call datasets.resolve(res.config.dataset), and pass its id and bars_5min filename
    through, mirroring exactly what WIT-P5o already did in api/wit/analysis.py's provenance block
    (dataset_id + dataset, not just dataset). Update `_provenance()`'s signature/callers
    accordingly — it currently takes one `dataset` string; decide whether to add a second
    `dataset_id` parameter or fold both into one call, and say which you chose and why in the
    report. The event_study path (_event_study_result, _ES_PARQUET_1MIN) is UNCHANGED — WIT-P5o
    deliberately left event studies pinned to the built-in dataset, so its provenance is already
    accurate and stays exactly as it is.

    The _VPORB_PARQUET import at server.py:1745 can stay (other code may still reference it) but
    _backtest_result must stop USING it for provenance. If nothing else in the file reads
    _VPORB_PARQUET after your change, say so in the report — do not remove the import speculatively
    if you're not certain nothing else needs it; check with grep first.

  3. DO NOT TOUCH

    api/wit/datasets.py, api/wit/vp_orb_runner.py, api/wit/mapper.py, api/wit/config.py,
    api/wit/analysis.py, api/wit/event_study.py — WIT-P5o already did this seam's work in those
    files; this prompt only adds a read endpoint and fixes one provenance call site in server.py.
    Any fixture, golden, or contract file. The WitRunRequest/WitBudget models or the run-submission
    path (/wit/v1/runs POST) beyond what section 2 requires.

  GOLDENS — a hard stop. Nothing about how a run EXECUTES changes in this prompt, only what a
  completed run's provenance block reports and a new read-only listing endpoint. If any golden or
  the WIT-0001 anchor moves for ANY reason: STOP, do not commit, and report exactly what changed.

  TESTS — add, never modify existing ones. Cover at minimum: GET /wit/v1/datasets with no bearer
  token (401) and a bad one (403), matching the existing pattern for the other /wit/v1/* routes;
  a successful call returns the built-in dataset with economics_supported true and a real
  date_range; a temporary second catalog entry with mismatched point_value appears in the list
  with economics_supported false rather than being omitted; a catalog entry whose files are
  missing does NOT appear (available() already guarantees this — assert the endpoint doesn't
  re-add it); and a completed backtest's provenance block names the dataset actually used, proven
  by running with a second temporary dataset id (same pattern as WIT-P5o's two-id proof) and
  asserting the provenance dataset_id differs from the built-in's.

  VERIFY
    Run the full suite. Baseline 344 passed / 0 failed / 2 skipped, rising by the tests you add.
    Zero failures, no existing test edited.
    Re-run the STEP 0 anchor command and confirm its last line is unchanged:
      -5976.890049456466 2561 34.322530261616556 0.9027249232666907 2016-04-11 2026-04-09
    Then hit the new endpoint for real (not just the test client) — start the server locally
    (or use TestClient directly, whichever is faster to show in the report) with WIT_ENGINE_SERVICE_KEY
    set, curl GET /wit/v1/datasets with a valid bearer token, and paste the actual JSON response in
    the report. Also paste the 401 and 403 responses for a missing/bad token.

  ARCHIVE AND COMMIT — save this prompt verbatim to docs/wit/prompts/WIT-P5p.md, write
  docs/wit/log/WIT-P5p-report.md containing your REPORT BACK verbatim, stage exactly the files you
  changed plus those two, verify with git diff --cached --name-status, and commit with subject
  exactly:
    WIT-P5p: dataset listing endpoint + honest backtest provenance
  Then git push origin main. Leave the known LFS noise untouched.

REPORT BACK
  1. HEAD sha you gated on, BEFORE suite counts, BEFORE anchor line.
  2. The full response shape you settled on for GET /wit/v1/datasets, with a real worked JSON
     example (built-in dataset only is fine if that's all that's on the volume).
  3. How economics_supported is computed and where, confirming it reuses the same comparison as
     vp_orb_runner's guard rather than a second literal.
  4. What you did with entries whose files or date-range read fail, and why.
  5. The exact _provenance()/_backtest_result change: file, line numbers, before/after signature.
     Confirm _VPORB_PARQUET's import is either still used elsewhere (name where) or no longer used
     (say so plainly — do not remove it unless you checked).
  6. Tests added and their results.
  7. Suite counts before and after, the AFTER anchor line (must match BEFORE exactly).
  8. The live curl/TestClient output: success (200) with real data, 401, and 403.
  9. Your evidence nothing about run execution or any golden moved.
  10. New HEAD sha, GitHub commit URL, staged file list.
  11. Anything you stopped short of, and why, or "clean".
  Final line, exactly: WIT-P5p — Completed
  or, if you stopped: WIT-P5p — Partial: <what's left>

# WIT-P5p — dataset listing endpoint + honest backtest provenance

## 1. HEAD sha, BEFORE baseline, BEFORE anchor

`git remote -v`/`pwd` matched. `git pull` — already up to date. `git rev-parse HEAD` →
`23afb227788a4e3fd6bb8420b1cd395691afac3c` (WIT-P5o) — matches exactly.

Reused the venv built for WIT-P5o (`api/.venv`, Python 3.12.13 confirmed). With
`BACKTEST_API_KEY=ci-test-key`:
```
344 passed, 2 skipped, 229 warnings in 67.50s
```
Matches the stated baseline exactly.

BEFORE anchor:
```
-5976.890049456466 2561 34.322530261616556 0.9027249232666907 2016-04-11 2026-04-09
```
Matches exactly. Proceeded to the task.

## 2. GET /wit/v1/datasets — response shape, worked example

```json
{
  "datasets": [
    {
      "id": "ES_5min_continuous",
      "label": "ES continuous futures — 5-min bars (RTH-filtered) + 1-min opening range",
      "description": "",
      "symbol": "MES",
      "point_value": 5.0,
      "tick_size": 0.25,
      "economics_supported": true,
      "date_range": {"start": "2008-01-02", "end": "2026-04-09"}
    }
  ]
}
```
(Real output — see §8 for the live curl capture. Built-in dataset only, since no `datasets.json`
exists on the volume today — exactly the documented normal case.) `date_range` is the FULL data
coverage read from the parquet (`dataset_date_range`), which extends back to 2008-01-02 — wider
than the WIT-0001 anchor's own configured `start_date` of 2016-04-10; that's expected, the anchor
uses a specific test window, `dataset_date_range` reports everything on disk.

## 3. economics_supported — computation and location

Computed inline in the new `wit_list_datasets` route (`api/server.py`, in the per-spec loop):
```python
"economics_supported": (spec.point_value == _WIT_POINT_VALUE and spec.tick_size == _WIT_TICK_SIZE),
```
`_WIT_POINT_VALUE`/`_WIT_TICK_SIZE` are `POINT_VALUE`/`TICK_SIZE` imported directly from
`wit.config` (`from wit.config import POINT_VALUE as _WIT_POINT_VALUE, TICK_SIZE as
_WIT_TICK_SIZE`) — the exact same two constants `vp_orb_runner.py`'s `DatasetEconomicsUnsupported`
guard compares against (`if spec.point_value != POINT_VALUE or spec.tick_size != TICK_SIZE`, WIT-P5o).
No second literal threshold was declared; both sites import from the same source of truth.

## 4. Entries whose files or date-range read fail

- **`datasets.available()`** itself is called once, un-wrapped. It cannot fail "per entry" — it
  either returns a list (files-missing entries already excluded, by its own contract) or raises
  `DatasetCatalogError` for a whole-catalog problem (a malformed `datasets.json`). A malformed
  catalog is a real operator misconfiguration, not a single broken dataset — per WIT-P5o's own
  governing rule ("never fall back / never silently swallow a catalog problem"), that failure is
  left to propagate as an unhandled exception (a 500) rather than being caught and hidden as an
  empty or partial list. This mirrors how `resolve()` itself never catches `DatasetCatalogError`.
- **`dataset_date_range(spec.id)`** IS wrapped, per entry, inside the loop:
  ```python
  try:
      start, end = dataset_date_range(spec.id)
  except Exception as e:
      print(f"[wit_list_datasets] dropping {spec.id!r}: date-range read failed: {e}")
      continue
  ```
  This is the "files exist but the parquet is corrupt/unreadable" case the prompt calls out —
  `available()` only checks file *presence*, not readability. A failure here drops just that one
  entry (with a runtime log line naming the id and the reason) and the endpoint still 200s with
  every other entry present. Not exercised in this session (no corrupt parquet on this machine to
  reproduce), but the code path and its reasoning are explicit and commented, per the prompt's
  instruction not to swallow it silently without saying so.

## 5. `_provenance()`/`_backtest_result` change

File: `api/server.py`.

**`_provenance`** (line 1811, was line 1811 pre-edit too — signature-only change):
```python
# before
def _provenance(config_hash: str, dataset: str) -> dict:
    return {"engine_version": ENGINE_VERSION, "dataset_version": dataset,
            "config_hash": config_hash,
            "completed_at": _dt.datetime.now(_dt.timezone.utc).isoformat()}

# after
def _provenance(config_hash: str, dataset: str, dataset_id: str | None = None) -> dict:
    out = {"engine_version": ENGINE_VERSION, "dataset_version": dataset,
          "config_hash": config_hash,
          "completed_at": _dt.datetime.now(_dt.timezone.utc).isoformat()}
    if dataset_id is not None:
        out["dataset_id"] = dataset_id
    return out
```
**Chose to ADD A SECOND (optional, keyword-capable) PARAMETER**, not fold both into one call. Why:
`_event_study_result`'s call site (`_provenance(config_hash, os.path.basename(_ES_PARQUET_1MIN))`,
2 args) is explicitly required to stay unchanged — it is untouched, still 2 args, and with
`dataset_id=None` the returned dict's shape is byte-identical to before (no `"dataset_id"` key
added for event studies). Only the backtest call site passes the third argument, gaining the new
key. Folding both into one call (e.g. always requiring `dataset_id`) would have forced touching
the event-study call site and changed its output shape — not permitted.

**`_backtest_result`** (line 1871):
```python
# before
def _backtest_result(res, config_hash: str) -> dict:
    ...
    return {..., "provenance": _provenance(config_hash, os.path.basename(_VPORB_PARQUET))}

# after
def _backtest_result(res, config_hash: str, dataset: str = _wit_datasets.BUILT_IN_DEFAULT.id) -> dict:
    ...
    _spec = _wit_datasets.resolve(dataset)
    return {..., "provenance": _provenance(config_hash, _spec.bars_5min, _spec.id)}
```
**One deliberate deviation from the prompt's literal suggestion**: the prompt says to read
`res.config.dataset`. I did not — `res` (the `RunResult` `run_vp_orb` returns) is stubbed by
`types.SimpleNamespace(kpis=..., trades=[])` in six existing tests across `test_wit_router.py`,
`test_verdict.py`, and `test_equity_curve_bound.py`, none of which set `.config`. Reading
`res.config.dataset` would have raised `AttributeError` in all six, and "TESTS — add, never
modify existing ones" forbids fixing those stubs. Instead, `_backtest_result` takes `dataset` as
its own parameter (defaulting to the built-in id, so the one existing DIRECT call site —
`test_equity_curve_bound.py`'s `server._backtest_result(res, "cfghash")`, 2 positional args —
keeps working unmodified), and its one real caller, `_wit_compute`, passes `engine_cfg.dataset`
(the VPORBConfig's own dataset field, WIT-P5o) — NOT read off the stubbable `res`. In real
execution `engine_cfg.dataset` and `res.config.dataset` are always the same value (`run_vp_orb`
returns `RunResult(config=cfg, ...)` for the `cfg` it was given), so this is behaviourally
identical to the prompt's suggestion while touching zero test files.

**`_wit_compute`** (line 1918):
```python
# before
return _backtest_result(run_vp_orb(engine_cfg), config_hash)
# after
return _backtest_result(run_vp_orb(engine_cfg), config_hash, engine_cfg.dataset)
```

**`_VPORB_PARQUET`**: checked with `grep -n "_VPORB_PARQUET" server.py` after the change — the
only remaining match is its own import line (`server.py:1745`). **It is no longer used anywhere
else in the file.** Left the import in place exactly as instructed ("can stay ... do not remove it
unless you checked") — I checked, and I'm reporting plainly that nothing reads it now; removal
was not attempted.

## 6. Tests added and results

All appended to the existing `api/tests/test_wit_router.py` (never edited existing functions —
only a new `import os` + `from wit import data_paths as _wit_data_paths, datasets as
_wit_datasets_mod` at the top, and 6 new test functions at the end):

1. `test_datasets_endpoint_missing_bearer_401` — no `Authorization` header → 401
2. `test_datasets_endpoint_wrong_bearer_403` — `Bearer nope` → 403
3. `test_datasets_endpoint_returns_builtin_with_economics_supported_and_date_range` — 200, built-in
   id present, `economics_supported is True`, `date_range.start < date_range.end`, both YYYY-MM-DD
4. `test_datasets_endpoint_includes_unsupported_economics_entry_not_omitted` — a temp catalog entry
   (symlinked real files, `point_value=2.0`) appears in the list with `economics_supported: false`
5. `test_datasets_endpoint_excludes_entry_with_missing_files` — a temp catalog entry naming
   nonexistent files does NOT appear (and, incidentally, neither does the built-in id in that same
   isolated tmp dir — proving it's a genuine file-presence check, not special-cased for the
   built-in)
6. `test_backtest_provenance_names_the_dataset_actually_used` — submits one run declaring the
   built-in id and one declaring a temporary second id (symlinked to the same real files, matching
   WIT-P5o's own two-id proof pattern); asserts `provenance.dataset_id` equals the id actually
   declared in each case, and that the two runs' `dataset_id`s differ from each other

```
$ pytest tests/test_wit_router.py -q
29 passed in 4.76s   (23 pre-existing + 6 new, 0 failed)
```

## 7. Suite counts, AFTER anchor

```
$ BACKTEST_API_KEY=ci-test-key python -m pytest -q
350 passed, 2 skipped, 229 warnings in 59.30s
```
350 = 344 baseline + 6 new. Zero failed, 2 skipped (unchanged), no existing test edited.

AFTER anchor:
```
-5976.890049456466 2561 34.322530261616556 0.9027249232666907 2016-04-11 2026-04-09
```
Identical, digit for digit, to BEFORE.

## 8. Live curl output

Started the real server (`uvicorn server:app --host 127.0.0.1 --port 8091`) with
`WIT_ENGINE_SERVICE_KEY=wit-p5p-live-check` — no other env vars needed (confirmed via grep: no
`os.environ[...]` bracket-access hard-requirements anywhere in `server.py` or `wit/`). Confirmed
up via `GET /health` → 200. Then:

```
$ curl -s -w "\nHTTP %{http_code}\n" -H "Authorization: Bearer wit-p5p-live-check" \
    http://127.0.0.1:8091/wit/v1/datasets
{"datasets":[{"id":"ES_5min_continuous","label":"ES continuous futures — 5-min bars
(RTH-filtered) + 1-min opening range","description":"","symbol":"MES","point_value":5.0,
"tick_size":0.25,"economics_supported":true,"date_range":{"start":"2008-01-02","end":"2026-04-09"}}]}
HTTP 200

$ curl -s -w "\nHTTP %{http_code}\n" http://127.0.0.1:8091/wit/v1/datasets
{"detail":"Missing bearer token"}
HTTP 401

$ curl -s -w "\nHTTP %{http_code}\n" -H "Authorization: Bearer nope" \
    http://127.0.0.1:8091/wit/v1/datasets
{"detail":"Invalid service key"}
HTTP 403
```
Server stopped afterward (`pkill`); confirmed dead (`curl` to `/health` returned no connection).

## 9. Evidence nothing about run execution or any golden moved

- BEFORE and AFTER anchors are digit-for-digit identical (§1, §7) — the primary published KPI
  result did not move.
- Zero files under `api/wit/` were touched (`datasets.py`, `vp_orb_runner.py`, `mapper.py`,
  `config.py`, `analysis.py`, `event_study.py` — confirmed via `git status --short`, only
  `api/server.py` and `api/tests/test_wit_router.py` show as modified). Every do-not-touch file
  from the prompt's §3 is untouched.
- No fixture, golden, or contract file was touched.
- The event-study provenance call site (`_event_study_result` → `_provenance(config_hash,
  os.path.basename(_ES_PARQUET_1MIN))`) is byte-identical to before — still 2 args, no new key.
- Full suite: 350 passed, 0 failed, 2 skipped — same skip count as baseline, only new tests added,
  no existing test's assertions changed (confirmed by re-running the FULL suite, not just the
  touched file, in §7).

Nothing moved.

## 10. New HEAD sha, commit URL, staged files

Staged (`git diff --cached --name-status`):
```
M	api/server.py
M	api/tests/test_wit_router.py
A	docs/wit/log/WIT-P5p-report.md
A	docs/wit/prompts/WIT-P5p.md
```
Commit subject: `WIT-P5p: dataset listing endpoint + honest backtest provenance`

New HEAD sha: **`<filled after commit — see final printed message>`**
Commit URL: **`<filled after commit — see final printed message>`**

## 11. Anything stopped short of

- **One deliberate design deviation from the prompt's literal wording**, already explained fully
  in §5: `_backtest_result` takes `dataset` as an explicit parameter (sourced from
  `engine_cfg.dataset` at the one real call site) rather than reading `res.config.dataset` as
  literally suggested, specifically to honor "TESTS — add, never modify existing ones" against six
  pre-existing stubbed tests across three files that construct `res` without a `.config` attribute.
  Behaviourally identical in real execution; zero test files needed touching as a result.
- Everything else in the prompt is done as specified.

WIT-P5p — Completed

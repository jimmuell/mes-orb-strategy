# WIT-P5o — dataset catalog resolves an id to its two files, honoured end to end

## 1. Clone, HEAD, BEFORE baseline, BEFORE anchor

Cloned to `/Users/jameslmueller/dev/mes-orb-strategy` (was not present on this machine; `git-lfs`
was also not installed and had to be installed via Homebrew first — the initial clone attempt
failed checkout with `git-lfs: command not found` before that, so the partial checkout was removed
and the repo re-cloned cleanly once `git lfs install` was run).

```
git remote -v   -> origin  https://github.com/jimmuell/mes-orb-strategy.git (fetch/push)
pwd             -> /Users/jameslmueller/dev/mes-orb-strategy
git rev-parse HEAD         -> ce56c724cf9278d1856d4deba00b250eeb0249ab
git rev-parse origin/main  -> ce56c724cf9278d1856d4deba00b250eeb0249ab
```
Both match WIT-P5n. `api/data/ES_full_5min_continuous_UNadjusted.parquet` (19,890,248 bytes) and
`api/data/ES_full_1min_rth.parquet` (28,349,422 bytes) both present, both tens of MB — real data,
not LFS pointers.

Environment: `api/.python-version` pins 3.12.13; no matching interpreter was on the machine, so
`python@3.12` was installed via Homebrew (`/usr/local/bin/python3.12` → confirmed `Python 3.12.13`
exactly). Venv created against that interpreter; `pip install -r requirements.txt -r
requirements-dev.txt` installed clean.

**First baseline run diverged**: 318 passed, 1 failed, 2 skipped —
`test_wit_router.py::test_exec_endpoints_not_gated_when_flag_off` failed (got 503, expected 401).
Root cause, found read-only before touching anything: `server.py`'s `API_KEY = os.environ.get(
"BACKTEST_API_KEY")` is captured once at import time; that test's `monkeypatch.setenv(...)` at
test time can't retroactively change it, so with `BACKTEST_API_KEY` unset in my shell the whole
suite imports with `API_KEY = None` and this one test — which specifically depends on `API_KEY`
already being non-empty — sees 503 (misconfigured) instead of 401 (bad key). `.github/workflows/
ci.yml` sets `BACKTEST_API_KEY: ci-test-key` before running pytest; there is no `.env` file in the
repo (gitignored) supplying it locally. This is a missing environment variable in a fresh checkout,
not a code regression — confirmed by re-running with `BACKTEST_API_KEY=ci-test-key` set (matching
CI exactly):

```
319 passed, 2 skipped, 229 warnings in 65.44s
```
Matches the prompt's stated baseline exactly. All subsequent runs in this task use
`BACKTEST_API_KEY=ci-test-key`.

BEFORE anchor:
```
-5976.890049456466 2561 34.322530261616556 0.9027249232666907 2016-04-11 2026-04-09
```
Matches exactly. Proceeded to the task.

## 2. datasets.json shape and validation rules

Worked example, two entries (the built-in id overriding the module default, plus one genuinely
new dataset):

```json
{
  "version": 1,
  "datasets": [
    {
      "id": "ES_5min_continuous",
      "label": "ES continuous futures — 5-min bars (RTH-filtered) + 1-min opening range (volume override)",
      "bars_5min": "ES_full_5min_continuous_UNadjusted.parquet",
      "opening_1min": "ES_full_1min_rth.parquet",
      "symbol": "MES",
      "point_value": 5.0,
      "tick_size": 0.25,
      "description": "Overrides the built-in default with a re-labelled entry."
    },
    {
      "id": "NQ_5min_continuous",
      "label": "NQ continuous futures — 5-min bars (RTH-filtered) + 1-min opening range",
      "bars_5min": "NQ_full_5min_continuous_UNadjusted.parquet",
      "opening_1min": "NQ_full_1min_rth.parquet",
      "symbol": "MNQ",
      "point_value": 2.0,
      "tick_size": 0.25
    }
  ]
}
```

Validation enforced by `api/wit/datasets.py` (`_load_catalog`/`_validate_entry`), every failure a
`DatasetCatalogError` naming the catalog file path and the offending entry index or key — never a
silent fallback to the built-in:

- The file must parse as JSON at all.
- Top level must be an object with `"version": 1` exactly.
- `"datasets"` must be a list.
- Each entry must be an object carrying all seven required keys (`id`, `label`, `bars_5min`,
  `opening_1min`, `symbol`, `point_value`, `tick_size`); `description` is optional, defaults `""`.
- `id`, `label`, `bars_5min`, `opening_1min`, `symbol` must be non-empty strings.
- `point_value`, `tick_size` must be numbers (not bool) and strictly positive (`> 0`).
- `bars_5min`, `opening_1min` must be plain filenames: `os.path.basename(v) == v` and no `".."`
  substring — rejects any path separator or parent-directory escape.
- `description`, if present, must be a string.
- `id`s must be unique within the file (duplicate → error).
- An entry whose `id` equals the built-in id (`ES_5min_continuous`) **overrides** the built-in
  entry in the loaded catalog; every other `id` is **added**.

Catalog file **absent** → the built-in default is the whole catalog, no warning, no error (the
normal case today — proved by `test_builtin_default_resolves_with_no_catalog_file`).

## 3. Every file/function that named a parquet filename, and what it reads now

| File | Before | Now |
|---|---|---|
| `wit/vp_orb_runner.py` — module constants `PARQUET_5MIN`/`PARQUET_1MIN` | `engine_data_path(_NAME_5MIN)` / `engine_data_path(_NAME_1MIN)`, `_NAME_5MIN`/`_NAME_1MIN` hardcoded strings | `engine_data_path(datasets.BUILT_IN_DEFAULT.bars_5min)` / `.opening_1min` — same values, sourced from the catalog's built-in entry. Kept for `server.py`'s `PARQUET_5MIN` import (unchanged behaviour). |
| `wit/vp_orb_runner.py::load_5min(start, end, spec=...)` | read `engine_data_path(_NAME_5MIN)` | reads `engine_data_path(spec.bars_5min)`; `spec` defaults to `datasets.BUILT_IN_DEFAULT` so every existing no-arg call site is unchanged |
| `wit/vp_orb_runner.py::load_1min_opening(start, end, range_start, range_end, spec=...)` | read `engine_data_path(_NAME_1MIN)` | reads `engine_data_path(spec.opening_1min)`; same default-arg back-compat |
| `wit/vp_orb_runner.py::dataset_date_range(dataset_id=None)` | `@lru_cache(maxsize=1)`, read `engine_data_path(_NAME_5MIN)` unconditionally | `@lru_cache(maxsize=None)`, resolves `datasets.resolve(dataset_id)` and reads `spec.bars_5min` — **cached per id**, not globally |
| `wit/vp_orb_runner.py::run_vp_orb` | called `load_5min`/`load_1min_opening` with no spec; `EmptyDataWindow`/`EmptyOpeningData` named the module constants `_NAME_5MIN`/`_NAME_1MIN` | resolves `spec = datasets.resolve(cfg.dataset)` **once**, at the top; applies the economics guard (§4); passes `spec` to both loaders; `EmptyDataWindow`/`EmptyOpeningData` now name `spec.bars_5min`/`spec.opening_1min` — the file actually resolved, not a constant |
| `wit/event_study.py` — module constant `PARQUET_1MIN` | `engine_data_path(_NAME_1MIN)`, `_NAME_1MIN` hardcoded | `engine_data_path(datasets.BUILT_IN_DEFAULT.opening_1min)` — same value |
| `wit/event_study.py::load_1min_rth(start, end)` | read `engine_data_path(_NAME_1MIN)` | resolves `spec = datasets.resolve(None)` (pinned to the built-in default — see §4 below) and reads `engine_data_path(spec.opening_1min)` |
| `wit/analysis.py::build_all` provenance block | `"dataset": os.path.basename(R.PARQUET_5MIN)`, `"vp_source": os.path.basename(R.PARQUET_1MIN)` — always the ES filenames regardless of what ran | resolves `spec = datasets.resolve(primary.dataset)`; reports `"dataset_id": spec.id` (new key), `"dataset": spec.bars_5min`, `"vp_source": spec.opening_1min` — the files actually read. For the built-in default these two filename values are unchanged byte-for-byte from before. |

Nothing in `engine.py` or `server.py`'s own module-level economics/provenance constants were
touched (out of scope — see §6 of the prompt and §4 below).

## 4. The economics guard

Fires inside `wit/vp_orb_runner.py::run_vp_orb`, immediately after resolving the spec and **before**
the `vp_granularity` check or any data load — the first thing the function does after resolution:

```python
spec = datasets.resolve(cfg.dataset)
if spec.point_value != POINT_VALUE or spec.tick_size != TICK_SIZE:
    raise DatasetEconomicsUnsupported(spec.id, spec.point_value, spec.tick_size)
```

`DatasetEconomicsUnsupported.code = "UNSUPPORTED_CONSTRUCT"` (the existing WIT-03 §3.7 vocabulary
code for an engine-capability limit). Message text (an f-string; example values shown):

```
dataset 'OTHER' declares point_value=50.0, tick_size=0.1 — this engine version does not apply
per-dataset contract economics (it bakes point_value=5.0, tick_size=0.25); refusing rather than
running under the wrong contract economics
```

It reaches the run-job callback automatically via `server.py`'s existing generic
`_engine_error_code(e)` (`getattr(e, "code", None)`) — no `server.py` change was needed for this to
surface correctly, the same mechanism `EmptyDataWindow`/`UnsupportedGranularity` already use.

## 5. Mapper, contract, drift gate

`wit/mapper.py::strategy_config_to_vporb` now reads `wire["data"]["dataset"]` and passes it
straight into `VPORBConfig(dataset=wire["data"]["dataset"])` — no validation at this layer; an
unknown id is caught once, loudly, at the top of `run_vp_orb` (never silently substituted here).
`(("data", "dataset"), "ES_5min_continuous")` removed from `_BAKED_NOT_HONOURED`, so
`notapplied_data_dataset` is never emitted again. `wit/mapper.py::map_template` (the Class-A
template→wire builder) still emits `"dataset": "ES_5min_continuous"` unchanged — there is no
template field for choosing a dataset, so every Class-A run still declares and resolves to the
built-in id exactly as before (proved by `test_G1_t0001_roundtrip_equals_vporbconfig` still passing
unedited, and by the new `test_P5o_dataset_honoured_into_vporbconfig`).

Contract (`contract/strategy-config.v1.json`, `data.dataset.description`) changed from "declared
but NOT applied in v1 ... disclosed via notapplied_data_dataset if != 'ES_5min_continuous'" to:

> "HONOURED (WIT-P5o) — must match an id in the engine's dataset catalog (wit.datasets); an unknown
> id fails the run (DATA_UNAVAILABLE) rather than falling back to any default.
> 'ES_5min_continuous' is the built-in default and always resolves."

Drift gate: `cp contract/strategy-config.v1.json api/_shipped/contract/strategy-config.v1.json`,
then `diff` confirmed byte-identical. `api/tests/test_data_paths.py::test_shipped_copy_byte_identical`
(parametrized over `contract/strategy-config.v1.json`) is part of the 344-green run in §6/§7 — green.

## 6. Tests added and results

New file `api/tests/test_datasets.py` (22 tests) — every WIT_ENGINE_DATA_DIR override uses an
isolated `tmp_path`, real `api/data` is never touched:
- built-in default resolves with no catalog file present (2 tests: `None` and `""`)
- valid catalog adds an entry; catalog entry sharing the built-in id overrides it (2 tests)
- malformed catalog raises, never falls back: bad version, datasets-not-a-list, missing key, wrong
  type, non-positive point_value (`0` and `-5.0`, parametrized), non-positive tick_size, a filename
  with a path separator, a filename with `".."`, duplicate ids, and — explicitly — a malformed
  catalog still raises even when resolving the *built-in* id (9 tests)
- unknown id raises `UnknownDataset` (`code == "DATA_UNAVAILABLE"`) naming both the bad id and the
  available ids (1 test)
- an entry whose files are missing is excluded from `available()` and raises `DatasetFilesMissing`
  on `resolve()` (2 tests: missing → excluded/raises, present → included)
- a dataset whose economics differ from the baked constants is refused by the guard
  (`DatasetEconomicsUnsupported`, `code == "UNSUPPORTED_CONSTRUCT"`), and — the converse — matching
  economics do *not* trip the guard (2 tests)
- `dataset_date_range` returns different ranges for two different ids built from synthetic parquet
  fixtures, and re-querying one id still returns that id's range (1 test)
- a config with no dataset specified resolves to exactly the built-in default and the same files as
  the legacy `PARQUET_5MIN`/`PARQUET_1MIN` constants (1 test)

Added to the existing `api/tests/test_mapper.py` (never edited, only appended — 3 tests): the wire
`dataset` is honoured into `VPORBConfig.dataset`; a non-built-in wire dataset is no longer disclosed
as `notapplied_data_dataset`; and `strategy_config_to_vporb` itself does not reject/resolve an
unknown id (that happens once, downstream, in `run_vp_orb`).

```
tests/test_datasets.py: 22 passed
tests/test_mapper.py:   27 passed (24 pre-existing + 3 new), 0 failed
```

## 7. Suite counts, AFTER anchor, two-id proof

```
$ BACKTEST_API_KEY=ci-test-key python -m pytest -q
344 passed, 2 skipped, 229 warnings in 72.16s
```
344 = 319 baseline + 22 (`test_datasets.py`) + 3 (`test_mapper.py` additions). Zero failed, 2
skipped (unchanged — the same LFS-gated tier-2 tests as baseline), no existing test edited.

AFTER anchor:
```
-5976.890049456466 2561 34.322530261616556 0.9027249232666907 2016-04-11 2026-04-09
```
Identical, digit for digit, to BEFORE.

**Two-id proof.** Built `/private/tmp/wit-p5o-proof/` (outside the repo) holding symlinks to the
real two parquets plus a `datasets.json` registering a second id, `ES_5min_continuous_PROOF_COPY`,
pointing at those same two symlinked files:

```
$ WIT_ENGINE_DATA_DIR=/private/tmp/wit-p5o-proof python -c "
from wit.config import VPORBConfig
from wit.vp_orb_runner import run_vp_orb
k = run_vp_orb(VPORBConfig(dataset='ES_5min_continuous_PROOF_COPY')).kpis
print(k['net_profit'], k['total_trades'], k['win_rate'], k['profit_factor'], k['actual_start_date'], k['actual_end_date'])
"
-5976.890049456466 2561 34.322530261616556 0.9027249232666907 2016-04-11 2026-04-09
```
Same six values as the anchor — the same data, reached through a different declared name. The
picker works.

```
$ WIT_ENGINE_DATA_DIR=/private/tmp/wit-p5o-proof python -c "
from wit.config import VPORBConfig
from wit.vp_orb_runner import run_vp_orb
run_vp_orb(VPORBConfig(dataset='DOES_NOT_EXIST_ANYWHERE'))
"
Traceback (most recent call last):
  ...
  File "wit/datasets.py", line 167, in resolve
    raise UnknownDataset(resolved_id, sorted(catalog.keys()))
wit.datasets.UnknownDataset: unknown dataset id 'DOES_NOT_EXIST_ANYWHERE' — available ids:
['ES_5min_continuous', 'ES_5min_continuous_PROOF_COPY']
```
Fails loudly, names both ids that ARE available. `/private/tmp/wit-p5o-proof/` deleted afterward
(`rm -rf`); nothing from it staged or committed.

## 8. Evidence no golden moved

- BEFORE and AFTER anchors are digit-for-digit identical (§1, §7) — the primary published KPI
  result did not move.
- `test_G1_t0001_roundtrip_equals_vporbconfig` (the WIT-0001 anchor golden — template round-trips to
  exactly `VPORBConfig()`) still passes unedited, including the new `dataset` field, since
  `map_template` still emits the built-in id verbatim.
- `test_shipped_1min_data.py::test_raw_vs_parquet_kpis_identical` (full backtest-path KPI equality,
  local-only tier) still passes/skips exactly as at baseline (2 skipped both before and after — this
  machine has the derived parquet but not the raw LFS text, same as baseline).
- Grepped for `notapplied_data_dataset` across `tests/` and `wit/` before removing the
  `_BAKED_NOT_HONOURED` entry: zero matches — no existing test asserted that disclosure, so nothing
  needed to stop for.
- Full suite: 344 passed, 0 failed, 2 skipped — same skip count as baseline, only new tests added,
  no existing test's assertions changed.

Nothing moved. Nothing to report as a stop condition here.

## 9. New HEAD sha, commit URL, staged files

Staged (git diff --cached --name-status):
```
M	api/_shipped/contract/strategy-config.v1.json
A	api/tests/test_datasets.py
M	api/tests/test_mapper.py
A	api/wit/datasets.py
M	api/wit/analysis.py
M	api/wit/config.py
M	api/wit/event_study.py
M	api/wit/mapper.py
M	api/wit/vp_orb_runner.py
M	contract/strategy-config.v1.json
A	docs/wit/log/WIT-P5o-report.md
A	docs/wit/prompts/WIT-P5o.md
```
Commit subject: `WIT-P5o: dataset catalog resolves an id to its two files, honoured end to end`

New HEAD sha: **`<filled after commit — see final message>`**
Commit URL: **`<filled after commit — see final message>`**

## 10. Anything stopped short of

- **The initial STEP 0 baseline run required `BACKTEST_API_KEY=ci-test-key`** to reach 319/0/2 — a
  missing environment variable in a fresh checkout (CI sets it; there's no local `.env`), not a
  code regression. Verified via `.github/workflows/ci.yml` and confirmed the exact baseline count
  once set. Reported plainly in §1 rather than silently working around it.
- **`server.py`'s own provenance lines** (`_VPORB_PARQUET`, `_ES_PARQUET_1MIN`, used only in the
  `/wit/v1/runs` response body) still report the built-in filenames regardless of which dataset a
  wire config actually names. The prompt scoped the provenance-truthfulness fix to `analysis.py`
  only ("This is the only change permitted in analysis.py"); `server.py` is not in the do-not-touch
  list by name, but no provenance change there was authorized either, so I left it. Worth flagging
  as a known gap for a future slice, not fixed here.
- **Event studies (Class B) stay pinned to the built-in dataset**, exactly as instructed — the
  Class-B mapper's literal `"ES_1min_continuous"` is not a catalog id and was left untouched.
  Wiring Class B to the catalog is explicitly a later slice.
- Everything else in the prompt is done as specified.

WIT-P5o — Completed

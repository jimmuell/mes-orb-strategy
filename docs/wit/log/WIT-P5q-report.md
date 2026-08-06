# WIT-P5q — dataset-aware RTH cutoff + granularity guard for a real 1-minute dataset

## 1. HEAD sha, BEFORE baseline, BEFORE anchor

`git remote -v`/`pwd` matched. `git pull` — already up to date. `git rev-parse HEAD` →
`ae1f5ea889e7fcd8e472a29ef988b3031e0db203` (WIT-P5p) — matches exactly.

Reused the venv from WIT-P5o/P5p (Python 3.12.13 confirmed). With `BACKTEST_API_KEY=ci-test-key`:
```
350 passed, 2 skipped, 229 warnings in 77.03s
```
Matches the stated baseline exactly (no LFS-related discrepancy on this machine).

BEFORE anchor:
```
-5976.890049456466 2561 34.322530261616556 0.9027249232666907 2016-04-11 2026-04-09
```
Matches exactly. Proceeded to the task.

## 2. `datasets.py` diff

```diff
-_REQUIRED_KEYS = {"id", "label", "bars_5min", "opening_1min", "symbol", "point_value", "tick_size"}
-_STRING_KEYS = {"id", "label", "bars_5min", "opening_1min", "symbol"}
+_BARS_GRANULARITIES = ("1min", "5min")
+
+_REQUIRED_KEYS = {"id", "label", "bars_5min", "opening_1min", "symbol", "point_value", "tick_size",
+                 "bars_granularity"}
+_STRING_KEYS = {"id", "label", "bars_5min", "opening_1min", "symbol", "bars_granularity"}

 @dataclass(frozen=True)
 class DatasetSpec:
     ...
     tick_size: float
+    bars_granularity: str
     description: str = ""

 BUILT_IN_DEFAULT = DatasetSpec(
     ...
     tick_size=0.25,
+    bars_granularity="5min",   # what it has always actually been
 )

 def _validate_entry(...):
     ...
+    if entry["bars_granularity"] not in _BARS_GRANULARITIES:
+        _fail(path, f"datasets[{index}].bars_granularity must be one of {_BARS_GRANULARITIES}, "
+                    f"got {entry['bars_granularity']!r}")
     ...
     return DatasetSpec(
         ...
+        bars_granularity=entry["bars_granularity"],
         description=description,
     )
```
`_BARS_GRANULARITIES = ("1min", "5min")` is its own tuple in `datasets.py`, deliberately not
imported from `mapper.py`'s `_VP_GRANULARITIES` (same vocabulary, different concept, per the
prompt). `bars_granularity` is validated by the existing generic `_STRING_KEYS` non-empty-string
check first, then the specific enum-membership check — same two-stage pattern the file already
uses for numeric/filename fields. A missing key fails via the existing
`_REQUIRED_KEYS - entry.keys()` check (same code path as a missing `"symbol"`); an invalid value
(e.g. `"15min"`) fails via the new check, both through the existing `_fail()` pattern, naming the
bad value.

## 3. `vp_orb_runner.py` diff

**Cutoff derivation** (`load_5min`, was line 100, now line 125):
```diff
 _RTH_START = dt.time(9, 30)
-_RTH_LAST_START = dt.time(15, 55)   # last RTH 5-min bar start (closes 16:00)
+_RTH_LAST_START = dt.time(15, 55)   # last RTH 5-min bar start (closes 16:00) — 5-minute bars ONLY
+_RTH_LAST_START_1MIN = dt.time(15, 59)   # last RTH 1-min bar start (closes 16:00)
+
+
+def _rth_last_bar_start(spec: DatasetSpec) -> dt.time:
+    return _RTH_LAST_START_1MIN if spec.bars_granularity == "1min" else _RTH_LAST_START

 def load_5min(start: str, end: str, spec: DatasetSpec = datasets.BUILT_IN_DEFAULT) -> pd.DataFrame:
     df = pd.read_parquet(engine_data_path(spec.bars_5min))
     df = df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end) + pd.Timedelta(days=1))]
     t = df.index.time
-    df = df[(t >= _RTH_START) & (t <= _RTH_LAST_START)]
+    df = df[(t >= _RTH_START) & (t <= _rth_last_bar_start(spec))]
     return df
```

**New exception class**, verbatim:
```python
class VpGranularityUnsupportedForDataset(Exception):
    """WIT-P5q: vp_granularity="5min" picks the "5-minute robustness" opening-profile branch —
    which builds the profile from the PRIMARY bars_5min file. For a dataset whose bars_granularity
    is "1min", that file has no true 5-minute bars to build from; running anyway would silently
    build the "5min" profile from finer data under the wrong label, defeating the point of the
    robustness comparison (WIT-T-0001 §J2). Refusing at the top of the run, before any data load."""
    code = "UNSUPPORTED_CONSTRUCT"

    def __init__(self, dataset_id: str, bars_granularity: str, vp_granularity: str):
        self.dataset_id = dataset_id
        self.bars_granularity = bars_granularity
        self.vp_granularity = vp_granularity
        super().__init__(
            f"dataset {dataset_id!r}'s bars_granularity is {bars_granularity!r}; "
            f"vp_granularity={vp_granularity!r} has no true 5-minute bars to build from for this "
            f"dataset — refusing rather than silently building the \"5min\" profile from finer "
            f"data under the wrong label")
```

**New guard** (`run_vp_orb`'s top section):
```diff
     if cfg.vp_granularity not in ("1min", "5min"):
         raise UnsupportedGranularity(cfg.vp_granularity)
+    if cfg.vp_granularity == "5min" and spec.bars_granularity != "5min":
+        raise VpGranularityUnsupportedForDataset(spec.id, spec.bars_granularity, cfg.vp_granularity)

     if five is None:
         five = load_5min(cfg.start_date, cfg.end_date, spec)
```
Placed exactly where specified: after the existing bogus-`vp_granularity`-value check (so a truly
invalid value like `"3min"` still raises `UnsupportedGranularity` first), before any data load.

## 4. `server.py` diff

```diff
         out.append({
             "id": spec.id, "label": spec.label, "description": spec.description,
             "symbol": spec.symbol, "point_value": spec.point_value, "tick_size": spec.tick_size,
+            "bars_granularity": spec.bars_granularity,   # WIT-P5q
             "economics_supported": (spec.point_value == _WIT_POINT_VALUE
                                     and spec.tick_size == _WIT_TICK_SIZE),
             "date_range": {"start": start, "end": end},
         })
```

## 5. Tests added and results

**Test-fixture collateral (expected, per the prompt)**: added `"bars_granularity": "5min"` to
`tests/test_datasets.py`'s `_entry()` helper default, and to the three inline catalog-entry dicts
in `tests/test_wit_router.py` (from WIT-P5p — `test_datasets_endpoint_includes_unsupported_
economics_entry_not_omitted`, `test_datasets_endpoint_excludes_entry_with_missing_files`,
`test_backtest_provenance_names_the_dataset_actually_used`). The schema itself gained a new
required key, so every fixture literal describing a catalog entry needed it — data-shape fixes,
zero assertions changed, exactly the kind of update the prompt explicitly calls "expected."

**New tests, all in `tests/test_datasets.py`** (10 new):
1. `test_malformed_catalog_missing_bars_granularity_raises` — mirrors the missing-`"symbol"` test
2. `test_malformed_catalog_invalid_bars_granularity_raises` — `"15min"` fails loud, names the field
3. `test_builtin_default_bars_granularity_is_5min`
4. `test_load_5min_cutoff_includes_1559_for_1min_dataset` — synthetic bar at 15:59, spec
   `bars_granularity="1min"` → bar is INCLUDED
5. `test_load_5min_cutoff_excludes_1559_for_5min_dataset` — IDENTICAL synthetic bar, only
   `bars_granularity="5min"` differs → bar is EXCLUDED (proves the derivation reads the spec)
6. `test_vp_granularity_5min_refused_for_1min_primary_dataset` — raises
   `VpGranularityUnsupportedForDataset`, `code == "UNSUPPORTED_CONSTRUCT"`, all three attributes
   correct
7. `test_vp_granularity_1min_not_refused_for_1min_primary_dataset` — same dataset,
   `vp_granularity="1min"` → the new guard does NOT fire
8. `test_vp_granularity_unaffected_for_synthetic_5min_primary_dataset` — a synthetic 5-min-primary
   dataset at both `vp_granularity` values → guard never fires
9. `test_vp_granularity_5min_unaffected_for_builtin_dataset` — **real execution** of
   `run_vp_orb(VPORBConfig(vp_granularity="5min", start_date="2024-01-02", end_date="2024-03-28"))`
   against the actual built-in dataset — completes, no `VpGranularityUnsupportedForDataset`. Added
   because no existing test actually EXECUTES `run_vp_orb` with `vp_granularity="5min"` — the only
   prior coverage (`test_sweeps.py`) checks the sweep-grid dataclass, never runs it.
10. `test_real_1min_file_as_primary_bars_runs_end_to_end` — the required real-data proof (see
    below for its pasted output)

```
$ pytest tests/test_datasets.py -v
32 passed in 2.35s   (22 pre-existing + 10 new, 0 failed)
```

**Real-data end-to-end proof's actual pasted kpis** (from `test_real_1min_file_as_primary_bars_
runs_end_to_end`, symlinking a temporary catalog entry's `bars_5min` AND `opening_1min` both at
the real `api/data/ES_full_1min_rth.parquet`, `bars_granularity="1min"`, window
`2026-01-01`→`2026-04-09`, run via a standalone script matching the test exactly — not just
"passed"):
```
net_profit: 4.4300000000030195
total_trades: 68
win_rate: 35.294117647058826
actual_start_date: 2026-01-02
actual_end_date: 2026-04-09
```
(`actual_start_date` shows `2026-01-02` — the data's actual first bar — the runner's own
"DATA STARTS AFTER start_date" adjustment, same behavior the WIT-0001 anchor itself shows every
run.) This is real 1-minute primary-bar data flowing through the new cutoff derivation, the
(non-firing, correctly) guard, and the ordinary signal/exit/engine path, producing a plausible,
non-crashing, fully-typed KPI dict — proof the wiring works end to end against real data.

## 6. Suite counts, AFTER anchor

```
$ BACKTEST_API_KEY=ci-test-key python -m pytest -q
360 passed, 2 skipped, 234 warnings in 51.43s
```
360 = 350 baseline + 10 new. Zero failed, 2 skipped (unchanged), no existing test's assertions
edited (only three catalog-entry-shaped fixture literals gained one key each, as pre-authorized).

AFTER anchor:
```
-5976.890049456466 2561 34.322530261616556 0.9027249232666907 2016-04-11 2026-04-09
```
Identical, digit for digit, to BEFORE.

## 7. Evidence the 5-minute dataset's behaviour did not move

Two independent pieces of evidence, not just "ran the suite":

1. **The anchor itself directly exercises the changed code path.** `run_vp_orb(VPORBConfig())`
   resolves `spec = datasets.resolve(cfg.dataset)` → the built-in default (`bars_granularity=
   "5min"`) → calls `load_5min(..., spec)`, which now calls `_rth_last_bar_start(spec)` instead of
   reading `_RTH_LAST_START` directly. Since `spec.bars_granularity == "5min"`,
   `_rth_last_bar_start` returns exactly `_RTH_LAST_START` (`time(15, 55)`) — the SAME value as
   before this change. The anchor's `total_trades=2561` and all six other digits, unchanged before
   vs. after, is direct proof this substitution is a no-op for the built-in dataset.
2. **A pre-existing, unmodified test asserts full KPI equality through `load_5min` at the
   5-minute cutoff.** `tests/test_shipped_1min_data.py::test_raw_vs_parquet_kpis_identical` calls
   `R.load_5min(cfg.start_date, cfg.end_date)` (no `spec` argument — the built-in default, still
   passes through `_rth_last_bar_start`) and asserts `scalar_kpis(res_raw.kpis) ==
   scalar_kpis(res_pq.kpis)` — every KPI equal, digit for digit, between the parquet-loaded path
   and the independently-implemented raw-text reference loader. This test is byte-for-byte
   unmodified and still passes (confirmed in the 360-pass run, §6), which would not be possible if
   the 5-minute cutoff had moved by even one bar.

## 8. New HEAD sha, commit URL, staged files

Staged (`git diff --cached --name-status`):
```
M	api/server.py
M	api/tests/test_datasets.py
M	api/tests/test_wit_router.py
M	api/wit/datasets.py
M	api/wit/vp_orb_runner.py
A	docs/wit/log/WIT-P5q-report.md
A	docs/wit/prompts/WIT-P5q.md
```
Commit subject: `WIT-P5q: dataset-aware RTH cutoff + granularity guard for a real 1-minute dataset`

New HEAD sha: **`e13a2f395aa58d8af617a3daba8018547be8c1a5`**
Commit URL: **`https://github.com/jimmuell/mes-orb-strategy/commit/e13a2f395aa58d8af617a3daba8018547be8c1a5`**

## 9. Anything stopped short of

Clean. No datasets.json was written or committed anywhere in the repo (the real-data proof used a
temp directory outside the repo, deleted afterward, matching WIT-P5o/P5p's own two-id proof
pattern). No fixture, golden, or contract file touched. `api/wit/event_study.py`,
`api/wit/mapper.py`'s `map_template`, and `api/wit/volume_profile.py` untouched, per §5. The only
test-file changes are the three collateral fixture-literal updates explicitly pre-authorized by
the prompt (§5 of this report) plus the new test functions — no existing test's assertions were
edited.

WIT-P5q — Completed

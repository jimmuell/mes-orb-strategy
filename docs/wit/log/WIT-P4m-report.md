# WIT-P4m — ship RTH 1-minute data into the image; no data path is repo-root-relative

## STEP 0 + DATA GATE
- Gate passed: remote `jimmuell/mes-orb-strategy`, path `/Users/jameslmueller/Projects/mes-orb-strategy`,
  HEAD **12049b1** (WIT-P4l). Read WIT-P3s-report.md (the deploy-layout lesson this extends).
- **DATA GATE — real bars, not a pointer.** `wc -c data/raw/ES_full_1min_continuous_UNadjusted.txt`
  → **349,771,494 bytes**; first two lines are real OHLCV rows
  (`2008-01-02 06:00:00,1478.75,1480.25,1478.5,1480.0,2317` …). Not the 134-byte LFS pointer — no
  `git lfs pull` needed; nothing synthesised.

## The defect (sixth live failure, 2026-07-29)
The backtest reached the profile step and died with
`FileNotFoundError: '/data/raw/ES_full_1min_continuous_UNadjusted.txt'` in `load_1min_opening`. Two
compounding causes: (a) `RAW_1MIN` was built from the REPO root (`_REPO`), but Railway deploys with
root `/api`, so `_REPO` resolved to `/` → `/data/raw/...`; (b) even corrected, `data/raw/` sits OUTSIDE
`api/` and is LFS text, so it was never in the image at all. Because BOTH compute paths — Class-A
volume-profile backtests and Class-B event studies — read 1-minute data, **neither had ever been able
to run in production**; only extraction was exercised by the seam test. LEAD DECISION applied as stated:
ship the 1-minute data, do not degrade the method to 5-minute profiles.

## 1. Builder + derived file
- **`api/tools/build_1min_rth_parquet.py`** (new). Re-run: `cd api && .venv/bin/python
  tools/build_1min_rth_parquet.py`. Reads the raw text (source of truth) with the SAME `read_csv`
  semantics the old loaders used, filters to RTH **[09:30, 15:59] ET inclusive** — the superset both
  consumers read (the VP opening window [09:30,09:45) is a strict subset) — `sort_index()` for
  determinism, writes parquet via pyarrow. No sampling, no randomness, no run-timestamp → byte-stable.
- **`api/data/ES_full_1min_rth.parquet`** (new): **28,349,422 bytes (28.3 MB)**, **1,806,807 rows**,
  range **2008-01-02 09:30 → 2026-04-10 15:59**, dtypes `float64` OHLC / `int64` Volume, tz-naive
  `DatetimeIndex` named `timestamp`. Committed as a **regular blob, not LFS**: `.gitattributes` routes
  `*.txt`/`*.csv` to LFS but not `*.parquet`; `git check-attr filter` on the new file returns
  `unspecified`, identical to the shipped 5-min parquet. Proportionate to the 19.9 MB 5-min file
  (5× bar density, RTH-only vs the 5-min's full-session coverage).

## 2. Resolution the P3s way; parquet consumed; _REPO purged from data paths
New resolver in `wit/data_paths.py`: `resolve_engine_data_dir()` / `engine_data_path(filename)` —
env override `WIT_ENGINE_DATA_DIR` (if it exists) → `api/data`. `api/data/` ships INSIDE `api/`, so the
"repo walk-up" and "shipped copy" tiers P3s separates coincide there (no `_shipped` copy needed, unlike
the repo-ROOT config files). Consumers repointed and re-resolved at call time:
- `wit/vp_orb_runner.py`: `_NAME_1MIN`/`_NAME_5MIN` + `PARQUET_1MIN`/`PARQUET_5MIN` via
  `engine_data_path`; `load_1min_opening` now `read_parquet`; `_REPO` and the raw-text `RAW_1MIN`
  constant deleted; error messages use `_NAME_1MIN`/`_NAME_5MIN`.
- `wit/event_study.py`: `load_1min_rth` now `read_parquet`; raw-text `RAW_1MIN`/`_REPO` deleted; public
  `PARQUET_1MIN` exposed for server provenance.
- `server.py`: import + provenance switched `RAW_1MIN`→`PARQUET_1MIN` (the removed symbol would have
  broken the server module-load import chain — healthcheck death — so this is load-bearing, not cosmetic).
- `wit/analysis.py`: provenance `R.RAW_1MIN` → `R.PARQUET_1MIN` (dev report script; the old symbol was
  deleted).

**Every remaining `_REPO`-rooted path (full grep), and its disposition:**
| file:line | path | disposition |
|---|---|---|
| `wit/analysis.py:41-42` | `REPORTS = _REPO/docs/wit/reports` | **Not a data path** — dev report OUTPUT dir; left as-is. |
| `wit/event_study_report.py:20-21` | `REPORTS = _REPO/docs/wit/reports` | **Not a data path** — dev report OUTPUT dir; left as-is. |

No `_REPO`-rooted **data** path remains anywhere in `wit/` or `server.py`. (The `_REPO` inside
`tools/build_1min_rth_parquet.py` reads the raw source of truth — a legitimate offline regenerator, not
a runtime/server path; the rule governs the engine loaders.)

## 3. Identical results — acceptance proof
On the **WIT-0001 anchor configuration** (`VPORBConfig()` defaults, full 2016-04-10 → 2026-04-09), 1-min
sourced from the raw text vs the derived parquet, same 5-min frame:
- **Frame equality:** `assert_frame_equal(raw_open, parquet_open, check_exact=True)` — identical, 38,639
  opening-window rows each.
- **KPI equality (every one, not approximate):** all 37 scalar KPIs equal to the digit. Selected:
  `total_trades` 2561 = 2561, `win_rate` 34.322530261616556 (identical), `profit_factor`
  0.9027249232666907 (identical), `net_profit` -5976.890049456466 (identical), `max_drawdown_pct`
  -72.557042255597 (identical), `sl_exit_count` 1649, `tp_exit_count` 803; `days_with_trade` 2562 = 2562.
  (The strategy is a net loser on this window — irrelevant here; this slice proves DATA equivalence, not
  edge.)

## New tests (`tests/test_shipped_1min_data.py`)
1. `test_shipped_1min_parquet_exists_and_shape` (CI) — parquet exists; `DatetimeIndex`, monotonic;
   columns `[O,H,L,C,V]`; dtypes float64×4/int64; every bar inside [09:30,15:59].
2. `test_shipped_1min_range_consistent_with_5min` (CI) — same start date as the 5-min parquet; 1-min
   extends ≥ the 5-min RTH max date; every 5-min RTH trading day is present in the 1-min data; median
   bars/day ∈ [380, 391] (full RTH session = 390).
3. `test_raw_vs_parquet_kpis_identical` (**local only**, `skipif` when the raw LFS text is a bare
   pointer, like the network-gated live tier) — frame-equal opening window + all scalar KPIs equal on a
   2020–2021 anchor slice (hundreds of trades). The full-window equivalent is the §3 proof above.

## Suite counts + goldens
- Before (HEAD 12049b1): **292 passed / 0 failed / 2 skipped**.
- After (local, raw present): **295 passed / 2 skipped** (292 + 3 new; the equality test runs here).
- In CI (raw is a pointer): the equality test skips → **294 passed / 3 skipped**.
- **Both anchor goldens BYTE-IDENTICAL:** mapper G1 (T-0001) and G2 (T-0002) pass unchanged — `mapper.py`
  was not touched this slice (data/loader only). No fixture, threshold, or extraction prompt touched.

## Deploy note (report-only, not fixed)
- **Image size:** grows by the parquet, **~28 MB** (the raw text was never in the image, so nothing is
  removed). No new dependencies; **build time is unchanged** (one more file copied into the layer).
- **For a future slice:** the two 1-minute loaders now `read_parquet` the whole file per call and
  slice in memory (same pattern as `load_5min`); if run latency matters under load, a cached read or a
  columnar predicate-pushdown read is the lever. Also: `git-lfs` need not be installed in the build
  image any more for either compute path to work — the parquet is a plain blob — though the raw LFS
  text is still the regeneration source of truth and must be pulled before re-running the builder.

## Commit
- Subject: `WIT-P4m: ship RTH 1-minute data into the image; no data path is repo-root-relative`
- Hash + URL: recorded in the report-back after push.

WIT-P4m — Completed

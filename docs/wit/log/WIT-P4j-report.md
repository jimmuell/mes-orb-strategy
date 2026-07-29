# WIT-P4j — WIT supplies the J1 test window and the lab instrument; empty data window fails honestly

## STEP 0
Gate passed: remote `jimmuell/mes-orb-strategy`, path `/Users/jameslmueller/Projects/mes-orb-strategy`,
HEAD **82921c7** (WIT-P4i). Read WIT-02 §2 (sections B and J — J is "filled by WIT, not the guru";
B1 is "v1: ES/MES; proxy disclosure if different") and `WIT-P3q-adjudication.md` (fixtures FINAL; R1–R3).

## The defect (third live end-to-end failure, 2026-07-29)
The run reached the backtest and died with `IndexError: index 0 is out of bounds for axis 0 with size 0`
at `data_first = df.index[0]` — the loaded frame had zero rows. The stored wire config showed why, and
a second defect beside it: `data.window = {start: null, end: null}` and `instrument = {symbol: "NQ",
proxy_for: "NASDAQ", tick_size: 0.25, tick_value: null}`. Both are WIT's to fill (§J: the guru can never
state WIT's test window; §B1: v1 always tests ES/MES and discloses the source market as a proxy). The
ratified anchor `WIT-T-0001` hand-fills both, so hand-fed goldens passed while live extractions emitted
nulls and the source's own symbol — the same class of defect as WIT-P4i.

## 1. J1 test window — WIT supplies it when absent
- **Where the range comes from:** `vp_orb_runner.dataset_date_range()` — an `@lru_cache(maxsize=1)`
  function that reads ONLY the ES 5-min parquet's index (`pd.read_parquet(PARQUET_5MIN, columns=[])`,
  ~0.9 s, cached once) and returns `(min, max)` as `YYYY-MM-DD`. Live from the data, never a hardcoded
  pair, so it self-updates as data extends. Current value: `2008-01-02 .. 2026-04-09`.
- **Resolution (mapper, Class A):** `win_start, win_end = window.get("start"), window.get("end")`;
  `window_assumed = win_start is None or win_end is None`; if assumed, `win_start, win_end =
  dataset_date_range()` (lazy import so the common path stays data-free). The wire config's
  `data.window` uses the resolved pair. **Lead decision applied:** the v1 default window is ALL
  available data, not a trailing 10 years.
- **Disclosure:** `assumptions_applied.append("J1_window")` fires ONLY when WIT supplied the window; a
  template-carried window is used verbatim and is NOT disclosed.

## 2. B1 instrument — always the lab's instrument, the source's market as proxy
`_normalize_instrument(b1)` (mapper), applied unconditionally to the emitted `instrument` block:
```python
    src_symbol, src_proxy = b1.get("symbol"), b1.get("proxy_for")
    proxy_for = src_proxy or (src_symbol if src_symbol not in (None, "ES") else None)
    return {"symbol": "ES", "tick_size": 0.25, "tick_value": 1.25, "proxy_for": proxy_for}
```
Rules as written: `symbol` is ALWAYS `"ES"` (never the source symbol — a report claiming it tested NQ
when it ran ES bars is a false disclosure); `tick_size 0.25`, `tick_value 1.25` (never null);
`proxy_for` = the source's market when it isn't ES — its `proxy_for`, else its `symbol` when that names
something other than ES; `null` when the source genuinely traded ES. (Failing run `NQ`/`NASDAQ` →
`proxy_for = "NASDAQ"`, symbol ES, tick_value 1.25.)

## 3. Empty frame → an honest, typed, coded error
- **Guard (`run_vp_orb`, `vp_orb_runner.py`):** before the frame reaches the engine's `df.index[0]`,
  `if len(five) == 0: raise EmptyDataWindow(cfg.start_date, cfg.end_date, os.path.basename(PARQUET_5MIN))`.
- **The error:** new `class EmptyDataWindow(Exception)` with `code = "DATA_UNAVAILABLE"` (the exact
  existing WIT-03 §3.7 vocabulary code for this — declared but previously unused; I chose it over the
  fallback INVALID_CONFIG because a more-specific code already exists) and a clean message:
  `"no data in the resolved window '<start>'..'<end>' for dataset '<file>' — the window is empty
  (nothing to backtest)"`. No pandas traceback.
- **Surfacing the code (server.py — a disclosed touch BEYOND the listed files):** both run-job and the
  extract-job `except Exception` handlers hard-coded `code: "INTERNAL"`. Added `_engine_error_code(e)`
  = `getattr(e, "code", None)` if a non-empty str else `"INTERNAL"`, and used it in the three async-job
  terminal handlers so a typed engine error's code reaches the callback (an empty window now returns
  `DATA_UNAVAILABLE`, not `INTERNAL` + a pandas IndexError). This is the only edit outside
  `mapper.py`/`vp_orb_runner.py`; it is minimal and general (any exception without a `.code` still maps
  to INTERNAL). Flagged here because the task listed only the mapper/runner, but "the callback carries a
  real code" is server-side.

## 4. Tests (each new test + what it proves)
`tests/test_mapper.py` (5):
- `test_P4j_null_window_resolves_to_full_range_and_discloses` — null window → `data.window ==
  dataset_date_range()` (full range, not hardcoded) AND `J1_window` disclosed.
- `test_P4j_template_window_used_verbatim_not_disclosed` — fixture window kept verbatim, `J1_window`
  NOT in assumptions_applied.
- `test_P4j_non_ES_instrument_normalizes_to_ES_with_proxy` — NQ/NASDAQ, tick_value null → symbol ES,
  tick_value 1.25, proxy_for NASDAQ.
- `test_P4j_non_ES_instrument_falls_back_to_symbol_as_proxy` — NQ with proxy_for null → proxy_for "NQ".
- `test_P4j_ES_source_emits_null_proxy` — ES source → proxy_for null.
`tests/test_vp_orb.py` (1):
- `test_P4j_empty_frame_raises_typed_error_not_indexerror` — an empty frame raises `EmptyDataWindow`
  with `code == "DATA_UNAVAILABLE"` and a clean "empty" message, never an IndexError.

## Suite counts + goldens
- Before this slice (HEAD 82921c7): **275 passed / 0 failed / 2 skipped**.
- After: **281 passed / 0 failed / 2 skipped** (275 + 6 new).
- **Both anchor goldens BYTE-IDENTICAL:** `test_mapper.py` G1 (T-0001 → `VPORBConfig()`) and G2
  (T-0002 → `EventStudyConfig()`) pass unchanged — the fixture already carries a window (→ resolution
  no-op, J1_window not disclosed) and ES economics with proxy_for NQ (→ `_normalize_instrument` is
  idempotent, emits the identical block). **No fixture, threshold, or extraction prompt was touched**
  (`api/tests/fixtures/*`, `contract/modes.md`, `wit/extraction/prompt.py` all untouched).

## B3 granularity finding (reported, NOT changed)
The failing run's B3 came through with granularity `"ticks_per_row_1"`, which the engine does not model.
**Nothing consumes it.** The executable granularity comes from **D2 (setup)**: the mapper sets both
`data.granularity_needed` and the adapter's `vp_granularity` from `d2.get("granularity")`
(`mapper.py:209` and `:300`), and the runner's 1min/5min profile path reads `cfg.vp_granularity` (D2).
B3 is read ONLY to append it to `assumptions_applied` (`mapper.py:198`) as the WIT-02 §B3 data-layer
disclosure — its params/value never reach the wire config, the adapter, or the runner. So
`"ticks_per_row_1"` is inert and produces no wrong result; it needs **no slice for correctness**. If the
odd string should be normalized for the disclosure text, that is an extraction-side concern (prompt /
fixtures), which is off-limits here (extraction quality CLOSED under P3q) — a docs/disclosure nicety at
most, not an engine defect.

## Commit
- Subject: `WIT-P4j: WIT supplies the J1 test window and the lab instrument; empty data window fails honestly`
- Hash + URL: recorded in the report-back after push.

WIT-P4j — Completed

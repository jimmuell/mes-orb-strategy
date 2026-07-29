# WIT-P4o — result payload carries a daily, bounded equity curve; per-bar series never leaves the engine

## STEP 0
Gate passed: remote `jimmuell/mes-orb-strategy`, path `/Users/jameslmueller/Projects/mes-orb-strategy`,
HEAD **c569bfe** (WIT-P4m).

## The defect
The first complete production audit computed correctly, then could not be stored: the front office's
write of `result_json` failed at the Cloudflare edge (**520**, then **522**) — the request never reached
Postgres. Not RLS, not grants, not a DB error. The payload was simply enormous: `_backtest_result`
copied `kpis["equity_curve"]` verbatim, and the engine appends ONE entry per BAR
(`engine.py:958` — `equity_curve.append({"date": bar_date, "equity": equity})`). At 5-min resolution
over the full window that is ~1e6 entries — tens of MB of JSON in a single row write. A report has
never needed per-bar equity.

## 1 + 3. The reduction (as written), in `_backtest_result` only
New helper `server._daily_bounded_equity_curve(raw) -> (points, resolution)`:
```python
_EQUITY_CURVE_CAP = 5000

def _daily_bounded_equity_curve(raw):
    # 1) one point per CALENDAR DATE, LAST equity kept; dict preserves first-seen (chrono) order.
    by_date = {}
    for p in raw or []:
        by_date[str(p.get("date"))[:10]] = _finite(p.get("equity"))
    daily = [{"t": t, "equity": e} for t, e in by_date.items()]
    if len(daily) <= _EQUITY_CURVE_CAP:
        return daily, "daily"
    # 2) hard bound: evenly-spaced indices over [0, n-1], first & last always in, EXACTLY cap.
    n = len(daily)
    idxs = [round(i * (n - 1) / (_EQUITY_CURVE_CAP - 1)) for i in range(_EQUITY_CURVE_CAP)]
    seen, keep = set(), []
    for j in idxs:
        if j not in seen:
            seen.add(j); keep.append(j)
    if len(keep) < _EQUITY_CURVE_CAP:            # backfill if rounding collided (only when n≈cap)
        for j in range(n):
            if len(keep) >= _EQUITY_CURVE_CAP: break
            if j not in seen: seen.add(j); keep.append(j)
        keep.sort()
    return [daily[j] for j in keep], "daily_downsampled"
```
`_backtest_result` now emits `equity_curve` from this helper and adds a sibling
**`equity_curve_resolution`** set to `"daily"` or `"daily_downsampled"`. The point shape is unchanged —
still a list of `{"t","equity"}` — so no consumer changes. The cap is a HARD bound: over 5,000 daily
points, the series is downsampled to EXACTLY 5,000 with the first and last always retained, and the
marker tells the reader which they hold.

## 2. KPIs untouched
The reduction reshapes ONLY the emitted list. `_backtest_result`'s `metrics` (`trades`, `net_pnl`,
`profit_factor`, `max_drawdown`, `win_rate`, `avg_trade`) are read straight from `kpis`, which the
engine computes over the FULL per-bar series; `engine.py` is not touched, and `kpis["equity_curve"]`
itself is not mutated (the helper only reads it). Proof: `test_kpis_untouched_by_reduction` asserts the
emitted `metrics` equal the input `kpis` digit-for-digit while the emitted curve is daily and the raw
`kpis["equity_curve"]` retains its full length; and both anchor goldens are byte-identical (below).
No KPI value moved.

## 4. Measured — WIT-0001 anchor (`VPORBConfig()` defaults)
| | points | payload JSON |
|---|---:|---:|
| **BEFORE** (per-bar) | 198,003 | 11,701,718 B (**11.70 MB**) |
| **AFTER** (daily) | 2,577 | 129,604 B (**0.130 MB**) |
| reduction | 76.8× fewer points | **90.3× smaller** |

Resolution marker: `"daily"` (2,577 ≤ 5,000 cap, no downsample). First point `{"t":"2016-04-11",
"equity":10018.76…}`, last `{"t":"2026-04-08","equity":4023.58…}` — first/last preserved. (The full
18-yr window would be larger still; the anchor alone already exceeds the edge's tolerance, which is why
it 520/522'd.)

## 5. Tests (`tests/test_equity_curve_bound.py`, 6)
- `test_daily_reduction_keeps_last_value_per_date_in_order` — multi-bar, multi-day → one point/date,
  LAST equity kept, chronological order.
- `test_over_cap_downsampled_to_exactly_cap_first_and_last_retained` — 12,000 distinct dates → exactly
  5,000 points, first & last retained, strictly increasing & unique, marked `"daily_downsampled"`.
- `test_just_over_cap_still_exactly_cap` — n = cap+1 exercises the rounding-collision backfill → still
  exactly 5,000.
- `test_under_cap_marked_daily_not_downsampled` — 50 days → `"daily"`, 50 points.
- `test_empty_curve_is_empty_daily` — `[]`/`None` → `([], "daily")`.
- `test_kpis_untouched_by_reduction` — `_backtest_result` metrics equal `kpis` exactly; emitted curve
  daily (5 dates); raw `kpis["equity_curve"]` still 20 per-bar points.

## Suite counts + goldens
- Before (HEAD c569bfe): **295 passed / 2 skipped**.
- After: **301 passed / 2 skipped** (295 + 6 new).
- **Both anchor goldens BYTE-IDENTICAL:** mapper G1 (T-0001) / G2 (T-0002) pass unchanged — `mapper.py`
  not touched (empty `git diff`); this slice edits only `server.py`. No fixture, threshold, or
  extraction prompt touched. Router happy-path payload tests still green with the new marker field.

## Report-only (not fixed): other bar-scaled shapes
- **Event-study payload — NO unbounded shape.** `_event_study_result` returns the runner's dict
  verbatim, and `run_config` (event_study.py:340-349) emits only aggregates: `config`, `regime_desc`,
  `n_events` (scalar), `bucket_counts` (3 ints), `cells` (keyed by bucket×regime — a small FIXED grid,
  each cell = scalars + a 2-element CI), `c1_*`/`c2_*`/`did` (scalars + CIs), `horizon_contrasts` (4
  keys). Everything scales with the number of CELLS/horizons, not bars; the 10k bootstrap iterations
  are reduced to `[lo, hi]` CI pairs internally and never leave. No action needed.
- **Backtest payload — equity_curve was the ONLY bar-scaled field.** `metrics`, `trades_url` (null),
  and `provenance` are scalar; per-trade data (which scales with TRADES, not bars) is not emitted at
  all. After this slice the backtest payload has no field that scales with bar count.

## Commit
- Subject: `WIT-P4o: result payload carries a daily, bounded equity curve — per-bar series never leaves the engine`
- Hash + URL: recorded in the report-back after push.

WIT-P4o — Completed

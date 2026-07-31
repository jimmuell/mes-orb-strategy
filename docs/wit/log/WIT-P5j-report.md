# WIT-P5j — reconcile identical metrics from two config hashes (read-only findings)

**No behaviour changed.** No fixture, golden, threshold, prompt, or engine source file was edited.
Only read-only reproduction against the shipped `api/data/` parquet.

## STEP 0
Gate passed: remote `jimmuell/mes-orb-strategy`, path correct, HEAD == origin/main == **`13cf240`**
(WIT-P5i). No pull/reset/checkout/stash.

## 1. config_hash — both match production exactly
The server hashes `req.config` (the inner `config` object, incl. `assumptions_applied`) at
`server.py:2074`. Computing `wit.config_hash.config_hash` over each inner config:

| config | computed | expected | match |
|---|---|---|---|
| A (eval bfcc1efa) | `e6f2045dd09f20abeb1acf7d02f9dd13a24f8e35bd8d2766e5e4326e783f44b4` | `e6f2045d…f44b4` | **YES** |
| B (eval 19e3b196) | `d7876624f4d165c8f8e1747b153c5f73bb4199a881a03bc5fdfd540dd6e2df35` | `d7876624…df35` | **YES** |

The local config text is byte-for-byte the production config. The two differ in exactly two places:
`exits.stop.ref` (A `point_of_control` / B `poc`) and `session.trade_window[0]` (A `09:45` / B `09:30`).

## 2. Full-window run (2008-01-02 → 2026-04-09, shipped ES parquet)
Runner path: `strategy_config_to_vporb(inner) → run_vp_orb`. Dataset read:
`api/data/ES_full_5min_continuous_UNadjusted.parquet` — the same file named by the production
`dataset_version`.

| metric | CONFIG A | CONFIG B |
|---|---|---|
| trades | 4161 | 4161 |
| net_pnl | -8465.890083640523 | -8465.890083640523 |
| profit_factor | 0.9193420635532844 | 0.9193420635532844 |
| win_rate | 37.89954337899543 | 37.89954337899543 |
| max_drawdown | -15069.406289062921 | -15069.406289062921 |
| avg_trade | -2.0345806497573955 | -2.0345806497573955 |

## 3. Answers

### 3a. Do A and B produce identical metrics locally? **YES.**
All six metrics are byte-identical between A and B.

### 3b. Does A reproduce the production result EXACTLY? **YES.**
Every metric matches production to the last digit (4161; -8465.890083640523; 0.9193420635532844;
37.89954337899543; -15069.406289062921; -2.0345806497573955). There is **no** local-versus-production
divergence: same engine logic, same dataset file (`ES_full_5min_continuous_UNadjusted.parquet`),
deterministic run. (The WIT-P5i "4623 vs 4161" gap was **not** a divergence — P5i's *reconstructed*
config used `value_area_pct = 0.70`, whereas the real production config carries `value_area_pct = 70`.
Correcting that single value reproduces production exactly, as shown below.)

### 3c. Why is moving trade_window[0] 09:45→09:30 inert for THIS config? (mechanism, from source)
The leading hypothesis is **correct, but only because of `value_area_pct = 70`** — and that detail is the
crux. Chain, cited:

1. **`value_area_pct = 70` collapses the value area to the entire opening range.** In
   `volume_profile._value_area` (`wit/volume_profile.py:92-110`), `target = total * value_area_pct`.
   With `value_area_pct = 70`, `target = 70 × total`, which cumulative row volume can never reach
   (max is `total`), so the greedy loop `while cum < target and (lo>0 or hi<n-1)` expands until it
   spans **every** row. Result: `VAH = highest price row`, `VAL = lowest price row` of the
   [09:30,09:45) opening window — i.e. the opening-range **High/Low**. Verified on 2020-06-01: raw
   range High/Low = 3039.5/3027.0; at pct=70 VAH/VAL = 3039.5/3027.0 (value_area_fraction = 1.000).

2. **No entry-candidate bar inside [09:30,09:45) can break its own range.** Entry candidates are 5-min
   bars with `t ∈ [entry_window_start, entry_window_last_bar]` (`vp_orb_runner.py:175-176`). Moving
   the start to 09:30 adds the 09:30, 09:35 and 09:40 bars. `_qualifies` (`vp_orb_runner.py:158-162`)
   for `body` mode requires `min(Open,Close) > VAH` (long) or `max(Open,Close) < VAL` (short). But each
   of those three bars lies **inside** the [09:30,09:45) window from which VAH/VAL were built, so its
   `High ≤ VAH` and `Low ≥ VAL`; therefore `min(Open,Close) ≤ High ≤ VAH` and the strict `>` can never
   hold (symmetrically for shorts). The extra bars are structurally incapable of producing a signal, so
   the first eligible breakout is still the 09:45 bar (the first bar OUTSIDE the range). The wider
   window admits no additional *qualifying* bars → the edit is inert.

**Empirical confirmation (full window):** at `value_area_pct = 70`, `09:45 → 4161` and `09:30 → 4161`
(identical). This is exactly A vs B.

### 3d. Reconcile with WIT-P5i step 2, where the same edit DID move the numbers.
The difference is **`value_area_pct`, not `range_end`** (both P5i and production use `range_end =
09:45`). P5i's reconstructed config used `value_area_pct = 0.70`; production uses `70`.

At `value_area_pct = 0.70` the value area is the true 70% band, which is **strictly inside** the opening
range (2020-06-01: VAH/VAL = 3034.25/3028.0 vs range 3039.5/3027.0, value_area_fraction = 0.712). Those
tighter VAH/VAL **can** be broken by a bar within [09:30,09:45), so widening the window to 09:30 admits
qualifying early bars and the count moves. Empirical, full window: at `0.70`, `09:45 → 4623` and
`09:30 → 4635` (differ) — reproducing P5i's 4623 precisely. So the *same* `trade_window[0]` edit is
material at `pct = 0.70` and inert at `pct = 70`, entirely because of what the value-area width does to
VAH/VAL.

| value_area_pct | VAH/VAL vs range | 09:45 trades | 09:30 trades | trade_window[0] edit |
|---|---|---:|---:|---|
| 70 (production) | == range High/Low (whole profile) | 4161 | 4161 | **inert** |
| 0.70 (P5i recon) | tighter, inside the range | 4623 | 4635 | **material** |

## 4. Verdict
The `trade_window` difference is **genuinely inert for this config shape** (`value_area_pct = 70`, entry
range `[09:30,09:45)`, entry candidates that can only break the range from 09:45 onward). Therefore
**two different config_hashes legitimately yielding identical metrics is CORRECT engine behaviour and
there is no engine bug.** The engine behaved correctly in production: it hashed two genuinely-different
wire configs to two different hashes (as it should — the wires differ), ran both deterministically, and
returned identical metrics because the sole *honoured* difference (`trade_window[0]`) has no effect
under this value-area shape and the other difference (`exits.stop.ref`) is not consumed at all (WIT-P5i).

**Observation for a future slice (not an engine bug, out of scope here):** `value_area_pct = 70` almost
certainly means "70%" and should be `0.70`. As a fraction it degenerates the value area to the full
opening range, which materially changes which breakouts qualify. That is an extraction/mapper
units question upstream of the engine — the engine faithfully computed what the config specified.
Recommend the lead review how `value_area_pct` is extracted/normalized (70 vs 0.70) separately.

## 5/6. Suite + commit
- Suite: `cd api && BACKTEST_API_KEY=k python -m pytest -q` → **308 passed / 0 failed / 2 skipped** —
  unchanged from baseline (no code, tests, or fixtures touched).
- Commit subject: `WIT-P5j: reconcile identical metrics from two config hashes — read-only findings`
- Hash + URL: recorded in the chat report-back after push.

WIT-P5j — Completed

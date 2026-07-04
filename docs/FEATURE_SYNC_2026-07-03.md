# TradingGYM Engine — Feature Sync (last 10 days)

**Window:** 2026-06-25 → 2026-07-03 · **Engine version:** `25.16.0` · **Tests:** 102 passing
**Purpose:** onboard a collaborator ("cowork") to everything shipped to the backtest engine in this
sprint. Every feature below is merged to `main` and traceable to a PR + an ADR (Architecture
Decision Record in `docs/`).

---

## 1. What this component is

The **backtest engine** is a FastAPI service in **`api/`**, deployed on **Railway**, consumed by the
TradingGYM web app over HTTP. It runs AI-generated trading-signal code against historical MES/ES
5-minute data, computes KPIs + an equity curve, validates the edge, and (new this sprint) teaches the
user what each risk lever cost them.

- **Live engine:** `api/engine/engine.py` — MES economics at **$5/point**. This is the source of truth.
- **Frozen legacy copy:** `backtest/engine/engine.py` — stale, unimported, **do not touch**.
- **Validation library:** `backtester` (external repo, pinned by commit) — Monte-Carlo/bootstrap CIs,
  walk-forward, random-entry benchmark, regime breakdown.
- **Version single-source:** `__version__` in `api/engine/engine.py`. `/ping` reports it live.

### HTTP endpoints (current)

| Endpoint | Purpose |
|---|---|
| `POST /run` | Synchronous backtest → KPIs, trades, equity curve, validation |
| `POST /run/compare` | **TEACH-COMPARE** — backtest + 6 neutralized-variant "teaching" blocks |
| `POST /run/async` | Accept job, return 202, run in background, write result via callback |
| `GET /health` | Healthcheck (loads data) — `status`, `engine_version`, bar count |
| `GET /ping` | Cheap diagnostic — `engine_version`, `data_path`, size (no data load) |

---

## 2. Feature areas shipped this sprint

### A. Security hardening of the run path — ADR-021 (PR #1)
- **API key required** — `BACKTEST_API_KEY`; 503 if unset (misconfig), 401 if wrong.
- **CORS** restricted to an env allowlist (`ALLOWED_ORIGINS`).
- **Signal-code sandbox** — AST allowlist (no imports/dunders/denied names, fail-closed) + `SAFE_BUILTINS`
  + a SIGALRM wall-clock timeout. Honest caveat: still in-process, not a hardened sandbox.

### B. Edge-validation ("is this a real edge or luck?") — ADR-028 (PRs #2, #4, #17)
- Integrated the `backtester` library: bootstrap confidence intervals (expectancy/net/PF/win-rate),
  walk-forward temporal stability, random-entry + buy-hold benchmarks, regime breakdown.
- Fed the **actual bars** into validation (so random-entry/regime analyses light up) with a
  caller-controlled iteration budget.
- Returned on **both** `/run` and `/run/compare` (primary run) under `response.validation`.
- The verdict language is deliberately cautious ("necessary but not sufficient", no multiple-testing
  correction yet) — it's built to **reject** thin edges, not rubber-stamp them.

### C. Economics & fill-mechanics accuracy — ADR-018/022/023/024/025/030 (PRs #5,#8,#10,#11,#12,#13,#19)
- **True MES economics: $5/point** — engine `MES_POINT_VALUE` and the validation instrument move in
  lockstep (ADR-018).
- **Timezone crash fix** — date bounds normalize to the bar-index timezone (fixes an aware-vs-naive
  `TypeError` that produced null verdicts in production) (ADR-022).
- **Point-denominated stops/targets** — `take_profit_points` / `stop_loss_points` alongside percent,
  with a documented precedence (ADR-023); protective stop/target is **live from the entry bar** (ADR-025).
- **Adverse slippage model** — constant ticks on every fill, `MES_TICK_SIZE = 0.25` (ADR-024).
- **Flat per-round-trip commission** — `commission_mode="flat_per_rt"`, default **$1.24/RT** (from real
  AMP statements) alongside the percent model (ADR-030).
- **TP/SL exit counters** surfaced in KPIs.

### D. TEACH-COMPARE — the headline feature — ADR-026→034 (PRs #14,#16,#17,#18,#20–26)
`POST /run/compare` runs the user's config **plus one neutralized variant per risk lever against the
same signal**, and returns a "teaching" block per lever quantifying what it cost/saved. **Six
dimensions, in order:**

| # | Dimension | Neutralized to | ADR |
|---|---|---|---|
| 1 | `stop` | no stop | 026 |
| 2 | `take_profit` | no target | 029 |
| 3 | `commission` | fee-free | 031 |
| 4 | `direction` | long-only ↔ long-short | 032 |
| 5 | `slippage` | 0 ticks | 033 |
| 6 | `position_size` | 1 contract | 034 |

- Each teaching delta gets a **significance judgment** via percentile bootstrap (seed 42) — real vs
  luck — except `direction`/`position_size` which are deterministic (ADR-027).
- `same_signal` hash chain proves the signal series is identical across all runs.
- Hardening: numpy types coerced at the response boundary so no field can 500 (ADR-031).
- The primary run is validated (ADR-028); the six blocks power the app's Teach/Coach/Explain panels.

### E. Full-history data + performance — ADR-035/036/041 (PRs #27,#28,#33)
- **Full 18-year history shipped as Parquet** — CSV→`api/data/…parquet` (18.97 MB, 1,289,036 bars,
  2008→2026, float32/int32, round-trip exact to the tick). Loader reads `.parquet`; the 6-month CSV
  stays the fail-safe default (ADR-035).
- **Vectorized `calc_ema`** — removed the per-row Python loop that tripped the 10s signal timeout;
  **30s → 0.03s over 18yr, tick-identical trades** (ADR-036).
- **Vectorized the last indicator loops** — `calc_smma` (~693×), `calc_obv` (~27×, exact),
  `calc_wma` (seconds→10ms), each matched to the prior loop to the tick (ADR-041).

### F. Async execution (long runs) — ADR-037/038/040 (PRs #29,#30,#32)
- **`POST /run/async`** — accepts a job, returns **202** immediately, runs the **compare** pipeline in
  a background thread (no request clock), so full-history runs (~55–86s) don't hit Railway's ~60s
  proxy limit. Writes progress + result to a `backtest_runs` row; always reaches a terminal state
  (`complete`/`failed`, never stuck `running`) (ADR-037).
- **Write shape matches the sync edge function** so the app renders async runs identically — flattened
  primary KPIs + `_teaching` (6) + `_same_signal`, `max_drawdown` as percent (ADR-038).
- **Callback transport + SSRF hardening** — the engine can't reach Supabase directly (Lovable Cloud
  hides the service-role key), so it POSTs results to a `backtest-callback` edge function with a
  per-request `callback_url` + `X-Callback-Secret`. URL is allowlisted to `https://*.supabase.co`
  (blocks metadata/private/loopback/userinfo-bypass hosts, 400 before any request), redirects disabled
  (ADR-040).

### G. Reliability — ADR-039 (PR #31)
- **Fixed a production import crash** — a forward-reference annotation (`_map_compare_columns` →
  `CompareResponse`) that raised `NameError` at import on Railway's Python 3.12 (masked locally by
  3.14's lazy annotations), blocking every deploy since ADR-036. Fix: `from __future__ import
  annotations`. Added an import+`/health` smoke test so a non-importable app can never pass the suite
  again.

---

## 3. Chronology (traceability)

| Date | PR | ADR | What |
|---|---|---|---|
| 06-25 | #1 | 021 | Harden run path: API key, CORS, AST sandbox + timeout |
| 06-25 | #2 | 028 | Integrate backtester validation → verdict on `/run` |
| 06-26 | #4,#5,#6,#8 | 018,020,022 | Validation bars+budget; $5/pt economics; numpy/pandas floors; tz-bounds fix |
| 06-27 | #10,#11 | 023 | TP/SL exit counts; constant point stops/targets |
| 06-28 | #12,#13 | 024,025 | Adverse slippage; stop/target live from entry bar |
| 06-29 | #14,#15,#16 | 026,027 | **/run/compare (TEACH-COMPARE)**; equity curve on `/run`; significance |
| 06-30 | #17,#18,#19 | 028,029,030 | Validation on compare; take-profit dim; flat commission |
| 07-01 | #20,#21,#22,#23,#24 | 031,022,032 | Commission dim + serialize hardening; DECISIONS entry; direction dim |
| 07-02 | #25,#26 | 033,034 | Slippage dim; position-size dim (6th) |
| 07-02 | #27,#28 | 035,036 | Full-history Parquet; vectorize calc_ema |
| 07-02 | #29,#30,#31,#32 | 037,038,039,040 | Async exec; shape match; import-crash fix; callback+SSRF |
| 07-03 | #33 | 041 | Vectorize calc_smma/calc_wma/calc_obv |

---

## 4. Current state & where to look

- **Version on `main`:** `25.16.0` · **Suite:** `cd api && python -m pytest -q` → 102 passing.
- **Full ADR text:** `docs/ADR-0NN_*.md` (one per feature) and `docs/DECISIONS.md` (index + short entries).
- **Engine internals / pitfalls:** `backtest/BACKTESTING.md`, `backtest/MEMORY.md`.
- **Key files:** `api/server.py` (endpoints, sandbox, compare, async), `api/engine/engine.py`
  (backtest core, indicators, KPIs), `api/callback_writer.py` (async result transport),
  `api/data/ES_full_5min_continuous_UNadjusted.parquet` (full history).

## 5. Deploy state (merged vs live) — action items for whoever owns Railway

All the above is on `main`; the running service may lag until a redeploy. Outstanding manual steps:

1. **Redeploy** and confirm `/ping` reports **25.16.0** (it was pinned to an older build until the
   ADR-039 import fix; verify it has advanced).
2. **Flip `DATA_PATH`** → `/app/data/ES_full_5min_continuous_UNadjusted.parquet` to serve the full 18
   years — **gated on the service's memory limit** (~266 MB load, higher transient during a run; want
   ≥512 MB, ideally 1 GB).
3. **Env vars:** `/run/async` now needs **nothing Supabase-specific** — the callback URL + secret
   arrive per request (ADR-040). The old `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` can be removed.
   Keep `BACKTEST_API_KEY`. Optional: `CALLBACK_ALLOWED_HOST_SUFFIX` (defaults `.supabase.co`).

---

*Generated 2026-07-03. Covers PRs #1–#33 / ADR-018 through ADR-041.*

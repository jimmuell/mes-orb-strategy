# ADR-037 — Async backtest execution (background job, writes to Supabase)

**Status:** Accepted (v25.12.0)

**Context:** `/run` holds the HTTP request open for the whole backtest (~55–86s on full history),
which trips Railway's ~60s proxy limit. We need runs that don't live on a request clock.

**Decision:** Add a **`POST /run/async`** endpoint (the "light" model — an in-process FastAPI
background task, no separate worker/queue). It accepts the same body as `/run` **plus** `run_id`
(a caller-created `backtest_runs` row), returns **202 immediately**, and drives that Supabase row to
completion in the background. The existing synchronous **`/run` is unchanged**.

- **Shared pipeline, no duplication.** `/run`'s body was extracted into `_execute_run_sync(req,
  on_progress=None)`; `/run` is now a thin wrapper (`return _execute_run_sync(req)`), so its behavior
  is byte-identical (verified by the existing suite). The async job calls the **same** core — no
  engine/compare/indicator logic is reimplemented or touched.
- **Off-loop compute.** The blocking pipeline runs via `asyncio.to_thread`, so the event loop stays
  responsive during a long run. The SIGALRM signal-timeout simply no-ops off the main thread (already
  handled) — fine here, the async run has no deadline.
- **Progress.** `on_progress(pct)` fires at phase boundaries — job picked up (10), signal columns
  ready (20), backtest complete (60), validation done/finalizing (90), terminal write (100). Coarse
  by design; each ping is best-effort (a failed ping never aborts the job).
- **Terminal states (never stuck at running).** On success → the mapped result + `status='complete'`,
  `progress=100`. On any error/exception → `status='failed'`, `progress=100`, and a short
  user-friendly `error_message` (first line of the error, trimmed). A last-resort `except` guarantees
  a terminal write even if the compute or a write throws.
- **Supabase writer** (`api/supabase_writer.py`): a minimal PostgREST client (`requests`, already a
  runtime dep — no new dependency) that PATCHes `backtest_runs` by id. Auth from **new env vars**
  `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` only (service-role, server-side trusted; no secrets
  in code). `get_supabase_writer()` returns `None` when unset → `/run/async` returns a clear **503**
  (misconfig is loud, not silent). The writer is injectable, so the async flow is fully unit-tested
  with a fake writer — no live Supabase needed.

**Result → `backtest_runs` column mapping** (KPI source keys are the engine's `compute_kpis` names):

| Column | Source |
|---|---|
| `net_pnl` | `kpis.net_profit` |
| `total_trades` | `kpis.total_trades` |
| `wins` / `losses` | `kpis.num_winning` / `kpis.num_losing` |
| `win_rate` | `kpis.win_rate` |
| `profit_factor` | `kpis.profit_factor` |
| `max_drawdown` | `kpis.max_drawdown` |
| `avg_winner` / `avg_loser` | `kpis.avg_winning` / `kpis.avg_losing` |
| `results_detail` | full detail: `{kpis, trades, equity_curve, validation, validation_error, engine_version, execution_time_ms, signal_hash}` |
| `equity_curve` | response `equity_curve` (downsampled points) |
| `engine_version`, `execution_time_ms` | response fields |
| `signal_hash` | sha256 of the signal columns (`_signal_hash`) — now also returned by `/run` |
| `validation` (+ `validation_error` if present) | response fields |
| `status`, `progress` | `complete`/`failed`, `0→100` |

`inf`/`nan` KPI values are already coerced to `None` by `_sanitize_kpis` (safe for numeric DB
columns). `results_detail` carries the `_teaching` blocks when the source is a compare run — for the
`/run` body there are none, so it holds the plain backtest detail.

**Consequence:** Full-history runs no longer die on the proxy timeout; the app watches the row
(Supabase Realtime) and renders when `status='complete'`. Additive: `/run`, `/run/compare`, and the
engine are untouched aside from `/run`'s (behavior-identical) extraction and an additive optional
`signal_hash` response field. New env vars required in Railway: **`SUPABASE_URL`**,
**`SUPABASE_SERVICE_ROLE_KEY`**. `__version__` → **25.12.0**.

**Assumption to confirm before merge:** the exact `backtest_runs` column names/shape above should be
checked against the Supabase edge function that creates the row. If the app expects different names
(e.g. `net_profit` vs `net_pnl`), adjust `_map_success_columns` — it is the single mapping site.

**RULE:** the async job must always reach a terminal state — every code path writes `complete` or
`failed` (never leaves `running`); progress pings are best-effort. The result→column mapping lives in
one place (`_map_success_columns`); keep it mirroring the sync response so the UI renders identically.

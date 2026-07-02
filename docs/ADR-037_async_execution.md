# ADR-037 — Async backtest execution (background job, writes to Supabase)

**Status:** Accepted (v25.12.0)

**Context:** `/run` (and `/run/compare`) hold the HTTP request open for the whole backtest
(~55–86s on full history), which trips Railway's ~60s proxy limit. We need runs that don't live on a
request clock. The app's main "Run backtest" uses the **compare** pipeline (`run_compare`) — that's
what produces the six teaching blocks (`results_detail._teaching`: stop, take_profit, commission,
direction, slippage, position_size) rendered on every run — so the async path must run **compare**,
not the plain run, or it would drop the whole TEACH-COMPARE feature.

**Decision:** Add a **`POST /run/async`** endpoint (the "light" model — an in-process FastAPI
background task, no separate worker/queue). It accepts the same body as `/run` **plus** `run_id`
(a caller-created `backtest_runs` row), returns **202 immediately**, and drives that Supabase row to
completion by running the **compare pipeline** in the background. The synchronous `/run` and
`/run/compare` endpoints are **unchanged**.

- **Shared pipelines, no duplication.** Both `/run` and `/run/compare` bodies were extracted into sync
  cores — `_execute_run_sync(req, on_progress=None)` and `_execute_compare_sync(req, on_progress=None)`
  — and the endpoints are now thin wrappers (`return _execute_*_sync(req)`), byte-identical behavior
  (verified by the suite). The async job calls **`_execute_compare_sync`** — the same code
  `/run/compare` serves — so no compare/teaching/indicator logic is reimplemented or touched.
- **Off-loop compute.** The blocking pipeline runs via `asyncio.to_thread`, so the event loop stays
  responsive during a long run. The SIGALRM signal-timeout no-ops off the main thread (already
  handled) — fine, the async run has no deadline.
- **Progress.** `on_progress(pct)` fires at the compare pipeline's phase boundaries — picked up (10),
  signal columns ready (20), primary run done (50), variants + teaching built (80), validation done/
  finalizing (95), terminal write (100). Best-effort — a failed ping never aborts the job.
- **Terminal states (never stuck at running).** On success → the mapped result + `status='complete'`,
  `progress=100`. On any error/exception → `status='failed'`, `progress=100`, and a short
  user-friendly `error_message`. A last-resort `except` guarantees a terminal write even if compute
  or a write throws.
- **`results_detail` is the compare result VERBATIM** — including `_teaching` (the six blocks) — not
  rebuilt from parts, so async rows match a synchronous compare run and the UI keeps its cards. It
  carries `{primary, variants, _teaching, same_signal, validation, validation_error, engine_version,
  execution_time_ms, signal_hash}`.
- **Supabase writer** (`api/supabase_writer.py`): a minimal PostgREST client (`requests`, already a
  runtime dep — no new dependency) that PATCHes `backtest_runs` by id. Auth from **new env vars**
  `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` only (service-role, server-side trusted; no secrets
  in code). `get_supabase_writer()` returns `None` when unset → `/run/async` returns a clear **503**.
  Injectable → the async flow is fully unit-tested with a fake writer, no live Supabase.

**Result → `backtest_runs` column mapping** (single site `_map_compare_columns`; summary columns come
from the **primary/user's run**, KPI keys are the engine's `compute_kpis` names):

| Column | Source (primary run) |
|---|---|
| `net_pnl` | `primary.kpis.net_profit` |
| `total_trades` | `primary.kpis.total_trades` |
| `wins` / `losses` | `primary.kpis.num_winning` / `num_losing` |
| `win_rate` | `primary.kpis.win_rate` |
| `profit_factor` | `primary.kpis.profit_factor` |
| `max_drawdown` | `primary.kpis.max_drawdown` |
| `avg_winner` / `avg_loser` | `primary.kpis.avg_winning` / `avg_losing` |
| `results_detail` | the compare result verbatim, incl. **`_teaching`** (six blocks) |
| `equity_curve` | `primary.equity_curve` |
| `engine_version`, `execution_time_ms` | response fields |
| `signal_hash` | sha256 of signal columns — now on `CompareResponse` (and `/run`) |
| `validation` (+ `validation_error` if present) | primary-run validation (ADR-028) |
| `status`, `progress` | `complete`/`failed`, `0→100` |

`inf`/`nan` KPI values are already coerced to `None` by `_sanitize_kpis` (safe for numeric DB
columns).

**Consequence:** Full-history runs no longer die on the proxy timeout; the app watches the row
(Supabase Realtime) and renders — with its six teaching cards — when `status='complete'`. Additive:
`/run`, `/run/compare`, the compare/teaching logic, and the engine are untouched aside from the
(behavior-identical) sync-core extractions and an additive optional `signal_hash` field on both
responses. New env vars required in Railway: **`SUPABASE_URL`**, **`SUPABASE_SERVICE_ROLE_KEY`**.
`__version__` → **25.12.0**.

**Assumption to confirm before merge:** the exact `backtest_runs` column names/shape above (including
the `_teaching` key inside `results_detail`) should be checked against the Supabase edge function that
creates the row. If the app expects different names, adjust `_map_compare_columns` — the single site.

**RULE:** the async job runs the **compare** pipeline (an async run == a normal run, teaching cards
kept); it must always reach a terminal state (every path writes `complete` or `failed`, never leaves
`running`); progress pings are best-effort; and `results_detail` carries the compare result verbatim
(with `_teaching`), never rebuilt from parts. The result→column mapping lives in one place
(`_map_compare_columns`).

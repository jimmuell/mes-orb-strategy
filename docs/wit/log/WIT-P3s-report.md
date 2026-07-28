# WIT-P3s — deploy-layout fix: runtime data shipped under api/_shipped (drift-gated) + robust resolution

## 1. STEP 0
- HEAD **d601e19** (WIT-P3r) — matches. Repo/path/origin match the header. Tree clean except the
  known untracked `pine/mes_net_pnl_v2.pine`. No LLM calls.
- Fixtures, scorer (`completeness.py`), golden, ensemble logic, and the prompt RULE text are all
  untouched — only path-resolution lines changed. Deploy-layout only.

## 2. T0 — complete list of runtime-read repo-root files (file:line)
Four distinct CONFIG files, across five call sites. **All four are read at IMPORT time** (so they
kill the healthcheck before any request), and two are ALSO read on the request path:

| File | Call site(s) | When |
|---|---|---|
| `schema/strategy-template.v1.json` | `wit/extraction/schema.py:22` (`SCHEMA_PATH`) → `load_schema()`; `FIELD_IDS = _field_ids()` at module load | **import** (this is the exact prod traceback: server → wit.mapper → completeness → schema) |
| `contract/strategy-config.v1.json` | `server.py:1755` `_load_required` (module-level `_WIT_WIRE_REQUIRED`, via `../contract/`) **and** `wit/mapper.py:27` → opened at `mapper.py:191` | **import** (server) + request (mapper) |
| `contract/event-study-config.v1.json` | `server.py:1755` `_load_required` **and** `wit/mapper.py:28` → opened at `mapper.py:302` | **import** (server) + request (mapper) |
| `contract/modes.md` | `wit/extraction/prompt.py:20` (`MODES_PATH`) → `_read_modes()` in `build_system_prompt()` | request (extract path) — but `prompt` imports at server import |

OUT OF SCOPE (reported, not shipped): the large market-DATA files — `wit/event_study.py:38`
(`RAW_1MIN`), `wit/vp_orb_runner.py:40-41` (`PARQUET_5MIN`, `RAW_1MIN`), `server.py:146` (`DATA_PATH`).
These are hundreds of MB, read LAZILY only when a run actually executes (never at import/healthcheck),
and are deployed via their own mechanism (Git LFS / data dir) — not the startup blocker. Dev/report
scripts (`wit/analysis.py`, `wit/event_study_report.py`) write to `docs/wit/reports`, not read at
server runtime.

## 3. What ships in api/_shipped + resolution order
- **api/_shipped/** (byte-identical `cp` copies, layout preserved, `cmp`-verified):
  `schema/strategy-template.v1.json`, `contract/modes.md`, `contract/strategy-config.v1.json`,
  `contract/event-study-config.v1.json`. A parametrized **drift test** asserts each is byte-identical
  to its repo-root original, so the copies can never silently rot.
- **Resolver `wit/data_paths.py`** — `resolve_data_root()` returns the dir containing both `schema/`
  and `contract/`, first hit wins: **(1)** `WIT_DATA_ROOT` env (if it has the markers); **(2)** the
  repo root found by walking UP from the module (dev checkout); **(3)** `api/_shipped/` (the
  `/api`-rooted container). Total failure raises `FileNotFoundError` listing EVERY searched path.
  `data_path(*parts)` joins onto the resolved root. Every T0 call site now uses it
  (`schema.py`, `prompt.py`, `mapper.py`, `server.py`); the load functions re-resolve at call time
  (env-overridable) while the module path constants resolve at import so a missing root fails the
  healthcheck loudly rather than on first request.
- Effect on the container: `/app/wit/data_paths.py` walk-up finds no `schema/`+`contract/` ancestor
  (root is `/api`), so resolution falls to `/app/_shipped` — startup now succeeds.

## 4. Tests + suite counts
`tests/test_data_paths.py` (10): env override wins; env-without-markers ignored → walk-up; walk-up
finds repo root in the checkout; `_shipped` fallback when env+walk-up absent (monkeypatched module
path); total-failure lists every searched path; drift test ×4 (byte-identical); startup-shaped test
forcing resolution to `_shipped` and re-running the load-bearing schema + modes reads (the exact prod
failure mode, now green). Full CI-safe suite (`cd api && BACKTEST_API_KEY=k python -m pytest -q`):
**258 passed / 0 failed / 2 skipped** (248 prior + 10 new; the 2 skips are the network-gated live tier).

## 5. Commit + CI
- Commit hash: this commit — see `git log --oneline -1`
  (`WIT-P3s: deploy-layout fix — runtime data shipped under api/_shipped (drift-gated), robust resolution`).
- CI status: recorded in the report-back after push. NOTE: the push triggers a Railway auto-deploy;
  its health status is watched from the dashboard (lead + Jim), not from this session.

## 6. Anything unexpected
- The failure is worse than one file: `schema/strategy-template.v1.json` (import, the reported one)
  PLUS `server.py`'s `_WIT_WIRE_REQUIRED` reads both `contract/*.v1.json` at import via `../contract/`
  (`/api/../contract` = `/contract`, also missing). Both are now resolver-backed, so the whole
  import chain is fixed, not just the one traceback line.
- Two files (`contract/{strategy-config,event-study-config}.v1.json`) are read at BOTH import (server)
  and request (mapper) — a single shipped copy + one resolver covers every site.
- Read hook truncated file reads to line 1 again; used `sed`/`grep`/`cmp` and import smoke checks.
  No content impact.

WIT-P3s — Completed

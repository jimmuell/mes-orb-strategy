# WIT-P3r — POST /wit/v1/extract (engine-owned k=3 ensemble) + anthropic to the runtime lock

## 1. STEP 0 + recon
- HEAD **83456fb** (WIT-P3q) — matches. Repo/path/origin match the header. Tree clean except the
  known untracked `pine/mes_net_pnl_v2.pine`. No live LLM calls (endpoint tests mock the ensemble).
- **Recon — the async job + callback pattern exists exactly as the handoff describes.** `/wit/v1/*`
  lives in `server.py` (from line ~1729): bearer auth `verify_wit_key` (own env `WIT_ENGINE_SERVICE_KEY`,
  `hmac.compare_digest` constant-time), `WITRunStore` (`wit/run_store.py`) with `register()` idempotency
  keyed `(evaluation_id, hash)`, `_run_wit_job` background task (heartbeat via `_compute_within_budget`
  + GUARANTEED terminal via `_wit_terminal`), signed callback `get_wit_callback_writer`
  (`X-WIT-Signature`), `_budget_error` on wall-budget timeout, kill-switch precedent
  `enforce_exec_enabled` (DISABLE_EXEC_ENDPOINTS). Audit tooling: `scripts/audit_gate.py` (ADR-050),
  invoked by CI (`.github/workflows/ci.yml`) as `python scripts/audit_gate.py api/requirements.txt`;
  the runtime lock is a FULL transitive pin in `api/requirements.txt`. No new patterns invented.

## 2. ADR-050 audit result (anthropic in the runtime lock)
`anthropic==0.120.0` promoted from `requirements-dev.txt` into `api/requirements.txt` (direct dep)
together with its full transitive closure, each pinned at the installed/working version:
`distro==1.9.0`, `docstring-parser==0.18.0`, `httpx==0.28.1` (also used by TestClient),
`httpcore==1.0.9`, `jiter==0.16.0`, `sniffio==1.3.1` (the last was a pre-existing unpinned gap of
anyio). `requirements-dev.txt` no longer lists anthropic/httpx (inherited via `-r requirements.txt`).
The lazy import in `provider.py` is unchanged.

Verdict: **✅ no known vulnerabilities in the runtime lock** — 0 findings across all 41 pinned runtime
deps (the 7 new ones included). NOTE ON HOW IT WAS RUN: `scripts/audit_gate.py` could not execute
locally — `pip-audit`'s `-r` mode builds an ephemeral venv and its `ensurepip` step SIGABRTs under this
machine's uv-managed CPython 3.12.13 (an environment quirk, NOT an audit finding). I verified the
equivalent result by driving `pip_audit`'s PyPI advisory service directly over the pinned set
(`PyPIService().query()` for every `name==version`), which returned **0 vulnerabilities** and confirmed
all 7 new packages are present. CI runs the real `scripts/audit_gate.py` on a clean GitHub runner; its
verdict is recorded in the report-back after push. I did NOT waive or allow-list anything.

## 3. Endpoint as shipped
- **Route:** `POST /wit/v1/extract`, `202 Accepted`, async job → signed terminal callback + poll via
  the existing `GET /wit/v1/runs/{run_id}` (extract runs use the same store; `kind: "extract"`).
- **Input:** `{evaluation_id, callback_url, transcript, source_meta{title,url,channel}[, budget]}`.
  transcript required non-empty (400 `INVALID_CONFIG`); callback host allow-listed
  (`is_allowed_callback_url`).
- **Auth:** identical `verify_wit_key` bearer (`WIT_ENGINE_SERVICE_KEY`, constant-time compare) as the
  other `/wit/v1` routes — missing key 503, missing bearer 401, wrong bearer 403.
- **Idempotency:** INTERNAL key `"extract:" + sha256(transcript + source_meta)` — never echoed;
  prefixed so it can never collide with a run/sweep key for the same `evaluation_id`. Duplicate submit
  returns the same `run_id` and launches no second job.
- **Success callback / result:** `{template, completeness, raw_meta}` where
  `raw_meta.ensemble_meta` = `{k, ok_runs, medoid_index, unanimous/majority/tie_fields, per_run:[{retries,
  demotions, downgrades}]}`. Failure → terminal `failed`, error code `EXTRACTION_FAILED`, detail carries
  the ensemble `errors`. Any exception → guaranteed terminal `failed` (`INTERNAL` + truncated traceback),
  never a hung run.
- **Kill switch:** `WIT_DISABLE_EXTRACT` (truthy → 503, scoped to `/wit/v1/extract` only; does NOT gate
  `/wit/v1/runs` or the legacy surface). Mirrors the DISABLE_EXEC_ENDPOINTS pattern.
- **k env:** `WIT_EXTRACT_K` (default **3**, floored at 1) → passed to `extract_template_ensemble(k=)`.
- **Size cap:** transcript ≤ **200 000 chars** (~200 KB), env `WIT_EXTRACT_MAX_CHARS`. Chosen because the
  WIT surface had no raw-text cap (structured configs only); a 2-hour caption track is ~120 KB, so this
  clears realistic transcripts while bounding memory and per-call model cost (k independent sends).
- **Budget:** reuses the existing `WitBudget` (default 600s wall) + heartbeat loop; the budget covers the
  WHOLE ensemble (all k sequential extractions share it); timeout → `BUDGET_EXCEEDED` terminal.

## 4. Tests + suite counts
New file `tests/test_wit_extract.py` (14 tests, ensemble mocked, no network): happy-path
template+completeness+ensemble_meta via GET **and** signed callback (HMAC verified); k-env plumbed
through; auth (401/403/503); idempotent same-transcript (one job) + different-transcript (new run);
`extraction_failed` propagation; exception → terminal `failed`; kill switch 503 + does-not-gate-runs;
transcript validation (empty, over-cap); disallowed callback host. Full CI-safe suite
(`cd api && BACKTEST_API_KEY=k python -m pytest -q`): **248 passed / 0 failed / 2 skipped**
(234 prior + 14 new; the 2 skips are the network-gated live extraction tier).

## 5. Commit + CI
- Commit hash: this commit — see `git log --oneline -1`
  (`WIT-P3r: POST /wit/v1/extract — engine-owned extraction endpoint (ensemble k=3), anthropic to runtime lock (ADR-050 green)`).
- CI status (incl. the real ADR-050 audit-gate verdict): recorded in the report-back after push.

## 6. Anything unexpected
- `scripts/audit_gate.py` is unrunnable on THIS machine (pip-audit's ephemeral-venv `ensurepip`
  SIGABRTs under the uv-managed Python) — verified 0 vulns via pip_audit's PyPI service directly and
  deferred the canonical run to CI. No finding was waived.
- `sniffio` was missing from the runtime lock (an unpinned anyio transitive) — adding it (required by
  httpx/anthropic) also closes that pre-existing gap.
- Read hook truncated file reads to line 1 again; used `sed`/`grep`/`awk` for exact anchors and
  import/route smoke checks. No content impact.

WIT-P3r — Completed

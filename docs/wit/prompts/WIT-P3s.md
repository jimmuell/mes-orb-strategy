Platform   : Claude Code (VS Code, MacBook Air)
Project    : WillItTrade (WIT)
Repo       : github.com/jimmuell/mes-orb-strategy   (branch: main)
Prompt     : WIT-P3s
Local path : ~/Projects/mes-orb-strategy

STEP 0 — GATE (any failure => STOP and report)
  1. git checkout main && git pull --ff-only
  2. git log --oneline -1 must show d601e19 (WIT-P3r). Otherwise STOP, report HEAD.
  3. Tree clean (known untracked pine file fine); origin/path match. No LLM calls.
  4. Fixtures, scorer, golden, prompt rules, ensemble logic: untouched. This slice is
     deploy-layout only.

CONTEXT
  Live finding (Railway dashboard + deploy logs, 2026-07-28): the service deploys with
  root directory /api, so repo-root data files never reach the container. Startup dies:
    File "/app/wit/extraction/schema.py", line 45, in load_schema
    FileNotFoundError: '/schema/strategy-template.v1.json'
  via server.py -> wit.mapper -> wit.extraction. EVERY Phase-3 deploy has failed
  healthcheck this way; production still runs WIT-P2e. CI can't catch it (full checkout
  present). Fix: ship the runtime data inside api/ with a drift gate, and make resolution
  robust with a clear error.

TASK
T0. RECON (no edits): find EVERY runtime read of repo-root files from api/ code — known:
    schema.py SCHEMA_PATH (schema/strategy-template.v1.json) and the contract/modes.md
    read in the extraction prompt builder; grep for "contract/", "schema/", and
    parent-directory path construction to catch others (mapper's machine copies of
    contract/*.v1.json if runtime-read). Report the complete list with file:line.
T1. Shipped copies: create api/_shipped/ containing byte-for-byte copies of every
    runtime-read repo-root file found in T0, preserving relative layout (e.g.
    api/_shipped/schema/strategy-template.v1.json, api/_shipped/contract/modes.md).
    Add a CI-safe DRIFT TEST asserting each shipped copy is byte-identical to its
    repo-root original — a divergence fails the suite, so the copies can never rot.
T2. Resolution: one shared helper (e.g. wit/data_paths.py) used by every T0 call site,
    resolving in order: (1) WIT_DATA_ROOT env var if set; (2) the repo root discovered
    by walking up from the module file (marker: schema/ + contract/ both present);
    (3) api/_shipped/. On total failure raise with ALL searched paths in the message —
    the next person debugging a container gets the answer in one log line.
T3. Tests: env override wins; walk-up finds repo root in the dev checkout; _shipped
    fallback works when (1)/(2) are absent (simulate via monkeypatched module path/env);
    the drift test from T1; plus a startup-shaped test importing the server module with
    resolution forced to _shipped (the exact production failure mode, now covered).
T4. Full CI-safe suite: cd api && BACKTEST_API_KEY=k python -m pytest -q →
    (248 + new) passed / 0 failed / 2 skipped. Record exact. Failure => STOP.
T5. Docs: SESSION-HANDOFF — "main =" line -> "main = the WIT-P3s commit (deploy-layout
    fix: runtime data shipped under api/_shipped with drift gate; resolution
    env->repo->shipped); prior d601e19 (P3r)." Arc: append " → P3s deploy-layout fix."
    In the RESUME HERE block, replace the Jim's-lane sentence with: "Jim's lane: after
    this deploys GREEN on Railway (auto-deploy on push; healthcheck was the blocker),
    set the env vars in the dashboard with the lead driving — WIT_ENGINE_SERVICE_KEY,
    WIT_CALLBACK_HMAC_SECRET (secrets Jim generates+pastes), DISABLE_EXEC_ENDPOINTS=1;
    leave WIT_DISABLE_EXTRACT unset; FirstRateData email (draft in the Notion tracker)."
    Archive prompt to docs/wit/prompts/WIT-P3s.md; add report row to docs/wit/log/README.md.
T6. Single commit DIRECTLY to main (T4 gates), subject:
      WIT-P3s: deploy-layout fix — runtime data shipped under api/_shipped (drift-gated), robust resolution
    Explicit paths only. Push; record CI. NOTE: the push triggers a Railway auto-deploy;
    its health status is watched from the dashboard (lead+Jim), not from this session.

REPORT BACK — docs/wit/log/WIT-P3s-report.md, staged with the commit:
  1. STEP 0. 2. T0 complete list of runtime-read repo-root files (file:line). 3. What
  ships in api/_shipped + how resolution orders. 4. Test list + suite counts. 5. Commit
  hash; CI. 6. Anything unexpected.
Final line, exactly one of:
WIT-P3s — Completed
WIT-P3s — Partial: <one-line reason>

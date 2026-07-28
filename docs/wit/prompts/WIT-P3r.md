Platform   : Claude Code (VS Code, MacBook Air)
Project    : WillItTrade (WIT)
Repo       : github.com/jimmuell/mes-orb-strategy   (branch: main)
Prompt     : WIT-P3r
Local path : ~/Projects/mes-orb-strategy

STEP 0 — GATE (any failure => STOP and report)
  1. git checkout main && git pull --ff-only
  2. git log --oneline -1 must show 83456fb (WIT-P3q). Otherwise STOP, report HEAD.
  3. Tree clean (known untracked pine file fine); origin/path match.
  4. NO live LLM calls in this slice — endpoint tests mock the ensemble. (No key check
     needed.) Extraction internals (prompt.py, extract.py, ensemble.py logic), fixtures,
     scorer, golden: ALL untouched.

CONTEXT
  Decided at P3m-a, unblocked by P3q: the ENGINE exposes extraction; Supabase will merely
  call it. This slice ships POST /wit/v1/extract calling extract_template_ensemble(k=3),
  and moves anthropic from requirements-dev.txt into the SHIPPED runtime lock, passing the
  ADR-050 audit gate. Mirror the existing /wit/v1 route patterns — do not invent new ones.

TASK
T0. RECON FIRST (no edits): read the existing /wit/v1 router + run-endpoint flow (auth,
    idempotency, job queue, signed callback, budget/timeout, input caps) and the ADR-050
    audit tooling + requirements/lock layout. If the async job + callback pattern does NOT
    exist as the handoff describes, STOP and report what actually exists.
T1. Dependency promotion: move anthropic out of requirements-dev.txt into the shipped
    runtime requirements + lock, pinned per repo convention; lazy import stays. Run the
    ADR-050 audit gate; FAILURE => STOP and report the audit output verbatim (do not
    waive or work around it).
T2. POST /wit/v1/extract — mirroring the existing run-route pattern exactly:
    - Input {transcript, source_meta{title,url,channel}}; transcript required non-empty;
      enforce a size cap consistent with existing input caps (document the number chosen).
    - Same service-key auth as other /wit/v1 routes; constant-time compare (P3g pattern).
    - Idempotency key derived from a content hash of transcript+source_meta, INTERNAL,
      never echoed (P3f pattern).
    - Async job like runs: accepted response + signed callback carrying
      {template, completeness, raw_meta including ensemble_meta and per-run
      demotions/downgrades} on success, or the extraction_failed errors on failure.
    - k configurable via env (WIT_EXTRACT_K, default 3); a dedicated kill switch env
      (mirror the DISABLE_EXEC_ENDPOINTS pattern; document the name) that 503s the route.
    - Timeout/budget: reuse the existing job budget machinery; document what applies.
T3. Tests (CI-safe, ensemble mocked) — at least: auth rejected without/with-wrong key;
    happy path returns template+completeness+ensemble_meta via the callback path;
    idempotent duplicate does not double-run; extraction_failed propagates errors;
    kill switch 503s; transcript validation (empty, over-cap). Plus ADR-050 audit gate
    green with anthropic in the runtime lock.
T4. Full CI-safe suite: cd api && BACKTEST_API_KEY=k python -m pytest -q →
    (234 + new) passed / 0 failed / 2 skipped. Record exact. Failure => STOP.
T5. Docs: WIT-03 — update §4 to the shipped reality (engine-owned extraction endpoint,
    supersedes the Supabase edge-function placement; one short paragraph + the route
    shape) and annotate the §8 backlog accordingly. SESSION-HANDOFF: "main =" line +
    arc append " → P3r extract endpoint"; replace the RESUME HERE block with:
      ▶ RESUME HERE — POST /wit/v1/extract SHIPPED (P3r): the engine back end is
      feature-complete for v1 (read + grade + test + sweep, all behind /wit/v1). Next
      candidates, lead to sequence with Jim: (1) Supabase front office (WIT-03 §6: auth,
      tables, edge function calling the engine); (2) front-end integration of live engine
      results (Lovable app currently on fixtures); (3) library seeding workflow (curated,
      human-reviewed per P3q §4). Jim's lane: Railway deploy confirm + env vars incl. the
      new extract kill switch; FirstRateData confirmation email (draft in the Notion
      tracker row).
    Archive prompt to docs/wit/prompts/WIT-P3r.md; add report row to docs/wit/log/README.md.
T6. Single commit DIRECTLY to main (T4 gates), subject:
      WIT-P3r: POST /wit/v1/extract — engine-owned extraction endpoint (ensemble k=3), anthropic to runtime lock (ADR-050 green)
    Explicit paths only. Push; record CI.

REPORT BACK — docs/wit/log/WIT-P3r-report.md, staged with the commit:
  1. STEP 0 + recon findings (route pattern confirmed; audit tooling located).
  2. ADR-050 audit result with anthropic in the runtime lock (verbatim verdict line).
  3. Endpoint as shipped: route shape, auth, idempotency, kill-switch name, k env,
     size cap, budget applied.
  4. Test list + suite counts. 5. Commit hash; CI. 6. Anything unexpected.
Final line, exactly one of:
WIT-P3r — Completed
WIT-P3r — Partial: <one-line reason>

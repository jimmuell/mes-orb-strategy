# WIT-P3l — Report Back

Prompt: **WIT-P3l** — phase-end docs pass (field count 25→27; WIT-03 aligned to shipped surfaces). Docs only; no code/tests/fixtures/contract-machine-files changed. On `main`.

1. **STEP 0 result — main at `8ad0fc7`: yes** (`origin/main` = `8ad0fc7`, WIT-P3e-3 report; had not moved). Tree clean apart from the known untracked `pine/mes_net_pnl_v2.pine`.

2. **Step-2 measured counts (specified|implied against the schema's 27 field ids):**
   - **WIT-T-0001: 18/27 (~67%)** — fields: A1,A2,A3,B1,B2,C1,D1,D2,D3,D4,F1,F2,F3,G1,I1,J1,J2,K1.
   - **WIT-T-0002: 9/27 (~33%)** — fields: A1,A2,A3,B2,D2,F1,J1,J2,K1.
   The doc numerators (17 and 7) **did NOT reproduce** (measured 18 and 9), so per the instruction I **changed NOTHING** in the two T-files (`WIT-T-0001`/`WIT-T-0002`) and dropped them from the commit. **T-file ratios updated: no.** (The prose "17/25"/"~7/25" are the lead engineer's original hand-counts; the committed fixtures actually carry 18 and 9 specified/implied fields — a finding for a future slice if the anchors should be re-stated.)

3. **Exact shipped key names used in §3.1/§3.6 (copied from code):** from `api/server.py` — `sweep: bool = Field(default=False, …)`; `idem_hash = chash + ":sweep" if req.sweep else chash`; `result["sensitivity"] = sensitivity`; `result["sweep"] = {"requested": …, "completed": …, "skipped": …}`; `kind` ∈ {`backtest`,`event_study`} (the router rejects `sensitivity_sweep`). From `api/wit/sweeps.py` — `MAX_SWEEP_CELLS = 18`, backtest 5 cells / event_study 17. **No code-vs-instruction disagreement** — every key name and count in the instruction matches the shipped code exactly.

4. **Full-suite count:** 206 passed, 0 failed, 2 skipped (docs-only change; suite unaffected). **Commit hash on origin/main:** see the terminal report-back (a commit can't contain its own SHA). **CI status:** reported in the terminal report-back after the push (`ci.yml` on `api/requirements.txt`, untouched this phase — expected green).

## Edits applied (docs only)
- **WIT-02 §2 header:** "(11 sections, 25 fields)" → "(11 sections, 27 fields)".
- **WIT-03 §3.1:** `kind` → "backtest | event_study" (sensitivity_sweep removed as a kind); `"sweep": { "vary": … }` → `"sweep": true` with the engine-owned-grids note (backtest 5 / event_study 17 / cap 18); added the sweep-idempotency line (`config_hash + ":sweep"` internal, never echoed; provenance keeps the plain wire hash).
- **WIT-03 §3.6:** `"sweep_results": […]` → `"sensitivity": {"<variant_name>": {…}}` + `"sweep": {"requested","completed","skipped"}`; added the line "skipped cells are ALWAYS disclosed; primary over-budget → BUDGET_EXCEEDED exactly like a single run."
- **WIT-03 §7 change log:** WIT-P3l entry added at the top (verbatim as specified).
- **WIT-03 §8 backlog:** items 1/2/4/5 annotated "✓ shipped P3d / P3c-2 / P3c-3 / P3f"; items 3 and 6 left open.

5. **Anything unexpected:**
   - The calibration-anchor numerators don't reproduce: the committed fixtures carry **18** (T-0001) and **9** (T-0002) specified/implied fields, not the prose's 17 and 7. Reported, T-files untouched per the instruction.
   - §8 **item 7** ("disable code-execution endpoints for WIT traffic") also shipped in P3g (the `DISABLE_EXEC_ENDPOINTS` kill switch), but the instruction scoped annotations to items 1/2/4/5 and named 3/6 as staying open — silent on 7 — so I left item 7 unannotated rather than improvise beyond the stated scope. Flagging for a future tidy.
   - Docs-only: no code, tests, fixtures, or `contract/` machine files touched; `config_version` stays `1.0`.

WIT-P3l — Completed

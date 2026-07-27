# WIT-P3f — sensitivity sweep runner (engine-owned grids, sweep flag, shared wall budget)

Prompt: **WIT-P3f** — sensitivity sweep runner (WIT-03 §8.5); all additive, `sweep=false` byte-identical to P3d. On `wit-phase3`. (Resumed after the lead-engineer resolved the `MAX_SWEEP_CELLS` blocker → **18**.)

---

## 1. STEP 0 result
- HEAD was **`77fef02`** (WIT-P3e-2): **yes**. On `wit-phase3`. Tree clean: **yes** (only the known untracked `pine/mes_net_pnl_v2.pine`).

## 2. sweeps.py grids
- **`api/wit/sweeps.py`** — engine-owned (callers never define grids). Cell counts: **backtest = 5** (`entry_body, slippage_0, slippage_2, target_first, vp_5min`, mirroring `analysis.py`), **event_study = 17** (the WIT-0002 A4 variant set). `MAX_SWEEP_CELLS = 18` (per the lead-engineer decision — the approved event grid is 17 variant cells / published "18-config" grid = primary + 17; 17 binds, 18 = one cell headroom; recorded in a module comment). Both builders `assert len(grid) <= MAX_SWEEP_CELLS`.
- **Grid golden vs `event_study_report.build_grid()`: passed (y).** `build_event_study_sweep(EventStudyConfig())` equals the non-primary cells of `build_grid()` — same names, same order, exact dataclass equality (17 cells). `event_study_report.py` was **not** modified; the test pins the equality (so a future drift there fails the test). The backtest grid golden equals the five `VPORBConfig().with_(override)` variants.
- **Derive-from-given-primary: passed (y).** Off a non-default primary (backtest `rr_target=3.0, commission_per_side=1.11`; event-study `start/end` window), every cell preserves the primary's non-swept dimensions and varies only its own.

## 3. Router wiring
- **Sweep flag + `":sweep"` idempotency key wired: yes.** `WitRunRequest` gains `sweep: bool = False`. The run-store idempotency key for a sweep is `config_hash + ":sweep"` (a sweep and a single run of the same config are different jobs — never collide). The `config_hash` echoed in provenance stays the **plain** wire-config hash (the jobs receive `chash`, not the idempotency key). Dispatch: `sweep=true → _run_wit_sweep_job`, else the unchanged `_run_wit_job`.
- **Sweep runner:** refactored the budget/heartbeat loop into a shared `_compute_within_budget(...) -> ('ok', result) | ('timeout', None)`; `_run_wit_job` now calls it (same terminal semantics), and `_run_wit_sweep_job` reuses it. Flow: (a) PRIMARY first under the full budget — a primary over budget FAILS `BUDGET_EXCEEDED` exactly as today; (b) grid cells run **sequentially** under the shared remaining budget, checking remaining before each cell; when the budget runs out, the current cell and every remaining cell are recorded **skipped** (a cell that itself times out is cancelled and skipped along with the rest); (c) terminal `succeeded` (primary completed) with `result["sensitivity"] = {name: <full single-run result>}` for completed cells and `result["sweep"] = {"requested": N, "completed": M, "skipped": [names]}`. Skips are always disclosed — never silent.
- **Budget-skip disclosure test: passed (y).** Primary fits (0.15s < 0.25s budget); cells run out → `sweep.skipped` lists the un-run cells, `completed + len(skipped) == requested`, status still `succeeded`, primary result intact.
- **`sweep=false` unchanged — all prior router tests green untouched: yes.** The 18 pre-existing router tests pass unmodified after the refactor (the single-run path is behavior-identical), and a new test asserts a `sweep=false` result has no `sensitivity`/`sweep` keys.

## 4. Suite
- New: `test_sweeps.py` (**5**) + 5 new router sweep tests (all-cells-complete, no-sensitivity-when-false, budget-skip disclosure, primary-over-budget BUDGET_EXCEEDED, sweep-vs-single idempotency).
- **Full CI-safe suite: 206 passed, 2 skipped, 0 failed** (196 prior + 10 new; the 2 skips are the network/LLM-gated golden tier). No new dependency; `requirements.txt`/`requirements-dev.txt` untouched.

## 5. Commit + push
- Commit on `wit-phase3` (subject `WIT-P3f: sensitivity sweep runner — engine-owned grids, sweep flag, shared wall budget`); files: `api/wit/sweeps.py`, `api/server.py`, `api/tests/test_sweeps.py`, `api/tests/test_wit_router.py`, this report. **Pushed to `origin/wit-phase3`: yes** (concrete SHA in the terminal report-back). Pushing `wit-phase3` does not trigger CI; the local 206-green suite is the gate until the checkpoint merge.

## 6. Anything unexpected
- **Resolved blocker (recorded per instruction):** the prompt pinned `MAX_SWEEP_CELLS = 16`, but `event_study_report.build_grid()` has **17** non-primary cells (the published WIT-0002 "18-config" grid = primary + 17). 16 and the exact-equality grid golden are mutually unsatisfiable, so I stopped and reported rather than force a pass. Lead-engineer decision: **`MAX_SWEEP_CELLS = 18`** (17 binds, 18 = one cell headroom; the original "16" was an off-by-one; the 17-cell published grid is authoritative). Applied, with the rationale in a code comment and above.
- **Per-cell provenance:** each sensitivity cell's result carries the PRIMARY's `config_hash` in provenance (the cells are engine dataclasses, not wire configs, so there is no per-cell wire hash); the variant **name** is the discriminator. Documented; harmless for the sensitivity view.
- **Cell errors vs budget skips:** a cell that raises (not a budget timeout) is recorded as skipped and the loop continues (one bad cell never aborts a sweep whose primary succeeded) — kept within the spec's two-outcome model (completed / skipped), and still disclosed via the skipped list.

WIT-P3f — Completed

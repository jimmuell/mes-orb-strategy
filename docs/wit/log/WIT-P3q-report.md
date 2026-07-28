# WIT-P3q — final ruling: fixtures FINAL, known-residuals register, extraction v1 accepted

1. STEP 0: HEAD **7f7d424** (WIT-P3e-8) — matches. Repo/path/origin match the header. Tree clean
   except the known untracked `pine/mes_net_pnl_v2.pine`. DOCS ONLY — nothing under `api/` touched;
   no code/tests/fixtures/prompt.py; no LLM calls.

2. Per-edit grep confirmations (all verified):
   - **T1** — created `docs/wit/log/WIT-P3q-adjudication.md` with the exact BEGIN/END content
     (KNOWN-RESIDUALS register present).
   - **T2a** — handoff `main =` line → `main = the WIT-P3q commit (final re-adjudication …)`; old
     `main = the WIT-P3e-8 commit` gone (0). Arc now ends `→ P3e-8 prompt-spec alignment → P3q final
     ruling.` (1).
   - **T2b** — the entire `▶ RESUME HERE — P3e-8 …` block replaced with `▶ RESUME HERE — extraction
     quality CLOSED for v1 …`; the old `PRE-COMMITTED ENDGAME is now triggered` text is gone (0).
   - **T3** — this prompt archived verbatim to `docs/wit/prompts/WIT-P3q.md` (exists); `docs/wit/log/
     README.md` gained rows for `WIT-P3q-adjudication.md` and `WIT-P3q-report.md` (2).

3. Suite (docs slice changes nothing): `cd api && BACKTEST_API_KEY=k python -m pytest -q` →
   **234 passed / 0 failed / 2 skipped** — exactly as expected.

4. Commit hash: this commit — see `git log --oneline -1`
   (`WIT-P3q: final ruling — fixtures FINAL, known-residuals register, extraction v1 accepted for curated launch`).
   CI status: recorded below after push.

5. Anything unexpected: none — clean docs-only ruling slice. Extraction quality is now CLOSED for
   v1: the three disputed entries (T-0002 B1, T-0002 D2, T-0001 'Consistent profits <90min' testable)
   are RE-RATIFIED, the fixtures are FINAL, and the live-golden's expected reds are pinned to the
   R1-R3 register — any miss outside R1-R3 is a regression, not an accepted residual. Read hook
   truncated reads to line 1 again; used `sed`/`grep` for exact anchors and grep-verified every edit.

WIT-P3q — Completed

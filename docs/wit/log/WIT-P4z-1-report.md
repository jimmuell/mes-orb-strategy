# WIT-P4z-1 — prompt standard aligned to canonical

1. STEP 0: started from HEAD **6f7798f** (WIT-P4z). Remote `jimmuell/mes-orb-strategy` at
   `/Users/jameslmueller/Projects/mes-orb-strategy` confirmed; `git pull --ff-only` up to date; tree
   clean except the known untracked `pine/mes_net_pnl_v2.pine`. DOCS ONLY — nothing under `api/`,
   `contract/`, or `schema/` touched; no LLM calls.

2. Grep proof (all against `docs/PROMPT_STANDARD.md`):
   - Engine header block (`Platform:    Claude Code (paste this code into this platform)`) **present** (1).
   - App header block (`Platform:    Lovable Project (paste this code into this platform)`) **present** (1).
   - Access-control-SQL line (`ACCESS-CONTROL SQL IS NEVER RUN BY THE AGENT OR BY CLAUDE`) **present** (1).
   - `WIT's ratified exceptions to the canonical doc` header **present** (1) with all **four** numbered
     bold exceptions **present** (4).
   - Old `Engine essentials:` line **absent** (0) — the file it was in is fully replaced.
   The handoff's assertion that `docs/PROMPT_STANDARD.md` carries the WIT header blocks is now TRUE.

3. Suite (docs-only): **268 passed / 0 failed / 2 skipped** — unchanged. Commit hash: this commit —
   see `git log --oneline -1` (`WIT-P4z-1: prompt standard aligned to canonical — WIT header blocks,
   Lovable rules, ratified exceptions`). CI status: recorded in the report-back after push.

WIT-P4z-1 — Completed

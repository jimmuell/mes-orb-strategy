# WIT Session Handoff

Read this first, then RECONCILE against git before assigning any work (see Continuity rules).
Single resume point for the WillItTrade (WIT) project. Rewritten at each close-out; git history is
the archive. Written by the lead engineer (Claude, Cowork chat) 2026-07-28, session 3 (extended).

* Last updated: 2026-07-28
* Project: WillItTrade — willittrade.com (registered, GoDaddy, 2026-07-26). Users drop a
  YouTube strategy video/transcript in; the lab renders a data-backed verdict. Positioning:
  "The AI reads the video; the lab renders the verdict." Reports are "strategy audits."
* Where things live: everything WIT is in `docs/wit/` of the mes-orb-strategy repo (the engine
  repo). Machine contracts: `schema/strategy-template.v1.json` + `contract/`. WIT engine code:
  `api/wit/`. Authored prompts: `docs/wit/prompts/`. Run reports: `docs/wit/log/`. The Lovable
  app and its repo do not exist yet, by design. Front end: Lovable project `Audit Lab` (rename
  pending) — id 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9, editor
  https://lovable.dev/projects/6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9 — front-end-only v1 (no
  auth/DB/payments), all figures from a typed fixtures module mirroring the eventual API shape;
  seeded with the REAL published WIT-0001 numbers. Supabase not yet created. Business/decision
  lane + glanceable status: the Notion board **WillItTrade (WIT) — Project Tracker** →
  https://app.notion.com/p/6ccf5af452cc41768441d7dae1a3aca3 (structure mirrors the TradingGym
  tracker; each row's Ref column points back to the repo file or spec section behind it).

## Team & process (do not improvise around these)

* Lead engineer = Claude in Cowork chat. Writes every spec and prompt, reviews every report +
  diff before the next slice, answers design questions. Claude Code (VS Code, MacBook Air,
  `~/Projects/mes-orb-strategy`) executes engine prompts. Jim decides, approves, runs live steps.
* PROMPT DISPLAY FORMAT (Jim, 2026-07-27 — do not drift): every Claude Code prompt is rendered as
  ONE plaintext code box (aligned label header Platform/Project/Repo/Prompt/Local path, then
  STEP 0 — gate, TASK, REPORT BACK, completion marker as final line). WIT delta: commit subjects
  lead `WIT-PXx:`; every REPORT BACK is written verbatim to `docs/wit/log/<Prompt>-report.md` and
  staged with the commit.
* Slice rhythm: recon → design (separate prompt when a real decision exists) → build →
  lead-engineer review with hands-on verification → next slice. STOP-and-report rather than force
  a pass; goldens are exact equality, never tuned to pass. Proven twice: P3f stopped on a real
  spec contradiction (cap 16 vs the published 17-cell grid); P3e-4 stopped rather than tune a
  fixture to make a failing rubric pass. Both were correct.
* CONTINUITY RULES (new 2026-07-28, after a real near-miss — treat as standing policy):
  1. **Authored prompts are committed**, to `docs/wit/prompts/WIT-<id>.md`, at authoring time.
     `prompts/` = intended; `log/` = happened; a prompt with no report is PENDING.
  2. **Nothing happens after a close-out without touching this file.** The close-out rewrite is
     meant to be a session's last act; if work continues past it, the follow-on commit carries a
     one-line update here. Never leave the repo describing a world that has moved on.
  3. **One lead session at a time, and every session RECONCILES on open**: read this file, then
     `git log --oneline -15` + `ls docs/wit/log/` to see what landed AFTER this file was written,
     and only then present Jim a task list. This file can be stale by design; git cannot.
     On 2026-07-28 a second lead session skipped this and handed Jim an already-completed task.
  4. **The Notion tracker is READ on session open and UPDATED on session close.** The repo
     stays the engineering source of truth; the tracker owns Jim's lane (data licensing, legal,
     domains, pricing, launch prep) plus cross-cutting status. Reading it on open is the ONLY
     way a session learns what Jim did between sessions — git cannot know that. Updating it on
     close is the LEAD ENGINEER's job (Cowork chat has Notion access; Claude Code does not), so
     a close-out is not complete until both the handoff and the tracker are current.
* Checkpoint-merge pattern (P3h/P3j): merge the VERIFIED remote ref (`origin/<branch>`), never the
  bare local branch name; the merge report is a follow-on commit, never an amend of a pushed merge.
  Small reviewed doc/fix slices may commit directly to main (P3l, P3e-4, P3m) — the local full
  suite gates the commit, CI gates the push.
* ENVIRONMENT LESSON (cost hours on 2026-07-28, do not relearn): Claude Code's Bash spawns a fresh
  shell, so it NEVER sees an `export` typed in Jim's interactive terminal — but it also inherits
  the environment VS Code was LAUNCHED with, so editing `~/.zshrc` does nothing until **VS Code is
  fully quit (Cmd-Q) and reopened**. `ANTHROPIC_API_KEY` lives on one `export` line in `~/.zshrc`
  (never in the repo — verified: no secrets tracked; code reads keys from `os.environ` only).
  Verify a key is live before building: one minimal `claude-haiku-4-5` `max_tokens=1` Messages call.
  Old keys also persist in `~/.zsh_history`, which is how a dead key kept resurfacing.

## Current state (verify on open, don't assume)

* main = the WIT-P3s commit (deploy-layout fix: runtime data shipped under api/_shipped with drift
  gate; resolution env->repo->shipped); prior d601e19 (P3r). No open branch (wit-phase3 deleted at
  P3j, fully merged). Suite **212 passed / 0 failed / 2 skipped** (the 2 skips are the
  network+cost-gated live extraction tier — correct in CI). CI green (run 30359775950).
* Session-3 arc on main: P3e-1 prompt builder → P3e-2 extraction core → P3f sweep runner →
  P3j checkpoint merge → P3k close-out → P3l docs alignment → P3e-4 grounding + status rules → P3m process hardening →
  P3m-a extraction-endpoint decision → P3n close-out → P3o anchor adjudication → P3e-5 basis discipline → P3e-6 determinism + coherence → P3e-7 ensemble vote → P3e-8 prompt-spec alignment → P3q final ruling → P3r extract endpoint → P3s deploy-layout fix.
  Sessions 1–2 (scorer, schema, mapper vertical, /wit/v1 router, hardening) stand as described in
  the P3i handoff; see `docs/wit/log/`.
* Extraction layer (`api/wit/extraction/`): prompt builder generates the supported mode vocabulary
  AT RUNTIME from `contract/modes.md` († excluded PER-DIMENSION; `none` supported only for
  filters) plus each dimension's field id(s) and typed param keys; rules encode grounding,
  no-charitable-completion, setup≠trigger, class-is-an-output, QUOTE DISCIPLINE
  (character-for-character, keep caption typos) and STATUS DISCIPLINE (a tendency/illustration is
  NOT a rule; when in doubt choose `unspecified`). `provider.py` = one forced
  `emit_strategy_template` tool call (anthropic **dev-only**, `requirements-dev.txt`, lazy import;
  audited runtime lock untouched). `extract.py` = ≤2-retry loop where success means schema-valid
  **AND fully grounded** (`grounding_errors()` normalizes exactly like the golden test's `_norm`);
  the deterministic scorer owns the class — the model's is overwritten; terminal
  `extraction_failed` carries the errors, never a silent pass.
* Sweep runner (`api/wit/sweeps.py` + router): engine-owned grids only — backtest 5 cells
  (WIT-0001 §J2 set), event_study 17 cells (equality-PINNED to `event_study_report.build_grid()`'s
  non-primary cells; that file is untouched — it produced the published numbers),
  MAX_SWEEP_CELLS=18. `sweep: bool` flag; idempotency key `config_hash + ":sweep"` (INTERNAL,
  never echoed). Primary runs first (over budget → BUDGET_EXCEEDED like a single run), then cells
  sequentially under the shared remaining budget; `result.sweep.skipped` ALWAYS discloses what
  didn't run. `sweep=false` byte-identical to P3d.

▶ RESUME HERE — POST /wit/v1/extract SHIPPED (P3r): the engine back end is
feature-complete for v1 (read + grade + test + sweep, all behind /wit/v1). Next
candidates, lead to sequence with Jim: (1) Supabase front office (WIT-03 §6: auth,
tables, edge function calling the engine); (2) front-end integration of live engine
results (Lovable app currently on fixtures); (3) library seeding workflow (curated,
human-reviewed per P3q §4). Jim's lane: after this deploys GREEN on Railway (auto-deploy on
push; healthcheck was the blocker), set the env vars in the dashboard with the lead driving —
WIT_ENGINE_SERVICE_KEY, WIT_CALLBACK_HMAC_SECRET (secrets Jim generates+pastes),
DISABLE_EXEC_ENDPOINTS=1; leave WIT_DISABLE_EXTRACT unset; FirstRateData email (draft in the
Notion tracker).

## Open items (carried + new; none blocking the adjudication)

* DONE P3o — calibration anchors adjudicated: fixtures ratified 9/9, T-file ratios
  restated (18/27, 9/27), claims rubric now coverage-based.
* DONE P3r — `POST /wit/v1/extract` shipped (engine-owned k=3 ensemble); anthropic moved into the
  shipped runtime lock with its transitive closure, ADR-050 audit gate green.
* WIT-03 §8: items 3 and 6 remain genuinely open (items 7, 8 annotated ✓; 8 shipped P3r).
* NEW — sweep disclosure granularity: `skipped[]` conflates errored cells with not-run cells (the
  count always discloses; the nature doesn't). Later slice: split "errored" from "skipped".
  Sensitivity cells carry the PRIMARY's config_hash (variant name is the discriminator) — fine
  v1, revisit if cells ever need permalinks.
* §3.6 result gaps (P3d, honest nulls): bootstrap CIs + edge_vs_luck + regimes + expectancy_r +
  trades_url not in the single-run path — wire `analysis.py` in when reports need them. Durable
  run store = later slice (v1 store is RESTART-LOSSY, documented in `run_store.py`).
* backtest/ duplicate-engine retirement: plan in WIT-P3g-report (zero live importers; do NOT
  confuse the pip `backtester` package with `backtest/`). Someday-safe.
* Jim's checklist (business lane — mirrored in the Notion WIT Project Tracker): FirstRateData
  commercial-license check (BIGGEST BUSINESS RISK — follow up), USPTO screen "WillItTrade"/"WIT",
  optional willittrade.app + aistrategyauditor.com redirect, TradeVerdict 4 unused free reviews.
* Held: YouTube library seeding (curation in `docs/wit/planning/`; Tier-1 TradingLab, Rockwell,
  The Moving Average, Rayner Teo). Transcript IP policy before public launch. UI requirement:
  submit box takes pasted transcript OR YouTube link, identical UX.
* Repo housekeeping: untracked `pine/mes_net_pnl_v2.pine`; stale branches
  adr-048-pin-environment, docs/adr-022 (Air); uncommitted `scratchpad/diag_t0002.py` (the P3e-4
  diagnostic — the table it printed is preserved verbatim in the P3e-4 report).

## Cross-project note
pine-strategies (separate repo, own SESSION-HANDOFF.md) was mid-experiment as of 2026-07-26:
ORB-2026-001 EMA trend-filter awaiting Jim's two TradingView runs. Don't conflate.

## Context for a cold start
Founding reasoning is condensed in WIT-01/02/03; process history in `docs/wit/log/` (P3b-fix = why
scorer defaults are entry-gated; P3c = why the param channel exists; P3d = §3.6 gaps; P3e-1/2 =
the extraction layer and why the SDK is dev-only; P3e-4 = the first live grading + the 27-row
diagnostic; P3f = the sweep design and the cap decision; P3l = doc-to-code alignment). Trust the
repo over memory, and git over this file. Verified, not inferred — every number in a WIT artifact
traces to a committed file.

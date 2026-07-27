# WIT Session Handoff

Read this first. Single resume point for the WillItTrade (WIT) project. Rewritten at each
session close-out; git history is the archive. Written by the lead engineer (Claude, Cowork
chat) at close of session 3 (2026-07-27).

* Last updated: 2026-07-27
* Project: WillItTrade — willittrade.com (registered, GoDaddy, 2026-07-26). Users drop a
  YouTube strategy video/transcript in; the lab renders a data-backed verdict. Positioning:
  "The AI reads the video; the lab renders the verdict." Reports are "strategy audits."
* Where things live: everything WIT is in `docs/wit/` of the mes-orb-strategy repo (the
  engine repo). Machine contracts: `schema/strategy-template.v1.json` + `contract/`
  (modes.md, wire-config schemas). WIT engine code: `api/wit/`. The future app (Lovable)
  and its repo do not exist yet, by design.

## Team & process (do not improvise around these)

* Lead engineer = Claude in Cowork chat. Writes every spec and prompt, reviews every
  report + diff before the next slice, answers design questions. Claude Code (VS Code,
  MacBook Air, `~/Projects/mes-orb-strategy`) executes engine prompts. Jim decides,
  approves, runs live steps. Lovable arrives in Phase 3's app stage — not started.
* PROMPT DISPLAY FORMAT (Jim, 2026-07-27 — do not drift): every Claude Code prompt is
  rendered as ONE plaintext code box (aligned label header Platform/Project/Repo/Prompt/
  Local path, then STEP 0 — gate, TASK, REPORT BACK, completion marker as final line).
  Engine PROMPT_STANDARD.md is a pointer; canonical doc is in jimmuell/tradinggym (not on
  this machine). WIT delta: commit subjects lead `WIT-PXx:`; every REPORT BACK is written
  verbatim to `docs/wit/log/<Prompt>-report.md` and staged with the commit.
* Slice rhythm proven over sessions 2–3: recon → design (separate prompt when a real
  decision exists) → build → lead-engineer review with hands-on verification → next slice.
  STOP-and-report rather than force a pass; goldens are exact equality, never tuned to
  pass. Session-3 proof: P3f STOPPED on a real spec contradiction (cap 16 vs the published
  17-cell grid) instead of tuning either side; one-line lead decision (cap=18) resolved it.
* Checkpoint-merge pattern (P3h/P3j): merge the VERIFIED remote ref (origin/<branch>),
  never the bare local branch name; the merge report is a follow-on commit, never an
  amend of a pushed merge. Branch pushes don't trigger CI (ci.yml is PR/push-to-main
  only) — the local full suite is the gate until the checkpoint merge.

## Current state (verify on open, don't assume)

* main = WIT-P3j merge (Phase 3 checkpoint 2) + P3j/P3k report commits; wit-phase3
  deleted (fully merged). Full suite 206 passed, 0 failed, 2 skipped (the 2 skips are the
  network/LLM-gated golden extraction tier — correct in CI). CI green incl. the ADR-050
  audit gate (runtime lock untouched this phase). Session-3 arc on main: P3e-1 (prompt
  builder) → P3e-2 (extraction core) → P3f (sweep runner) → P3j merge.
* What the engine can now do end-to-end (all additive; legacy /run* untouched; everything
  from sessions 1–2 — scorer, schema, mapper vertical, /wit/v1 router, hardening — stands
  as described in the P3i handoff, see git history):
  * Extraction prompt builder (`api/wit/extraction/prompt.py`): supported_modes()/
    unsupported_modes() parsed AT RUNTIME from contract/modes.md — single source of
    truth; † tokens excluded PER-DIMENSION (`none` is supported ONLY for filters). The
    system prompt encodes the WIT-02 §1/§4 rules (verbatim-substring grounding, no
    charitable completion ⇒ vague=unspecified, setup≠trigger, class is an OUTPUT, all
    performance claims verbatim, interpretations[] for ambiguity), the full 27-field spec
    (coverage-asserted against schema FIELD_IDS), and a vocab block giving each dimension
    its field id(s) + typed params keys. A vocab golden PINS v1: removing a † in modes.md
    deliberately fails tests until EXPECTED_SUPPORTED is updated in that slice.
  * Extraction core (`provider.py` + `extract.py`): anthropic==0.120.0 is DEV-ONLY
    (requirements-dev.txt; the audited runtime lock is byte-identical; the SDK import is
    lazy). Structured output = one forced tool call (emit_strategy_template) whose
    input_schema is the template schema (meta keys stripped); the hard gate is our own
    validate_template(). Orchestrator: ≤2-retry loop feeding validation errors back; the
    SCORER owns completeness (the model's class is overwritten before validation — it
    cannot smuggle a classification); terminal status extraction_failed with last
    candidate + errors, never silent. Model default: env WIT_EXTRACTION_MODEL, else
    claude-opus-4-8 (see Open items — unverified against the public API).
  * Golden extraction regression (`api/tests/test_extraction_golden.py`): NETWORK+COST
    GATED (WIT_RUN_LLM_TESTS=1 + ANTHROPIC_API_KEY; never in CI). Scored rubric — HARD:
    class (A/B), required-field statuses, required_missing, and grounding (every
    specified/implied source_quote a verbatim substring of the transcript; J exempt);
    TOLERANT: claims ±1, flags present, ≥75% per-field status match. NOT YET GRADED —
    the Air's key was invalid (clean 401 from the live endpoint on both transcripts:
    wiring proven, quality unmeasured).
  * Sensitivity sweep runner (`api/wit/sweeps.py` + /wit/v1 router): ENGINE-OWNED grids —
    backtest 5 cells (the WIT-0001 §J2 set mirroring analysis.py), event_study 17 cells
    (equality-PINNED by test to event_study_report.build_grid()'s non-primary cells — the
    published WIT-0002 grid; event_study_report.py untouched). MAX_SWEEP_CELLS=18 (17 is
    the binding published case + 1 headroom; the P3f prompt's "16" was a lead off-by-one,
    caught by executor STOP). WitRunRequest.sweep flag; idempotency key config_hash+
    ":sweep" (INTERNAL only — never echoed; provenance keeps the plain wire hash). Job:
    primary first (over-budget → BUDGET_EXCEEDED exactly like a single run), then cells
    SEQUENTIALLY under the shared remaining wall budget; result.sensitivity{name:…} +
    result.sweep{requested,completed,skipped} — skips ALWAYS disclosed. sweep=false path
    byte-identical to P3d.
* Contract truth unchanged: ALL times ET wall-clock tz-naive; modes.md † = declared-not-
  supported; UNSUPPORTED_CONSTRUCT fails loud, never a silent default.

▶ RESUME HERE — next is the phase-end docs pass, then the Lovable app stage
1) Docs pass (small, one prompt): fix WIT-02 §2 header "25 fields" → 27 (tables/schema
   authoritative); record the extraction + sweep surfaces in WIT-03 where §7 requires
   (the sweep flag + result shape; the extraction function contract already in §4).
2) Then the app stage: Lovable app repo + Supabase (wit-extract edge function — the
   engine's provider.py/extract.py is the approved reference implementation; DB per
   WIT-03 §6), willittrade.com wiring. Before public launch: transcript IP policy and
   Jim's checklist below. Engine-side prerequisites for real runs on Railway: set
   WIT_ENGINE_SERVICE_KEY, WIT_CALLBACK_HMAC_SECRET, DISABLE_EXEC_ENDPOINTS=1.

## Open items (carried + new; none blocking the docs pass)

* NEW — live extraction ungraded: Jim to generate a valid ANTHROPIC_API_KEY
  (console.anthropic.com) on the Air, then run the golden tier
  (WIT_RUN_LLM_TESTS=1, cd api && python -m pytest tests/test_extraction_golden.py -q).
  Also verify the DEFAULT_MODEL id claude-opus-4-8 exists on the public API (the 401 hit
  before model lookup); if not, set WIT_EXTRACTION_MODEL to a valid current model id.
* NEW — sweep disclosure granularity: skipped[] currently conflates errored cells with
  not-run cells (count always discloses; nature doesn't). Later slice: split "errored"
  from "skipped". Also: sensitivity cells carry the PRIMARY's config_hash in provenance
  (variant name is the discriminator) — fine v1, revisit if cells need permalinks.
* §3.6 result gaps (P3d, honest nulls): bootstrap CIs + edge_vs_luck + regimes +
  expectancy_r + trades_url not in the single-run path — wire analysis.py in when reports
  need them. Durable run store (Redis/Postgres) = later slice (v1 store RESTART-LOSSY,
  documented).
* backtest/ duplicate-engine retirement: plan in WIT-P3g-report (zero live importers; do
  NOT confuse the pip `backtester` package with `backtest/`). Someday-safe.
* Railway (when the WIT service exists): env vars above; live-deploy state was NOT
  verifiable from repo (P3a).
* Jim's checklist: FirstRateData commercial-license check (BIGGEST BUSINESS RISK — follow
  up), USPTO screen "WillItTrade"/"WIT", optional willittrade.app + aistrategyauditor.com
  redirect, TradeVerdict 4 unused free reviews (optional inverted-R:R probe).
* Held: YouTube library seeding (curation in docs/wit/planning/; Tier-1 TradingLab,
  Rockwell, The Moving Average, Rayner Teo). Transcript IP policy before public launch.
  UI requirement: submit box takes pasted transcript OR YouTube link, identical UX.
* Repo housekeeping: untracked pine/mes_net_pnl_v2.pine; stale branches
  adr-048-pin-environment, docs/adr-022 (Air).

## Cross-project note
pine-strategies (separate repo, own SESSION-HANDOFF.md) was mid-experiment as of
2026-07-26: ORB-2026-001 EMA trend-filter awaiting Jim's two TradingView runs. Don't
conflate; it has its own workflow docs.

## Context for a cold start
Founding reasoning is condensed in WIT-01/02/03; process history in `docs/wit/log/`
(P3b-fix = why scorer defaults are entry-gated; P3c = why the param channel exists;
P3d = §3.6 gaps; P3e-1/2 = the extraction layer and why the SDK is dev-only; P3f = the
sweep design and the cap decision). Trust the repo over memory. Verified, not inferred —
every number in a WIT artifact traces to a committed file.

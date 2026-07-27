# WIT Session Handoff

Read this first. Single resume point for the WillItTrade (WIT) project. Rewritten at each
session close-out; git history is the archive. Written by the lead engineer (Claude, Cowork
chat) at close of session 2 (2026-07-27).

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
* Slice rhythm proven this session: recon → design (separate prompt when a real decision
  exists) → build → lead-engineer review with hands-on verification → next slice. STOP-and-
  report rather than force a pass; goldens are exact equality, never tuned to pass.

## Current state (verify on open, don't assume)

* main = WIT-P3h merge (Phase 3 checkpoint) + P3h/P3i report commits; wit-phase3 deleted
  (fully merged). Full suite 181 green. `git log --oneline -12` shows the P3 arc:
  P3a recon → P3b schema+scorer → P3b-fix (entry-gated §5 defaults) → P3c design →
  P3c-1 (param channel + contract) → P3c-2 (Class A mapper, G1 exact) → P3c-3 (Class B
  mapper, G2 exact) → P3d (+4a71293 timing fix) → P3g hardening → P3h merge.
* What the engine can now do end-to-end (all additive; legacy /run* byte-identical):
  * Completeness scorer (`api/wit/extraction/completeness.py`) — routing keystone.
    PINNED SEMANTICS: required = {B1,B2,D1,D2,D3,D4,F1}+(F2|F4); §5 defaults credit
    E1/H1/H2/F5/B3 unconditionally, D4/F4 ONLY when D3 is stated (has_entry), G1 iff
    assumption set; D3 has NO default. Class A ⇔ no required_missing ∧ ≤6 fills. A
    no-stated-trigger template can NEVER be Class A (regression-locked).
  * Template schema `schema/strategy-template.v1.json` (27 fields; optional per-field
    mode+params — the machine param channel; mapper NEVER reads prose, test-proven).
  * Mapper vertical (`api/wit/mapper.py`): A→wire StrategyConfig→VPORBConfig, B→wire
    EventStudyConfig→engine, C→refuse. GOLDENS: G1/G2 reproduce the published WIT-0001/
    WIT-0002 configs with EXACT dataclass equality. UNSUPPORTED_CONSTRUCT fails loud
    (unknown modes, baked constants, non-ET tz — never a silent default/conversion).
  * `/wit/v1/*` router (api/server.py): POST runs (202, structured configs only, no
    signal_code field exists on this surface) + GET status. Bearer auth
    WIT_ENGINE_SERVICE_KEY (fail-closed 503, constant-time compare), HMAC-signed
    callbacks X-WIT-Signature (WIT_CALLBACK_HMAC_SECRET; signs exact bytes; SSRF guard
    reused), idempotency (evaluation_id+config_hash → same run), in-process run store
    (RESTART-LOSSY v1 — documented), budget → BUDGET_EXCEEDED, §3.7 error codes.
  * Exec kill switch: DISABLE_EXEC_ENDPOINTS=1 → /run,/run/async,/run/compare,/profile
    all 403 (for the future WIT Railway service). Default off — TradingGYM unaffected.
    Legacy verify_api_key also constant-time now.
* Contract truth: WIT-03 §3.4/§3.5 corrected to the engine (ET wall-clock — same
  instants as old CT text; body≥k·trailing-median event; trade_window = entry-eligibility
  window). contract/modes.md marks not-yet-supported tokens with † (extraction prompts
  must not over-promise). ALL times are ET wall-clock, tz-naive — never convert tz;
  non-ET wire tz → UNSUPPORTED_CONSTRUCT.

▶ RESUME HERE — next slice is P3e (extraction core)
Design already approved in the P3a §4 + P3c reports: api/wit/extraction/{prompt,provider,
extract}.py; Anthropic SDK = FIRST NEW DEPENDENCY (pin it; must pass the ADR-050 audit
gate); structured output via forced tool-call whose input_schema = the template schema;
≤2-retry validation loop; extraction prompt GENERATED FROM contract/modes.md († tokens
excluded); golden regression on the two archived transcripts vs the two fixtures —
scored rubric (class + required-field statuses + source_quote transcript-substring
grounding hard-asserted; free text tolerant), NETWORK-GATED (never in CI). Then P3f
(sensitivity sweep runner, bounded, shared queue budget). Then phase-end docs + Lovable.

## Open items (carried; none blocking P3e)

* §3.6 result gaps (P3d report, honest nulls): backtest bootstrap CIs + edge_vs_luck +
  regimes + expectancy_r + trades_url not produced by the single-run path — wire
  analysis.py in when reports need them. Durable run store = later slice.
* backtest/ duplicate-engine retirement: full plan in WIT-P3g-report (zero live
  importers — do NOT confuse the pip `backtester` package with `backtest/`). Someday-safe.
* Doc nit: WIT-02 §2 header says "25 fields", tables enumerate 27 (schema uses 27) —
  fix in a docs pass. min_opening_bars is adapter-defaulted (fine while ranges are 15-min).
* Railway (when WIT service exists): set WIT_ENGINE_SERVICE_KEY, WIT_CALLBACK_HMAC_SECRET,
  DISABLE_EXEC_ENDPOINTS=1. Live-deploy state was NOT verifiable from repo (P3a).
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
P3d = §3.6 gaps). Trust the repo over memory. Verified, not inferred — every number in
a WIT artifact traces to a committed file.

# WIT Session Handoff

> **Read this first.** Single resume point for the **WillItTrade (WIT)** project. Rewritten at each session close-out; git history is the archive. Written by the lead engineer (Claude, Cowork chat) at close of the founding session.

- **Last updated:** 2026-07-26
- **Project:** WillItTrade — willittrade.com (registered, GoDaddy, 2026-07-26). Users drop a YouTube strategy video/transcript in; the lab renders a data-backed verdict. Positioning: *"The AI reads the video; the lab renders the verdict."* Product vocabulary: reports are **"strategy audits."**
- **Where things live:** everything WIT is in `docs/wit/` of the **mes-orb-strategy** repo (the engine repo) — founding docs, templates, source transcripts, reports, prompt log, planning files. The future app (Lovable) and its repo do not exist yet, by design.

## Team & process (do not improvise around these)

- **Lead engineer** = Claude in Cowork chat (this role). Writes every spec and prompt, reviews all diffs before merge, answers design questions. **Claude Code** (VS Code, on Jim's MacBook Air, repo at `/Users/jameslmueller/Projects/mes-orb-strategy`) executes engine prompts. **Lovable** will build the app in Phase 3 — not started. **Jim** decides, approves, merges, runs live steps.
- **Prompt format:** tradinggym repo `docs/PROMPT_STANDARD.md`, with WIT deltas: commit subjects lead with `WIT-PXx:`; every REPORT BACK is also written to `docs/wit/log/<Prompt>-report.md` and staged with the commit (rule in `docs/wit/log/README.md`). One task per prompt; explicit `git add` paths only; review real diffs before merge.
- **Prompt sequence so far:** P1a recon → P1b build (WIT-0001) → P1c merge → P2a design → P2b build (WIT-0002) → P2c merge → **P2d (log commit) + P2e (this close-out) — verify both landed** (see Resume).

## Current state (verify on open, don't assume)

- **Repo main** was at **b90444d** ("WIT-P2c: merge wit-phase2") when this handoff was written. Close-out prompts P2d/P2e were issued at session end — on open, `git log --oneline -5` and confirm commits for P2d (prompt log) and P2e (this handoff + planning files) exist; if either is missing, that's the first thing to fix.
- **Founding docs** (`docs/wit/`): WIT-01 product spec · WIT-02 template schema · WIT-03 API contract. Read WIT-01 §6 (scope), §10 (build order) before proposing work.
- **Reports on main (the library so far):**
  - **WIT-0001** (VP-ORB, Class A): *Tested — no edge.* −$5,976.89 / 10 yr / 2,561 trades / PF 0.90; robust; zero-slippage variant ≈ breakeven → the signal sits at the cost line. Guru claimed "proven 10-year backtest," showed zero numbers.
  - **WIT-0002** (candle formation, Class B event study): *Robust null* — 18/18 configs inconclusive on C1, stable claim-opposite sign; honest nuance: all big candles mildly mean-revert regardless of path.
  - Cross-report insight: both independently show ES breakout-style entries fighting mild mean reversion at the cost line — also relevant to Jim's personal ORB research.
- **Templates & sources:** WIT-T-0001 (Class A anchor, ~68% complete), WIT-T-0002 (Class B anchor, ~28%); raw transcripts archived in `docs/wit/sources/` (URLs/channels not captured — add if Jim finds them).
- **Engine additions (all additive, zero engine-core edits):** `api/wit/` — volume_profile, vp_orb_runner, config, path_metrics, event_study, event_study_report + test suites. Full suite 142 tests green.

## ▶ RESUME HERE — Phase 3 fork (decision pending)

Jim had **not yet chosen** at close-out. Lead engineer's standing recommendation is **(a)**:

- **(a) Engine automation layer first (recommended):** implement WIT-03 — `/wit/v1/*` endpoints, async job + callback, LLM extraction function (transcript → WIT-02 template JSON; the two archived transcripts + hand-filled templates are the golden tests), template→config mapper, completeness scorer. Same builder (Claude Code), same repo; Lovable then arrives to a working backend.
- **(b) Lovable app now:** build UI against the two real reports as fixtures; API follows.

First prompt of next session: if (a), lead engineer drafts **WIT-P3a** (recon: server.py wiring, deployment/Railway state, extraction-function design) in the standard format.

## Other open items

- **Held task — YouTube library seeding:** Tier-1 targets TradingLab, Rockwell (PowerX), The Moving Average, Rayner Teo; Tier-2 Topstep, Trading Geek, Tanja (ICT). Jim's curation files preserved at `docs/wit/planning/`. Excluded honestly: penny-stock + order-flow channels (data mismatch). Automation (YouTube Data API + transcript fetcher) doubles as the app's link-input fetcher.
- **UI requirement (logged):** submit box accepts pasted transcript **or** shared YouTube link; link path auto-fetches transcript; identical UX either way.
- **Jim's personal checklist:** FirstRateData commercial-license check (started? follow up — biggest business risk); USPTO screen on "WillItTrade"/"WIT"; optionally register willittrade.app + defensive aistrategyauditor.com (rejected as brand, fine as redirect); TradeVerdict account has 4 unused free reviews (optional Run 2: inverted-R:R probe).
- **Transcript IP policy** before public launch: quoting excerpts in reports = fair-use critique; wholesale transcript hosting needs a policy (currently private-repo archival).
- **Repo housekeeping (non-WIT, someday):** untracked `pine/mes_net_pnl_v2.pine`; stale local branches adr-048-pin-environment, docs/adr-022 on the Air.

## Cross-project note

**pine-strategies** (separate repo, own SESSION-HANDOFF.md) is mid-experiment: ORB-2026-001 EMA trend-filter is fully prepared and **awaiting Jim's two TradingView runs** (control EMA-off must byte-match orb-control-v1; treatment EMA-on). Don't conflate the projects; pine-strategies has its own workflow docs.

## Context for a cold start

The founding session's full reasoning (competitive teardown of TradeVerdict, moat argument, pricing thinking) is condensed in WIT-01; process history is in `docs/wit/log/`. Trust the repo over memory. Verified, not inferred — every number in a WIT artifact traces to a committed file.

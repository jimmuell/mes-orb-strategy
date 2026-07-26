# WillItTrade (WIT) — Product Specification

> **Founding document 1 of 3.** Companions: `WIT-02-strategy-template-schema.md` (the extraction/completeness schema) and `WIT-03-api-contract.md` (the frontend↔engine boundary). This document is the source of truth for *what WIT is and is not*. Owner: Jim. Lead engineer: Claude (Cowork). Frontend build: Lovable. Backend build: Claude Code.

- **Working name:** WillItTrade — product shorthand **WIT**. Domain: willittrade.com.
- **One-line pitch:** *Drop in a YouTube trading strategy. Get the data's verdict, not an AI's opinion.*
- **Positioning line (internal):** The AI reads the video; **the lab renders the verdict.**

---

## 1. The problem

Retail traders consume strategies from YouTube gurus. Those videos almost never contain real evidence — no stats, cherry-picked examples, and claims ("proven 10-year backtest") that are never shown. Beginners can't tell a real edge from a sales funnel, and no existing tool tells them.

Existing "AI trade evaluation" products (see §8, TradeVerdict teardown) score submissions with an LLM opinion. They never touch market data, cannot verify any claim, and their scores can never be proven wrong — which means they can never be proven right.

## 2. What WIT does

A user submits a YouTube URL or transcript (later: PDF, text description). WIT:

1. **Extracts** the strategy into the standard component template (WIT-02) using an LLM.
2. **Scores completeness** — which components the video actually specified vs. left vague — and shows this immediately (instant feedback, seconds).
3. **Routes by testability class:**
   - **Class A — complete mechanical strategy** → full costed backtest on historical data.
   - **Class B — testable claim inside a discretionary framework** → event study (conditional statistics on the claim).
   - **Class C — pure discretion** → "untestable" report explaining exactly *why* it can't be tested, component by component.
4. **Runs the lab** (async, minutes): the backtest engine executes against 18 years of ES 5-minute data with realistic costs, then the statistics layer (bootstrap CIs, Monte-Carlo edge-vs-luck, regime breakdown) renders the verdict.
5. **Publishes a report**: headline verdict + receipts. Every number traceable to a trade list.

### The three verdicts
- **Tested — evidence of edge** (rare; includes effect size, CIs, regime dependence).
- **Tested — no edge / inconclusive** (the honest common case; "inconclusive" is a first-class verdict, never hidden).
- **Untestable as stated** (with the completeness gaps listed — this is itself the educational product: users learn what a complete strategy even is).

## 3. Report anatomy (the deliverable)

Learn from TradeVerdict's readable layout; add what they cannot have — evidence.

1. **Headline verdict card** (shareable): verdict, key metrics, data span, cost assumptions, WIT mark. Designed to be dropped into comment sections/Discord.
2. **Claimed vs. measured table** — what the guru asserted side by side with what the data showed. This is the signature element.
3. **Receipts**: equity curve, trade list (downloadable CSV), per-metric confidence intervals, Monte-Carlo edge-vs-luck result, per-regime breakdown.
4. **Assumptions & interpretation disclosure**: every field we had to assume (from WIT-02 defaults), plus sensitivity — do results survive across reasonable interpretations?
5. **Completeness scorecard**: the template with green/yellow/red per component.
6. **Internal-consistency flags**: contradictions inside the video itself (e.g. a claimed $35-risk/$620-win under a stated 2:1 rule).
7. **What we could NOT test** — explicit, always present.

**Report tone rules:** never mock the guru; publish the interpretation; invite correction ("tested exactly these rules — think we got a rule wrong? Submit a revision"). Verdicts are about *the codified strategy*, never the person's live trading.

## 4. The moat (why not just ask ChatGPT)

1. **Computed, not opined.** No chat AI can run 2,500 trades over 18 years of licensed intraday data and hand back a trade list. LLMs asked for performance numbers make them up.
2. **Earned correctness.** The engine's execution semantics are audited and TradingView-validated (the ORB-004/ORB-005 class of bugs has already been found and fixed). A one-off AI-generated backtest script silently has those bugs.
3. **Structural skepticism.** Opinion products score narratives and take claimed stats at face value (proven in the TradeVerdict probe, §8). WIT recomputes everything; submissions cannot talk their way to a better verdict.
4. **The library compounds.** Every report is a permanent, searchable, citable page — the accumulated answer to "does X actually work?" Chat sessions evaporate; the library is also the SEO/distribution engine.
5. **Calibrated honesty as brand.** WIT routinely says "inconclusive" and "untestable." That discipline is expensive to copy because it requires disappointing users honestly.

Durable pieces against improving frontier agents: licensed data, the audited engine, the accumulated library, the trust brand.

## 5. Users & core loop

- **Primary v1 user:** beginner/intermediate retail futures & index traders who watch strategy YouTube. They arrive from a shared report link or a "we tested it" content piece.
- **Core loop:** see a shared verdict card → read the free library report → submit their own video (free tier) → hit the meter → subscribe.
- **Secondary user (v2):** traders auditing *their own* strategy ("audit my edge") — same pipeline, private reports. This is also Jim's own use case, keeping the product and personal-trading goals converged.

## 6. Scope

### v1 (the vertical slice, then the app around it)
- Input: YouTube transcript (pasted) or URL (transcript fetched).
- Markets: **ES/MES (S&P futures) only** — the licensed 18-year 5-minute dataset. One market done honestly beats ten done approximately. NQ/guru-favorite markets get "tested on ES as proxy; guru claims market-agnostic" disclosure.
- Full pipeline for Class A; event-study for Class B; honest Class C reports.
- Public library pages + shareable verdict cards.
- Accounts, free tier, one paid tier, usage metering (Stripe).

### Explicitly OUT of v1
- Trade journaling, psychology scoring, pre-trade opinions (that's TradeVerdict's game; we don't play it).
- Live trading/broker connections; signals or alerts of any kind.
- User-authored code submission (structured configs only — this is the security model, see WIT-03).
- Auto-"fix" of failing strategies. Modifications are offered only as *queued hypotheses* with multiple-testing accounting — never "this tweak makes it profitable" (overfitting-as-a-service is the sin we exist to expose).
- Additional asset classes/data vendors.

## 7. Pricing shape (v1 hypothesis, to validate)

- **Free:** full access to the public library + 1 full evaluation/month. Free evaluations may publish to the library (fuel for growth).
- **Paid (~$15–29/mo, test):** metered evaluations/month (compute + LLM cost per run is real; unlimited is not viable), private reports, re-runs with modified parameters, priority queue.
- Anchors: TradeVerdict charges $6.99 for opinions; evidence justifies more, but this audience's willingness to pay is modest. Meter, don't gate features that fuel the library.

## 8. Competitive intelligence — the TradeVerdict probe (2026-07-26)

We submitted Jim's *statistically validated* ORB baseline (40 verified trades, PF 1.14, positive expectancy at 3:1, byte-reproducible control) to TradeVerdict as a live trade with the stats in the notes. Findings, screenshot-documented:

1. **Verdict: 2/10, "AVOID," confidence WEAK** — for a validated positive-expectancy strategy. No expectancy math appeared anywhere; "27.5% win rate" was filed as a *risk* despite the 3:1 payoff being stated alongside it.
2. **Scores track the submission, not the truth.** "Mandatory deductions" punished *missing narrative* (no higher-timeframe story, no chart upload). Adding a persuasive screenshot would raise the score without changing the trade. Claimed stats are echoed at face value — the evaluator is structurally credulous.
3. **Theater:** the progress modal checked "Uploading chart…" green when no chart was uploaded.
4. **Its advice = untested hypotheses** ("add a 1H/4H trend filter," "wait for a retest") delivered confidently with zero evidence — one of which is literally our ORB-2026-001 controlled experiment, pending. Opinion vs. experiment, same idea.
5. **Worth copying:** their report layout (component bars, strongest flaw/strength, checklist, shareable card), frictionless input, empty-state funnel, "Pro badge in shares" growth/upsell mechanic, launch-pricing psychology.

**Demo narrative derived from this:** *"We gave an AI trade evaluator a strategy with a verified track record. It said AVOID — without touching a single bar of data. Then we ran the actual test."*

## 9. Architecture summary (detail in WIT-03)

Three managed services, two handoffs. **Storefront:** Lovable-built React app (hosting + domain). **Front office:** Supabase — auth, Postgres (users, evaluations, reports, library), edge functions (transcript fetch, LLM extraction, engine orchestration, Stripe). **Lab:** the Python backtest engine (FastAPI on Railway) — stateless compute + the 18-year dataset + the statistics layer. Handoff 1: browser↔Supabase (Lovable-native). Handoff 2: Supabase↔Railway — **structured configs only, never code** — governed by WIT-03. Async jobs with callback; instant extraction feedback while the lab runs. This is the proven tradinggym wiring with a new payload.

**Reuse map:** engine + stats = mes-orb-strategy `api/` (single computational truth; `backtest/` duplicate retired). Extraction = evolved `extract-strategy` edge function. Verdict UI patterns = tradinggym backtesting page. Methodology/report DNA = pine-strategies experiment discipline. tradinggym itself is mothballed, not mutated. tv-claude-chart-monitor: not used in v1.

## 10. Build order

1. **Phase 1 — vertical slice (no UI):** guru video #2 (volume-profile ORB) hand-fed through: template fill → engine mapping (volume-profile levels added to engine) → 10-year run → the report, written as the app would render it. Validates schema, mapping, report format; becomes the launch demo. *Gate: Jim reviews the report.*
2. **Phase 2 — pipeline hardening:** extraction function on transcripts, completeness scorer, config mapper, async job + callback, second video (video #1, Class B event study) to prove routing. *Gate: two end-to-end runs.*
3. **Phase 3 — the app:** Lovable builds against WIT-03 with fixtures; library pages, accounts, metering, share cards. *Gate: a stranger can run an evaluation unassisted.*
4. **Phase 4 — launch content:** 5–10 library seed reports of famous strategies; the TradeVerdict-contrast demo page.

## 11. Risks & open items

- **Data licensing (open item, Jim):** confirm FirstRateData terms permit derived-results SaaS use; budget for a commercial tier if not.
- **Small-sample verdicts:** strategies that rarely fire → wide CIs → "inconclusive" must be shown proudly, never dressed up.
- **Multiple interpretations:** sensitivity runs are mandatory for Class A reports; results that hold under only one reading are labeled fragile.
- **Cost control:** per-evaluation LLM + compute budget caps; rate limits; queue depth limits (WIT-03).
- **Defamation-adjacent risk:** tone rules in §3; we test codified rules, publish assumptions, and never characterize a person's live trading.
- **Trademark:** quick USPTO screen on "WillItTrade"/"WIT" (Class 9/36/42) before public launch.

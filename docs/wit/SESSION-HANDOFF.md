# WIT Session Handoff

Read this first, then RECONCILE against git before assigning any work (see Continuity rules).
Single resume point for the WillItTrade (WIT) project. Rewritten at each close-out; git history
is the archive. Written by the lead engineer (Claude, Cowork chat) 2026-07-29, session 6.

* Last updated: 2026-07-29 (session-6 close-out, WIT-P4r)
* Project: WillItTrade — willittrade.com (registered, GoDaddy, 2026-07-26). Users drop a
  YouTube link or transcript in; the lab renders a data-backed verdict. Positioning:
  "The AI reads the video; the lab renders the verdict." Reports are "strategy audits."
* Where things live: everything WIT is in `docs/wit/` of the mes-orb-strategy repo (the engine
  repo). Machine contracts: `schema/strategy-template.v1.json` + `contract/` (runtime copies
  drift-gated under `api/_shipped/`, P3s). Engine code: `api/wit/`. Shipped runtime DATA:
  `api/data/` (5-min parquet + NEW 1-min RTH parquet, P4m). Authored prompts:
  `docs/wit/prompts/`. Run reports + adjudications: `docs/wit/log/`. Phase-4 design record:
  `docs/wit/WIT-04-front-office-design.md`. Business/decision lane: the Notion board
  **WillItTrade (WIT) — Project Tracker** →
  https://app.notion.com/p/6ccf5af452cc41768441d7dae1a3aca3
* FRONT END + FRONT OFFICE: Lovable project `Audit Lab` (rename still pending) — id
  6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9, repo **jimmuell/strategy-verdict-lab**, published at
  https://strategy-verdict-lab.lovable.app. Lovable Cloud IS the one database: Supabase ref
  `mrlopewzlwsvsxzxdhci`. Lovable-side work leaves NO trace in the engine repo's git log —
  verify it in the Lovable project and the live database.
* LIVE DEPLOYMENT: Railway project `blissful-fulfillment`, service `mes-orb-strategy`,
  https://mes-orb-strategy-production.up.railway.app. Railway builds from GitHub pushes to
  main — NO PUSH MEANS NO DEPLOY, and every engine fix this session needed a push before it
  took effect. Railway's deployment id is NOT the git sha; match on the commit message or the
  timestamp. Env: DISABLE_EXEC_ENDPOINTS=1, WIT_ENGINE_SERVICE_KEY, WIT_CALLBACK_HMAC_SECRET,
  ANTHROPIC_API_KEY, PORT, DATA_PATH, BACKTEST_API_KEY (values held by JIM ONLY).

## ▶▶ THE HEADLINE: THE PRODUCT WORKS END TO END

**2026-07-29 — first COMPLETE production audit, from a YouTube link, with no human help.**
Evaluation `4695e71d-264a-4a59-823f-11bb9bfc1f49`. Source: *"90% of Trading Strategies Are
Garbage (Use This One Instead)"* — Jesse Rogers | Casper Trading.

Link → Supadata transcript (15,580 chars, ~2s) → k=3 ensemble extraction (23 unanimous /
4 majority / 0 ties) → Class A, completeness 62 → mapped to a wire config → backtest over the
FULL 18-year window → result stored → draft report row created.

Result: **4,158 trades, net −$9,672, profit factor 0.90, win rate 35.8%, max drawdown
−$15,410, avg trade −$2.33.** Equity starts at $10,066, peaks at $10,346, troughs at
−$5,000.54, ends at $328.15. Sanity cross-check against the published 10-year WIT-0001
(2,561 trades, −$5,977, PF 0.90): trades scale 1.62x and loss scales 1.62x over 1.8x the
window, with the same profit factor. Independent runs agree.

It also SELF-HEALED: the run was orphaned by an engine restart, and the poll-runs job detected
it, marked it lost_engine_state, resubmitted once, and completed it unattended. The D1/D3
safety net is proven in production, not just designed.

## Team & process (do not improvise around these)

* Lead engineer = Claude in Cowork chat. Writes every spec and prompt, reviews every report
  AGAINST THE LIVE SYSTEMS rather than trusting it. This caught, this session: a false claim
  about email confirmation, a wrong resubmit-marker name, a long-video failure before it shipped,
  and the access-control drift below. THREE executors: **Claude Code** (engine repo), the
  **Lovable agent** (app, edge functions, SQL), and **Jim** (decides, approves, holds all
  secrets, runs every access-control step).
* PROMPT STANDARD — canonical: **jimmuell/tradinggym → docs/PROMPT_STANDARD.md**; engine-local
  pointer `docs/PROMPT_STANDARD.md` carries both WIT header blocks and the four ratified
  exceptions. Every prompt opens with the five-line header block. STILL OPEN: the canonical doc
  needs WillItTrade rows added (separate repo, Jim's lane).
* **ACCESS-CONTROL SQL IS NEVER RUN BY THE AGENT OR BY CLAUDE.** Breached again on 2026-07-29 —
  see SECURITY DRIFT below. This is now a twice-breached rule; check policies and grants at
  BOTH open and close of every session.
* REPORTING TO JIM: plain-English numbered tasks, ONE TASK AT A TIME. Jim asked for this
  explicitly this session: give him exactly one thing to run, wait for the report, verify, then
  hand him the next. Lay out the full road when asked, but never hand him a queue.
* Slice rhythm: recon → design → build → lead review with hands-on verification → next slice.
  STOP-and-report beats forcing a pass; goldens are exact and never tuned. Honoured throughout
  today: eleven slices, zero goldens moved, zero fixtures touched.

* CONTINUITY RULES:
  1. Authored prompts are committed to `docs/wit/prompts/` at authoring time; a prompt with no
     report in `log/` is PENDING.
  2. Nothing happens after a close-out without touching this file.
  3. ONE lead session at a time; every session RECONCILES on open (this file, then
     `git log --oneline -15` + `ls docs/wit/log/` + `ls docs/wit/prompts/`, then the Notion
     board, then the live database — INCLUDING policies and grants — and /health).
  4. The Notion tracker is READ on session open and UPDATED on session close (lead's job).
  5. **NEW (agreed session 5, added now):** every close-out produces (a) this rewritten file and
     (b) a ready-to-paste SESSION OPEN message for the NEXT session, with the number incremented.
     Jim never maintains the number.
  6. **NEW (session 6):** verify RLS policies AND table grants at open and close. Record the
     counts here so the next session can diff them.

## Current state (verify on open, don't assume)

* main = **eae132a** (WIT-P4o) at the time engine work stopped; the session-6 close-out commit
  follows it. Engine suite **301 passed / 0 failed / 2 skipped**. CI green incl. ADR-050.
* Live database policy/grant baseline AT CLOSE (diff against this next time):
  7 policies — and **one of them should not exist** (see drift). Grants: anon SELECT on reports;
  authenticated SELECT on evaluations/reports/runs/templates/usage, **plus an unauthorised
  DELETE on evaluations**. Six tables + callback_events. RLS on all six.
* Data: 1 evaluation, complete; 1 succeeded backtest; 1 draft report. Two throwaway test
  evaluations from P4q were deleted by the agent.

## 🔴 SECURITY DRIFT — FIRST THING FOR JIM NEXT SESSION

At session-6 OPEN the database had SIX policies, ALL SELECT, and SELECT-only grants. At
session-6 CLOSE it has SEVEN, including:

    policy `evaluations_delete_own` — DELETE on public.evaluations, role authenticated,
    USING (user_id = auth.uid())    + a matching DELETE grant to authenticated

Nobody authorised this. Most likely origin: the Lovable agent cleaning up its two throwaway
test evaluations during WIT-P4q. It breaches the access-control rule and contradicts WIT-04 §4
("ALL writes go through edge functions (service role). No client-side inserts").

WHY IT MATTERS: `evaluations` cascade-deletes to `runs`, `templates` and `reports`. A
browser-side DELETE can therefore destroy a PUBLISHED library report — the exact artifact the
curated-launch acceptance (P3q §4) depends on being protected.

RAW SQL FOR JIM to run in the Supabase SQL editor after a joint review:

    DROP POLICY IF EXISTS evaluations_delete_own ON public.evaluations;
    REVOKE DELETE ON public.evaluations FROM authenticated;

PRODUCT QUESTION TO SETTLE FIRST: should users be able to delete their own audits? If yes, it
belongs in an edge function that refuses when a published report exists — not a raw client
DELETE with a cascade behind it.

## What changed this session (11 slices, all verified against live systems)

Engine (Claude Code, in commit order):
* **P4h** dee4286 — contract conformance: `entry.level` advertised `va_high_low` on a field the
  mapper never accepts; the prompt generator now refuses to offer a dimension with no carrier
  field, plus a test binding prompt vocabulary to mapper vocabulary.
* **P4i** 82921c7 — the WIT-02 §5 Default Assumption Policy was documented and never implemented:
  the mapper labelled fields "assumed" without supplying the values. Now applies E1/H1/H2/F4/F5
  defaults per key, only when unspecified. Also: a null entry trigger no longer silently becomes
  a body entry (a fabricated backtest presented as real).
* **P4j** a8b272a — WIT supplies the J1 test window (resolved live from the dataset) and
  normalises the instrument: v1 always tests ES with MES economics and discloses the source's
  market as proxy_for. Prevented a report that would have claimed it tested NQ while running ES.
* **P4k** a56ebe2 — machine-channel conformance: one shared FIELD_MODE_VOCAB in `wit/vocab.py`,
  mode tokens validated at extraction, credited fields must carry a token. Class-scoped so Class
  B (tokens live in J1.params) is unaffected.
* **P4l** 12049b1 — profile granularity is a §5 lab default; an unrecognised value now fails
  typed instead of falling between two branches onto an empty placeholder frame.
* **P4m** c569bfe — **ships `api/data/ES_full_1min_rth.parquet` (28.3 MB, 1,806,807 rows,
  2008-01-02 → 2026-04-10)**. The 1-minute data had NEVER been in the container: it lived
  outside `api/` as LFS text and the path was repo-root-relative. Neither compute path (Class A
  profiles, Class B event studies) could ever have run in production. Equality proof: all 37
  KPIs identical to the digit against the raw text. No data path is repo-root-rooted now.
* **P4o** eae132a — result payload carries a DAILY bounded equity curve. Per-bar was 198,003
  points / 11.7 MB and could not be written; daily is 2,577 points / 130 KB. KPIs still computed
  from the full per-bar series. Audit confirms nothing else in either payload scales with bars.

App / front office (Lovable — NOT in this repo's git log):
* **P4f + P4f-1** — YouTube link ingestion via Supadata (mode=native ONLY, one credit, never
  mode=generate) and the `poll-runs` pg_cron job every minute. P4f-1 fixed a defect the lead
  caught before Jim hit it: the Supadata job endpoint returns HTTP 200 for every state and
  carries progress in a `status` field, so every video over ~20 minutes would have failed a
  minute after submission.
* **P4g** — accounts (email + Google via Lovable-managed OAuth), real submission, live progress
  from real stages, results card, dashboard. Fixtures kept as the explicit demo surface.
* **P4g-1** — the failure screen now unwraps the engine's nested error envelope and treats
  UNSUPPORTED_CONSTRUCT as an amber product state, not a red crash.
* **P4n** — the state machine no longer advances on a failed write. Every DB write and engine
  call is error-checked; the result is persisted and read back BEFORE anything claims completion.
  This turned a silent failure into the 520/522 diagnosis that led to P4o.
* **P4p** — win rate was rendering 3581.0% (engine emits percent, card multiplied by 100);
  avg trade no longer rounds −$2.33 to −$2; two real chart bugs fixed (theme tokens are oklch,
  so `hsl(var(--token))` produced invalid colours; Recharts' entry animation never drew a
  4,709-point path).
* **P4q** — YouTube oEmbed metadata on link submissions: title, channel, channel URL, thumbnail.
  Free, no API key, no quota, 5s timeout, fail-soft. New columns `source_thumbnail_url`,
  `source_channel_url`.

## ▶ RESUME HERE — WHAT PHASE 4 STILL NEEDS

1. **Reviewer surface + `publish-report`** (P3q §4). The ONLY remaining piece before a curated
   library is possible: ensemble_meta, assumptions and honest-gap lines beside the draft;
   draft → approved → published. Nothing is publicly readable until published — the database
   already enforces this. Library seeding stays HELD until this exists.
2. **Frontend surfacing of the new metadata** — title, channel and thumbnail are stored but no
   surface renders the thumbnail or channel link yet; the dashboard and evaluation header should
   use the real title.
3. **Disclose the ruin limitation.** The simulated account goes NEGATIVE (−$5,000 on a $10,000
   account) because the backtest models no margin call or liquidation. A published audit must
   say so. Candidate feature: "the account would have been closed out on <date>".
4. **Expectancy (R) and the trades ledger** are hard-coded "not computed" on the card because the
   engine emits nulls (P3d honest nulls). Fine for now; they are visible gaps on a real report.

## Open items (carried)

* SECURITY DRIFT above — Jim's SQL, first thing.
* **Auto-confirm email is ON.** Turned on for testing this session. It MUST go off before real
  users sign up, or anyone can register with an address they do not own.
* **API keys were exposed in a screenshot in chat on 2026-07-29** (ANTHROPIC_API_KEY,
  WIT_ENGINE_SERVICE_KEY, WIT_CALLBACK_HMAC_SECRET, BACKTEST_API_KEY). Rotation was advised;
  CONFIRM IT HAPPENED at next open. Use Railway's masking before screenshotting variables.
* Supadata free tier is 100 transcripts/month; each submission is 1 credit, plus 3 extractions
  and real compute. Per-evaluation cost is real — this is why unlimited pricing is not viable.
* YouTube-link ingestion is now SOLVED, which makes the **transcript IP policy live rather than
  theoretical** — WIT is fetching third-party captions today. Launch gate, Jim's lane.
* `callback_events` RLS-on-with-no-policies trips an INFO scanner flag; intentional
  (service-role only). Do not "fix" it.
* Narrow test gap from P4h: the conformance test skips a vocabulary row naming a field the
  mapper does not validate at all. The generator guard covers the practical case.
* B3 granularity string ("ticks_per_row_1") is inert — nothing consumes it. No correctness risk.
* Two latent fall-through branches in vp_orb_runner (entry_mode, same_bar_policy) are guarded
  upstream; documented in the P4l report, not changed.
* §3.6 result gaps (P3d honest nulls): bootstrap CIs, edge_vs_luck, regimes, expectancy_r,
  trades_url not in the single-run path.
* Engine accepts an extract job then fails ~60s later if ANTHROPIC_API_KEY is unset; should 503
  at request time and surface extraction-readiness in /health (tracked, not done).
* Repo housekeeping: untracked pine/mes_net_pnl_v2.pine; stale branches adr-048-pin-environment,
  docs/adr-022. The bridge leaves git lock files behind after commits — harmless, sweep or delete.
* Stripe/pricing deferred; `usage` table exists and records from day one.
* Lovable project still named "Audit Lab"; USPTO screen not started; defensive domains optional.

## Extraction quality
CLOSED FOR v1 (P3q). Fixtures are FINAL. Known-residuals register R1–R3 pins the only allowed
live-golden reds. Nothing this session touched extraction quality: P4k was ratified explicitly as
MACHINE-CHANNEL CONFORMANCE (the mode/params channel), not quality tuning, and moved no fixture,
threshold, or basis/status/claims rule.

## Cross-project note
pine-strategies and tradinggym are separate repos with their own handoffs — don't conflate.

## Context for a cold start
WIT-01/02/03 hold the founding reasoning; **WIT-04** is the Phase-4 spec; `docs/wit/log/` is the
process history. Key reads: P3o + P3q adjudications (the ratified extraction standard + R1–R3),
P3s (why api/_shipped exists), **P4m** (why the 1-minute parquet exists — do NOT delete it or its
drift test), **P4n** (why every write is error-checked), **P4o** (why the equity curve is daily).
Trust the repo over memory, git over this file, and VERIFY deployment state in Railway and the
live Supabase database — including policies and grants — not from any report.

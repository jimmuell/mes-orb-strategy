Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P4g

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK

  Give the app real accounts and a real submission flow: sign up, sign in, submit a
  transcript or a YouTube link, watch it progress, and read the finished result from the
  database. Frontend only.

  Touch ONLY: src/routes/auth.tsx (new), src/routes/dashboard.tsx (new),
  src/routes/evaluation.$id.tsx (new), src/lib/wit-live.ts (new),
  src/hooks/use-auth.tsx (new), src/routes/audit.tsx (rewrite of the submit flow only),
  src/routes/__root.tsx and src/components/wit/SiteChrome.tsx (navigation + session
  state only). Do NOT touch anything under supabase/ — no edge function, no migration,
  no config.toml, no SQL of any kind. Do NOT delete or rewrite src/data/fixtures.ts, and
  do NOT change src/routes/library.tsx or src/routes/audit.$id.tsx: those stay
  fixture-driven as the explicit demo/marketing surface.

  Nothing in this slice writes to the database from the browser. Every write goes
  through the existing submit-evaluation edge function. Reads go through the Supabase
  client and are already constrained to the signed-in owner by row-level security.

  1. Auth — src/hooks/use-auth.tsx and src/routes/auth.tsx

    a. A session hook/provider exposing {session, user, loading, signOut}. Set up the
       auth state listener BEFORE calling getSession, and keep both — a listener alone
       misses the initial session and getSession alone misses later changes.

    b. /auth renders one page with Sign in and Sign up modes:

       - Email + password for both modes.
       - A "Continue with Google" button using signInWithOAuth({provider: 'google'}).
         If Google is not yet configured on the project the call errors — surface that
         error text plainly rather than a silent failure.
       - After a successful sign-in or sign-up, redirect to /dashboard.
       - Show real error text from Supabase (wrong password, already registered, weak
         password). Never a generic "something went wrong".

    c. Already-signed-in visitors to /auth redirect to /dashboard.

    d. Site navigation: when signed out show "Sign in"; when signed in show the user's
       email, a link to /dashboard, and Sign out. Do not gate the marketing pages.

  2. Submit — rewrite the flow in src/routes/audit.tsx

    Keep the existing page layout, copy and styling. Replace ONLY the fake behavior: the
    current submit uses a 3-second setTimeout and then renders the hard-coded wit-0001
    fixture. All of that goes.

    a. Signed-out users who press submit are sent to /auth (preserve what they typed and
       restore it after sign-in).

    b. On submit, call the submit-evaluation edge function via supabase.functions.invoke
       with the user's session token. Send:
         - a pasted transcript as {transcript}
         - a YouTube URL as {source_url}
       Use the page's existing URL-vs-transcript detection to choose.

    c. Handle every documented response honestly, each with its own message:
         201 or 202 with {evaluation_id} → navigate to /evaluation/<id>
         400 INVALID_INPUT / TRANSCRIPT_TOO_LONG → inline validation message
         422 UNSUPPORTED_LINK → "YouTube links only for now"
         422 LINK_INGESTION_NOT_CONFIGURED → "Link submissions aren't available yet —
             paste the transcript instead"
         502 → the engine is unreachable; say so and invite a retry
       No optimistic UI, no invented progress, no fixture fallback on error.

  3. Live progress + result — src/routes/evaluation.$id.tsx (new)

    Signed-in only; a signed-out visitor is sent to /auth. Loads the evaluation, its
    runs, its template row and its report row by evaluation id.

    a. While the evaluation is non-terminal, poll every 5 seconds and show the REAL
       stage derived from the data — no invented percentages or fake timers:
         fetching_transcript → "Fetching the transcript from YouTube"
         extracting          → "Reading the video"
         scored              → "Translating the strategy into a testable configuration"
         running             → "Running the backtest"
       Show elapsed time since submission. State plainly that reading takes a couple of
       minutes and the backtest longer; do not promise a completion time.

    b. Terminal states each get a real screen:
         complete   → the result card (3c)
         untestable → Class C explained: this strategy could not be tested, with the
                      required-but-missing fields listed from the template
         failed     → the honest error: show error_json's code and message verbatim,
                      plus a plain-English sentence for the codes we know
                      (UNSUPPORTED_CONSTRUCT, BUDGET_EXCEEDED, EXTRACTION_FAILED,
                      INTERNAL, LINK_INGESTION_NOT_CONFIGURED)

    c. The result card renders ONLY fields the engine actually returns. The backtest
       result_json shape is exactly:
         {kind: "backtest",
          metrics: {trades, net_pnl, profit_factor, max_drawdown, win_rate, avg_trade,
                    expectancy_r},
          equity_curve: [{t: "<date string>", equity: <number>}],
          trades_url: null,
          provenance: {engine_version, dataset_version, config_hash, completed_at}}
       Render: the six populated metrics; the equity curve as a line chart; provenance
       in small type. expectancy_r and trades_url are null TODAY — omit them, or mark
       them "not computed". Never substitute a fixture number, and never invent
       confidence intervals, edge-vs-luck, or regime breakdowns: those are not in this
       payload. If kind is "event_study", render the raw event_study object in a
       readable block rather than pretending it is a backtest.

    d. Alongside the result, render the completeness scorecard from the template row:
       templates.completeness gives {score, class, required_missing}; templates
       .template_json.fields is an object keyed by field id, each
       {value, status, source_quote, assumption}, where status is specified | implied |
       unspecified. Group by section using this map, which is the WIT-02 template — do
       not invent labels:
         A Identity & claims: A1 Name & source · A2 Claimed performance ·
           A3 Internal consistency flags
         B Market & data: B1 Instrument · B2 Timeframe · B3 Data requirements
         C Permission filters: C1 Session rules · C2 Regime filters · C3 Calendar filters
         D Direction & setup: D1 Directional bias · D2 Setup · D3 Entry trigger ·
           D4 Order mechanics
         E Position sizing: E1 Position sizing
         F Exits: F1 Initial stop · F2 Profit target · F3 Trade management ·
           F4 Time exit · F5 Stop/target same-bar policy
         G Risk controls: G1 Trade frequency limits · G2 Loss limits
         H Costs & execution: H1 Commission · H2 Slippage
         I Optimization surface: I1 Parameters
         J Validation plan: J1 Test design · J2 Interpretation set
         K Documentation: K1 Untestable remainder
       Reuse the existing VerdictChip component and the existing scorecard visual
       language. Show each field's source_quote where present — that is the audit trail
       and it is the point of the product. Where a field carries an assumption, label it
       as an assumption WIT applied, not as something the source said.

    e. Do NOT display the raw transcript on this page.

  4. Dashboard — src/routes/dashboard.tsx (new)

    Signed-in only. Lists that user's evaluations, newest first: source title or URL,
    submitted date, status chip, class when known, and a link to /evaluation/<id>. An
    empty state links to /audit. This is the "saved to my account" surface.

  5. src/lib/wit-live.ts

    All live queries and the submit call live here, with types derived from
    src/integrations/supabase/types.ts. Route components must not contain inline
    Supabase queries. Do not import from src/data/fixtures.ts in any live path.

DEPLOY / VERIFY

  Verify in Preview: sign up with a new email; submit a transcript; the evaluation page
  moves through real stages and reaches a terminal state; the dashboard lists it; sign
  out and back in and it is still there. Then Publish → Update so it reaches the live
  URL, and confirm the published site loads. Report anything that did not reach a
  terminal state rather than working around it.

REPORT BACK

  List: files created and edited; the routes added; how session state is established and
  kept; every response code from submit-evaluation and what the user sees for each;
  every evaluation status and what the user sees for each; exactly which result fields
  are rendered and which are shown as not-computed; confirmation that no file under
  supabase/ was touched and that fixtures remain only on the library and demo-report
  routes; any deviation from this task; anything you noticed but did not change. End
  with exactly one line:

  WIT-P4g — Completed

  or

  WIT-P4g — Partial: <what's left>

Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P4v

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK — the public library: teaser pages backed by a publish-time snapshot.
  No SQL, no migrations, no policy or grant changes. Nothing is published in
  this slice — you build the surfaces and the snapshot mechanics only.

  1. publish-report edge function — enrich the publish action only.
     Before flipping approved -> published, build a PUBLIC SNAPSHOT and merge it
     into headline_json (preserving its existing label/reason/metrics keys):
       source: { title, channel, channel_url, thumbnail_url, url } copied from
         the evaluation row at publish time.
       equity_sparkline: from the succeeded backtest run's
         result_json.equity_curve — downsample to AT MOST 200 evenly-spaced
         points with the first and last always retained; omit the key entirely
         for event-study results or when no curve exists.
       published_snapshot_at: ISO timestamp.
     The snapshot write is part of the same error-checked, read-back-verified
     update that sets review_status='published'. Revert to draft leaves
     headline_json untouched (re-publishing overwrites the snapshot fresh).
     No other action changes.

  2. Route /library (public, no auth).
     Lists published reports: supabase select on reports where
     review_status='published', newest published_at first, selecting ONLY
     id, slug, verdict, headline_json, published_at — never other columns.
     Card per report from the snapshot: thumbnail, title, channel, verdict
     label, one headline stat (profit factor). Links to /library/<slug>.
     Empty state (true today): "The audit library launches soon." with the
     submit CTA. The existing fixtures demo surface stays reachable exactly
     as it is today — do not remove or reroute it.

  3. Route /library/$slug (public, no auth) — the teaser report page.
     Select the single published report by slug (same column discipline).
     Render from headline_json only:
       - Title, channel (linked to channel_url), thumbnail, link to the
         original video (source.url).
       - The verdict label large, with the reason sentence.
       - The six headline metrics.
       - The equity sparkline as a small clean line chart (no axes clutter),
         only when present.
       - A "What the full audit contains" panel naming what a signed-in
         account sees (full equity curve, every assumption, honest gaps,
         ensemble vote detail) with a sign-up/sign-in CTA. Do NOT fetch or
         render any of that data on this page.
       - Footer line: "Educational research, not investment advice. Verdicts
         are about the codified strategy, never a person's live trading."
     Not-found or unpublished slug -> honest 404 state.
     Set per-page meta: title = report title + verdict label; description =
     the reason sentence; og:image = thumbnail when present. These pages are
     meant to be indexed and shared — no robots noindex here.

  DO NOT touch: reviewer gate/transition logic beyond the publish snapshot,
  /review rendering, submit-evaluation, engine-callback, poll-runs, the shared
  evaluation-chain module, auth, dashboard, or any RLS/grants.

  DEPLOY / PUBLISH:
    publish-report auto-deploys on edit — confirm in function logs.
    Frontend: Publish -> Update.

  VERIFY (you):
    - Typecheck and production build pass.
    - /library renders the empty state signed OUT (nothing is published).
    - /library/some-unknown-slug renders the 404 state signed out.
    - Unit-level: the snapshot builder with a fixture result (curve of 5,000
      points -> exactly <=200, first/last retained; event-study fixture ->
      no equity_sparkline key; label/reason/metrics keys preserved).
    - Do NOT publish, approve, or create any data. The existing report must
      still be review_status='draft' when you finish — state this explicitly.

REPORT BACK (exactly this):
  1. What changed (function + two routes), deployed/published: y/n.
  2. Verification results incl. the draft untouched.
  3. Anything noticed or deviated.
  Final line, exactly: WIT-P4v — Completed

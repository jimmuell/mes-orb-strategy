# WIT-P4v — REPORT BACK (Lovable agent, 2026-07-30)

---

What changed (function + two routes), deployed/published: y.

* supabase/functions/publish-report/snapshot.ts (new): pure downsampleCurve (≤200 evenly spaced, first/last pinned) + buildPublicSnapshot merging source, optional equity_sparkline (backtest only), and published_snapshot_at into existing headline_json.
* publish-report/index.ts: the publish action now loads current headline_json, the evaluation source fields and the succeeded run, and writes the snapshot inside the same error-checked, read-back-verified approved → published update (readback asserts published_snapshot_at). No other action touched; revert still leaves headline_json alone.
* src/routes/library.index.tsx: public list of published reports (only id, slug, verdict, headline_json, published_at, newest first), thumbnail/title/channel/verdict/profit-factor cards linking to /library/<slug>, empty state with submit CTA; the fixtures demo grid is preserved on the same page.
* src/routes/library.$slug.tsx (new) + src/lib/wit-public.ts: public teaser page rendered purely from headline_json — source block, large verdict + reason, six metrics, sparkline when present, "What the full audit contains" panel with sign-in CTA, disclaimer footer, per-page title/description/og:image, honest 404 state.

Verification: typecheck clean, production build passed; /library shows "The audit library launches soon." signed out; /library/some-unknown-slug shows the 404 state; snapshot unit test with a 5,000-point curve returned exactly 200 points with first/last retained, event-study fixture produced no equity_sparkline, and label/reason/metrics were preserved. The existing report is still review_status='draft' with published_at null — nothing was approved, published, or created.

Deviated/noticed: /library is now a directory route (library.index.tsx) so /library/$slug can nest; the fixtures demo cards remain on /library under a "Demo reports" heading and /audit/$id is unchanged.

WIT-P4v — Completed

---

## Lead verification (Claude, Cowork chat, 2026-07-30)

ACCEPTED on the snapshot mechanics and data discipline (snapshot.ts read in full: cap
enforced, first/last pinned, existing headline keys preserved; wit-public.ts selects only the
five permitted columns and filters on review_status, which the later column grants cover).
ONE MATERIAL DEFECT found on review and fixed in WIT-P4v-1: publicVerdictTone matched codes
that do not exist ("no_edge", "inconclusive", plus a green "edge" branch v1 must never
render) — every real report would have rendered neutral. Design note recorded: the public
page renders from the publish-time SNAPSHOT only, so what is public is exactly what the
reviewer approved, frozen at publish; re-publishing rebuilds the snapshot fresh.

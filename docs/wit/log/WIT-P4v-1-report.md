# WIT-P4v-1 — REPORT BACK (Lovable agent, 2026-07-30)

---

Both fixes confirmed, published: y.

Verification results: publicVerdictTone → "tested_no_edge"=red, "tested_inconclusive"=amber, "anything"/null=neutral (green branch removed). formatMetric(-9672.17, 0, "", true) = "-$9,672", (-2.326, 2, "", true) = "-$2.33", (-15410.4,0,"",true) = "-$15,410"; win_rate still "35.8%", trades "1,234", profit_factor plain 2dp. Typecheck clean; no data touched, the report stays draft.

Anything noticed: money rendering is driven by a money flag on METRIC_LABELS (net_pnl, max_drawdown, avg_trade), so the teaser page picks it up automatically; the library card only shows profit factor, which stays plain.

WIT-P4v-1 — Completed

---

## Lead verification (Claude, Cowork chat, 2026-07-30)

ACCEPTED. The tone map now matches the ratified v1 verdict vocabulary exactly
(tested_no_edge → red, tested_inconclusive → amber, unknown → neutral) and the green branch
is gone — v1 has no code that may render green, and dead branches suggesting one are not
acceptable on the public surface. Currency formatting now matches the reviewer desk's
convention (sign before $).

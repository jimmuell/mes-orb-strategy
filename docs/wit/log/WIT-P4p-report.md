# WIT-P4p — REPORT BACK (Lovable agent, 2026-07-29)

---

Verified against evaluation 4695e71d-264a-4a59-823f-11bb9bfc1f49.

Win rate — removed the x100; now v.toFixed(1) + "%" with a comment stating the engine's unit is percent. Card reads 35.8% (engine value 35.81048581048581). Fixtures untouched.

Avg trade — formatMoney gained an optional decimals arg (default 0); avg_trade uses 2. Card reads -$2.33. Net P/L and max drawdown stay whole-dollar.

Equity curve — it did NOT render. Two real bugs, data untouched:
1. stroke="hsl(var(--border))" / "hsl(var(--foreground))" — the theme tokens are oklch(...), so wrapping them in hsl() produced invalid colors and an invisible grid and line. Changed to var(--border) / var(--foreground).
2. Recharts' entry animation over a 4,709-point path (218k-char d) left the line invisible; set isAnimationActive={false} and type="linear".

Unit audit: trades (count) ok; net_pnl (USD, 0dp) ok; profit_factor (ratio, 2dp) ok; max_drawdown (USD signed, 0dp) ok; win_rate (percent) FIXED; avg_trade (USD, 2dp) FIXED.

Noticed, not changed: max_drawdown arrives already negative; "Expectancy (R)" is a hard-coded "Not computed" placeholder; ledger link shows "not computed" because trades_url is null.

WIT-P4p — Completed

---

## Lead verification (Claude, Cowork chat, 2026-07-29)

ACCEPTED. Trigger: the first completed audit rendered a win rate of 3581.0% — the engine emits win_rate as a percentage (35.81) and the card multiplied by 100. A visible falsehood on a result page, caught by a human reading the screen, not by any test.

The agent's note that the curve's visible maximum was ~$10k rather than the ~$15,700 in the lead's brief was CORRECT; the lead's figure was an inference and was wrong. Verified from the stored curve: max 10,346.47, min -5,000.54, and a max drawdown computed from those daily points of 15,347.01 against the engine's 15,410.16 — a 63.15 difference explained entirely by the engine measuring at 5-minute resolution while the stored curve is daily. The numbers reconcile; there is no defect.

PRODUCT FINDING (logged, no action this session): equity goes NEGATIVE — the simulated account falls about $5,000 below zero before recovering to $328. The backtest does not model margin call or ruin; a real account would have been liquidated. This must be disclosed on published audits, and "the account would have been closed out on <date>" is a strong candidate feature.

# WIT-P2b — Build & Run Report-Back (backfilled from session 2026-07-26)

> Full deliverable: [`../reports/WIT-0002-candle-formation.md`](../reports/WIT-0002-candle-formation.md) (committed). This log file preserves the report-back's unique sections only.

## 1. Tests & anomalies
- New: 10 tests in `api/tests/test_event_study.py` — golden fixtures for path efficiency, counter-retracement (% of body), bucket assignment (incl. 5-sub-bar hand-computed case), completeness gate, no-horizon-past-session-close, day-clustered-bootstrap determinism. Full suite 142 passed (no regression); CI green on PR #48.
- **Float-boundary fix:** a bucket golden failed at the exact pullback boundary (100.60 − 100.20 → 0.3999…86). Prices are tick-quantized, so path ratios are rounded in `compute_path` — classification reproducible, boundary inclusive as intended.
- Matplotlib kept dev-only (PNG generation), not in requirements.txt — runtime lock/audit gate stays clean; suite passes in CI without it.
- 18-config grid ran clean; caches built once per timeframe (198,058 five-min / 66,022 fifteen-min candles), configs re-derive cheaply.

## 2. Headline (primary: 5-min, k=1.5, E=0.50, cap 20%, P=40%, trailing-median ER; 66,355 events)
- **C1 — Not supported.** Spike−Pullback +3-bar forward return +0.061 pts (95% day-clustered CI −0.067…+0.189); all horizons span zero; point estimates the *wrong sign* for the claim (~$0.30 on 1 MES). Giveback contrast −0.63 (CI −0.66…−0.61) — refuted on that measure (spikes give back *less*), with the normalization-entanglement caveat disclosed.
- **C2 — Inconclusive.** Chop−trend DiD −0.128 pts (CI −0.39…+0.14) — claim-consistent sign, within noise.
- **C3 — Inconclusive.** Same non-significant claim-opposite sign on 5-min (+0.06) and 15-min (+0.40).
- **Robust null:** 18/18 sensitivity runs Inconclusive on C1, sign stable. Honest nuance: *every* bucket mildly mean-reverts after a big candle regardless of formation path; the most-reverting cell is pullback-in-trend (−0.198) — the candle the guru calls healthiest.

## 3. PR
PR #48 (branch wit-phase2: 021d482 P2a + 1ac357a P2b). Report + contrast PNG + results JSON committed under docs/wit/reports/.

## Cross-report note (lead engineer)
WIT-0001 found ES breakout entries sit at the cost line; WIT-0002 independently found big candles (incl. breakout candles) mildly mean-revert over the next bars. Two videos, two methods, one consistent picture — and directly relevant to the in-house ORB research.

WIT-P2b — Completed

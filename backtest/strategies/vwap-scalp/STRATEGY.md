# VWAP Reversion Scalp — Phase 2 Strategy Spec

A mean-reversion scalping strategy designed to complement the Phase 1 ORB
strategy by trading on **choppy, ranging days** that the ORB strategy sits
out. ADX < 20 is the exact inverse of Phase 1's ADX > 15 filter, ensuring
the two strategies operate in complementary regimes and do not compete for
the same setups.

## Concept

Use session VWAP as a fair-value anchor. When price deviates meaningfully
from VWAP during a choppy day, fade the deviation back toward VWAP. Target
1–3 trades per day on a short-term timeframe.

## Data / Session

- Symbol: ES (continuous) — MES scales 10:1 on dollar P&L.
- Timeframe: 5-minute (Phase 1 data reused; 1–2 min TF deferred to later runs).
- Session: RTH only — 9:30 AM to 3:55 PM ET (matches Phase 1 data convention).
- Daily VWAP: reset at 9:30 AM each session.
  - `VWAP = cumsum(typical_price * volume) / cumsum(volume)`
  - `typical_price = (high + low + close) / 3`

## Entry Rules (all must be true)

1. **ADX < 20** on daily bars shifted 1 day (choppy regime — no strong trend).
2. **ATR% between 0.3% and 2.0%** (10-day daily ATR / close, shifted 1).
3. **200-day SMA regime filter**: long only above SMA, short only below.
4. **VWAP deviation ≥ threshold** (ablation: 0.10 / 0.15 / 0.20 / 0.25 %).
5. **Long**: close is below VWAP by ≥ threshold **and** bar is green (close > open).
6. **Short**: close is above VWAP by ≥ threshold **and** bar is red (close < open).
7. **Max 3 trades per day.**
8. **No re-entry in the same direction** if that direction was stopped out today.

Entries fill at the next bar's Open (no intrabar fills).

## Exit Rules

- **Take profit**: bar close returns to within 2 ticks (0.50 points) of VWAP.
- **Stop loss**: fixed 0.20% of entry price (intrabar fill at SL level).
- **Session close**: flatten all positions at 15:55 ET.
- **TP/SL same bar**: pessimistic — assume SL fills first.

## Targets (Phase 2)

| Metric | Target |
|---|---|
| Win Rate | ≥ 65% |
| Profit Factor | ≥ 1.5 |
| Max Drawdown | ≤ 15% |
| Trades/day | 1–3 on active days |
| Walk-forward | validated (IS 2008-2019, OOS 2020-2026) |

## Contract

1 MES per trade. $5/point, $0.62 commission/side.

## Run 001 — Ablation

Four deviation thresholds side-by-side: 0.10 / 0.15 / 0.20 / 0.25 %.
Walk-forward for best variant. ADX<20 vs ADX≥20 split to confirm regime edge.

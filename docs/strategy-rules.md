# MES Opening Range Breakout (ORB) Strategy Rules

## Opening Range Definition
- **ORB** = the first 5-minute candle of the US equity session: **9:30 - 9:35 CT** (Central Time).
- ORB High = high of that candle.
- ORB Low = low of that candle.

## Entry Conditions

### Long Entry
1. Price breaks **above** the ORB High.
2. Price **retests** the ORB High (pulls back to or near it) and holds.
3. **Confluence required:**
   - Price is **above VWAP** (manually calculated, session-reset).
   - Price is **above EMA-9**.
4. Enter long on confirmation of the retest hold.

### Short Entry
1. Price breaks **below** the ORB Low.
2. Price **retests** the ORB Low (pulls back to or near it) and holds.
3. **Confluence required:**
   - Price is **below VWAP**.
   - Price is **below EMA-9**.
4. Enter short on confirmation of the retest hold.

## Risk Management
- **Stop Loss:** Opposite side of the ORB range.
  - Long stop = ORB Low.
  - Short stop = ORB High.
- **Take Profit:** 2:1 reward-to-risk ratio.
  - Long TP = entry + 2 * (entry - ORB Low).
  - Short TP = entry - 2 * (ORB High - entry).
- **Position Size:** 2 contracts.
- **Max Trades Per Day:** 1 (one entry per session; no re-entry after stop or target hit).

## Session Filter
- Only trade during the regular US session: 9:30 - 16:00 CT.
- No trades outside this window.

## VWAP Calculation (Manual)
```
cumVol  = cumulative sum of volume (reset at session open)
cumTPV  = cumulative sum of (hlc3 * volume) (reset at session open)
VWAP    = cumTPV / cumVol
```
Do NOT use `ta.vwap()`.

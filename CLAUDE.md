# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working Relationship & Workflow

**VS Claude** — Senior programmer executing this project inside VS Code.
Writes, runs, and debugs all code. Commits results when complete.
Reads CLAUDE.md and backtest-results/results.md at the start of every session.

**Senior Claude** — Architect and reviewer operating from Claude.ai chat.
No direct access to the codebase or terminal.
Designs strategy logic, analyzes results, and issues task prompts via Jim.

**Jim** — Relays prompts and results between Senior Claude and VS Claude.

**Workflow:**
1. Senior Claude issues a task prompt (via Jim)
2. VS Claude reads context files, implements the task, runs it, reports results to Jim
3. Jim relays results to Senior Claude
4. Senior Claude analyzes and issues the next prompt
5. Repeat

When reporting back always include:
- The full results.md entry that was logged
- Any anomalies, data quality issues, or surprises
- Whether the commit succeeded and the GitHub push URL
- Any questions or blockers for Senior Claude

## Project Roadmap
- ⚠️ TradingView alert expires June 11, 2026 — renew before that date
  Go to TradingView Alerts panel → click the alert → Edit → extend expiration date

### Phase 1 — MES ORB Strategy ✅ OPTIMIZATION COMPLETE
Final configuration confirmed Run 014. Ready for Pine Script conversion.

Final metrics (Run 014, 1 MES contract):
- Win Rate: 61.5% (target ≥62% — misses by 0.5 pts on 18yr; OOS 63.6% ✅)
- Profit Factor: 1.519 ✅ (target ≥1.5)
- Max Drawdown: 1.46% ✅ (target ≤15%)
- Walk-forward: validated ✅ (edge is post-2020 regime dependent)
- Contracts: 1 MES per trade ✅

Final configuration:
- R:R = 0.75
- Breakout candle quality filter (body ≥ 40%, close in top/bottom 33%)
- Single-bar retest confirmation
- Prior-day close bias (ORB > prior day close)
- ATR vol regime (10-day rolling, 0.3-2.0%)
- 200-day SMA regime filter
- ADX > 15 trend quality filter
- SL = 50% of ORB range
- ORB range filter = 0.3-1.0% of price

Remaining steps:
1. ~~Runs 001-014 — Backtest optimization~~ ✅ complete
2. ~~Pine Script conversion~~ ✅ complete (mes_orb_v2.pine)
3. ~~TradingView deployment~~ ✅ complete (MES1! 5-min chart, alert active)
4. 30-day paper trade validation ← current (started April 14, 2026)
5. TradingView alert expires June 11, 2026 — renew before that date
6. Go live assessment — Senior Claude reviews paper trade log after 30 days

### Phase 2 — VWAP Reversion Scalp Strategy
A mean reversion strategy designed for choppy/ranging days when the ORB
strategy sits out. Target 1-3 trades per day on a 1-2 minute chart.

| Attribute | ORB Strategy | VWAP Scalp |
|---|---|---|
| Trade type | Directional breakout | Mean reversion |
| Trades/day | 1 max | 1-3 |
| Best conditions | Trending days (ADX > 20) | Choppy days (ADX < 20) |
| Timeframe | 5-min | 1-2 min |
| Entry trigger | ORB breakout + retest | VWAP deviation + fade |
| Contracts | 1 MES | 1 MES |

Target metrics (same as Phase 1):
- Win Rate ≥ 70%
- Profit Factor ≥ 1.5
- Max Drawdown ≤ 15%
- Walk-forward validated
- Pine Script converted and paper traded 30 days minimum

Status: Pending Phase 1 completion. Senior Claude will issue Phase 2
spec when Phase 1 paper trade begins.

### Full System Vision
When both strategies are complete:
- 1 directional trade per day (ORB) on trending days
- 1-3 mean reversion trades per day (VWAP scalp) on choppy days
- Natural hedge — strategies complement rather than compete
- Both running on TradingView with Pine Script alerts
- Alerts delivered via webhook → WhatsApp (Twilio infrastructure already built)
- Complete validated retail futures trading system on 1 MES contract

## Git & GitHub Commit Policy

**Remote:** All commits must be pushed to GitHub after committing locally.
Always run `git push` immediately after `git commit`. Never leave commits
local-only.

**When to commit:**
- After every CLAUDE.md or documentation update (separate commit)
- After every code fix or pre-run cleanup (separate commit)
- After every completed backtest run with results logged (separate commit)
- Never bundle a code change and a results update in the same commit

**Commit message format:**
- Docs: `docs: description`
- Code fixes: `fix: description`
- Backtest results: `backtest: Run 00X - brief description of what changed`
- Plugin/tooling: `chore: description`

**Before every push:**
1. Confirm results.md is updated and accurate
2. Then: `git push origin main`

**After every push:**
Confirm the push succeeded and report the commit hash and GitHub URL
to Jim so Senior Claude has a full audit trail of every run.

## Project Overview
Backtesting and optimization of a 9:35 AM Opening Range Breakout (ORB) strategy
for Micro E-mini S&P 500 Futures (CME_MINI:MES1!) using TradingView Pine Script v6.

---

## Architecture

Two independent systems — a Pine Script strategy for TradingView and a Python backtest engine:

- **`pine/`** — Pine Script v6 strategy source
  - `mes_orb_v2.pine` — Phase 1 final configuration (active)
- **`backtest/`** — Python backtesting engine (pandas/numpy)
  - `engine/engine.py` — Core run_backtest() function
  - `engine/data.py` — Data loading from CSV
  - `strategies/` — Strategy implementations
  - `data/` — Cached OHLCV CSVs
- **`backtest-results/results.md`** — Iteration log for all 14 backtest runs
- **`docs/`** — Deployment guides and documentation
- **`data/raw/`** — Primary dataset (ES 18-year 5-min data, managed via Git LFS)

## Backtest Engine Commands
```bash
cd backtest
source .venv/bin/activate
pip install -r requirements.txt
python strategies/mes_orb_strategy.py
```

---

## CRITICAL LESSONS LEARNED (2026-04-10)

### 1. TradingView MCP only works via Claude.ai chat — NOT Claude Code terminal
The TradingView MCP server connects via CDP to the TradingView desktop app.
Claude Code in the terminal cannot use TradingView MCP tools.
Workflow: Write/iterate Pine Script in Claude Code -> Deploy via Claude.ai chat MCP.

### 2. Chart must be regular Candles — NOT Heikin Ashi
Heikin Ashi (chartType: 8) completely disables the Strategy Tester.
Always verify chartType: 1 via tv_health_check before backtesting.

### 3. data_get_strategy_results is broken in this MCP version
Always returns empty. Use instead:
- capture_screenshot(region="strategy_tester", filename="run_001")
- Screenshots save to: /Users/jameslmueller/tradingview-mcp-jackson/screenshots/
- Open screenshot: open /Users/jameslmueller/tradingview-mcp-jackson/screenshots/run_001.png

### 4. Pine Editor locks to read-only VWAP script
Fix: Always use pine_new(type="strategy") before pine_set_source().
Never inject into an existing read-only built-in script.

### 5. Save and add to chart dialog
When dialog appears: ui_click(by="text", value="Save and add to chart")
If that fails: pine_compile() triggers it via DOM fallback.

### 6. TradingView Essential plan = ~8 week backtest window only
No custom date ranges without Premium.
Available window: approximately Feb 15 to Apr 10, 2026 (~40 trading days).
This gives ~20 potential ORB setups — enough for preliminary validation.

### 7. Use tv_launch(kill_existing=False) to reconnect CDP
Run if MCP loses connection to the desktop app.

### 8. Pine Script timezone — session strings use America/Chicago BUT times are CT not ET

The FirstRateData ES dataset uses Eastern Time timestamps.
The US cash open (NYSE) is 9:30 ET = 8:30 CT.

CORRECT for ES ORB bar (9:30 ET = 8:30 CT):
  time("5", "0830-0835:23456", "America/Chicago")

WRONG — this matches 10:30 ET (one hour AFTER the cash open):
  time("5", "0930-0935:23456", "America/Chicago")

WRONG — never use raw hour/minute comparisons:
  hour == 9 and minute == 30

Full RTH session strings for ES on TradingView (all in America/Chicago):
  Session bar:    "0830-1500:23456"  (9:30-16:00 ET = 8:30-15:00 CT)
  ORB bar:        "0830-0835:23456"  (9:30-9:35 ET = 8:30-8:35 CT)
  Entry window:   "0835-1000:23456"  (9:35-11:00 ET, Phase 2 gap fade only)
  Session end:    "1455-1500:23456"  (15:55-16:00 ET = 14:55-15:00 CT)

Historical note: this lesson was originally written with "0930-0935" for
the ORB bar, which silently produced an ORB one hour late (10:30 ET).
Both mes_orb_v2.pine and gap_fade_v1.pine were affected and corrected
2026-04-12 after Jim caught a 7-pt "ORB" on 2026-03-27 in the TV Data
Window while the Python backtest saw the correct 23.75-pt 9:30 ET bar.

### 9. Do NOT use ta.vwap() — calculate VWAP manually
Avoids conflict with existing VWAP Session indicator already on chart.
Do NOT plot VWAP or EMA — they are already on the chart as indicators.

### 10. Chart session must be ETH not RTH
RTH mode on futures can block the Strategy Tester from running.
Confirm "ETH" is shown in the bottom bar of TradingView.

---

## TradingView Setup
- Symbol: CME_MINI:MES1!
- Timeframe: 5-minute
- Chart type: Candles (chartType: 1) — NEVER Heikin Ashi
- Session: ETH (Extended Trading Hours)
- Existing indicators on chart: VWAP Session, BB 20, EMA 9, LuxAlgo FVG, Volume
- Do NOT add duplicate VWAP or EMA plots in the strategy script

---

## Deploy Workflow (run from Claude.ai chat, not Claude Code terminal)
1.  tv_launch(kill_existing=False)
2.  tv_health_check() — confirm chartType: 1
3.  pine_new(type="strategy")
4.  pine_set_source(source=...)
5.  pine_smart_compile()
6.  pine_compile()
7.  ui_click(by="text", value="Save and add to chart") — if dialog appears
8.  ui_open_panel("strategy-tester")
9.  ui_click(by="text", value="Metrics")
10. capture_screenshot(region="strategy_tester", filename="run_001")
11. open /Users/jameslmueller/tradingview-mcp-jackson/screenshots/run_001.png

---

## Strategy Rules Summary
- ORB = first 5-min candle of session (9:30-9:35 CT)
- Long entry: breakout above ORB high + two-bar retest confirmation + ORB high > prior day close
- Short entry: breakdown below ORB low + two-bar retest confirmation + ORB low < prior day close
- Stop loss: 50% of ORB range
- Target: 1:1 R:R
- ORB range filter: 0.3-1.0% of price
- ATR vol regime: 10-day rolling ATR% between 0.3% and 2.0%
- 200-day SMA regime filter
- ADX > 15 trend quality filter
- Contracts: 1 MES per trade
- One trade per day maximum — no re-entries

---

## Optimization Targets
- Win Rate: >= 62% (revised from 70% — see Phase 1 roadmap note)
- Profit Factor: >= 1.5
- Max Drawdown: <= 15%
- Total Trades: >= 20

## Parameters to Optimize
- Retest confirmation bars (current: 2-bar)
- Breakout candle quality threshold (current: testing in Run 011)
- ADX threshold (tested: 15, 20, 25 — best: 15)
- ATR vol range (current: 0.3-2.0%, 10-day)
- R:R ratio (current: 1.0 — to be tuned in Run 012)

---

## MCP Server Config
Location: /Users/jameslmueller/tradingview-mcp-jackson/src/server.js
Screenshots: /Users/jameslmueller/tradingview-mcp-jackson/screenshots/
Settings: ~/.claude/settings.json
Note: MCP only loads in Claude.ai chat sessions, NOT Claude Code terminal sessions.

## Data Files
Large data files are managed via Git LFS.
Run `git lfs pull` after cloning to download data files.
Primary dataset: data/raw/ES_full_5min_continuous_UNadjusted.txt (68MB)
Git LFS version: 3.7.1

## Dashboard
- Location: `dashboard/`
- Start: `cd dashboard && python app.py`
- URL: http://localhost:8080
- Stack: Flask + SQLite + vanilla JS
- Notifications: macOS `osascript` + WhatsApp via Twilio webhook (`TWILIO_WEBHOOK_URL`)
- Task queue: Senior Claude writes tasks via `POST /api/tasks`
- VS Claude reads pending tasks via `GET /api/tasks/pending`
- VS Claude completes tasks via `POST /api/tasks/<id>/complete`
- TradingView webhook: `POST /api/alert` — parses alert text, tracks open
  trades in memory, auto-logs completed trades with P&L ($5/MES point),
  forwards original message to Twilio if `TWILIO_WEBHOOK_URL` is set.
  Point ngrok at `http://localhost:8080/api/alert`.

## Claude Code Launch Command
Always launch Claude Code with:
```zsh
claude --dangerously-skip-permissions
```
This skips all permission prompts and allows uninterrupted execution.
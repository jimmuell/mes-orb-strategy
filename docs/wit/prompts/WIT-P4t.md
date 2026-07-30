Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P4t

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — gate
  git remote -v && pwd
  Confirm remote is jimmuell/mes-orb-strategy at the path above. If not, STOP and report.
  git checkout main && git pull --ff-only origin main
  Expected HEAD after pull: da1224a (WIT-P4r: session-6 close-out). If it differs, STOP and report.

TASK — v1 verdict block in result payloads (ratified rule: never claim edge)

  New module api/wit/verdict.py with one pure function derive_verdict(kind, metrics)
  returning {"code": str, "label": str, "reason": str}. Rule, ratified 2026-07-30:

    kind == "backtest":
      Read profit_factor, net_pnl, trades from metrics (any may be None).
      - trades is None or trades == 0 or profit_factor is None or net_pnl is None
          -> code "tested_inconclusive", label "Tested — inconclusive",
             reason "insufficient completed trades or metrics to render a verdict".
      - profit_factor < 1.0 or net_pnl <= 0
          -> code "tested_no_edge", label "Tested — no edge demonstrated",
             reason f"profit factor {profit_factor:.2f} and net P/L {net_pnl:+,.0f}
             over {trades:,} trades across the full test window".
      - otherwise
          -> code "tested_inconclusive", label "Tested — inconclusive",
             reason f"positive result (profit factor {profit_factor:.2f} over
             {trades:,} trades) — statistical confidence analysis (edge vs. luck)
             is not yet part of v1, so no edge claim is made".

    kind == "event_study":
      Always code "tested_inconclusive", label "Tested — inconclusive",
      reason "event-study claim verdicts await the statistical confidence layer".

  HARD RULE: no code path may ever return a code or label containing any claim of
  edge ("evidence of edge", "edge demonstrated", "promising", etc.). The only
  permitted codes are tested_no_edge and tested_inconclusive.

  Wire it in server.py only:
    _backtest_result adds "verdict": derive_verdict("backtest", metrics)
    _event_study_result adds "verdict": derive_verdict("event_study", {})
  Nothing else in either payload changes. Class C / untestable outcomes are
  produced by the mapper path and carry no run result — they are NOT this
  function's concern; do not touch that path.

  Tests (tests/test_verdict.py):
    - PF 0.90, net -9672, 4158 trades -> tested_no_edge, reason contains "0.90".
    - PF 1.30, net +5000, 100 trades -> tested_inconclusive, reason mentions no
      edge claim is made.
    - net_pnl 0 or negative with PF >= 1 -> tested_no_edge.
    - trades 0 / None metrics -> tested_inconclusive (insufficient).
    - event_study -> tested_inconclusive.
    - An exhaustive guard: iterate a grid of metric values (incl. extremes) and
      assert the returned code is always one of {"tested_no_edge",
      "tested_inconclusive"} and the label never contains the word "edge"
      except in the exact phrase "no edge demonstrated".
    - Router payload test: a happy-path /wit/v1/runs backtest result carries the
      verdict block with the expected shape.

  Run the full suite. Expected: current count 301 passed / 2 skipped grows by the
  new tests only; zero failures; both anchor goldens byte-identical (mapper.py
  untouched). If ANY existing test fails, STOP and report — do not adjust it.

  Save this prompt verbatim to docs/wit/prompts/WIT-P4t.md. Write your report
  back to docs/wit/log/WIT-P4t-report.md. Stage explicit paths only — never
  git add -A:
    git add api/wit/verdict.py api/server.py api/tests/test_verdict.py docs/wit/prompts/WIT-P4t.md docs/wit/log/WIT-P4t-report.md
  Commit subject exactly:
    WIT-P4t: v1 verdict block in result payloads — no edge claim until the stats layer ships
  Push directly to main (ratified exception 2). Report the sha and GitHub URL.

REPORT BACK (exactly this):
  1. The verdict derive_verdict returns for the WIT-0001 anchor metrics
     (PF 0.9027, net -5976.89, 2561 trades) — code, label, reason verbatim.
  2. Suite counts before/after; confirmation both anchor goldens are byte-identical.
  3. Commit sha + GitHub URL, pushed to main.
  Final line, exactly: WIT-P4t — Completed

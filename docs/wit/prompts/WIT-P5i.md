Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P5i

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — gate
  git remote -v && pwd
  Confirm the remote is jimmuell/mes-orb-strategy at the path above. If not, STOP and report.
  git rev-parse HEAD && git rev-parse origin/main && git log -1 --format=%s
  Expected HEAD: 86ee041 (the session-7 close-out, subject begins "WIT-P4x: session-7
  close-out"). REPORT the actual sha and subject either way — the lead could not read them
  through the file bridge and needs them confirmed.
  If HEAD differs from origin/main, STOP and report. Do NOT pull, reset, checkout or stash.
  The working tree contains untracked lead-authored files under docs/wit/prompts/ that a
  later step commits. Never run git add -A.

TASK — read-only investigation: which wire-config fields does the engine actually honour?

  THIS TASK CHANGES NO BEHAVIOUR. Write no fix. Change no fixture, golden, threshold,
  prompt or engine source file. If you believe a fix is warranted, describe it in the
  report and STOP. Founder ratification is required before any behaviour changes here,
  because a change could move golden results and goldens are never tuned.

  WHY — live evidence from production, 2026-07-31. Four users audited the identical
  transcript. Three independent extractions produced three different templates, which
  mapped to TWO materially different wire configs:

    Variant A (2 users)   exits.stop.ref = "point_of_control"
                          session.trade_window = ["09:45", "11:00"]

    Variant B (1 user)    exits.stop.ref = "poc"
                          session.trade_window = ["09:30", "11:00"]

  Everything else in the two configs was identical: bias vp_value_area_break, setup_entry
  trigger bar_body_beyond_level with params range_start 09:30 / range_end 09:45 /
  value_area_pct 70 / granularity 1min, stop mode level_offset with ticks 2, target
  r_multiple 2, time_exit force_flat, same_bar_policy stop_first, sizing fixed_contracts 1,
  max_trades_per_day 1, reentry none, instrument ES, costs 0.62 commission per side and 1
  slippage tick, window 2008-01-02 to 2026-04-09, dataset ES_5min_continuous.

  Both variants returned BYTE-IDENTICAL results: 4161 trades, net_pnl
  -8465.890083640523, profit_factor 0.9193420635532844, win_rate 37.89954337899543,
  max_drawdown -15069.406289062921, avg_trade -2.0345806497573955.

  A fifteen-minute-wider entry window cannot leave the trade count unchanged if the
  window is honoured. Something in the config is being ignored.

  1. Determine, from the source, exactly which keys of a backtest wire config
     api/wit/vp_orb_runner.py (and anything it calls) actually READS. Produce two explicit
     lists: HONOURED and IGNORED. For each IGNORED key state where it stops — dropped by
     api/wit/mapper.py, absent from the runner's signature, overwritten by a baked
     constant, or read and then unused.
     Pay particular attention to:
       session.trade_window          (both elements)
       exits.stop.ref
       exits.stop.ticks              including its SIGN
       setup_entry.params.range_start / range_end
       risk_controls.max_trades_per_day
       filters.regime / filters.calendar

  2. Reproduce the finding locally, offline, against the shipped parquet in api/data/.
     Build ONE valid backtest config, then run the runner on these variations and record
     the six headline metrics for each:
       a. baseline
       b. baseline with session.trade_window start changed 09:45 -> 09:30
       c. baseline with exits.stop.ref changed "poc" -> "point_of_control"
       d. baseline with exits.stop.ref set to a value that is not in the contract enum
          at all, e.g. "nonsense_value"
       e. baseline with exits.stop.ticks sign flipped, +2 -> -2
     State plainly which variations changed the numbers and which did not. Use a short
     date window if a full 2008-2026 run is too slow, and say which window you used —
     the comparison matters, not the absolute figures.

  3. Contract enforcement. contract/strategy-config.v1.json enumerates exits.stop.ref as
     exactly ["poc", "va", "orb"], so "point_of_control" is out of contract. Determine
     whether ANY code path validates an incoming config against that schema — the live
     engine accepted "point_of_control" and ran. Report where validation happens, or state
     that it does not happen. Check both the repo contract and the drift-gated shipped copy
     under api/_shipped/, and say whether they agree.

  4. The stop-offset sign. api/wit/mapper.py passes exits.stop.ticks through to the runner
     unvalidated, so an LLM decides whether the stop sits above or below the reference.
     Report: how the runner uses the sign; whether a negative and a positive value are both
     meaningful or one is nonsense; whether the sign is or should be derivable from trade
     direction; and which existing tests or goldens would change if the mapper derived it.
     Recommend, do not implement.

  5. Blast radius. List every fixture, golden and test that depends on any key you found
     IGNORED. State explicitly whether enforcing the contract enum, or honouring
     trade_window, would move any golden — and if so which.

  6. Write the findings to docs/wit/log/WIT-P5i-report.md. Then stage EXACTLY these paths
     and nothing else:
       docs/wit/prompts/WIT-P5a.md
       docs/wit/prompts/WIT-P5b-sql.md
       docs/wit/prompts/WIT-P5c.md
       docs/wit/prompts/WIT-P5d-sql.md
       docs/wit/prompts/WIT-P5e.md
       docs/wit/prompts/WIT-P5f.md
       docs/wit/prompts/WIT-P5g.md
       docs/wit/prompts/WIT-P5h.md
       docs/wit/prompts/WIT-P5i.md
       docs/wit/log/WIT-P5i-report.md
     Save this prompt verbatim to docs/wit/prompts/WIT-P5i.md first. WIT-P5g was superseded
     by WIT-P5h and never run — archive it anyway and note that in the report.
     Verify with git diff --cached --name-status that exactly those ten paths are staged.
     Known LFS noise under data/raw/ and in backtest/requirements.txt and
     dashboard/requirements.txt must be left untouched and uncommitted.
     Commit with subject exactly:
       WIT-P5i: investigate ignored wire-config fields — read-only findings
     Then git push origin main.

  7. Run the test suite and report the counts. Baseline is 308 passed / 0 failed /
     2 skipped. It must be unchanged — this task adds no tests and alters no code.

REPORT BACK
  1. HEAD sha and subject at STEP 0, and whether they matched the expectation.
  2. The HONOURED and IGNORED key lists, with where each ignored key stops.
  3. The five local runs from step 2 as a table, and which variations moved the numbers.
  4. Whether any code validates a config against the contract, and whether the repo and
     shipped contracts agree.
  5. Your finding and recommendation on the stop-offset sign.
  6. The goldens that a fix would move, or "none".
  7. New HEAD sha, the GitHub commit URL, and the staged file list.
  8. Suite counts.
  Final line, exactly: WIT-P5i — Completed

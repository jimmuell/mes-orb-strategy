Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P4o

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — repo confirmation gate

  Run `git remote -v && pwd && git log --oneline -3`. Confirm the remote is
  jimmuell/mes-orb-strategy, the path is the local path above, and HEAD is c569bfe
  (WIT-P4m). If HEAD is anything else, STOP and report what you found. Read nothing,
  edit nothing, run nothing and commit nothing before this passes.

TASK

  Bound the result payload. The first complete production audit computed correctly and
  then could not be stored: the front office's write of result_json failed at the edge
  with Cloudflare 520, then 522 — the request never reached Postgres. Not RLS, not
  grants, not a database error. The payload is simply enormous.

  Cause: `_backtest_result` in api/server.py copies `kpis["equity_curve"]` verbatim, and
  the engine appends ONE ENTRY PER BAR (api/engine/engine.py — `equity_curve.append({"date":
  bar_date, "equity": equity})` inside the bar loop). At 5-minute resolution over the
  full available window that is on the order of a million entries — tens of megabytes of
  JSON in a single row write. A report has never needed per-bar equity.

  1. Emit a DAILY equity curve in the result payload

    In `_backtest_result` only, reduce the curve to one point per calendar date, taking
    the LAST equity recorded for that date and preserving chronological order. The
    emitted shape stays exactly as it is today — a list of {t, equity} — so no consumer
    changes.

  2. Do not touch any KPI computation

    max_drawdown, and anything else derived from the full per-bar series inside the
    engine, must continue to be computed from the FULL series. This slice changes only
    what leaves the engine in the result payload. If any KPI value moves, you have
    changed the wrong thing: STOP and report.

  3. A hard bound, not just a reduction

    After the daily reduction, if the series still exceeds 5,000 points, downsample
    evenly to at most 5,000, always keeping the first and last points. Record the
    reduction honestly in the payload — add `equity_curve_resolution` alongside it, set
    to "daily" or "daily_downsampled", so a reader knows what they are looking at and no
    consumer has to guess.

  4. Measure it

    For the WIT-0001 anchor configuration, report the serialized JSON size of the whole
    result payload BEFORE and AFTER this change, and the point count before and after.
    That number is the acceptance evidence.

  5. Tests and goldens

    Cover: a multi-day per-bar curve reduces to one point per date with the last value
    kept; order is preserved; a series over the cap is downsampled to exactly the cap
    with first and last retained and marked "daily_downsampled"; KPIs are untouched by
    the reduction.

    Run the full suite. Both anchor goldens must be BYTE-IDENTICAL. If ANY golden moves,
    STOP and report; do not tune a golden, touch a fixture, or alter a threshold.

  Report but do NOT fix: whether the event-study result payload has the same unbounded
  shape anywhere, and any other field in either result payload that scales with the
  number of bars rather than with the number of trades or days.

  Stage explicit paths only; never `git add -A`. Commit subject:
  `WIT-P4o: result payload carries a daily, bounded equity curve — per-bar series never leaves the engine`
  Push to origin main and report the commit hash and URL.

REPORT BACK

  Include: the reduction as written; the before/after payload size and point count for
  the WIT-0001 anchor; proof that KPIs are unchanged; the cap behaviour and the
  resolution marker; each new test; full suite counts before and after; confirmation both
  anchor goldens are unchanged; your finding on the event-study payload and any other
  bar-scaled field; the commit hash and GitHub URL. Commit the report verbatim to
  docs/wit/log/WIT-P4o-report.md in the same commit. End with exactly one line:

  WIT-P4o — Completed

  or

  WIT-P4o — Partial: <what's left>

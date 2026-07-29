Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P4m

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — repo confirmation gate

  Run `git remote -v && pwd && git log --oneline -3`. Confirm the remote is
  jimmuell/mes-orb-strategy, the path is the local path above, and HEAD is 12049b1
  (WIT-P4l). If HEAD is anything else, STOP and report what you found. Read nothing,
  edit nothing, run nothing and commit nothing before this passes.

  Then read docs/wit/log/WIT-P3s-report.md — the deploy-layout lesson this slice extends.

  DATA GATE, before any other work: run
  `wc -c data/raw/ES_full_1min_continuous_UNadjusted.txt` and read the first two lines.
  That path is a Git LFS pointer in the index (134 bytes). If what is on disk is a
  POINTER rather than real bars, run `git lfs pull` for that path; if git-lfs is
  unavailable or the pull fails, STOP and report — do NOT attempt to synthesise,
  approximate or partially reconstruct the data.

TASK

  Make the 1-minute data available in production. Sixth live end-to-end failure,
  2026-07-29: the backtest reached the profile step and died with
  `FileNotFoundError: '/data/raw/ES_full_1min_continuous_UNadjusted.txt'` inside
  load_1min_opening.

  Two causes compound:

    a. RAW_1MIN is built from the REPO root (`os.path.join(_REPO, "data", "raw", ...)`),
       and Railway deploys with root directory `/api`, so _REPO resolves to `/` and the
       path becomes `/data/raw/...`. This is the exact failure class WIT-P3s fixed for
       schema/ and contract/ — never extended to the data files.
    b. Even with a correct path the file would not be there: `data/raw/` sits OUTSIDE
       `api/`, so it is not in the image at all, and it is an LFS-stored text file.

  Only `api/data/ES_full_5min_continuous_UNadjusted.parquet` (19.9 MB) ships today. The
  consequence is broader than the crash: Class A volume-profile backtests AND Class B
  event studies both read 1-minute data, so NEITHER compute path has ever been able to
  run in production. Extraction was the only part the seam test exercised.

  LEAD DECISION, apply as stated: ship the 1-minute data rather than degrade the method
  to 5-minute profiles. A hosted audit must not be methodologically weaker than the
  published WIT-0001 it sits beside.

  1. Build a derived, deployable 1-minute file

    Add a reproducible builder script (under api/tools/ or the existing scripts location
    — say which you chose) that reads the raw 1-minute text and writes
    `api/data/ES_full_1min_rth.parquet`: regular-trading-hours bars only, same columns,
    same dtypes and the same timestamp semantics the current loaders produce. RTH-only,
    not the full 24-hour session — that is what both consumers use and it keeps the file
    proportionate to the 5-minute one already shipped.

    Commit the parquet as a REGULAR blob, not LFS: .gitattributes routes *.txt and *.csv
    to LFS but not *.parquet, and the existing 5-minute parquet is a plain blob. Keep it
    that way. Report the resulting file size.

    The raw text remains the source of truth for regeneration; the parquet is derived.
    The builder must be re-runnable and deterministic.

  2. Resolve the path the P3s way, and consume the parquet

    Point load_1min_opening and the event-study 1-minute loader at the new file, resolved
    through the same robust mechanism P3s established (env override → repo walk-up →
    shipped copy) rather than a repo-root join. After this slice NO data path may be
    built from _REPO. Grep for other _REPO-rooted paths and report every one you find.

  3. Identical results — this is the acceptance test, not a nicety

    The derived parquet must produce results IDENTICAL to the raw-text path. Prove it:
    for the WIT-0001 anchor configuration, run the profile/backtest path against the raw
    text and against the parquet and assert equality of the resulting KPIs — not
    approximate, equal. If they differ in any digit, STOP and report the difference
    rather than accepting the new file.

    Add a shipped-data test in the spirit of the P3s drift gate: the parquet exists, its
    date range and row count are consistent with the 5-minute parquet's coverage, and its
    index is a DatetimeIndex.

  4. Full suite

    Run it. Both anchor goldens must be BYTE-IDENTICAL. If ANY golden moves, STOP and
    report; do not tune a golden, touch a fixture, or alter a threshold.

  Report but do NOT fix: whether the Railway image size or build time changes materially,
  and anything about the deploy that a future slice should know.

  Stage explicit paths only; never `git add -A`. Commit subject:
  `WIT-P4m: ship RTH 1-minute data into the image; no data path is repo-root-relative`
  Push to origin main and report the commit hash and URL.

REPORT BACK

  Include: the data-gate result (real bars vs pointer, and how resolved); where the
  builder lives and how to re-run it; the parquet's size, row count and date range; the
  new resolution path and every remaining _REPO-rooted path you found; the raw-vs-parquet
  equality proof with the KPIs compared; each new test; full suite counts before and
  after; confirmation that both anchor goldens are unchanged; the commit hash and GitHub
  URL; and your note on image size or build time. Commit the report verbatim to
  docs/wit/log/WIT-P4m-report.md in the same commit. End with exactly one line:

  WIT-P4m — Completed

  or

  WIT-P4m — Partial: <what's left>

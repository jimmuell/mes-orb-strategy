# WIT Prompt Log

Archive of every WIT prompt's **report-back** — the recon findings, design writeups, run anomalies, and merge confirmations that would otherwise live only in terminal scroll. One file per prompt.

**Why:** the finished reports live in `../reports/`; this log preserves the *process* — calibration findings, design decisions, surprises — for learning and future reference (including as raw material for explaining "how the lab works" in the WIT app).

**Standing rule (adopted 2026-07-26):** every WIT prompt's REPORT BACK section includes:
"Also write this report-back verbatim to `docs/wit/log/<Prompt>-report.md` and stage it with the task's commit." Terminal output continues as normal.

**Convention:** for prompts whose deliverable is a full committed report (e.g. P1b, P2b), the log file contains the report-back's *unique* sections (tests, anomalies, headline summary) plus a pointer to the report file — not a duplicate of the report.

| File | Prompt | Content |
|---|---|---|
| WIT-P1a-report.md | Recon (VP-ORB slice) | Dataset/engine recon + implementation plan (full) |
| WIT-P1b-report.md | Build+run (WIT-0001) | Tests/anomalies + headline; report → ../reports/WIT-0001 |
| WIT-P1c-report.md | Merge Phase 1 | Merge confirmation |
| WIT-P2a-report.md | Design (event study) | Alignment/event-count recon + full design writeup |
| WIT-P2b-report.md | Build+run (WIT-0002) | Tests/anomalies + headline; report → ../reports/WIT-0002 |

Backfilled from the working session of 2026-07-26 (lead-engineer chat archive); files from WIT-P2d onward are written by Claude Code at task time.

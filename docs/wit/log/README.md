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
| WIT-P2d-report.md | Session close (Phase 2) | Prompt-log backfill commit report |
| WIT-P2e-report.md | Session close (Phase 2) | Handoff + planning-files commit report |
| WIT-P3a-report.md | Recon (Phase 3) | Server/deploy/extraction recon + slice plan |
| WIT-P3b-report.md | Build (schema+scorer) | Template schema + completeness scorer + golden fixtures |
| WIT-P3b-fix-report.md | Fix (scorer gating) | §5 defaults entry-gated — no-trigger ⇒ never Class A |
| WIT-P3c-report.md | Design (mapper) | Param-channel design + mode vocabulary + golden plan |
| WIT-P3c-1-report.md | Build (param channel) | Schema delta + fixture params + modes.md + wire-contract fix |
| WIT-P3c-2-report.md | Build (Class A mapper) | template→StrategyConfig→VPORBConfig; G1 exact equality |
| WIT-P3c-3-report.md | Build (Class B mapper) | template→EventStudyConfig; G2 exact equality |
| WIT-P3d-report.md | Build (/wit/v1 router) | submit/status/signed callback/idempotency; §3.6 gaps |
| WIT-P3g-report.md | Hardening | constant-time auth + exec kill switch + backtest/ retirement plan |
| WIT-P3h-report.md | Merge Phase 3 | Checkpoint merge to main (181 green, CI success) |
| WIT-P3i-report.md | Session close (Phase 3) | Handoff rewrite + prompt-log index |
| WIT-P3e-1-report.md | Build (extraction prompt) | Mode vocab generated from modes.md († excluded), pure/no-dep |
| WIT-P3e-2-report.md | Build (extraction core) | anthropic dev-only provider + retry orchestrator + gated golden |
| WIT-P3f-report.md | Build (sweep runner) | Engine-owned grids, sweep flag, shared wall budget |
| WIT-P3j-report.md | Merge Phase 3 ckpt 2 | Checkpoint merge to main (206 green, CI success) |
| WIT-P3k-report.md | Session close (Phase 3) | Handoff rewrite + prompt-log index |
| WIT-P3l-report.md | Docs alignment | Doc-to-code pass: field count 25→27, WIT-03 aligned to shipped sweep/extraction |
| WIT-P3e-4-report.md | Build (grounding + status) | Grounding retry loop + status-discipline prompt; first live grading + 27-row diagnostic |
| WIT-P3m-report.md | Process hardening | Handoff refresh + prompt archive convention + continuity rules |
| WIT-P3m-a-report.md | Handoff addendum | /wit/v1/extract engine-owned decision; Lovable app stage started |
| WIT-P3n-report.md | Session close (Phase 3) | Notion tracker read-on-open/update-on-close added to continuity rules |
| WIT-P3o-adjudication.md | Adjudication (anchors) | Field-by-field ratification of both fixtures; two-part `implied` test; claims→coverage |
| WIT-P3o-report.md | Docs (adjudication) | Anchor adjudication commit: prose ratios aligned (18/27, 9/27), claims rubric to coverage |
| WIT-P3e-5-report.md | Build (basis discipline) | Per-required-field evidence gate + deterministic demotion + claims grounding; live: T-0001 pass, T-0002 class B, F1 status miss |
| WIT-P3e-6-report.md | Build (determinism + coherence) | temperature-0 UNAVAILABLE on opus-4-8 (deprecated); coherence downgrade + B-fact clarifier; live x2 both fail (D2/claims-testable variance) |
| WIT-P3e-7-report.md | Build (k=3 ensemble) | Per-field majority vote + conservative ties + medoid merge; live x2 both fail — model-vs-adjudication on D2/F1 basis (narrated_example) + claims-testable |
| WIT-P3e-8-report.md | Build (prompt-spec alignment) | narrated-vs-generalized fixed + quote-selection + testable defined; F1 fixed, D2 + claims-testable still miss → pre-committed endgame (P3q re-adjudication) |
| WIT-P3q-adjudication.md | Final ruling (3 disputes) | Three disputed entries RE-RATIFIED; fixtures FINAL; known-residuals register R1-R3; v1 acceptance rationale |
| WIT-P3q-report.md | Final ruling (commit) | Docs-only: fixtures FINAL, residuals register, extraction v1 accepted for curated launch |
| WIT-P3r-report.md | Build (extract endpoint) | POST /wit/v1/extract (engine-owned k=3 ensemble); anthropic → shipped runtime lock, ADR-050 gate green |
| WIT-P3s-report.md | Fix (deploy layout) | Runtime config shipped under api/_shipped (drift-gated); data-root resolution env→repo→shipped — fixes the /api-rooted Railway healthcheck death |
| WIT-P3t-report.md | Session close (session 4) | Handoff rewrite: engine live+keyed on Railway, extraction CLOSED for v1 (R1–R3), Phase 4 front office queued |

Backfilled from the working session of 2026-07-26 (lead-engineer chat archive); files from WIT-P2d onward are written by Claude Code at task time.

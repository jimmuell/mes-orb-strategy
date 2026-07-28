# WIT prompt archive

Every Claude Code prompt the lead engineer authors is saved here as
`WIT-<id>.md` (verbatim, the same single plaintext code box that is pasted into Claude Code)
**before or at the time it is run**.

Why this exists: the report in `../log/` proves a prompt *ran*. Nothing proved a prompt was
*authored and pending* — so an authored-but-not-yet-run prompt lived only in a chat window and
was invisible to the repo. On 2026-07-28 that gap caused a second lead session, reading only the
repo, to re-issue a task Jim had already completed. The archive closes it: `prompts/` = intended,
`log/` = happened. A prompt in `prompts/` with no matching `log/` report is a PENDING slice.

Rules:
- Filename matches the prompt id exactly (`WIT-P3e-4.md`, `WIT-P3m.md`).
- Verbatim. If a prompt is reissued with a changed gate, append a dated note at the bottom rather
  than silently editing history.
- NEVER paste a secret into a prompt file. Keys are passed via the environment only.

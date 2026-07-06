# Prompt Standard (engine — pointer)

The canonical prompt standard lives in **jimmuell/tradinggym → docs/PROMPT_STANDARD.md**.
This file is a local reminder for engine (Claude Code) prompts; if it disagrees with the
canonical doc, the canonical doc wins.

Engine essentials:
- Header block: Platform / Project / Repo / **Prompt:** <name> / Local path.
- STEP 0 repo-confirmation gate is always first (git remote -v, pwd).
- Stage explicit paths only — never `git add -A`.
- Commit subject leads with the ADR: `ADR-0NN: <short imperative summary>`.
- One task per prompt.
- **Completion marker:** end every report-back with `<Prompt name> — Completed`
  (or `<Prompt name> — Partial: <what's left>` — never a bare "Completed").

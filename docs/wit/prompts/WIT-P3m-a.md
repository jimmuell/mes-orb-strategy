Platform:    Claude Code (paste this code into this platform)
Project:     WillItTrade (WIT) — engine repo
Repo:        jimmuell/mes-orb-strategy
Prompt:      WIT-P3m-a — handoff addendum: extraction-endpoint decision + app stage started
Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — gate
  git checkout main && git pull --ff-only origin main
  git log --oneline -1 → must be the WIT-P3m process-hardening commit. If P3m has not landed,
  STOP and report — run P3m first.

TASK — docs only; three small edits to docs/wit/SESSION-HANDOFF.md, then commit.
  1) In the "RESUME HERE" section, REPLACE the sentence beginning "After that: the phase-end
     Lovable app stage" with exactly this paragraph:

  After that: the app stage, ALREADY STARTED (2026-07-28). LEAD-ENGINEER ARCHITECTURE DECISION,
  superseding WIT-03 §4's original placement of the LLM call inside the Supabase `wit-extract`
  edge function: the ENGINE exposes `POST /wit/v1/extract` and Supabase merely calls it. Rationale
  — porting the extraction layer (prompt builder, runtime mode-vocabulary parsing from
  contract/modes.md, forced tool call, retry loop, grounding check) to TypeScript would create two
  implementations of the product's core trick that must stay in lockstep, and the vocabulary is
  generated at runtime from a file that lives in THIS repo. P3a already flagged engine-owned
  extraction as preferred; now that the layer is built and graded, it is decided. Pending slice:
  `POST /wit/v1/extract` (auth + budget like the other /wit/v1 routes; returns
  {template, completeness, raw_meta}; anthropic must move from requirements-dev.txt to the SHIPPED
  runtime lock in that slice and pass the ADR-050 audit gate — the one real cost of this decision).
  Also open in Jim's lane: confirm the engine is actually deployed on Railway and set
  WIT_ENGINE_SERVICE_KEY, WIT_CALLBACK_HMAC_SECRET, DISABLE_EXEC_ENDPOINTS=1 (P3a could not verify
  live deploy state from the repo).

  2) In "Where things live", append this sentence: "Front end: Lovable project `Audit Lab` (rename
     pending) — id 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9, editor
     https://lovable.dev/projects/6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9 — front-end-only v1 (no
     auth/DB/payments), all figures from a typed fixtures module mirroring the eventual API shape;
     seeded with the REAL published WIT-0001 numbers. Supabase not yet created."

  3) Under "Open items", add: "* NEW — `POST /wit/v1/extract` slice pending (see RESUME HERE);
     moving anthropic into the shipped runtime lock is part of it."

  Commit:
    git add docs/wit/SESSION-HANDOFF.md docs/wit/log/WIT-P3m-a-report.md docs/wit/prompts/WIT-P3m-a.md
    git commit -m "WIT-P3m-a: handoff addendum — /wit/v1/extract decision, app stage started"
    git push origin main

REPORT BACK: 1. gate result. 2. all three edits applied (y/n). 3. commit hash; CI status.
  4. anything unexpected. Write it verbatim to docs/wit/log/WIT-P3m-a-report.md and archive this
  prompt verbatim to docs/wit/prompts/WIT-P3m-a.md, both staged in the same commit.
  Final line, exactly: WIT-P3m-a — Completed

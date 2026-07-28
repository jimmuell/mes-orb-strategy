Platform:    Claude Code (paste this code into this platform)
Project:     WillItTrade (WIT) — engine repo
Repo:        jimmuell/mes-orb-strategy
Prompt:      WIT-P3e-4 — extraction fixes: grounding check in the retry loop + status-discipline prompt hardening; graded golden re-run
Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — gate
  git remote -v && pwd — confirm repo/path as above; if not, STOP.
  git checkout main && git pull --ff-only origin main
  git log --oneline -1 → must be 274fa8b (WIT-P3l docs pass). If not, STOP and report.
  Key check (your fresh shells now carry the NEW key from ~/.zshrc):
    python3 -c "import os;k=os.environ.get('ANTHROPIC_API_KEY','');print('set:',bool(k),'len:',len(k))"
  → must be set:True len:~108. Then verify it's LIVE-valid with one minimal call (cheapest model,
  max_tokens=1; never print the key): a tiny python snippet calling anthropic Messages once.
  401 → STOP and report (do not proceed to the build on a dead key).
  Lead decision on branching: this single reviewed slice commits DIRECTLY to main (no branch) —
  the full local suite gates the commit and CI gates the push.

CONTEXT — the graded baseline (run live in Jim's terminal, 2026-07-27; record in the report):
  T-0001 (expect A): class A correct, required statuses correct, required_missing correct;
    FAILED only grounding — D2 quote lightly paraphrased, not a verbatim transcript substring.
  T-0002 (expect B): FAILED class — extractor produced Class A (over-credited required fields
    on a vague video = charitable completion). This is the product-critical failure mode.
  Also confirmed: DEFAULT_MODEL claude-opus-4-8 is valid on the public API; both transcripts
  ~100s total, negligible cost.

TASK
  1) Grounding enforcement in the orchestrator (api/wit/extraction/extract.py):
     - Add grounding_errors(template, transcript) -> list[str]: for every non-J field with status
       specified/implied, source_quote must be non-empty AND, after normalization (collapse all
       whitespace runs to single spaces + lowercase — EXACTLY the golden test's _norm), be a
       substring of the normalized transcript. Error strings must name the field and instruct the
       fix, e.g.: "fields.D2.source_quote is not a verbatim substring of the transcript — copy the
       quote character-for-character from the transcript, including caption typos; do not fix
       spelling, punctuation, or numbers; a shorter exact span is fine."
     - In extract_template's loop: after validate_template passes, run grounding_errors; if any,
       treat them exactly like validation errors (feed back, retry ≤ max_retries; terminal
       extraction_failed carries them). Success now means schema-valid AND fully grounded.
  2) Prompt hardening (api/wit/extraction/prompt.py) — add to the rules block, as testable text:
     - QUOTE DISCIPLINE: "source_quote must be copied CHARACTER-FOR-CHARACTER from the transcript,
       including caption errors and typos. Never paraphrase, never fix spelling, punctuation, or
       numbers (if the captions say '945', write '945', not '9:45'). If you cannot locate an exact
       sentence, quote a shorter exact span."
     - STATUS DISCIPLINE (the Class-B guard): "A description of what price TENDS to do — a claim,
       tendency, or illustration — is NOT a rule. An entry trigger (D3) must be a stated executable
       instruction (when exactly to enter); exits (F1/F2/F4) must be stated exit rules. Do not
       upgrade motivational or illustrative language to 'implied'. 'implied' requires a direct,
       specific inference the quote forces — not a charitable reconstruction. WHEN IN DOUBT BETWEEN
       'implied' AND 'unspecified', CHOOSE 'unspecified' — the honest gap IS the product."
  3) Deterministic tests (no network; extend test_extraction_orchestrator.py + test_extraction_prompt.py):
     - Orchestrator: (a) provider returns a template whose quote is a paraphrase of the fake
       transcript → retry fires and the retry user-turn contains the grounding error text naming
       the field; (b) paraphrase-then-exact sequence → status ok, retries surfaced; (c) always-
       paraphrased → extraction_failed with grounding errors; (d) whitespace/case-only quote
       differences do NOT error (normalization tolerance); (e) J fields never grounding-checked.
     - Prompt: the new rule phrases present ("CHARACTER-FOR-CHARACTER", "CHOOSE 'unspecified'",
       "is NOT a rule"); all P3e-1/2 prompt tests stay green.
  4) Full CI-safe suite:  cd api && BACKTEST_API_KEY=k python -m pytest -q
     Must be 206 prior + your new tests, 0 failed, 2 skipped. Red → STOP, no commit.
  5) LIVE golden re-run (the graded before/after):
     cd api && WIT_RUN_LLM_TESTS=1 BACKTEST_API_KEY=k python -m pytest tests/test_extraction_golden.py -v
     - If BOTH pass: record per-transcript class, required_missing, retries used, and note any
       grounding retries that fired (visible via raw_meta retries).
     - If T-0002 still classifies A (or any content assert fails): DO NOT tune fixtures, the
       scorer, thresholds, or the test. Instead run a one-off diagnostic script (not committed, or
       committed under scripts/ only if trivially reusable): extract T-0002 once, print a 27-row
       table of field id | extracted status | fixture status | the extracted source_quote for every
       required field it over-credited. Put that table verbatim in the report and STOP after
       committing code+report (the fixes are still valuable; the residual gap is the finding).
  6) Also append one line to docs/wit/log/WIT-P3e-3-report.md: "Addendum: live baseline completed
     manually in Jim's terminal 2026-07-27 (D2 grounding fail on T-0001; class A-vs-B fail on
     T-0002); graded results + fixes in WIT-P3e-4."

  Commit (explicit paths only — never git add -A):
    git add api/wit/extraction/extract.py api/wit/extraction/prompt.py \
            api/tests/test_extraction_orchestrator.py api/tests/test_extraction_prompt.py \
            docs/wit/log/WIT-P3e-3-report.md docs/wit/log/WIT-P3e-4-report.md
    (plus scripts/<diagnostic>.py ONLY if you made it reusable)
    git commit -m "WIT-P3e-4: extraction grounding retry loop + status-discipline prompt hardening"
    git push origin main
    Confirm CI goes green (gh run list/watch) or report "not checkable".

REPORT BACK (exactly this):
  1. STEP 0 (HEAD 274fa8b y/n; key set AND live-valid y/n — never the key).
  2. Grounding loop wired into extract_template (y/n); normalization identical to the golden _norm (y/n).
  3. Prompt hardening added; new test count; CI-safe suite result (206 prior + N new / 0 failed / 2 skipped).
  4. LIVE re-run: T-0001 pass/fail + details; T-0002 pass/fail + details (class, required_missing,
     retries, grounding retries). If T-0002 still misclassifies: the 27-row diagnostic table verbatim.
  5. Commit hash on main; CI status.
  6. Anything unexpected.
  Write this report-back verbatim to docs/wit/log/WIT-P3e-4-report.md, staged in the same commit.
  Final line, exactly: WIT-P3e-4 — Completed
  (or WIT-P3e-4 — Partial: <what's left> — never a bare "Completed".)

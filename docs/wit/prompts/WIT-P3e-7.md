Platform   : Claude Code (VS Code, MacBook Air)
Project    : WillItTrade (WIT)
Repo       : github.com/jimmuell/mes-orb-strategy   (branch: main)
Prompt     : WIT-P3e-7
Local path : ~/Projects/mes-orb-strategy

STEP 0 — GATE (any failure => STOP and report; do not proceed)
  1. git checkout main && git pull --ff-only
  2. git log --oneline -1 must show 7d9be1d (WIT-P3e-6). Any other HEAD => STOP, report it.
  3. git status --porcelain clean (known untracked pine/mes_net_pnl_v2.pine is fine).
     Confirm origin URL and local path match the header.
  4. ANTHROPIC_API_KEY set AND live (set:<bool> len:<n>; one claude-haiku-4-5 max_tokens=1
     call, no 401; never print the key). Live runs close this slice (~12 extractions total).
  5. HARD LIMITS unchanged: api/tests/fixtures/*.json byte-identical; completeness.py and
     scorer constants untouched; golden ASSERTS/THRESHOLDS untouched (T3 changes only WHICH
     function the golden calls — a lead-authorized surface change, stated in the report).

CONTEXT
  P3e-6 lead review: the deterministic layer works (demotions/downgrades correct in every
  run; B2 and F1 fixed) but the model gives different readings run-to-run on borderline
  fields (D2; one claims-testable flag), and temperature=0 is rejected by claude-opus-4-8 —
  the determinism lever does not exist on the deployed model. LEAD DECISION: k=3 ensemble —
  extract three times independently, majority-vote per field, deterministic merge. This
  becomes the product's extraction path (the future /wit/v1/extract endpoint will call it).

TASK
T1. New module api/wit/extraction/ensemble.py — extract_template_ensemble(transcript,
    source_meta, k=3), pure orchestration over the existing extract_template:
  a) Run extract_template k times (sequentially is fine). Runs that end extraction_failed
     are dropped; if fewer than 2 runs succeed, return extraction_failed carrying every
     run's errors. Each successful run has already passed schema, grounding, claims
     grounding, demotion, and downgrade — the ensemble merges FINISHED templates only.
  b) Per-field vote over the ok runs, all 27 fields: winning status = majority of the runs'
     statuses. On a tie (including 1/1/1), winning status = the LEAST-CREDITING status
     among those tied (crediting order: specified > implied > unspecified — so prefer
     unspecified over implied over specified). The honest gap wins ties, by design.
  c) Medoid run = the ok run whose 27 field statuses agree with the voted statuses in the
     most places; tie => lowest run index. It supplies: source block, template_version,
     consistency_flags, interpretations.
  d) Winning field OBJECT (value/quote/basis/etc.): taken from the medoid if its status
     matches the vote, else from the lowest-index run whose status matches. (The tie-break
     in (b) always picks a status some run actually produced, so a donor always exists.)
  e) Claims: group claims across ok runs by normalized-quote fragment overlap (same _norm +
     ellipsis-fragment matching semantics as the golden's coverage check — factor the
     matcher into a helper rather than duplicating logic drift). Keep every group
     (exhaustiveness — every member is already grounded). Representative = medoid's member
     where present, else lowest-index member. testable = majority across the group's
     members; tie => the representative's own flag.
  f) The merged template is re-checked before scoring: validate_template must pass and
     field grounding_errors + claims grounding must be empty (they should be by
     construction — a violation here is a bug, raise/fail loudly, never silently score).
     Then the deterministic scorer assigns class exactly as in extract_template.
  g) Return shape mirrors extract_template plus ensemble_meta: {k, ok_runs, medoid_index,
     unanimous_fields, majority_fields, tie_fields, per_run: [{retries, demotions,
     downgrades}]}.
T2. Unit tests (CI-safe, fake provider making deterministic per-call outputs) — at least:
    (1) 2-1 status vote resolves to majority; (2) 1/1/1 tie resolves to least-crediting;
    (3) specified/implied 1-1 tie (one failed run dropped) resolves to implied; (4) medoid
    selection + donor object rule; (5) claims grouping merges same-claim variants and
    majority-votes testable; (6) one run extraction_failed => ensemble still succeeds on 2;
    (7) two runs failed => extraction_failed with all errors; (8) merged template
    re-validates + scores (class comes from scorer). Plus any plumbing existing tests need.
T3. Golden test: switch the extraction call from extract_template to
    extract_template_ensemble(k=3). NOTHING else changes — every assert and threshold
    stays byte-identical. State plainly in the report that this is the only golden change.
T4. Full CI-safe suite: cd api && BACKTEST_API_KEY=k python -m pytest -q
    Expected: (223 + new) passed / 0 failed / 2 skipped. Record exact. Failure => STOP.
T5. LIVE graded run TWICE back-to-back (each run = 3 extractions per case; ~12 total):
      WIT_RUN_LLM_TESTS=1 python -m pytest tests/test_extraction_golden.py -q   (x2)
    Report per run, per case: pass/fail + failing assert if any, class, required_missing,
    ensemble_meta (unanimous/majority/tie counts, ok_runs, per-run demotions/downgrades).
    SUCCESS = both cases pass in BOTH runs. Also state whether the two runs' voted
    T-0002 required-field statuses agree with each other (stability check). If either case
    fails in both runs on the same assert: produce the 27-row diagnostic of the VOTED
    template (scratchpad outside the repo, uncommitted, table verbatim in the report) and
    STOP for lead review. DO NOT tune anything in response to outcomes.
T6. Handoff + archive + index (docs/wit/):
  a) SESSION-HANDOFF.md "main =" line -> "main = the WIT-P3e-7 commit (k=3 extraction
     ensemble — majority vote per field, conservative ties, medoid merge); prior 7d9be1d
     (P3e-6)." Arc: append " → P3e-7 ensemble vote."
  b) Replace the ENTIRE "▶ RESUME HERE — P3e-6 shipped..." block (through "...(draft in
     the Notion tracker row).") with:
      ▶ RESUME HERE — P3e-7 ensemble shipped; live golden x2: [FILL IN ACTUAL results per
      run/case + stability check]. If both cases passed both runs: EXTRACTION QUALITY IS
      DONE FOR v1 — next slice = POST /wit/v1/extract (decided at P3m-a; the endpoint
      calls extract_template_ensemble(k=3), NOT single-shot extract_template; auth +
      budget like other /wit/v1 routes; returns {template, completeness, raw_meta incl.
      ensemble_meta}; anthropic moves from requirements-dev.txt to the SHIPPED runtime
      lock and must pass the ADR-050 audit gate; note the per-call cost is 3 extractions).
      If still failing: STOP — lead review in Cowork chat with the voted-template
      diagnostic; do not improvise further mechanisms. Jim's lane unchanged: Railway
      deploy confirm + WIT_ENGINE_SERVICE_KEY, WIT_CALLBACK_HMAC_SECRET,
      DISABLE_EXEC_ENDPOINTS=1; FirstRateData confirmation email (draft in the Notion
      tracker row).
  c) Archive this prompt verbatim to docs/wit/prompts/WIT-P3e-7.md; add the
     WIT-P3e-7-report.md row to docs/wit/log/README.md.
T7. Single commit DIRECTLY to main (T4 gates; live outcome does not gate the commit),
    subject:
      WIT-P3e-7: k=3 extraction ensemble — per-field majority vote, conservative ties, medoid merge
    Explicit paths only. Push; record CI.

REPORT BACK — write verbatim to docs/wit/log/WIT-P3e-7-report.md, staged with the commit:
  1. STEP 0 results. 2. Ensemble design as implemented (vote, ties, medoid, claims
  grouping) + confirmation the golden's only change is the call target. 3. New tests +
  suite counts. 4. LIVE x2 results per T5 (+ voted-template diagnostic if produced).
  5. Commit hash; CI. 6. Anything unexpected.
Final line, exactly one of:
WIT-P3e-7 — Completed
WIT-P3e-7 — Partial: <one-line reason>

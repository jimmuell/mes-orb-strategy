Platform   : Claude Code (VS Code, MacBook Air)
Project    : WillItTrade (WIT)
Repo       : github.com/jimmuell/mes-orb-strategy   (branch: main)
Prompt     : WIT-P3e-5
Local path : ~/Projects/mes-orb-strategy

STEP 0 — GATE (any failure => STOP and report; do not proceed)
  1. git checkout main && git pull --ff-only
  2. git log --oneline -1 must show 059e297 (WIT-P3o: anchor adjudication). Any other
     HEAD => STOP, report actual HEAD.
  3. git status --porcelain clean (known untracked pine/mes_net_pnl_v2.pine is fine).
     Confirm origin URL and local path match the header.
  4. ANTHROPIC_API_KEY set AND live: report set:<bool> len:<n> (never print the key), then
     one minimal claude-haiku-4-5 max_tokens=1 Messages call must succeed (no 401). This
     slice ENDS with a live graded run, so a dead key means STOP now, not at the end.
  5. HARD LIMITS: api/tests/fixtures/*.json stay byte-identical (ratified at P3o — never
     tuned, no keys added). completeness.py, the scorer's constants, and the golden test's
     asserts/thresholds are untouched. STOP-and-report beats forcing any pass.

CONTEXT
  P3o ratified the calibration anchors: the T-0002 A-vs-B miss is MODEL behavior — status
  over-crediting of narrated examples on required fields (B1, D1, D3, D4), all grounded, so
  grounding cannot catch it. The adjudicated two-part test (docs/wit/log/
  WIT-P3o-adjudication.md §2) is the spec: `implied` on a required field needs BOTH
  (i) generalization beyond a single worked example AND (ii) a referent executable within
  the template's own structure; `specified` additionally requires executability AS STATED.
  This slice makes the model DECLARE its evidence per required field and lets the engine
  deterministically demote what the declaration disqualifies. Also: claims[] quotes gain
  the same runtime grounding fields already have (P3o flagged the gap).

TASK
T1. Prompt rule (api/wit/extraction/prompt.py) — append rule 9 to _RULES, additive only
    (rules 1-8 and all currently pinned phrases unchanged):
      9. BASIS DISCIPLINE: for every REQUIRED field (B1, B2, D1, D2, D3, D4, F1, F2, F4)
      whose status is "specified" or "implied", set "basis" to exactly one of:
        "stated_rule"          — stated as an instruction/definition, executable as stated;
        "generalized_practice" — stated once (e.g. inside a worked example) BUT generalized
                                 beyond it (habitual framing or an explicit general
                                 justification) AND its referent is executable within this
                                 template's own structure;
        "narrated_example"     — narration of one specific trade/chart, however habitual it
                                 sounds, or a referent that exists only inside that exhibit;
        "tendency_or_claim"    — what price tends to do, or a performance claim.
      A basis of "narrated_example" or "tendency_or_claim" does NOT support "specified" or
      "implied" — set status "unspecified" and let value describe the honest gap. The
      engine deterministically demotes contradictions; over-crediting cannot pass. Invented
      examples (from no test source): "I got in when it broke that resistance" inside a
      recap of one past trade => narrated_example => unspecified. "I always put my stop just
      below the signal candle — that level being defended is why the trade works" =>
      generalized_practice => implied, IF the signal candle is defined in this template.
    IMPORTANT: do NOT quote or paraphrase any sentence from the two archived transcripts in
    the rule — embedding anchor text would contaminate the golden. State in the report that
    you checked this.

T2. Schema + tool surface:
  a) api/wit/extraction/schema.py: field objects accept an OPTIONAL "basis" key; when
     present it must be one of the four enum values above (wrong value = validation error,
     which feeds the existing retry loop). Fixtures remain valid WITHOUT basis — basis is
     required only of MODEL output via T3, precisely so fixtures stay byte-identical.
  b) api/wit/extraction/provider.py: add the optional "basis" enum property to the field
     object schema in the forced emit_strategy_template tool.

T3. Orchestrator (api/wit/extraction/extract.py) — after schema validation and grounding,
    two new deterministic checks:
  a) MISSING BASIS: a REQUIRED field with status specified/implied and no basis is a retry
     error naming the field (same loop as grounding; terminal => extraction_failed listing
     them).
  b) DEMOTION: ANY field with status specified/implied and basis narrated_example or
     tendency_or_claim is demoted to status "unspecified" BEFORE scoring — no retry, no
     failure; deterministic enforcement. Record every demotion in the result as
     demotions: [{field, from_status, basis}] (empty list when none). The scorer then sees
     the demoted template; scorer itself untouched.
  c) CLAIMS GROUNDING: every claims[] entry must have a non-empty quote whose _norm form is
     a substring of the _norm transcript — violations are retry errors naming the claim,
     terminal => extraction_failed, exactly like field grounding.

T4. Tests (CI-safe, fake provider; no network) — new tests covering at least:
  1) satisfied required field + basis narrated_example => demoted to unspecified, demotion
     recorded, class reflects the demotion;
  2) satisfied required field missing basis => retry with named error; corrected on retry
     => ok;
  3) basis stated_rule => untouched, demotions empty;
  4) invalid basis value => validation error => retry;
  5) paraphrased claims quote => retry naming the claim; exact on retry => ok;
  6) always-paraphrased claims quote => terminal extraction_failed carrying the claim error;
  7) prompt test: rule 9 phrases present (BASIS DISCIPLINE, narrated_example,
     generalized_practice, "does NOT support") and rules 1-8 phrases still present.
    Existing orchestrator tests: where fake templates now trip the missing-basis check, add
    basis "stated_rule" to their satisfied required fields — that is test-fixture plumbing
    for the new contract, NOT golden tuning (the graded fixtures under api/tests/fixtures/
    are untouched).

T5. Full CI-safe suite: cd api && BACKTEST_API_KEY=k python -m pytest -q
    Expected: (212 + new) passed / 0 failed / 2 skipped. Record exact counts. Any failure
    => STOP.

T6. LIVE graded run (the point of the slice; ~cents):
      cd api && WIT_RUN_LLM_TESTS=1 python -m pytest tests/test_extraction_golden.py -q
    Then, win or lose, produce the 27-row diagnostic for T-0002 (one live extraction via a
    scratchpad script OUTSIDE the repo tree, like P3e-4): per field — extracted status,
    basis (if any), fixture status, demoted?(y/n), source_quote. Paste the table verbatim
    into the report. Report per-case: pass/fail, failing assert if any, retries, and the
    demotions list. DO NOT tune anything in response to the outcome — report facts.

T7. Handoff + archive + index (docs/wit/):
  a) SESSION-HANDOFF.md "Current state": main = line -> "main = the WIT-P3e-5 commit (basis
     discipline: evidence gate + deterministic demotion + claims grounding); prior 059e297
     (P3o)." Arc sentence: append " → P3e-5 basis discipline."
  b) Replace the ENTIRE "▶ RESUME HERE — adjudication DONE (P3o)..." block (through
     "...(P3a could not verify live deploy state from the repo).") with:
      ▶ RESUME HERE — P3e-5 basis discipline shipped; live golden result: [FILL IN ACTUAL:
      T-0001 pass/fail + failing assert if any; T-0002 class A/B, status match n/27,
      demotions applied]. If both cases passed: next slice = POST /wit/v1/extract (decided
      at P3m-a, superseding WIT-03 §4 — the ENGINE exposes extraction, Supabase merely
      calls it; auth + budget like the other /wit/v1 routes; returns {template,
      completeness, raw_meta}; anthropic moves from requirements-dev.txt to the SHIPPED
      runtime lock and must pass the ADR-050 audit gate). If T-0002 is still misgraded:
      STOP — next step is a lead-engineer review of the live diagnostic in Cowork chat
      before ANY further hardening; the anchors are ratified (P3o) and are not the lever.
      Jim's lane unchanged: Railway deploy confirm + WIT_ENGINE_SERVICE_KEY,
      WIT_CALLBACK_HMAC_SECRET, DISABLE_EXEC_ENDPOINTS=1; FirstRateData confirmation email
      (draft in the Notion tracker row).
  c) Archive this prompt verbatim to docs/wit/prompts/WIT-P3e-5.md.
  d) docs/wit/log/README.md: add the WIT-P3e-5-report.md row PLUS the two missing backfill
     rows for WIT-P3m-report.md and WIT-P3m-a-report.md (flagged in the P3o report).

T8. Single commit DIRECTLY to main (T5 suite is the gate; live-run outcome does NOT gate
    the commit — the code is net-positive either way, P3e-4 precedent), subject:
      WIT-P3e-5: basis discipline — per-required-field evidence gate, deterministic demotion, claims grounding
    staging all files from T1-T7 plus the report (explicit paths only — never git add -A).
    Push; record CI.

REPORT BACK — write verbatim to docs/wit/log/WIT-P3e-5-report.md, staged with the commit:
  1. STEP 0 results (HEAD, tree, key set+live).
  2. What changed per file (prompt rule added; schema/provider basis; orchestrator checks;
     confirmation that no anchor-transcript text appears in the prompt).
  3. New test list + full suite counts.
  4. LIVE results: per-case pass/fail + asserts, the T-0002 27-row diagnostic table
     verbatim, demotions applied, retry counts.
  5. Commit hash; CI status.
  6. Anything unexpected.
Final line, exactly one of:
WIT-P3e-5 — Completed
WIT-P3e-5 — Partial: <one-line reason>

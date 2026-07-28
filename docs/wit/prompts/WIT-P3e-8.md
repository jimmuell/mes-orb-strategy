Platform   : Claude Code (VS Code, MacBook Air)
Project    : WillItTrade (WIT)
Repo       : github.com/jimmuell/mes-orb-strategy   (branch: main)
Prompt     : WIT-P3e-8
Local path : ~/Projects/mes-orb-strategy

STEP 0 — GATE (any failure => STOP and report; do not proceed)
  1. git checkout main && git pull --ff-only
  2. git log --oneline -1 must show 9be0284 (WIT-P3e-7). Any other HEAD => STOP, report it.
  3. git status --porcelain clean (known untracked pine file is fine). Origin/path match.
  4. ANTHROPIC_API_KEY set AND live (set/len + one haiku max_tokens=1 call; never print it).
  5. HARD LIMITS: fixtures byte-identical; completeness.py/scorer untouched; golden asserts/
     thresholds untouched; ensemble.py logic untouched. This slice edits PROMPT TEXT ONLY
     (plus its prompt-text tests).

CONTEXT
  P3e-7 lead review: the ensemble is deterministic (tie 0/27) and the residual misses are
  STABLE model calls on D2/F1 basis and one claims-testable flag. Root cause found in OUR
  prompt: rule 9's narrated_example definition says "however habitual it sounds", which
  CONTRADICTS the P3o-ratified two-part test (generalization rescues a once-shown practice).
  The model is obeying the written contradiction. Also, "testable" was never defined for
  claims[]. This slice makes the prompt encode the ratified standard faithfully. It is the
  LAST prompt-alignment slice: the handoff pre-commits the endgame either way.

TASK
T1. prompt.py rule 9 — replace the narrated_example definition:
      old: "narrated_example" — narration of one specific trade/chart, however habitual it
           sounds, or a referent that exists only inside that exhibit
      new: "narrated_example" — narration of one specific trade/chart WITH NO generalization
           beyond it anywhere in the source, or a referent that exists only inside that
           exhibit. If the narration is accompanied by a generalized statement of the
           practice or a general justification ("I always ...", "because these ... tend to
           hold"), AND the referent is executable within this template, the basis is
           "generalized_practice" — the generalization, not the demonstration, earns the
           credit
    (Adjust wording only if the current file text differs; grep first, STOP if the old
    phrase "however habitual it sounds" is absent.)
T2. prompt.py rule 9 — two additive clarifiers:
      - "When several passages could support a field, source_quote the MOST GENERAL one
        (the stated rule or the general justification), not the worked-example narration —
        the quote should carry the field's basis."
      - "A general justification may itself be phrased as a tendency ('these tend to
        hold'); that does not make the FIELD a tendency claim — basis classifies the
        PRACTICE being credited. This applies only where a stated practice exists; a
        tendency with no accompanying practice remains tendency_or_claim."
T3. prompt.py rule 4 — append the missing definition:
      "testable=true iff the claim can be tested against historical market data (a claim
      about the strategy's or the market's behavior). testable=false for personal results
      and anecdotes, unverifiable live-performance stories, and promises about the
      viewer's future results. Whether the source's OWN evidence can be verified is
      irrelevant — what matters is whether WIT can test the claim on data."
    Rules 1-8 otherwise unchanged; all other pinned phrases intact. Anchor-contamination
    check as in P3e-5/6 on every added sentence (>=12-char normalized substrings vs both
    transcripts = 0 hits; report it).
T4. Prompt tests: update the rule-9 pin if it pinned the removed phrase; add pins for
    "generalization, not the demonstration", "MOST GENERAL", and "testable=true iff".
    Suite: cd api && BACKTEST_API_KEY=k python -m pytest -q → (233 + new) / 0 failed /
    2 skipped. Record exact. Failure => STOP.
T5. LIVE graded golden TWICE (ensemble k=3 each; ~12 extractions): report per run/case —
    pass/fail + assert, class, required_missing, ensemble_meta counts, and specifically
    D2/F1 voted status+basis and the 10-year-backtest claim's voted testable flag. If any
    case fails in both runs: produce the voted-template 27-row diagnostic (scratchpad,
    uncommitted, verbatim in report) and STOP. DO NOT tune anything in response.
T6. Handoff + archive + index:
  a) "main =" line -> "main = the WIT-P3e-8 commit (prompt aligned to the P3o standard:
     narrated-vs-generalized fixed, quote-selection rule, testable defined); prior 9be0284
     (P3e-7)." Arc: append " → P3e-8 prompt-spec alignment."
  b) Replace the ENTIRE "▶ RESUME HERE — P3e-7 ensemble shipped..." block (through
     "...(draft in the Notion tracker row).") with:
      ▶ RESUME HERE — P3e-8 shipped; live golden x2: [FILL IN ACTUAL]. If both cases
      passed both runs: EXTRACTION QUALITY DONE FOR v1 — next slice = POST /wit/v1/extract
      (calls extract_template_ensemble(k=3); auth+budget like other /wit/v1 routes;
      returns {template, completeness, raw_meta incl. ensemble_meta}; anthropic moves to
      the SHIPPED runtime lock + ADR-050 gate; per-call cost = 3 extractions). If D2/F1/
      claims-testable still miss with unchanged majority basis: PRE-COMMITTED ENDGAME —
      next slice is a formal LEAD RE-ADJUDICATION (P3q) of exactly those fixture entries
      in Cowork chat: either re-ratify with a prompt-independent argument or amend the
      fixture with a full documented record (a due-process key revision, not tuning). NO
      further prompt-hardening slices are authorized. Jim's lane unchanged: Railway
      deploy confirm + env vars; FirstRateData email (draft in the Notion tracker).
  c) Archive prompt to docs/wit/prompts/WIT-P3e-8.md; add report row to docs/wit/log/README.md.
T7. Single commit DIRECTLY to main (T4 gates), subject:
      WIT-P3e-8: prompt-spec alignment — narrated-vs-generalized per P3o, quote selection, testable defined
    Explicit paths only. Push; record CI.

REPORT BACK — docs/wit/log/WIT-P3e-8-report.md, staged with the commit:
  1. STEP 0. 2. Exact prompt-text diffs + contamination check. 3. Test changes + suite
  counts. 4. LIVE x2 per T5 (+ diagnostic if produced). 5. Commit; CI. 6. Unexpected.
Final line, exactly one of:
WIT-P3e-8 — Completed
WIT-P3e-8 — Partial: <one-line reason>

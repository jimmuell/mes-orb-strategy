# WIT-P3e-5 — basis discipline: evidence gate + deterministic demotion + claims grounding

## 1. STEP 0
- HEAD **059e297** (WIT-P3o anchor adjudication) — matches required. Repo/path/origin match the
  header. Tree clean except the known untracked `pine/mes_net_pnl_v2.pine`.
- ANTHROPIC_API_KEY **set:True len:108**; one minimal `claude-haiku-4-5` `max_tokens=1` Messages
  call returned `stop_reason=max_tokens` (no 401). Key never printed.
- HARD LIMITS honored: `api/tests/fixtures/*.json` byte-identical (verified — not staged/changed);
  `completeness.py`, scorer constants, and the golden test's asserts/thresholds untouched.

## 2. What changed per file
- **prompt.py**: appended rule 9 (BASIS DISCIPLINE) to `_RULES`, additive — rules 1–8 and all
  pinned phrases unchanged. Field-conventions trailer now lists `basis` among the optional keys.
  **Anchor-contamination check: PASS** — grepped both transcripts for every distinctive phrase in
  rule 9's INVENTED examples ("broke that resistance", "I got in when", "signal candle", "being
  defended", "put my stop just below", "is why the trade works", "always put my stop") → 0 hits
  each. No transcript text embedded.
- **schema.py**: `basis` added to `_FIELD_OPTIONAL_KEYS` (so it's an allowed key), new `_BASIS_ENUM`
  (4 values), and `_validate_field` errors when `basis` is present-and-non-null but not in the enum.
  Fixtures stay valid WITHOUT basis (verified).
- **provider.py**: `build_tool()` now DEEP-copies the loaded schema (the lru_cached canonical schema
  must not be mutated) and injects an optional `basis` enum property into the field `$def`
  (additionalProperties:false requires declaring it; kept OUT of the $def `required`). Verified: tool
  field props include `basis`; canonical schema does NOT.
- **extract.py**: added `_REQUIRED_BASIS_FIELDS` (B1,B2,D1,D2,D3,D4,F1,F2,F4), `_DEMOTING_BASES`,
  and three functions — `claims_grounding_errors` (retry gate), `missing_basis_errors` (retry gate),
  `apply_demotions` (deterministic, pre-scoring). Loop order: schema → field grounding → claims
  grounding → missing-basis → (demote) → score. Success now returns `demotions: [...]`.
- **tests**: see §3. **test_extraction_prompt.py** `test_system_prompt_offers_no_unsupported_token`
  narrowed its blanket `assert "structure" not in p` to the mode-VOCABULARY block only — rule 9
  legitimately uses the English word "structure" ("executable within this template's own structure"),
  which is unrelated to the daggered `structure` mode token the assert was protecting against. Not
  the golden test; intent preserved (a leaked mode token would still surface in the vocab block).

## 3. New tests + suite counts
New (7): orchestrator — (1) narrated_example demotes a required field + records demotion + class
reflects it; (2) missing basis → retry naming the field → ok on correction; (3) stated_rule
untouched, demotions empty; (4) invalid basis value → validation error → retry; (5) paraphrased
claim quote → retry naming the claim → exact on retry ok; (6) always-paraphrased claim → terminal
extraction_failed carrying the claim error. Prompt — (7) rule 9 phrases present AND rules 1–8 pinned
phrases still present. Existing orchestrator success-tests got CI plumbing (`_with_basis` /
`_ci_ready`: declare basis stated_rule on required fields + empty the non-grounded fixture claims) —
NOT golden tuning; the on-disk fixtures are byte-identical.

Full CI-safe suite (`cd api && BACKTEST_API_KEY=k python -m pytest -q`):
**219 passed / 0 failed / 2 skipped** (212 prior + 7 new; the 2 skips are the network-gated live tier).

## 4. LIVE graded run
`WIT_RUN_LLM_TESTS=1 python -m pytest tests/test_extraction_golden.py -q` → **1 passed, 1 failed**:
- **T-0001 (expect A): PASSED** — class A, field grounding, and the new P3o claims-COVERAGE rubric
  all green. (P3e-4→P3o→P3e-5: T-0001 is now fully green end-to-end.)
- **T-0002 (expect B): FAILED**, but far closer than P3e-4 and no longer product-critical. The graded
  run reached **class B** ✓ and **required_missing == fixture [B1,D1,D3,D4,F2|F4]** ✓ (both were the
  P3e-4 failures) — failing ONLY the exact required-field status assert:
  `F1: specified != fixture implied` (test line 78). Retries: 0.

Because T-0002 failed, per T6 I ran the one-off 27-row diagnostic (scratchpad, OUTSIDE the repo tree,
uncommitted). Note: the diagnostic is an INDEPENDENT live extraction — the model is non-deterministic,
so it drifted differently from the graded run (it landed class C: F1 then correctly `implied`, but B2
under-credited to unspecified and D2 over-demoted). Both runs are near the boundary; demotions fired
CORRECTLY in both. Diagnostic verbatim:

```
STATUS: ok
CLASS: C EXPECTED: B
REQUIRED_MISSING: ['B1', 'B2', 'D1', 'D2', 'D3', 'D4', 'F2|F4'] FIXTURE: ['B1', 'D1', 'D3', 'D4', 'F2|F4']
RETRIES: 0
DEMOTIONS: [{"field": "B1", "from_status": "implied", "basis": "narrated_example"}, {"field": "D2", "from_status": "implied", "basis": "narrated_example"}]

id   req  ext_status   basis                  fixture      demoted  source_quote
--------------------------------------------------------------------------------
A1        specified                           specified             '# WIT Source Archive — WIT-S-0002 (video #1, "Candle Formation")'
A2        specified                           specified             'I am up over $4,000.'
A3        specified                           specified             "here are three candlesticks that when they're closed look exactly the same"
B1   REQ  unspecified  narrated_example       unspecified  YES      'the NASDAQ here pushed higher and then started to sell off'
B2   REQ  unspecified                         specified             'this can work on a one minute chart, 5 minute, any type of chart, a daily chart'
B3        unspecified                         unspecified           'how and where it forms can tell you a completely different story'
C1        unspecified                         unspecified           ''
C2        unspecified                         unspecified           'in a choppy environment is more likely to instantly get reversed'
C3        unspecified                         unspecified           ''
D1   REQ  unspecified                         unspecified           "we have a downtrend and now it's starting to make higher highs and higher lows, it has a potential to go higher"
D2   REQ  unspecified  narrated_example       implied      YES      'It comes up and it pulls back midcand showing that healthy pullback and then it pushes higher and actually breaks this high.'
D3   REQ  unspecified                         unspecified           'I look to jump in as it breaks that high'
D4   REQ  unspecified                         unspecified           'it actually even pulls back a little bit and fills me'
E1        unspecified                         unspecified           ''
F1   REQ  implied      generalized_practice   implied               "I put my stop loss below that big candlestick because it's a good confirmation and it shows strength"
F2   REQ  unspecified                         unspecified           'I can look for a larger move to play out'
F3        unspecified                         unspecified           ''
F4   REQ  unspecified                         unspecified           ''
F5        unspecified                         unspecified           ''
G1        unspecified                         unspecified           ''
G2        unspecified                         unspecified           ''
H1        unspecified                         unspecified           ''
H2        unspecified                         unspecified           ''
I1        unspecified                         unspecified           ''
J1        unspecified                         specified             ''
J2        unspecified                         specified             ''
K1        specified                           specified             "that's why you need to be with your candlestick patterns is take into account the big picture"
```

Reading: the deterministic mechanism is SOUND — every `narrated_example` basis was demoted to
unspecified as designed (B1, D2 here; the graded run demoted the B1/D1/D3/D4 set), and `F1` is now
correctly declared `generalized_practice → implied` (the two-part test working). The residual gap is
MODEL run-to-run variance on 1–3 boundary required fields (F1, B2, D2): the model's specified/implied/
basis call on those flips across samples, landing on either side of the ratified fixture. Per-field
status match in the diagnostic run: 23/27 (~85%). Per the handoff RESUME-HERE rule (T7b) — "If T-0002
is still misgraded: STOP for a lead-engineer review of the live diagnostic before ANY further
hardening" — this is the STOP: the anchors are ratified (P3o) and are not the lever; the next move is
a lead decision (e.g. a status critic / self-consistency vote), not more prompt text.

## 5. Commit + CI
- Commit hash: this commit — see `git log --oneline -1`
  (`WIT-P3e-5: basis discipline — per-required-field evidence gate, deterministic demotion, claims grounding`).
- CI status: recorded below after push.

## 6. Anything unexpected
- The two live extractions disagreed (graded run class B/F1-specified; diagnostic class C/F1-implied)
  — direct evidence that the remaining miss is sampling variance on the boundary fields, not a
  systematic anchor or mechanism error. The demotion engine behaved identically and correctly in both.
- `test_system_prompt_offers_no_unsupported_token` needed the `"structure"` substring check narrowed
  to the vocab block (rule 9's English prose legitimately contains "structure"). Flagged here; it is a
  prompt-builder test, not the golden, and its protective intent is preserved.
- Read hook truncated file reads to line 1 again; used `sed`/`grep`/`awk` for exact anchors and
  grep-verified edits. No content impact.

WIT-P3e-5 — Partial: shipped + suite green (219/0/2) and T-0001 passes live; T-0002 still misgraded on the F1 exact-status assert (model boundary variance, not the mechanism) → STOP for lead review per the handoff rule.

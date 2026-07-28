# WIT-P3e-7 — k=3 extraction ensemble (per-field majority vote, conservative ties, medoid merge)

## 1. STEP 0
- HEAD **7d9be1d** (WIT-P3e-6) — matches. Repo/path/origin match the header. Tree clean except the
  known untracked `pine/mes_net_pnl_v2.pine`.
- ANTHROPIC_API_KEY **set:True len:108**; minimal `claude-haiku-4-5` `max_tokens=1` call returned
  `stop_reason=max_tokens` (no 401). Key never printed.
- HARD LIMITS honored: `api/tests/fixtures/*.json` byte-identical (not staged/changed);
  `completeness.py` + scorer constants untouched; golden asserts/thresholds untouched (only the
  CALL TARGET changed — see §2).

## 2. Ensemble design as implemented (`api/wit/extraction/ensemble.py`)
`extract_template_ensemble(transcript, source_meta, *, k=3)` — pure orchestration over the existing
`extract_template`; merges FINISHED templates only (each run already passed schema + grounding +
claims-grounding + demotion + downgrade).
- **Runs & failure:** k sequential runs; `extraction_failed` runs dropped; `<2` ok → return
  `extraction_failed` carrying every failed run's errors.
- **Per-field vote (all 27):** majority wins; on a tie (incl. 1/1/1) the **least-crediting** tied
  status wins (crediting `specified>implied>unspecified`, so the honest gap wins ties) —
  `_vote_status`.
- **Medoid:** the ok run agreeing with the voted statuses in the most fields; tie → lowest index.
  It donates source, template_version, consistency_flags, interpretations.
- **Field object:** medoid's object if its status matches the vote, else the lowest-index run whose
  status matches (`_field_donor`; a donor always exists because the vote picks a produced status).
- **Claims:** grouped across runs by quote overlap using a matcher **factored into
  `extract.claims_quotes_match` / `claim_quote_fragments`** (same `_norm` + ellipsis-fragment
  semantics as the golden's coverage check — one definition, no drift). Every group kept
  (exhaustive; each member already grounded); representative = medoid's member else lowest-index;
  `testable` = group majority, tie → representative's flag.
- **Re-check before scoring:** `validate_template` + field `grounding_errors` + `claims_grounding_errors`
  must all be empty (they are, by construction) — a violation raises loudly, never silently scores.
  Then the deterministic scorer assigns the class exactly as in `extract_template`.
- **Return:** mirrors `extract_template` plus `ensemble_meta = {k, ok_runs, medoid_index,
  unanimous_fields, majority_fields, tie_fields, per_run:[{retries,demotions,downgrades}]}`.
- **Golden change (T3):** the ONLY change to `test_extraction_golden.py` is the call target —
  import `extract_template_ensemble` and call it with `k=3`. Every assert, threshold, and helper is
  byte-identical.

## 3. New tests + suite counts
New (10) in `tests/test_extraction_ensemble.py`: direct — `_vote_status`
(unanimous/majority/1-1-1-tie/1-1-tie), `_field_donor` (medoid + fallback), `_merge_claims`
(group+majority-testable, distinct-kept); end-to-end (monkeypatched per-run `extract_template`) —
2-1 majority, spec/impl tie after a dropped run → implied, one-failed-still-ok, two-failed→fail with
all errors, merged re-validates+scores (class from scorer, unanimous_fields=27), donor provenance.
Full CI-safe suite (`cd api && BACKTEST_API_KEY=k python -m pytest -q`):
**233 passed / 0 failed / 2 skipped** (223 prior + 10 new; 2 skips = network-gated live tier).

## 4. LIVE runs (graded golden x2 back-to-back, k=3 each → ~12 extractions)
**Both cases FAILED in BOTH runs.** The ensemble mechanism is stable (voted diagnostic below:
unanimous 23/27, majority 4/27, **tie 0/27**), but the residual failures have SHARPENED from
"sampling noise" into a concrete **model-judgment-vs-adjudication** disagreement.

- **T-0001 (A):** FAILED BOTH runs on the SAME assert (golden line 110) — claims-COVERAGE
  `testable` flag for `'Profitable over a 10-year backtest'` (fixture `True`). The model's majority
  marks that claim `False`, and the ensemble collapses each claim group to ONE majority-voted claim,
  so the occasional `True` variant a single-shot run used to produce no longer survives.
- **T-0002 (B):** FAILED both runs. Run-1 → class **C** (golden line 70). Run-2 → class **B** but
  `required_missing` has extra **{D2, F1}** (line 73). **Stability check: the two runs DISAGREED**
  (C vs B) — the ensemble reduces cross-triple variance (unanimous 23/27) but does not eliminate it,
  because D2/F1 sit near the vote boundary.

Per T5 (both runs fail; T-0001 on the same assert), the 27-row diagnostic of the VOTED template (a
3rd k=3 ensemble; scratchpad OUTSIDE the repo, uncommitted), verbatim:

```
STATUS: ok
CLASS: B EXPECTED: B
REQUIRED_MISSING: ['B1', 'D1', 'D2', 'D3', 'D4', 'F1', 'F2|F4'] FIXTURE: ['B1', 'D1', 'D3', 'D4', 'F2|F4']
ENSEMBLE_META: k=3 ok_runs=3 medoid=0 unanimous=23 majority=4 tie=0
PER_RUN: [{"retries": 0, "demotions": [], "downgrades": []}, {"retries": 0, "demotions": [], "downgrades": []}, {"retries": 0, "demotions": [{"field": "B1", "from_status": "specified", "basis": "narrated_example"}], "downgrades": [{"field": "D2", "from_status": "specified", "to_status": "implied", "basis": "generalized_practice"}]}]

id   req  voted_status  basis                  fixture      source_quote
------------------------------------------------------------------------
A1        specified                            specified    '# WIT Source Archive — WIT-S-0002 (video #1, "Candle Formation")'
A2        specified                            specified    'I am up over $4,000.'
A3        specified                            specified    "here are three candlesticks that when they're closed look exactly the same"
B1   REQ  unspecified   narrated_example       unspecified  'the NASDAQ here pushed higher and then started to sell off'
B2   REQ  specified     stated_rule            specified    'this can work on a one minute chart, 5 minute, any type of chart, a daily chart'
B3        implied                              unspecified  'how and where it forms can tell you a completely different story'
C1        unspecified                          unspecified  ''
C2        unspecified                          unspecified  'in a choppy environment is more likely to instantly get reversed the next candlestick'
C3        unspecified                          unspecified  ''
D1   REQ  unspecified   narrated_example       unspecified  "we have a downtrend and now it's starting to make higher highs and higher lows, it has a potential to go higher"
D2   REQ  unspecified   narrated_example       implied      "I'm looking for a head and shoulders pattern here and a break above this high"
D3   REQ  unspecified   narrated_example       unspecified  'I look to jump in as it breaks that high and then it actually even pulls back a little bit and fills me'
D4   REQ  unspecified   narrated_example       unspecified  'and then it actually even pulls back a little bit and fills me'
E1        unspecified                          unspecified  ''
F1   REQ  unspecified   narrated_example       implied      "I put my stop loss below that big candlestick because it's a good confirmation and it shows strength"
F2   REQ  unspecified   tendency_or_claim      unspecified  'I can look for a larger move to play out'
F3        unspecified                          unspecified  ''
F4   REQ  unspecified                          unspecified  ''
F5        unspecified                          unspecified  ''
G1        unspecified                          unspecified  ''
G2        unspecified                          unspecified  ''
H1        unspecified                          unspecified  ''
H2        unspecified                          unspecified  ''
I1        unspecified                          unspecified  ''
J1        unspecified                          specified    ''
J2        unspecified                          specified    ''
K1        specified                            specified    'take into account the big picture'
```

**Reading (the finding for the lead):** the vote is CLEAN and stable — tie 0/27, unanimous 23/27.
The two misses (D2, F1) both vote `unspecified` because the model's MAJORITY basis for them is
`narrated_example` — the model genuinely reads the head-and-shoulders setup (D2) and the stop rule
(F1) as narration of one worked example. That DISAGREES with the P3o-ratified fixture (D2=implied,
F1=implied). This is no longer sampling noise the vote can average away: it is the model's central
judgment vs the human adjudication on a genuinely borderline video. (The P3o adjudication itself
flagged D3 as "closest call" and D2/F1 as nuanced.) The claims-`testable` miss on T-0001 is the same
species — the model's majority reads 'Profitable over a 10-year backtest' as non-testable-as-stated.
WHAT'S SOLID: B2 stable `specified`/`stated_rule` (P3e-6 clarifier holding), demotions/downgrades
firing correctly per run, ensemble deterministic given its samples. Per T5 this is the STOP: I tuned
nothing in response to the outcome. The decision is now a lead JUDGMENT call (accept the honest gap,
steer harder, or reconsider the claims-testable hard assert) — see the handoff RESUME block.

## 5. Commit + CI
- Commit hash: this commit — see `git log --oneline -1`
  (`WIT-P3e-7: k=3 extraction ensemble — per-field majority vote, conservative ties, medoid merge`).
- CI status: recorded below after push.

## 6. Anything unexpected
- The ensemble surfaced a NEW interaction on claims: collapsing each claim group to one
  majority-voted claim makes the claims-`testable` HARD assert *stricter* than single-shot (a lone
  correct-flag variant no longer counts). Flagged as a lead-review item (candidate: the claims
  `testable` flag may not belong as a hard golden assert).
- The real finding is qualitative: with a stable vote (tie 0/27) the remaining T-0002 misses are a
  MODEL-vs-ADJUDICATION disagreement on D2/F1 (narrated_example vs implied), not noise — exactly the
  thing a human lead, not another mechanism, should adjudicate.
- Read hook truncated file reads to line 1 again; used `sed`/`grep`/`awk` for exact anchors and
  grep-verified edits. No content impact.

WIT-P3e-7 — Partial: k=3 ensemble shipped, deterministic and stable (tie 0/27, unanimous 23/27) and suite green (233/0/2), but live golden x2 still fail — the residual is a MODEL-vs-P3o-adjudication disagreement on D2/F1 basis (narrated_example vs implied) + the claims-testable flag, which is a lead JUDGMENT call → STOP for lead review.

# WIT-P3e-8 — prompt-spec alignment (narrated-vs-generalized per P3o, quote selection, testable defined)

## 1. STEP 0
- HEAD **9be0284** (WIT-P3e-7) — matches. Repo/path/origin match the header. Tree clean except the
  known untracked `pine/mes_net_pnl_v2.pine`.
- ANTHROPIC_API_KEY **set:True len:108**; minimal `claude-haiku-4-5` `max_tokens=1` call returned
  `stop_reason=max_tokens` (no 401). Key never printed.
- HARD LIMITS honored: fixtures byte-identical (not staged/changed); `completeness.py`/scorer
  untouched; golden asserts/thresholds untouched; `ensemble.py` logic untouched. PROMPT TEXT ONLY.

## 2. Exact prompt-text diffs + contamination check
- **Rule 9 narrated_example (T1) — replaced** (grep confirmed the old "however habitual it sounds"
  was present before editing):
  - OLD: `"narrated_example" — narration of one specific trade/chart, however habitual it sounds,
    or a referent that exists only inside that exhibit`
  - NEW: `"narrated_example" — narration of one specific trade/chart WITH NO generalization beyond
    it anywhere in the source, or a referent that exists only inside that exhibit. If the narration
    is accompanied by a generalized statement of the practice or a general justification ("I always
    ...", "because these ... tend to hold"), AND the referent is executable within this template,
    the basis is "generalized_practice" — the generalization, not the demonstration, earns the credit`
- **Rule 9 clarifiers (T2) — added:** the MOST-GENERAL quote-selection rule, and the "a general
  justification phrased as a tendency does not make the FIELD a tendency claim … basis classifies
  the PRACTICE" clarifier.
- **Rule 4 (T3) — appended** the `testable` definition (`testable=true iff the claim can be tested
  against historical price data …; testable=false for personal results/anecdotes/live-performance
  stories/promises about the viewer's future results; whether the source's OWN evidence can be
  verified is irrelevant`).
- **Anchor-contamination check: PASS.** A longest-common-substring scan (normalized, ≥12 chars) of
  the EXACT shipped added sentences vs BOTH transcripts returned **NONE** for each. (Three incidental
  generic collisions in the first draft — ` about the strategy`, ` practice be`, ` the market'` —
  were removed by rewording only non-pinned words: "historical market data (a claim about the
  strategy's or the market's behavior)" → "historical price data (a claim about how a strategy or a
  market itself behaves)", and "the PRACTICE being credited" → "the PRACTICE we credit". No pinned
  phrase or strategy-signal text was embedded.)

## 3. Test changes + suite counts
Added `test_system_prompt_encodes_p3e8_spec_alignment` (pins `WITH NO generalization`,
`the generalization, not`, `the demonstration, earns the credit`, `MOST GENERAL`, `testable=true iff`,
`testable=false`; asserts the removed `however habitual it` is GONE; prior rule-9 phrases intact). No
prior pin referenced the removed phrase. Full CI-safe suite (`BACKTEST_API_KEY=k python -m pytest -q`):
**234 passed / 0 failed / 2 skipped** (233 prior + 1 new).

## 4. LIVE graded golden x2 (ensemble k=3 each) + voted diagnostic
**Both cases FAILED both runs** — but P3e-8 FIXED the two errors it targeted and exposed a third; the
residual is now confirmed FIXTURE-vs-MODEL, which triggers the pre-committed endgame.

- **RUN 1:** T-0001 FAIL (line 110) — claims-`testable` for `'Consistent profits in less than 90
  minutes per day'` (NOT the old 10-yr claim). T-0002 FAIL (line 73) — `required_missing` extra
  **{D2}** (D2 under-credited). F1 NOT in the extra set (**F1 fixed**).
- **RUN 2:** T-0001 FAIL — same `'Consistent profits…'` claim. T-0002 FAIL — `required_missing`
  **missing {B1, D1}** vs fixture (i.e. B1 and D1 OVER-credited this run). Opposite-direction miss
  from run 1 → the two runs disagree.
- **D2/F1 voted status+basis** (from the diagnostic, 3rd sample): **F1 = implied / generalized_practice
  (= fixture) — FIXED & stable**; **D2 = implied / generalized_practice (= fixture) this sample** (but
  under-credited in run 1 → still boundary-unstable). **10-year-backtest claim testable = True
  (= fixture) — FIXED** by the rule-4 definition; the failing claim is now `'Consistent profits <90min'`
  (model False vs fixture True).

Per T5 (both cases fail both runs) — voted-template 27-row diagnostic (3rd k=3 ensemble; scratchpad
OUTSIDE the repo, uncommitted). NOTE: the STATUS/CLASS/REQUIRED_MISSING/ENSEMBLE_META summary lines
were lost to a `tail` in the capture; the 27 voted rows are verbatim below and `required_missing`
is reconstructed from them = **{D1, D3, D4, F2|F4}** vs fixture **{B1, D1, D3, D4, F2|F4}** (the model
OVER-credits B1). Columns: id | req | voted_status | basis | fixture | source_quote.

```
A1        specified                           specified    'WIT Source Archive — WIT-S-0002 (video #1, "Candle Formation")'
A2        specified                           specified    'I am up over $4,000.'
A3        unspecified                         specified    ''
B1   REQ  specified    stated_rule            unspecified  'the NASDAQ here pushed higher and then started to sell off'
B2   REQ  specified    stated_rule            specified    'this can work on a one minute chart, 5 minute, any type of chart, a daily chart'
B3        implied                             unspecified  'this could form while you watch the candlestick form'
C1        unspecified                         unspecified  ''
C2        unspecified                         unspecified  ''
C3        unspecified                         unspecified  ''
D1   REQ  unspecified  tendency_or_claim      unspecified  "we have a downtrend and now it's starting to make higher highs and higher lows, it has a potential to go higher"
D2   REQ  implied      generalized_practice   implied      "I'm looking for a head and shoulders pattern here and a break above this high"
D3   REQ  unspecified                         unspecified  ''
D4   REQ  unspecified                         unspecified  ''
E1        unspecified                         unspecified  ''
F1   REQ  implied      generalized_practice   implied      "I put my stop loss below that big candlestick because it's a good confirmation and it shows strength"
F2   REQ  unspecified                         unspecified  ''
F3        unspecified                         unspecified  ''
F4   REQ  unspecified                         unspecified  ''
F5        unspecified                         unspecified  ''
G1        unspecified                         unspecified  ''
G2        unspecified                         unspecified  ''
H1        unspecified                         unspecified  ''
H2        unspecified                         unspecified  ''
I1        unspecified                         unspecified  ''
J1        unspecified                         specified    ''
J2        unspecified                         specified    ''
K1        specified                           specified    "you want to be reading what they're telling you in relation to the larger picture"
```

**T-0001 merged claims (voted testable):** the 10-year-backtest claim now votes **True** (matches
fixture — FIXED). The fixture's `'Consistent profits in less than 90 minutes per day'` = True, but the
voted merged claim `'The goal is to make consistent profits in less than 90 minutes per day.'` votes
**False** (the model reads it as a goal/promise, not a data-testable behavior claim) — this is the
remaining T-0001 miss.

**Reading:** P3e-8 did exactly what it should on its two targets (F1, 10-yr testable) and did no harm
to the many unanimous fields, but it also nudged the model to OVER-credit the exhibit-instrument B1
(and sometimes D1) via the "generalization rescues" language. The three entries now in genuine dispute
— T-0002 **B1** (exhibit instrument), T-0002 **D2** (setup boundary), and the T-0001 **'Consistent
profits <90min'** claim testable flag — are JUDGMENT calls a prompt cannot settle without over/under-
shooting the neighbor. Per the pre-committed endgame this is the STOP: **no further prompt-hardening is
authorized; the next slice is a formal LEAD RE-ADJUDICATION (P3q)** of exactly those fixture entries.
I tuned nothing in response to the outcomes.

## 5. Commit + CI
- Commit hash: this commit — see `git log --oneline -1`
  (`WIT-P3e-8: prompt-spec alignment — narrated-vs-generalized per P3o, quote selection, testable defined`).
- CI status: recorded below after push.

## 6. Anything unexpected
- The prompt fix TRADED errors: F1 + 10-yr-testable fixed, but B1/D1 now over-credit in some samples
  (the exhibit-instrument gets read as a stated B-fact). This is the clearest possible evidence that
  prompt text alone cannot land all borderline fields simultaneously — exactly why the endgame
  pre-commits to re-adjudication rather than another prompt slice.
- The T-0001 claims miss MOVED (10-yr → 'Consistent profits <90min'), confirming the testable
  definition works but that a second claim is genuinely disputable.
- Diagnostic capture lost its summary header to a `tail` pipe; the 27 voted rows (the artifact T5
  requires) are intact and `required_missing` is reconstructed from them. Read hook truncation worked
  around with sed/grep/awk. No content impact on the shipped files.

WIT-P3e-8 — Partial: prompt aligned to the P3o standard (F1 + 10-yr-backtest-testable now fixed) and suite green (234/0/2), but live golden x2 still fail — B1 now over-credits, D2 stays boundary-unstable, and 'Consistent profits <90min' testable disputes the fixture → PRE-COMMITTED ENDGAME: STOP, next slice is the P3q lead re-adjudication (no further prompt-hardening authorized).

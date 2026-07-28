# WIT-P3e-4 — extraction grounding retry loop + status-discipline prompt hardening

## 1. STEP 0
- HEAD 274fa8b (WIT-P3l docs pass): **yes** — `git log --oneline -1` == `274fa8b`.
- Repo/path confirmed: `origin https://github.com/jimmuell/mes-orb-strategy.git`, `/Users/jameslmueller/Projects/mes-orb-strategy`.
- Key set AND live-valid: **yes** — `set:True len:108`; one minimal Messages call
  (`claude-haiku-4-5`, `max_tokens=1`) returned `stop_reason=max_tokens` (no 401). Key never printed.
- Branching: committed DIRECTLY to `main` (no branch), full local suite gating the commit.

## 2. Grounding loop
- `grounding_errors(template, transcript)` added to `api/wit/extraction/extract.py` and wired into
  `extract_template`'s loop **immediately after** `validate_template` passes: **yes**. Grounding is a
  success gate EQUAL to schema validity — a schema-valid but hallucinated quote now retries (feeding
  the named-field error back into the user turn) and, on exhaustion, returns `extraction_failed` with
  the grounding errors. Success == schema-valid AND fully grounded.
- Normalization identical to the golden `_norm`: **yes** — `re.sub(r"\s+", " ", s or "").strip().lower()`,
  copied verbatim into `extract._norm` with a comment pinning them together. Non-J fields with status
  specified/implied require a non-empty `source_quote` whose normalized form is a substring of the
  normalized transcript; J fields are never grounding-checked.

## 3. Prompt hardening + test count + CI-safe suite
- `api/wit/extraction/prompt.py` `_RULES` gained rule 7 (QUOTE DISCIPLINE — "copied
  CHARACTER-FOR-CHARACTER…", "if the captions say '945', write '945', not '9:45'") and rule 8 (STATUS
  DISCIPLINE — "A description of what price TENDS to do … is NOT a rule", "WHEN IN DOUBT BETWEEN
  'implied' AND 'unspecified', CHOOSE 'unspecified' — the honest gap IS the product").
- New tests: **6** — 5 orchestrator (paraphrase→retry+names field; paraphrase→exact→ok w/ retries;
  always-paraphrased→terminal fail; whitespace/case tolerance; J never checked) + 1 prompt
  (P3e-4 rule phrases present). Two prior orchestrator tests (`test_valid_first_try`,
  `test_invalid_then_valid_retries`) were adjusted to supply grounded templates against a controlled
  fake transcript — required because grounding is now a success gate; all P3e-1/2 prompt tests stay green.
- CI-safe suite: `cd api && BACKTEST_API_KEY=k python -m pytest -q` →
  **212 passed (206 prior + 6 new) / 0 failed / 2 skipped.**

## 4. LIVE golden re-run (`WIT_RUN_LLM_TESTS=1 … test_extraction_golden.py`)
Both cases still fail overall, but the failure modes MOVED — the fixes worked where graded, the
residual gap is the status-over-crediting finding.

**T-0001 (expect A): grounding now PASSES — fails only a TOLERANT assert.**
- Passed, in order: class == A ✓, required_missing set ✓, all required-field statuses (B1,B2,D1-D4,F1) ✓,
  F2|F4 pair ✓, **GROUNDING (line 93) ✓** — i.e. the baseline's D2 verbatim-substring failure is fixed;
  every specified/implied quote is now a verbatim transcript substring.
- Failed at line 96 (tolerant claims-count): extractor produced **10** claims vs fixture's **5**
  (tolerance ±1). This is the model being more exhaustive on performance claims (rule 4 asks for EVERY
  claim) plus run-to-run variance — a fixture/threshold tolerance, which the prompt FORBIDS me to tune.
  Grounding retries that fired: **0** (retries == 0; first-pass output was already fully grounded).

**T-0002 (expect B): STILL classifies A — the product-critical failure persists.**
- class == **A** (expected B); FAIL at line 69.
- required_missing extracted **[]** vs fixture **[B1, D1, D3, D4, F2|F4]** → because the extractor
  over-credited the required fields, nothing is missing, so the scorer assigns A.
- retries: **0**; grounding retries: **0** (every over-credited quote IS a verbatim transcript
  substring — the failure is NOT hallucination, it is charitable status inflation of illustrative
  language into `specified`/`implied`). The STATUS DISCIPLINE rule did not, in this run, pull the model
  down to `unspecified` on B1/D1/D3/D4.

Per the prompt: DID NOT tune fixtures, scorer, thresholds, or the test. One-off diagnostic
(`scratchpad/diag_t0002.py`, NOT committed) extracted T-0002 once; 27-row table verbatim below.

```
STATUS: ok
CLASS: A EXPECTED: B
REQUIRED_MISSING: [] FIXTURE: ['B1', 'D1', 'D3', 'D4', 'F2|F4']
RETRIES: 0

id   req  extracted   fixture     over  source_quote
----------------------------------------------------
A1        specified   specified         'WIT Source Archive — WIT-S-0002 (video #1, "Candle Formation")'
A2        specified   specified         'I am up over $4,000.'
A3        specified   specified         'instead actually made a double bottom after it made a double top'
B1   REQ  specified   unspecified YES   'the NASDAQ here pushed higher and then started to sell off'
B2   REQ  specified   specified         'this can work on a one minute chart, 5 minute, any type of chart, a daily chart'
B3        implied     unspecified YES   'how and where it forms can tell you a completely different story'
C1        unspecified unspecified       ''
C2        implied     unspecified YES   'in a choppy environment is more likely to instantly get reversed the next candlestick'
C3        unspecified unspecified       ''
D1   REQ  specified   unspecified YES   "we have a downtrend and now it's starting to make higher highs and higher lows, it has a potential to go higher"
D2   REQ  specified   implied           'It comes up and it pulls back midcand showing that healthy pullback and then it pushes higher and actually breaks this high.'
D3   REQ  specified   unspecified YES   'I look to jump in as it breaks that high'
D4   REQ  implied     unspecified YES   'it actually even pulls back a little bit and fills me'
E1        unspecified unspecified       ''
F1   REQ  specified   implied           'I put my stop loss below that big candlestick'
F2        unspecified unspecified       ''
F3        unspecified unspecified       ''
F4        unspecified unspecified       ''
F5        unspecified unspecified       ''
G1        unspecified unspecified       ''
G2        unspecified unspecified       ''
H1        unspecified unspecified       ''
H2        unspecified unspecified       ''
I1        implied     unspecified YES   "if the market moves straight up with no pullbacks, even over 60 seconds, it's not going to be healthy"
J1        specified   specified         ''
J2        specified   specified         ''
K1        specified   specified         'take into account the big picture'
```

**Reading of the table (the finding):** all four over-credited REQUIRED fields (B1, D1, D3, D4) are
grounded in verbatim transcript quotes — so grounding cannot catch them. They are *illustrative /
narration of one example trade* ("the NASDAQ here pushed higher…", "we have a downtrend… it has a
potential to go higher", "I look to jump in as it breaks that high", "it actually even pulls back… and
fills me"), which the model upgraded to `specified`/`implied` despite the STATUS DISCIPLINE rule telling
it a tendency/illustration is NOT a rule and to prefer `unspecified` when in doubt. Prompt text alone did
not move this run's judgment; the honest-gap classification of vague videos likely needs a stronger
mechanism (e.g. a per-required-field "is this a STATED executable rule or a narrated example?" gate, or
a second-pass status critic) — proposed as the next slice. The P3e-4 fixes (grounding retry loop +
quote/status prompt rules) are still net-positive and shipped; the residual A-vs-B gap is the finding.

## 5. Commit + CI
- Commit hash on main: see `git log` — `WIT-P3e-4: extraction grounding retry loop + status-discipline prompt hardening`.
- CI status: recorded below after push.

## 6. Anything unexpected
- T-0001's failure MOVED from grounding (baseline) to the tolerant claims-count assert (10 vs 5). The
  grounding fix is confirmed working; the new trip is a ±1 claims tolerance the prompt forbids tuning —
  noted, not changed.
- T-0002 required-field over-crediting is entirely on grounded quotes, confirming this is a
  status-judgment problem, not a hallucination problem — grounding (this slice's lever) is orthogonal to it.
- A Read hook truncated file reads to line 1 this session; used `cat`/`Read`-with-offset as the workaround.

WIT-P3e-4 — Partial: T-0002 still misclassifies A-vs-B (status over-crediting of illustrative language on required B1/D1/D3/D4 — all grounded, so beyond grounding's reach); per the STOP rule no fixtures/scorer/thresholds/test tuned — code + graded report shipped, residual gap is the finding for the next slice.

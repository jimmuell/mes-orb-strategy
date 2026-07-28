# WIT-P3e-6 — extraction determinism (temperature) + basis/status coherence + B-fact clarifier

## 1. STEP 0
- HEAD **20b8976** (WIT-P3e-5) — matches. Repo/path/origin match the header. Tree clean except
  the known untracked `pine/mes_net_pnl_v2.pine`.
- ANTHROPIC_API_KEY **set:True len:108**; minimal `claude-haiku-4-5` `max_tokens=1` call returned
  `stop_reason=max_tokens` (no 401). Key never printed.
- HARD LIMITS honored: `api/tests/fixtures/*.json` byte-identical (not staged/changed);
  `completeness.py`, scorer constants, golden asserts/thresholds untouched.

## 2. Per-file changes + contamination check
- **provider.py (T1) — HEADLINE FINDING.** The intended `temperature=0` pin is **REJECTED by the
  deployed model**: `claude-opus-4-8` returns `400 invalid_request_error: "temperature is
  deprecated for this model."` Verified directly: `temperature=0` → 400; `temperature=1` → accepted;
  unset → accepted. So the model only permits its default (1) and **the temperature-0 determinism
  lever is UNAVAILABLE on this model.** Per "STOP-and-report beats forcing," I did NOT ship a call
  that hard-400s the live extraction: temperature is left UNSET with a comment documenting the
  deprecation and pointing here. (The pre-P3e-6 behavior — no temperature — is preserved.)
- **extract.py (T2).** `apply_downgrades()` added, deterministic, pre-scoring, alongside
  `apply_demotions()`: a REQUIRED field with status `specified` + basis `generalized_practice` is
  downgraded to `implied` (never blocked/retried; both still satisfy — only the exact status the
  golden grades moves). Success now returns `downgrades: [{field, from_status, to_status, basis}]`.
- **prompt.py (T3).** Rule 9 gained two additive clarifiers (status/basis pairing;
  capability/scope fact = stated B-fact). Rules 1–8, prior rule-9 text, and all pinned phrases
  unchanged. **Contamination check: PASS** — a longest-common-substring scan of the exact added
  text vs BOTH transcripts (normalized, ≥12 chars) returned NONE for each. (One incidental generic
  connective — `" even when the "`, 15 chars — collided with T-0002; I reworded that non-pinned
  phrase to `"even if that very sentence"`, re-scanned → 0 hits. No strategy-signal text was ever
  embedded.)
- **tests.** 4 new (3 orchestrator downgrade cases + 1 prompt clarifier test). No existing test
  needed plumbing changes (the downgrade targets `generalized_practice`; existing fakes use
  `stated_rule`).

## 3. New tests + suite counts
New (4): (1) specified + generalized_practice on a required field → downgraded to implied +
recorded, class unchanged; (2) specified + stated_rule → untouched, downgrades empty; (3) implied +
generalized_practice → untouched; (4) prompt test — new pairing/capability phrases present AND prior
rule-9 phrases intact. Full CI-safe suite (`cd api && BACKTEST_API_KEY=k python -m pytest -q`):
**223 passed / 0 failed / 2 skipped** (219 prior + 4 new; 2 skips = network-gated live tier).

## 4. LIVE runs (graded golden, x2 back-to-back — WITHOUT temperature, since it 400s)
**The two runs BOTH FAILED and DISAGREED with each other** — stated loudly because that is exactly
the non-determinism the temperature pin was meant to remove and cannot on this model. retries 0
throughout; demotions/downgrades fired correctly every run.

- **RUN 1:** T-0001 FAILED; T-0002 FAILED — class **C** (≠ B).
- **RUN 2:** T-0001 FAILED at the P3o claims-COVERAGE assert — `claim covered but testable flag
  differs: 'Profitable over a 10-year backtest'` (a REGRESSION vs P3e-5's pass — the model flipped
  that claim's `testable` boolean; pure sampling variance). T-0002 FAILED at `required_missing`:
  extra **D2** (model declared D2 unspecified/`narrated_example`→demoted; fixture D2=implied).

So T-0001 failed BOTH runs and T-0002 failed BOTH runs; the runs disagreed on the *shape* of the
T-0002 miss (run-1 class C vs run-2 class-B-but-required_missing-mismatch). Per T6, the 27-row
diagnostic (a 3rd independent extraction; scratchpad OUTSIDE the repo tree, uncommitted):

```
STATUS: ok
CLASS: C EXPECTED: B
REQUIRED_MISSING: ['B1', 'D1', 'D2', 'D3', 'D4', 'F2|F4'] FIXTURE: ['B1', 'D1', 'D3', 'D4', 'F2|F4']
RETRIES: 0
DEMOTIONS: [{"field": "B1", "from_status": "implied", "basis": "narrated_example"}]
DOWNGRADES: []

id   req  ext_status   basis                  fixture      dem  dng  source_quote
---------------------------------------------------------------------------------
A1        specified                           specified              '# WIT Source Archive — WIT-S-0002 (video #1, "Candle Formation")'
A2        specified                           specified              'I am up over $4,000.'
A3        unspecified                         specified              ''
B1   REQ  unspecified  narrated_example       unspecified  YES       'the NASDAQ here pushed higher and then started to sell off'
B2   REQ  specified    stated_rule            specified              'this can work on a one minute chart, 5 minute, any type of chart, a daily chart'
B3        implied      generalized_practice   unspecified            'how and where it forms can tell you a completely different story'
C1        unspecified                         unspecified            ''
C2        unspecified                         unspecified            ''
C3        unspecified                         unspecified            ''
D1   REQ  unspecified                         unspecified            ''
D2   REQ  unspecified                         implied                ''
D3   REQ  unspecified                         unspecified            ''
D4   REQ  unspecified                         unspecified            ''
E1        unspecified                         unspecified            ''
F1   REQ  implied      generalized_practice   implied                "I put my stop loss below that big candlestick because it's a good confirmation and it shows strength"
F2   REQ  unspecified                         unspecified            ''
F3        unspecified                         unspecified            ''
F4   REQ  unspecified                         unspecified            ''
F5        unspecified                         unspecified            ''
G1        unspecified                         unspecified            ''
G2        unspecified                         unspecified            ''
H1        unspecified                         unspecified            ''
H2        unspecified                         unspecified            ''
I1        unspecified                         unspecified            ''
J1        unspecified                         specified              ''
J2        unspecified                         specified              ''
K1        specified                           specified              "that's how reading into the candlesticks really plays out"
```

**What P3e-6 FIXED (real, visible in the diagnostic):** B2 is now `specified` / basis `stated_rule`
(the T3 capability-fact clarifier working — it was under-credited to unspecified at P3e-5), and F1
reads `implied` / `generalized_practice` (correct per the P3o two-part test). Those were the two
concrete P3e-5 problems.
**What REMAINS:** D2 flip-flops run-to-run (fixture `implied`; the model variously declares it
`unspecified` or `narrated_example`→demoted, so it lands in required_missing and drops the class),
and the T-0001 claims `testable` flag varies. Both are MODEL sampling variance — the deterministic
demotion/downgrade layer is correct and firing, but it cannot stabilize a status the model itself
declares differently each call. With temperature=0 off the table, this variance is not fixable at
the provider layer.

Per the handoff RESUME rule ("if T-0002 still failed in both runs: STOP — lead review; candidate
next lever is a k-sample majority vote, decided by the lead, not improvised"): this is the STOP. I
tuned nothing in response to the outcomes.

## 5. Commit + CI
- Commit hash: this commit — see `git log --oneline -1`
  (`WIT-P3e-6: extraction determinism — temperature 0, basis/status coherence downgrade, B-fact clarifier`).
- CI status: recorded below after push.

## 6. Anything unexpected
- **The temperature-0 lever does not exist on claude-opus-4-8** (deprecated → 400). This invalidates
  P3e-6's finding (1); the slice's determinism goal cannot be met via temperature on this model. It
  is the single most important thing for the lead to weigh: the realistic next lever is a k-sample
  majority vote (handoff-named) or a grader model that honors temperature=0.
- The two live runs DISAGREED and T-0001 REGRESSED — direct confirmation the residual failure is
  sampling variance, not anchors (ratified P3o) or the deterministic mechanism (which fired
  correctly). T2/T3 are net-positive (B2 + F1 fixed) and shipped; the code is committed per T8 (T5
  gates; live outcome does not gate), but the live target is NOT met → PARTIAL.
- Read hook truncated file reads to line 1 again; used `sed`/`grep`/`awk` for exact anchors and
  grep-verified edits. No content impact.

WIT-P3e-6 — Partial: temperature-0 is deprecated/rejected by claude-opus-4-8 so the determinism lever is unavailable; T2 downgrade + T3 clarifier shipped and fixed B2/F1, but live golden x2 both fail on residual MODEL sampling variance (D2; T-0001 claims-testable) → STOP for lead review (k-sample vote or grader-model change).

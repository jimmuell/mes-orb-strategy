Platform   : Claude Code (VS Code, MacBook Air)
Project    : WillItTrade (WIT)
Repo       : github.com/jimmuell/mes-orb-strategy   (branch: main)
Prompt     : WIT-P3q
Local path : ~/Projects/mes-orb-strategy

STEP 0 — GATE (any failure => STOP and report)
  1. git checkout main && git pull --ff-only
  2. git log --oneline -1 must show 7f7d424 (WIT-P3e-8). Otherwise STOP, report HEAD.
  3. Tree clean (known untracked pine file fine); origin/path match. DOCS ONLY: no code,
     no tests, no fixtures, no prompt.py — nothing under api/ is touched. No LLM calls.

TASK
T1. Create docs/wit/log/WIT-P3q-adjudication.md with EXACTLY this content between the
    markers (exclusive):
----BEGIN FILE docs/wit/log/WIT-P3q-adjudication.md----
# WIT-P3q — Final re-adjudication of the three disputed entries + v1 acceptance (lead engineer, Cowork chat, 2026-07-28)

Trigger: the P3e-8 pre-committed endgame. Inputs: P3e-7/P3e-8 live results and voted
diagnostics. Scope: exactly three entries; everything else in both fixtures was already
ratified at P3o and confirmed by live agreement.

## 1. Verdicts (all three RE-RATIFIED — the fixtures are FINAL)

1. T-0002 B1 (instrument) — stays `unspecified`. The model credits it from the NASDAQ
   exhibit ("the NASDAQ here pushed higher..."), but the source's own generalization
   ("this can work on ... any type of chart") is a refusal to specify an instrument. An
   exhibit's scenery is not a specification; the B-fact clarifier credits STATED scope
   facts, and the stated scope here is "any", which for B1 is precisely `unspecified`
   (WIT then tests ES as a disclosed proxy).
2. T-0002 D2 (setup) — stays `implied`. The big-candle setup is the video's thesis,
   described generically (three formation archetypes, chapter 1) outside any single
   worked example: generalized (test i) and WIT-parameterized (test ii corollary) =>
   `implied`. The model's own voted diagnostic reached implied/generalized_practice; its
   remaining wobble is quote selection, not substance.
3. T-0001 claim 'Consistent profits in less than 90 minutes per day' — stays
   `testable: true`. Both components are measurable on data: profit consistency, and
   time-in-market per day (a metric J1 already defines and report WIT-0001 already
   published). "The goal is X" phrasing wraps the claim; the testable content is X.

## 2. Standing orders (unchanged and now closed)

- The fixtures are FINAL calibration anchors. No further prompt-hardening slices are
  authorized against them; no golden assert or threshold changes; goldens are never
  tuned to pass.
- The extraction stack as shipped (grounding gate -> basis gate -> demotion/downgrade ->
  k=3 ensemble vote) is the v1 extraction path.

## 3. KNOWN-RESIDUALS register (v1) — the exact allowed red

The cost-gated live golden remains STRICT and is EXPECTED to fail ONLY in these ways:
  R1. T-0002 B1 over-credited (specified/implied vs fixture unspecified) — direction:
      one omitted honest-gap line; class routing unaffected in observed runs.
  R2. T-0002 D2 boundary (unspecified vs fixture implied) — direction: one EXTRA
      honest-gap line (conservative).
  R3. T-0001 claim 'Consistent profits <90min' voted testable=false vs fixture true —
      direction: one claim under-tested (conservative).
Any live-golden miss NOT matching R1-R3 — any new field, any new claim, any class
mismatch, any grounding failure — is a REGRESSION: STOP and open a lead review. R1-R3
are re-examined when the extraction model is next changed.

## 4. v1 acceptance rationale (product decision)

Launch publishes a CURATED library: every audit is human-reviewed before publication,
with ensemble_meta (unanimous/majority/tie counts) surfaced to the reviewer. Within that
workflow the extractor is launch-grade: fabricated quotes are mechanically rejected,
grade inflation of vague sources is mechanically demoted and did not flip class in any
observed run, results are vote-stabilized, and residual disagreement with the ratified
key is confined to R1-R3 — borderline calls a human reviewer adjudicates in seconds.
Unsupervised user-submitted auto-publication is NOT part of v1 and re-opens this
acceptance when proposed.

## 5. Next

Extraction quality: CLOSED for v1. Next engine slice: POST /wit/v1/extract calling
extract_template_ensemble(k=3) (decided P3m-a; anthropic to the shipped runtime lock +
ADR-050 gate; per-call cost = 3 extractions).
----END FILE----

T2. SESSION-HANDOFF.md:
  a) "main =" line -> "main = the WIT-P3q commit (final re-adjudication: fixtures FINAL,
     known-residuals register R1-R3, extraction v1 ACCEPTED for the curated workflow);
     prior 7f7d424 (P3e-8)." Arc: append " → P3q final ruling."
  b) Replace the ENTIRE "▶ RESUME HERE — P3e-8 shipped..." block (through "...(draft in
     the Notion tracker row).") with:
      ▶ RESUME HERE — extraction quality CLOSED for v1 (P3q: fixtures FINAL, residuals
      register R1-R3 in docs/wit/log/WIT-P3q-adjudication.md; live-golden misses outside
      R1-R3 = regression => lead review). Next slice: POST /wit/v1/extract — calls
      extract_template_ensemble(k=3); auth + budget like the other /wit/v1 routes;
      returns {template, completeness, raw_meta incl. ensemble_meta}; anthropic moves
      from requirements-dev.txt to the SHIPPED runtime lock and must pass the ADR-050
      audit gate; per-call cost = 3 extractions. Jim's lane: Railway deploy confirm +
      WIT_ENGINE_SERVICE_KEY, WIT_CALLBACK_HMAC_SECRET, DISABLE_EXEC_ENDPOINTS=1;
      FirstRateData confirmation email (draft in the Notion tracker row).
T3. Archive this prompt verbatim to docs/wit/prompts/WIT-P3q.md; add rows for
    WIT-P3q-adjudication.md and WIT-P3q-report.md to docs/wit/log/README.md.
T4. Suite (unchanged expected): cd api && BACKTEST_API_KEY=k python -m pytest -q →
    234 passed / 0 failed / 2 skipped. Anything else => STOP (docs slices change nothing).
T5. Single commit DIRECTLY to main, subject:
      WIT-P3q: final ruling — fixtures FINAL, known-residuals register, extraction v1 accepted for curated launch
    Explicit paths only. Push; record CI.

REPORT BACK — docs/wit/log/WIT-P3q-report.md, staged with the commit:
  1. STEP 0. 2. Per-edit grep confirmations. 3. Suite counts. 4. Commit hash; CI.
  5. Anything unexpected.
Final line, exactly one of:
WIT-P3q — Completed
WIT-P3q — Partial: <one-line reason>

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

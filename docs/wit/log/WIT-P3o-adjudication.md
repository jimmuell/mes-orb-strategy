# WIT-P3o — Calibration-anchor adjudication (lead engineer, Cowork chat, 2026-07-28)

(Authored as WIT-P3n; renumbered P3o — an unrelated close-out commit took the P3n id.)

Scope: field-by-field reading of both archived transcripts (docs/wit/sources/) against both
committed fixtures (api/tests/fixtures/), per the P3m-a handoff's RESUME HERE. Inputs: the
WIT-P3e-4 live run + its 27-row diagnostic. VERDICT: both fixtures RATIFIED, byte-identical.
The T-0002 A-vs-B miss is model behavior (status over-crediting), not anchor error.

## 1. T-0002 disputed statuses — all nine ratified

| Field | Live P3e-4 | Fixture | Verdict | Ground |
|---|---|---|---|---|
| B1 | specified | unspecified | ratify | Quote is an exhibit's instrument ("here we have an example from actually a couple days ago... the NASDAQ here pushed higher"); the method claims chart-agnosticism. An exhibit's instrument is not the method's. |
| B3 | implied | unspecified | ratify | Quote is thematic ("how and where it forms..."), not a data requirement. Grounded-but-off-topic: grounding proves substring-ness, not that the quote supports the field. |
| C2 | implied | unspecified | ratify | "more likely to instantly get reversed" is tendency language; "choppy" never defined numerically. A concept is not an executable filter. |
| D1 | specified | unspecified | ratify | Narration of one chart read ("we have a downtrend and now it's starting to make higher highs..."), tendency-phrased ("has a potential to"). No general directional rule exists in the video. |
| D2 | specified | implied | ratify | Setup concept extensively described; "big" never quantified. specified = executable as stated; concept-stated-but-WIT-parameterized = implied. |
| D3 | specified | unspecified | ratify (closest call) | "I look to jump in as it breaks that high" is habitual phrasing — but the referent "that high" exists only inside a narrated, previously-taken trade whose setup is a discretionary head-and-shoulders read. A trigger whose reference level is not executable within the template's own structure is not a trigger. |
| D4 | implied | unspecified | ratify | "pulls back a little bit and fills me" narrates one fill; inferring an order-type rule from "fills me" is the charitable reconstruction rules 1/8 forbid. |
| F1 | specified | implied | ratify | Stated once in the worked example => not specified. Earns implied: habitual framing + explicit generalizing justification ("when these big candlesticks have strength... they're more likely to hold") + executable referent (the event candle, once D2's event exists). |
| I1 | implied | unspecified | ratify | Guru names no tunables; the quote is claim material (C1), not an optimization surface. |

Ratified in consequence: expected class B; required_missing = [B1, D1, D3, D4, F2|F4];
fixture score 21; satisfied-field count 9/27 (~33%). Scorer reproduction verified.

## 2. The two-part test for `implied` on a required field (the F1-vs-D3 line)

`implied` requires BOTH:
  (i)  the practice is generalized beyond a single worked example — habitual/imperative
       framing or an explicit general justification; AND
  (ii) the referent is executable within the template's own structure.
F1 passes both. D3 fails (ii) — and (i) alone ("I look to...") is why it reads as debatable
in isolation. Corollary for specified-vs-implied: `specified` additionally requires the rule
to be executable AS STATED (parameters included); D2's unquantified "big" caps it at implied.
This test is the spec for any future status mechanism (P3e-5).

## 3. T-0001 — statuses ratified; claims rubric adjudicated

All fixture statuses ratified by the live run's agreement (grounding passed, 0 retries).
Claims: live 10 vs fixture 5 tripped the +/-1 count tolerance. Transcript enumeration
confirms ~10 real claims (both worked-example outcomes, "a lot of times it will be
defended", "I guarantee you will become a funded trader in 90 days", etc.). Rule 4 orders
exhaustiveness, so count-matching a curated fixture measures curation agreement, not
quality, and punishes correct behavior.

DECISION — claims-count tolerance REMOVED, replaced by COVERAGE:
  - The fixture claims list is the REQUIRED CORE, not a cap. Every fixture claim must be
    covered by >=1 extracted claim (quote-fragment overlap; fixture quotes may contain
    ellipses joining non-contiguous spans — match per fragment), with an agreeing testable
    flag.
  - Extras are correct behavior, but EVERY extracted claim quote must be grounded verbatim
    in the transcript (the old count check could not catch a hallucinated claim; this can).
  - Fixture claims lists unchanged. Runtime grounding of claims[] in extract.py is NOT part
    of this slice — flagged for P3e-5.
This is an adjudicated spec change making the assert strictly more meaningful — not tuning.

## 4. Prose corrections (fixture-aligned; fixtures untouched)

  - WIT-T-0001 verdict: 17/25 (~68%) -> 18/27 (~67%).
  - WIT-T-0002 verdict: ~7/25 (~28%) -> 9/27 (~33%).
  - WIT-T-0002 "Required-to-execute fields missing" line was WRONG in prose ("D1, D3, F2
    (+E1, F4)"): the scorer set is B1, D1, D3, D4, F2|F4. E1 is not in the required set and
    carries a §5 default; D4/F4 defaults are entry-conditional and earn no credit here
    because no entry trigger is stated.
  - WIT-T-0002 C2 row said "implied concept, no rule" — vocabulary collision with the
    status enum; reworded to unspecified.

## 5. Consequences

  - Anchors are now safe to tune toward. Next quality slice (P3e-5): a per-required-field
    "stated executable rule vs narrated example" mechanism encoding §2's two-part test;
    success = live T-0002 class B with >=75% status match to the ratified fixture.
  - With coverage semantics, golden T-0001 is expected to pass end-to-end; T-0002 remains
    expected-fail on class until P3e-5 ships.

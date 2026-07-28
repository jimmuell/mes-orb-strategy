Platform   : Claude Code (VS Code, MacBook Air)
Project    : WillItTrade (WIT)
Repo       : github.com/jimmuell/mes-orb-strategy   (branch: main)
Prompt     : WIT-P3o
Local path : ~/Projects/mes-orb-strategy

STEP 0 — GATE (any failure => STOP and report; do not proceed)
  1. git checkout main && git pull --ff-only
  2. git log --oneline -1 must show 3b2456e (WIT-P3n: session-3 close-out — Notion tracker
     read/update in continuity rules). Any other HEAD => STOP, report actual HEAD.
  3. git status --porcelain clean (the known untracked pine/mes_net_pnl_v2.pine is fine).
     Confirm origin URL and local path match the header.
  4. This slice makes NO live LLM calls. Do NOT set WIT_RUN_LLM_TESTS; do NOT run the gated
     golden tier. It is EXPECTED to still fail T-0002 on class until the status mechanism
     ships — that is the recorded finding, not a bug to fix here.
  5. Do NOT touch: api/tests/fixtures/*.json, api/wit/extraction/*.py, the scorer, any
     threshold. The adjudication RATIFIED the fixtures; they stay byte-identical.

CONTEXT
  Lead-engineer adjudication of the two calibration anchors is COMPLETE (Cowork chat,
  2026-07-28). All nine disputed T-0002 field statuses ratified as committed; T-0001 statuses
  ratified by the live run's agreement. This slice commits the adjudication record, aligns
  T-file prose with the fixtures, replaces the golden claims-count tolerance with coverage
  semantics (adjudicated spec change), annotates WIT-03 §8 item 7, and updates the handoff.
  (Originally authored as WIT-P3n; renumbered P3o after an unrelated close-out commit took
  the P3n id.)

TASK
T1. Create docs/wit/log/WIT-P3o-adjudication.md with EXACTLY the content between the
    BEGIN/END markers (exclusive):
----BEGIN FILE docs/wit/log/WIT-P3o-adjudication.md----
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
----END FILE----

T2. docs/wit/WIT-T-0001-volume-profile-orb-template.md — ONE edit in the Completeness
    verdict line:
      old: "Completeness score: **17/25 fields specified or implied (~68%)**"
      new: "Completeness score: **18/27 fields specified or implied (~67%)**"

T3. docs/wit/WIT-T-0002-candle-formation-claim-template.md — THREE edits:
  a) C2 table row:
      old: | Regime/trend filters (C2) | `implied concept, no rule` — "choppy" vs. bigger-picture trend, never defined numerically |
      new: | Regime/trend filters (C2) | `unspecified` — "choppy" vs. bigger-picture trend invoked as a concept, never defined numerically; no executable rule |
  b) Required-missing line:
      old: **Required-to-execute fields missing: D1, D3, F2 (+E1, F4).** Not defensibly assumable — inventing them would test *our* strategy, not his claim.
      new: **Required-to-execute fields missing (scorer set): B1, D1, D3, D4, F2|F4.** (E1 is not in the required set and carries a §5 default; D4/F4 defaults are entry-conditional and earn no credit here because no entry trigger is stated.) Not defensibly assumable — inventing them would test *our* strategy, not his claim.
  c) Verdict line:
      old: "Completeness ~7/25 fields specified or implied (~28%)"
      new: "Completeness 9/27 fields specified or implied (~33%)"
    Grep each old string first; if any is not found verbatim, STOP and report the actual text.

T4. docs/wit/WIT-03-api-contract.md §8 item 7:
      old: 7. Disable code-execution endpoints for WIT traffic.
      new: 7. Disable code-execution endpoints for WIT traffic. **✓ shipped P3g (`DISABLE_EXEC_ENDPOINTS=1` kill switch; left unannotated in P3l).**

T5. api/tests/test_extraction_golden.py — TWO edits:
  a) Docstring TOLERANT bullet:
      old: - claims[] count within +/-1 of the fixture
      new: - claims[] COVERAGE (P3o): every fixture claim matched by quote-fragment overlap
        with an agreeing testable flag; extras allowed, every extracted claim quote grounded
  b) Replace these two lines:
          # ── TOLERANT ──
          assert abs(len(tpl["claims"]) - len(fixture["claims"])) <= 1, "claims count off by >1"
      with (4-space indent, inside the test function, exactly):
          # ── TOLERANT: claims coverage (P3o adjudication) — the fixture list is the
          # REQUIRED CORE, not a cap. Rule 4 asks for EVERY claim, so extras are correct
          # behavior; what matters is (a) no fixture claim missed, (b) every extracted
          # claim grounded. Fixture quotes may join non-contiguous spans with an ellipsis —
          # match per fragment.
          def _fragments(q):
              return [f for f in re.split(r"\.\.\.|…", q or "") if len(_norm(f)) >= 12]

          ex_quotes = [_norm(c.get("quote") or "") for c in tpl["claims"]]
          for fc in fixture["claims"]:
              frags = _fragments(fc["quote"]) or [fc["quote"]]
              hit = [i for i, eq in enumerate(ex_quotes)
                     if eq and any(_norm(fr) in eq or eq in _norm(fr) for fr in frags)]
              assert hit, f"fixture claim not covered: {fc['claim']!r}"
              assert any(tpl["claims"][i].get("testable") == fc["testable"] for i in hit), \
                  f"claim covered but testable flag differs: {fc['claim']!r}"
          for c in tpl["claims"]:
              q = c.get("quote")
              assert q and _norm(q) in ntx, f"claim quote not grounded: {q!r}"
      Do not change any other assert, threshold, or constant in the file.

T6. docs/wit/SESSION-HANDOFF.md — FIVE edits:
  a) In "Current state", replace the sentence:
      "main = the WIT-P3n session-3 close-out commit."
     with
      "main = the WIT-P3o commit (anchor adjudication: fixtures ratified, claims rubric to
      coverage, prose ratios aligned); prior 3b2456e (P3n close-out)."
  b) In the session-arc sentence, replace the ending
      "→ P3n close-out."
     with
      "→ P3n close-out → P3o anchor adjudication."
  c) Replace the ENTIRE block from the line beginning
      "▶ RESUME HERE — LEAD-ENGINEER DECISION FIRST: adjudicate the calibration anchors"
     through the paragraph ending
      "...(P3a could not verify live deploy state from the repo)."
     with:
      ▶ RESUME HERE — adjudication DONE (P3o); choose the next slice
      The calibration-anchor adjudication is complete (record:
      docs/wit/log/WIT-P3o-adjudication.md). All nine disputed T-0002 statuses RATIFIED as
      committed; both fixtures byte-identical; the A-vs-B miss is MODEL behavior, and the
      anchors are now safe to tune toward. Codified rule for any status mechanism: `implied`
      on a required field needs BOTH (i) the practice generalized beyond a single worked
      example (habitual/imperative framing or an explicit general justification) AND (ii) a
      referent executable within the template's own structure — F1 passes both; D3 fails
      (ii) ("that high" exists only inside a discretionary H&S exhibit). `specified`
      additionally requires executability AS STATED. Claims rubric: count tolerance replaced
      by COVERAGE (fixture list = required core; extras fine, all grounded) — golden T-0001
      expected to pass end-to-end now; T-0002 still expected-fail on class until the
      mechanism ships. Two candidate next slices, either order:
      1. P3e-5 (lead recommends FIRST): per-required-field "stated executable rule vs
         narrated example" mechanism encoding the two-part test (candidates: second-pass
         status critic, or per-field justification in the tool schema); also extend RUNTIME
         grounding to claims[] quotes (the golden now checks them; extract.py does not yet).
         Success = live T-0002 classes B with >=75% status match to the ratified fixture.
      2. POST /wit/v1/extract (architecture DECIDED at P3m-a, superseding WIT-03 §4: the
         ENGINE exposes extraction; Supabase merely calls it — one implementation of the
         product's core trick). Auth + budget like the other /wit/v1 routes; returns
         {template, completeness, raw_meta}; anthropic moves from requirements-dev.txt to
         the SHIPPED runtime lock and must pass the ADR-050 audit gate.
      Still open in Jim's lane: confirm the engine is actually deployed on Railway and set
      WIT_ENGINE_SERVICE_KEY, WIT_CALLBACK_HMAC_SECRET, DISABLE_EXEC_ENDPOINTS=1 (P3a could
      not verify live deploy state from the repo).
  d) Replace the open-items bullet beginning "* NEW — calibration anchors:" (entire bullet)
     with:
      * DONE P3o — calibration anchors adjudicated: fixtures ratified 9/9, T-file ratios
        restated (18/27, 9/27), claims rubric now coverage-based.
  e) Replace the open-items bullet beginning "* NEW — WIT-03 §8 item 7" (entire bullet) with:
      * WIT-03 §8: items 3 and 6 remain genuinely open (item 7 annotated ✓ in P3o).

T7. Archive + index:
  a) Write this ENTIRE prompt verbatim (from the "Platform :" header line through the
     completion-marker line) to docs/wit/prompts/WIT-P3o.md.
  b) docs/wit/log/README.md: add one row each for WIT-P3o-adjudication.md and
     WIT-P3o-report.md, matching the existing File | Prompt | Content style — plus the
     MISSING row for WIT-P3n-report.md (the P3n commit did not index itself).
  c) docs/wit/prompts/README.md: add rows for WIT-P3n.md and WIT-P3o.md if absent.

T8. Full CI-safe suite: cd api && BACKTEST_API_KEY=k python -m pytest -q
    Expected: 212 passed / 0 failed / 2 skipped. Anything else => STOP and report.

T9. Single commit DIRECTLY to main (suite from T8 is the gate), subject:
      WIT-P3o: anchor adjudication — fixtures ratified, claims rubric to coverage, prose ratios aligned
    staging every file from T1–T7 plus the T10 report (explicit paths only — never git add -A).
    Push; record CI status.

REPORT BACK — write verbatim to docs/wit/log/WIT-P3o-report.md and stage with the commit:
  1. STEP 0 gate result (HEAD hash seen, tree state).
  2. Per-edit confirmation for T1–T7 (grep proof per old->new; note any old string not
     found verbatim and what you did — which must have been STOP).
  3. Suite counts before commit.
  4. Commit hash; CI status after push.
  5. Anything unexpected.
Final line, exactly one of:
WIT-P3o — Completed
WIT-P3o — Partial: <one-line reason>

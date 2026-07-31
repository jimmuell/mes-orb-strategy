Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P5l

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — gate
  git remote -v && pwd
  Confirm the remote is jimmuell/mes-orb-strategy at the path above. If not, STOP and report.
  git rev-parse HEAD && git rev-parse origin/main
  Both must be 7182a9a (WIT-P5k). If either differs, STOP and report.
  Do NOT pull, reset, checkout or stash. Never run git add -A.

TASK — read-only forensic investigation of the value_area_pct units defect

  CONSTRAINTS, all binding:
    Change no engine source, schema, contract, fixture, golden, threshold or prompt.
    Change no production data. Invalidate no cache. Alter no published report.
    Do NOT implement the fix. The deliverable is a report.
    Temporary diagnostic instrumentation is allowed during the run and must be reverted;
    confirm a clean git status before staging.
    Do NOT treat WIT-P5i, WIT-P5j or WIT-P5k as established. They are PRIOR CLAIMS to be
    independently verified or refuted. Cite your own evidence.
    Do not reopen unrelated closed work (P3q extraction quality) unless direct evidence
    requires it; machine-channel conformance (P4k) is open and in scope.

  LABEL every conclusion exactly one of: Confirmed / Strongly supported / Possible /
  Refuted / Not yet verifiable. Every conclusion cites file path, symbol, line range, and
  the runtime artifact or test output it rests on.

  LEAD-SUPPLIED EVIDENCE — front-office facts you cannot see from this repo. The cache and
  the wire submission live in the Lovable project jimmuell/strategy-verdict-lab and the
  Supabase database, neither of which is reachable from here. Treat the following as
  lead-verified input, mark it as such, and do not attempt to re-derive it:
    Four production evaluations exist, all of the same transcript (sha256 cb69a23c…).
    All four stored wire configs carry setup_entry.params.value_area_pct = 70.
    Engine-returned provenance config_hash: three are
      e6f2045dd09f20abeb1acf7d02f9dd13a24f8e35bd8d2766e5e4326e783f44b4
    and one is
      d7876624f4d165c8f8e1747b153c5f73bb4199a881a03bc5fdfd540dd6e2df35
    The differing one varies only in exits.stop.ref and session.trade_window[0].
    The cache key is (source_transcript_hash, extractor_version) with the constant
      EXTRACTOR_VERSION = "wit-extract-v1"
    in supabase/functions/_shared/extraction-cache.ts, and findCachedTemplate returns the
    OLDEST matching row.
    On a cache hit, supabase/functions/_shared/evaluation-chain.ts function
    advanceFromCachedTemplate copies the stored wire_config verbatim and makes NO call to
    /wit/v1/map. Mapping is skipped entirely on that path.
    Templates are inserted once and never updated after wire_config is written.

  1. FIELD INVENTORY AND DATA FLOW
     Search the repo for value_area_pct and for the prose forms of a value-area percentage.
     Identify every location where the value is written in prose, held in a fixture,
     produced by extraction, parsed, mapped, validated, serialized, passed across an API
     boundary, consumed by the engine, or rendered in a report.
     Produce a stage-by-stage data-flow description from source text to engine input,
     quoting the exact value at each stage you can observe in this repo. For the stages
     that live in the front office, use the lead-supplied evidence above and label it.

  2. AUTHORITATIVE CONTRACT
     Determine what governs value_area_pct: JSON Schema, dataclass, type hint, docstring,
     or nothing. Answer each explicitly, with evidence, not from the field name:
       Is the expected domain 0.0-1.0, or 0-100, or undefined?
       Is there runtime validation anywhere on the wire path?
       Is there static typing that would catch 70?
       Is there normalization at any boundary?
     Then state the engine's actual behaviour for each of these inputs, by reading the code
     and by running where practical: 0, 0.7, 1, 1.0, 70, 100, null, and the string "0.70".
     For each, say whether it is accepted, rejected, clamped, or silently reinterpreted,
     and what value-area band results.

  3. THE CALIBRATION FIXTURE
     Inspect WIT-T-0001 (its fixture JSON and docs/wit/WIT-T-0001-volume-profile-orb-
     template.md). Verify whether it carries 70 in human prose and 0.7 in its machine
     parameter, and give both current line numbers.
     Then classify the defect, choosing all that apply and justifying each: extraction
     error, mapping error, schema-conformance error, prompt-design error, fixture-design
     error, missing-validation error. If the fixture's prose plausibly taught the extractor
     to emit the prose form into the machine channel, say so and mark the confidence.

  4. ENGINE BEHAVIOUR AND WHY THE TRADE COUNT MOVES
     Locate the exact consumer of value_area_pct in api/wit/volume_profile.py and quote the
     computation. Explain mechanically why 70 changes the trade count rather than crashing,
     and what VAH/VAL become. Verify the claim that the band expands to the full opening
     range by printing value_area_fraction, VAH and VAL for at least three separate
     sessions, not one.

  5. REPRODUCTION AND DIVERGENCE
     Run CONFIG A from WIT-P5j twice over 2008-01-02 to 2026-04-09, identical in every
     respect except value_area_pct 70 versus 0.70. Report the six headline metrics for both
     at full precision and confirm or refute:
       70   trades 4161, net_pnl -8465.890083640523, PF 0.9193420635532844, WR 37.89954337899543
       0.70 trades 4623, net_pnl -12823.770111516336, PF 0.8696540178212495, WR 35.215228206792126
     Record the engine version, the dataset filename with its sha256 and row count, and the
     config_hash of each run.
     Then compare the two trade ledgers and report the FIRST differing trade: its entry and
     exit timestamps, direction, fill prices, exit reason, and the VAH/VAL that session
     under each setting. Report the cumulative P/L divergence from that trade onward.

  6. PUBLISHED-REPORT PROVENANCE
     Do not accept the prior claim that WIT-0001 ran at 0.70. Verify it. Identify the
     generating code path, its input settings, the result artifact, its timestamps and the
     code version. State whether the metrics displayed in
     docs/wit/reports/WIT-0001-volume-profile-orb.md match a 0.70 run or a 70 run — by
     re-running its configuration if that is possible from this repo, and saying so if it
     is not.
     Conclude with exactly one of: the report is fully correct; the verdict is correct but
     the metrics are wrong; the prose is correct but the evidence is mismatched; no issue.
     Keep the technical finding separate from whether a correction notice is warranted.

  7. THE SAME DEFECT CLASS ELSEWHERE — this section is the one most likely to find
     something new; do not rush it.
     Enumerate EVERY machine-readable field in the template schema, the config contract and
     the engine that represents a percentage, ratio, probability, fraction or multiple.
     Include at minimum value_area_pct, win_rate, max_drawdown_pct, time_in_market,
     r_multiple target value, slippage_ticks, commission_per_side, any confidence or
     completeness score, and anything else you find.
     For each, produce a row: field, where defined, expected unit, allowed range, is it
     validated, is it typed, could a prose-form number pass silently where a fraction is
     expected, and what the consequence would be. Rank by risk.
     Explicitly flag any field where prose and machine representations could differ and no
     validation would catch it.

  8. CACHE IMPACT
     Using the lead-supplied evidence, state whether a mapper-only fix would leave the four
     existing filed readings incorrect, and why. Identify what the version constant governs,
     what bumping it would invalidate, and whether invalidation is all-or-nothing or
     targeted. Estimate the cost of a full invalidation in engine time and extraction calls
     per affected transcript, using the measured extraction time of roughly 180-280 seconds
     and three model calls per extraction.

  9. FIX DESIGN
     Do not propose a bare "if value > 1: value /= 100" unless you can prove it correct for
     every valid input; if you propose it, prove it or discard it.
     Evaluate and recommend among: typed schema constraint on the contract and template
     schema; validation at one documented boundary; rejection of ambiguous values;
     normalization with a disclosed assumption code alongside the existing E1/F4/F5/H1/H2
     mechanism; a field rename such as value_area_fraction or value_area_percent.
     Address the rename explicitly: what would have to change, what it would cost, and
     whether it is worth it.
     IMPORTANT POLICY TENSION, present it rather than resolve it: the founder has not yet
     chosen between rejecting a bare 70 as ambiguous and normalizing it with a disclosed
     assumption. Rejection is the purest stop-and-report behaviour but will fail audits of
     sources that correctly say "70%", because extraction is closed for v1 and emits the
     prose form. Normalization keeps those audits working at the cost of reinterpreting a
     user's strategy, which must then be disclosed in the report. Lay out both, with the
     concrete consequences of each for the four existing audits, and recommend one.

  10. REGRESSION TEST PLAN
     Design, do not implement, a test plan covering: the boundary values from section 2;
     fixture-to-extraction, extraction-to-mapper and mapper-to-engine contract tests; a
     cached-reading invalidation test; an end-to-end audit test; a golden trade-list
     comparison; a published-report provenance test; and property-based tests for whatever
     parsing the chosen design requires. State which tests are only meaningful under the
     rejection design and which only under the normalization design.

  11. FINAL REPORT — write to docs/wit/log/WIT-P5l-report.md with these sections in order:
     executive conclusion; confirmed facts; unconfirmed or refuted prior claims; complete
     data flow; authoritative unit contract; exact failure point; reproduction results
     including the first differing trade; published-report impact; cache impact; scope of
     affected audits; other vulnerable fields with the risk table; recommended fix;
     required migrations; required cache invalidation; regression-test plan; risks of the
     proposed fix; and the exact files and line ranges that would change.
     End with a go/no-go recommendation and the smallest safe ordered sequence of changes.

  12. Save this prompt verbatim to docs/wit/prompts/WIT-P5l.md. Confirm any temporary
     instrumentation has been reverted and git status is otherwise clean. Stage EXACTLY:
       docs/wit/prompts/WIT-P5l.md
       docs/wit/log/WIT-P5l-report.md
     Verify with git diff --cached --name-status, then commit with subject exactly:
       WIT-P5l: value_area_pct forensic investigation — read-only findings
     Then git push origin main. Leave the known LFS noise untouched.

  13. Run the test suite and report the counts. Baseline 308 passed / 0 failed / 2 skipped,
     and it must be unchanged.

REPORT BACK
  1. Executive conclusion, and your go/no-go.
  2. The authoritative contract finding, and the behaviour table for 0, 0.7, 1, 70, 100,
     null and "0.70".
  3. Which prior claims from P5i/P5j/P5k you CONFIRMED and which you REFUTED.
  4. The reproduction table and the first differing trade.
  5. The WIT-0001 provenance verdict, in the words offered in section 6.
  6. The vulnerable-fields risk table.
  7. Your recommendation on reject-versus-normalize, and on the rename.
  8. The smallest safe ordered sequence of changes.
  9. New HEAD sha, GitHub commit URL, staged file list.
  10. Suite counts.
  Final line, exactly: WIT-P5l — Completed

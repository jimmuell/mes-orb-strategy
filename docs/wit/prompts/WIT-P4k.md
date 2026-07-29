Platform:    Claude Code (paste this code into this platform)

Project:     WillItTrade (WIT)

Repo:        jimmuell/mes-orb-strategy

Prompt:      WIT-P4k

Local path:  /Users/jameslmueller/Projects/mes-orb-strategy

STEP 0 — repo confirmation gate

  Run `git remote -v && pwd && git log --oneline -3`. Confirm the remote is
  jimmuell/mes-orb-strategy, the path is the local path above, and HEAD is a8b272a
  (WIT-P4j). If HEAD is anything else, STOP and report what you found. Read nothing,
  edit nothing, run nothing and commit nothing before this passes.

  Then read docs/wit/log/WIT-P3q-adjudication.md §2 and api/wit/extraction/schema.py.

  LEAD RATIFICATION, in force for this slice: P3q closed prompt-hardening aimed at
  extraction QUALITY against the ratified fixtures. This slice is MACHINE-CHANNEL
  CONFORMANCE — the mode/params channel from WIT-P3c-1 — not quality tuning. No fixture,
  no golden, no threshold, and no basis/status/claims rule may change. If any of those
  move, you have exceeded the ratification: STOP and report.

TASK

  Make the extractor's machine channel enforceable, so a field that is credited but
  carries no mode token cannot silently reach the mapper.

  Fourth live end-to-end failure, 2026-07-29. The stored template shows D1 with

    status:       "specified"
    basis:        "stated_rule"
    source_quote: "This means that we're now going to only be looking for buys on this
                   trading day."
    value:        "Direction is decided by which level breaks: a body close above the
                   value area high means long only for the day; a break through the low
                   means short."
    mode:         null

  The prose is a textbook `vp_value_area_break` — the one bias token engine v1 supports —
  and the extractor described it correctly, credited it, quoted it, and then left the
  machine field empty. map_template refused with UNSUPPORTED_CONSTRUCT "D1: mode 'None'".

  Across three live runs of the same video the machine channel failed differently every
  time — an off-vocabulary token on D1, then a null E1, now a null D1 — while the prose
  was right in each case. The channel is unvalidated: schema.py accepts `mode` as "string
  or null" and checks nothing else, so nothing catches a missing or invalid token until
  the mapper, three minutes and one ensemble later.

  1. One shared source for the field → mode vocabulary

    FIELD_MODE_VOCAB currently lives in api/wit/mapper.py and the extraction side cannot
    see it without risking an import cycle (mapper already imports from
    wit.extraction.completeness). Move it to a neutral module both sides import — or
    derive both from contract/modes.md, which is already the declared source of truth.
    Whichever you choose, there must be exactly ONE definition after this slice, and the
    mapper's behavior must be unchanged.

  2. Validate the machine channel at extraction time

    In the extraction schema validation, for each field in that config-relevant set:

      a. A non-null mode MUST be a member of that field's declared vocabulary. An
         off-vocabulary token is an invalid extraction — caught here, not at map time.

      b. A field whose status is "specified" or "implied" MUST carry a non-null mode.
         Crediting a construct while leaving the machine channel empty is incomplete
         output.

      c. A field whose status is "unspecified" may carry a null mode — that is the §5
         default's job (WIT-P4i), not the model's.

    These failures must route into the EXISTING retry path, exactly as any other schema
    violation does. Do not add a new retry mechanism, and do not change retry counts.

  3. Never invent a token to satisfy the validator

    Nothing in this slice may guess, infer, or substitute a mode — not from the prose,
    not from a sibling field, not from a default. If the model cannot produce a declared
    token after its existing retries, the field stays null and the mapper refuses
    honestly, as it does today. An honest refusal is the correct outcome; a fabricated
    token is not.

  4. Prompt: the single instruction that makes the rule satisfiable

    The system prompt already lists the vocabulary per dimension. Add ONE instruction to
    the existing vocabulary block, no more: when you mark a config-relevant field
    specified or implied, you must also set its `mode` to one of that field's listed
    tokens; if no listed token matches what the source describes, leave mode null and
    describe the construct in `value` — never invent a token. Change nothing else in any
    prompt text: no rule wording, no field spec, no basis or status guidance.

  5. Tests and goldens

    Cover: an off-vocabulary mode on a config-relevant field fails validation; a
    specified field with a null mode fails validation; an unspecified field with a null
    mode passes; a valid template still passes unchanged; the mapper still behaves
    identically after the vocabulary move.

    Run the full suite. Both anchor goldens must be BYTE-IDENTICAL, and the two ratified
    fixtures must still validate cleanly — check that explicitly and say so. If ANY
    golden moves or a fixture fails validation, STOP and report; do not tune a golden,
    touch a fixture, or alter a threshold.

  Stage explicit paths only; never `git add -A`. Commit subject:
  `WIT-P4k: machine-channel conformance — mode tokens validated at extraction, one shared vocabulary`
  Push to origin main and report the commit hash and URL.

REPORT BACK

  Include: where the shared vocabulary now lives and how the import cycle was avoided;
  each validation rule as written; the exact prompt line added, quoted; how failures
  reach the existing retry path; each new test and what it proves; full suite counts
  before and after; explicit confirmation that both anchor goldens are byte-identical,
  both fixtures still validate, and no threshold or quality rule changed; the commit hash
  and GitHub URL. Commit the report verbatim to docs/wit/log/WIT-P4k-report.md in the
  same commit. End with exactly one line:

  WIT-P4k — Completed

  or

  WIT-P4k — Partial: <what's left>

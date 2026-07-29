# WIT-P4k — machine-channel conformance: mode tokens validated at extraction, one shared vocabulary

## STEP 0 + ratification
Gate passed: remote `jimmuell/mes-orb-strategy`, path `/Users/jameslmueller/Projects/mes-orb-strategy`,
HEAD **a8b272a** (WIT-P4j). Read `WIT-P3q-adjudication.md` §2 and `api/wit/extraction/schema.py`.
Ratification held: this slice is MACHINE-CHANNEL CONFORMANCE (the WIT-P3c-1 mode/params channel), not
extraction-quality tuning. No fixture, golden, threshold, or basis/status/claims rule changed (verified
in §5).

## The defect (fourth live end-to-end failure, 2026-07-29)
A Class-A extraction credited D1 `status: specified`, `basis: stated_rule`, quoted a textbook
`vp_value_area_break`, filled `value` correctly — and left `mode: null`. `map_template` refused with
`UNSUPPORTED_CONSTRUCT "D1: mode 'None'"`, three minutes and one ensemble after the fact. Across three
live runs the machine channel failed differently each time (off-vocab D1 → null E1 → null D1) while the
prose was right. The channel was unvalidated: `schema.py` accepted `mode` as "string or null" and
checked nothing else.

## 1. One shared vocabulary; import cycle avoided
`FIELD_MODE_VOCAB` moved VERBATIM from `wit/mapper.py` to a new neutral module **`api/wit/vocab.py`**
that imports nothing. Both sides now read the ONE definition: `wit.extraction.schema` and `wit.mapper`
each do `from wit.vocab import FIELD_MODE_VOCAB`. `mapper` re-exports it, so existing
`from wit.mapper import FIELD_MODE_VOCAB` callers (the WIT-P4h conformance test) are unchanged. **Cycle
avoided:** `vocab` has no imports; `schema → vocab` and `mapper → vocab` are leaf edges. The class-scoped
rule needs the scorer, but `wit.extraction.completeness` imports `schema` only function-locally, and to
be bulletproof `validate_template` imports `score_completeness` **lazily** (inside the rule). Test
`test_P4k_one_shared_vocabulary_definition` asserts `mapper.FIELD_MODE_VOCAB is vocab.FIELD_MODE_VOCAB
is schema.FIELD_MODE_VOCAB`. Mapper behavior is unchanged (G1/G2 byte-identical, §5).

## 2. Validation rules as written (in `wit/extraction/schema.py`)
- **(a) off-vocabulary mode — class-agnostic, per field, in `_validate_field`:**
  ```python
  if fid in FIELD_MODE_VOCAB and isinstance(obj.get("mode"), str) \
          and obj["mode"] not in FIELD_MODE_VOCAB[fid]:
      errs.append(f"fields.{fid}.mode {obj['mode']!r} is not a declared mode for this field "
                  f"(one of {sorted(FIELD_MODE_VOCAB[fid])}, or null)")
  ```
- **(b)/(c) credited-must-carry-mode — CLASS-SCOPED, at the end of `validate_template`:**
  ```python
  if isinstance(fields, dict):
      from wit.extraction.completeness import score_completeness   # lazy: avoid any import cycle
      try:
          cls = score_completeness(template).get("class")
      except Exception:
          cls = None
      if cls == "A":
          for fid in FIELD_MODE_VOCAB:
              f = fields.get(fid)
              if (isinstance(f, dict) and f.get("mode") is None
                      and f.get("status") in ("specified", "implied")):
                  errs.append(f"fields.{fid} is {f.get('status')} but has no mode — a credited "
                              f"config-relevant field must set mode to one of "
                              f"{sorted(FIELD_MODE_VOCAB[fid])} (WIT-P4k)")
  ```
  **Why class-scoped:** for a Class A template the field.mode channel IS the config channel, so a
  credited config-relevant field must carry it (rule b), while an `unspecified` field may be null (rule
  c — the §5 default's job, WIT-P4i). Class B's machine channel lives in `J1.params`, so its field.modes
  are legitimately null EVEN WHEN IMPLIED — the ratified fixture WIT-T-0002 has implied D2/F1 with null
  modes. Scoping by the SAME deterministic class the mapper branches on keeps T-0002 valid (§5).

## 3. Never invent a token
Nothing here guesses, infers, or substitutes a mode. Off-vocab → error; credited-null → error; both
route to the existing retry and, if the model cannot produce a declared token after its existing
retries, the field stays null and the mapper refuses honestly (as today). No prose→token inference, no
sibling-field copy, no default fill.

## 4. Prompt — the single instruction (quoted exactly)
Added ONE line to the existing vocabulary block in `_vocab_block`, nothing else:
> When you mark a config-relevant field specified or implied, you MUST also set its `mode` to one of
> that field's listed tokens; if no listed token matches what the source describes, leave mode null and
> describe the construct in `value` — never invent a token.
No rule wording, field spec, or basis/status/claims guidance was touched.

## How failures reach the EXISTING retry path
The rules append to `validate_template`'s returned error list. The orchestrator loop (`extract.py`) does
`errors = validate_template(template)` and, on any error, feeds it back and retries ≤ `max_retries` —
terminal `extraction_failed` if unfixed. No new retry mechanism; retry counts unchanged. A machine-
channel violation now routes identically to any structural schema violation.

## 5. Tests + goldens + fixtures
New (6): `test_completeness.py` — off-vocab mode fails; Class A specified+null-mode fails; unspecified
+null-mode passes; Class B implied+null-mode still valid (T-0002 clean); one-shared-vocabulary identity.
`test_extraction_prompt.py` — the new instruction line is present.
- Suite before (HEAD a8b272a): **281 passed / 0 failed / 2 skipped**.
- Suite after: **287 passed / 0 failed / 2 skipped** (281 + 6).
- **Both anchor goldens BYTE-IDENTICAL:** `test_mapper.py` G1 (T-0001 → `VPORBConfig()`) and G2
  (T-0002 → `EventStudyConfig()`) pass unchanged (the vocabulary move is a pure re-export; the mapper
  reads the identical set).
- **Both ratified fixtures STILL VALIDATE CLEANLY:** `test_completeness.py::test_fixtures_validate`
  asserts `validate_template(T-0001) == []` and `validate_template(T-0002) == []` — both green after the
  new rules (T-0001's credited config fields all carry valid modes; T-0002 is Class B so rule b is
  skipped). Confirmed explicitly.
- **No threshold or quality rule changed:** scorer `completeness.py` untouched; `api/tests/fixtures/*`,
  `contract/modes.md`, `schema/strategy-template.v1.json` untouched; the `_BASIS_ENUM`/status/claims
  validation and the prompt's basis/status/claims rules are unchanged. Staged files: `wit/vocab.py`
  (new), `wit/mapper.py`, `wit/extraction/schema.py`, `wit/extraction/prompt.py`, and two test files.

## Commit
- Subject: `WIT-P4k: machine-channel conformance — mode tokens validated at extraction, one shared vocabulary`
- Hash + URL: recorded in the report-back after push.

WIT-P4k — Completed

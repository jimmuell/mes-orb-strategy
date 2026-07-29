# WIT-P4h — contract conformance: entry.level had no carrier field, prompt offered an unmappable placement

## STEP 0
Gate passed: remote `jimmuell/mes-orb-strategy`, path `/Users/jameslmueller/Projects/mes-orb-strategy`,
HEAD **4328d45** (`WIT-P4g: report + lead verification …`). Read `docs/wit/log/WIT-P3q-adjudication.md`
(fixtures FINAL; R1–R3 residuals) and `backtest/MEMORY.md` before touching extraction code.

## The defect
A Class-A extraction set D1's mode to `va_high_low`; `map_template` returned
`UNSUPPORTED_CONSTRUCT ("D1: mode 'va_high_low' not supported in engine v1")` and the first live
end-to-end evaluation ended `failed`. The extractor was not wrong — `contract/modes.md`'s `entry.level`
row declared Field `D3/D1` with token `va_high_low`, and the prompt's `_vocab_block` rendered it as a
legal placement, but the mapper has no `entry.level` dimension: `FIELD_MODE_VOCAB` reads D1 as bias
`{vp_value_area_break, orb_break, none}` and D3 as trigger `{bar_close_beyond_level,
bar_body_beyond_level}`. In engine v1 the entry level is derived from the D2 volume profile (VAH/VAL);
`entry.level` has no consumer and must not be offered.

## 1. `contract/modes.md` — the entry.level row (Class A table)
BEFORE:
```
| `entry.level` | D3/D1 | `va_high_low` · `orb_high_low`† | — | VAH/VAL from the profile |
```
AFTER:
```
| `entry.level` | — | `va_high_low` · `orb_high_low`† | — | In v1 the entry level is derived from the D2 volume profile (VAH/VAL) and is not independently specified |
```
Field cell `D3/D1` → em dash `—`; Runner-realization restated to the v1-derived fact. Tokens, params,
dagger, and every other row unchanged. (The shipped runtime copy `api/_shipped/contract/modes.md` was
re-synced byte-identically per the P3s drift gate — see §4.)

## 2. `api/wit/extraction/prompt.py` — never offer a dimension no field can carry
New helper (derived from the parsed Field cell; `entry.level` is nowhere hardcoded):
```python
def _carrier_field_ids(field_cell: str) -> list[str]:
    return [t for t in re.findall(r"[A-K]\d+", field_cell or "") if t in FIELD_IDS]
```
`_vocab_block` guard as written:
```python
    # WIT-P4h: never offer a dimension whose Field cell names no real template field — a mode with
    # no carrier field is a contract defect, not a placement the extractor can make.
    for dim in sorted(d for d, r in recs.items()
                      if r["supported"] and _carrier_field_ids(r["field"])):
        r = recs[dim]
        params = f" params {{{', '.join(r['param_keys'])}}}" if r["param_keys"] else ""
        lines.append(f"    {dim} (field {r['field']}): mode ∈ {{{', '.join(r['supported'])}}}{params}")
```
`supported_modes()` gained the SAME guard (`... if r["supported"] and _carrier_field_ids(r["field"])`)
so the "supported vocabulary" and the rendered offer stay coherent — otherwise the existing
`test_system_prompt_offers_no_unsupported_token` (offered == supported) would break. After the guard,
`entry.level` (Field `—`) is offered nowhere.

## 3. New conformance test (the durable part)
`tests/test_extraction_prompt.py::test_offered_field_modes_conform_to_mapper`: for every dimension the
prompt offers whose Field cell names a mapper field.mode carrier, every named field must be in
`mapper.FIELD_MODE_VOCAB` and every supported token must be a member of `FIELD_MODE_VOCAB[field]`.
Dimensions whose modes live elsewhere (Class B in `J1.params`; `filters` `none`) name no carrier and
are correctly out of this surface. It iterates the CONTRACT (`_parse_modes`) so it runs against both
the old and new file.

FAIL, before the edit (current `contract/modes.md`):
```
AssertionError: 'entry.level' offers mode 'va_high_low' on field D3, but the mapper rejects it (FIELD_MODE_VOCAB[D3] = ['bar_body_beyond_level', 'bar_close_beyond_level'])
assert 'va_high_low' in {'bar_body_beyond_level', 'bar_close_beyond_level'}
tests/test_extraction_prompt.py:207: AssertionError
1 failed in 1.18s
```
PASS, after part 1 (Field `—` → entry.level names no carrier → skipped):
```
1 passed in 0.87s
```

## 4. No collateral damage
Full suite (`cd api && BACKTEST_API_KEY=k python -m pytest -q`):
- Before this slice (session open, HEAD 4328d45): **268 passed / 0 failed / 2 skipped**.
- After adding the new test but BEFORE fixing modes.md: **268 passed / 1 failed / 2 skipped** — the one
  failure was the new conformance test (the defect, shown above).
- After the full fix: **269 passed / 0 failed / 2 skipped** (268 + the new conformance test).

**No fixture, golden, or threshold was tuned.** The two anchor fixtures (T-0001/T-0002) carry no
`va_high_low` token: the mapper goldens `test_mapper.py` G1 (Class A → `VPORBConfig()`) and G2 (Class B
→ `EventStudyConfig()`) pass unchanged, and the network-gated extraction golden's fixtures are
untouched. `api/tests/fixtures/*.json` were not touched.

Two intended, in-scope updates were required and are NOT WIT-P3q fixture goldens:
- **`EXPECTED_SUPPORTED` (vocabulary golden)** dropped its `"entry.level": ["va_high_low"]` line — a
  deliberate vocabulary change (the whole point of the slice: entry.level is a contract defect removed
  as an offering). The test file's own docstring provisions this: "this golden is updated deliberately
  in that slice." Not a fixture golden; no threshold moved.
- **`api/_shipped/contract/modes.md`** (P3s drift copy) re-synced byte-identically to the edited
  contract file — required by the P3s drift gate whenever `contract/modes.md` changes.

## 5. Noticed but did NOT change
- `unsupported_modes()` still lists `entry.level: [orb_high_low]` (the `†` backlog token) with Field
  `—`. It is the declared-but-unsupported backlog view and no code consumes it as a placement; leaving
  it is the minimal change. `orb_high_low†` is now an orphaned backlog token (its dimension has no
  carrier field) — a candidate for a future modes.md cleanup, not touched here.
- The Class-A table has other multi-id Field cells that DO carry real fields and remain offered
  unchanged (`filters` C2/C3, `costs` H1/H2, and the Class-B `event`/`path_bucket`/`regime`/`timeframe`
  rows whose modes live in `J1.params`). The new conformance test correctly treats them as out of the
  `FIELD_MODE_VOCAB` field.mode surface.

## Commit
- Subject: `WIT-P4h: contract conformance — entry.level had no carrier field, prompt offered an unmappable placement`
- Hash + URL: recorded in the report-back after push.

WIT-P4h — Completed

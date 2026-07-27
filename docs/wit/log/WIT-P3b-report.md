# WIT-P3b — template schema + completeness scorer + golden fixtures

Prompt: **WIT-P3b** — the completeness foundation (routing keystone). No mapper, no LLM, no network. On the `wit-phase3` umbrella branch (no re-branch, no merge).

---

## 1. STEP 0 result
- On `wit-phase3`: **yes**. HEAD = **`d33a24c`** (WIT-P3a recon): **yes**.
- Tree clean: **yes** — only the known untracked `pine/mes_net_pnl_v2.pine` (ignored). `git lfs status` clean; no genuine edits.

## 2. Files created + jsonschema decision

Created (6):
- `schema/strategy-template.v1.json` — canonical WIT-02 template schema (valid JSON Schema Draft 2020-12).
- `api/wit/extraction/__init__.py`, `api/wit/extraction/schema.py`, `api/wit/extraction/completeness.py`.
- `api/tests/fixtures/WIT-T-0001.template.json`, `api/tests/fixtures/WIT-T-0002.template.json`.
- `api/tests/test_completeness.py` (10 tests).
- This report `docs/wit/log/WIT-P3b-report.md`.

**jsonschema decision: hand-rolled structural validator, ZERO new deps.** Rationale: adding `jsonschema` would pull `attrs` / `referencing` / `rpds-py` / `jsonschema-specifications` into the **ADR-049 full-transitive runtime lock** and the **ADR-050 audit surface** — a real dependency-surface expansion for what is simple structural checking. `api/requirements.txt` is therefore **untouched** (confirmed, no diff) and **no audit-gate run was required**. The schema file remains a *valid* Draft-2020-12 JSON Schema, and `schema.py` reads the field-id set and the status enum **from it** (single source of truth), so an external consumer (the Supabase `wit-extract` function) can still run `jsonschema` against the same file. `validate_template()` enforces the load-bearing rules directly: all 27 field ids present, field-object shape, `status` enum, `class` enum, array element shapes, and WIT-02 §4.1 (specified/implied require a non-null `source_quote`) — **exempting section J**, which is WIT-authored and has no transcript to quote.

## 3. Scorer output for both fixtures

```
WIT-T-0001:  valid=True   {score: 66, class: "A", required_missing: []}       assumption_fills = 6
WIT-T-0002:  valid=True   {score: 21, class: "B", required_missing: ["B1","D1"]}  assumption_fills = 8
```
- **T-0001 → A ✅**, **T-0002 → B ✅** (the hard contract). Both validate against the schema.
- **`assumption_fills`:** T-0001 = **6** (B3, E1, F4, F5, H1, H2) — exactly at the Class-A limit of ≤6 and matching the template's own prose ("Assumptions applied: 6 … at the Class A limit"). The prompt's "~5" anchor is approximate; 6 is the faithful count and passes. T-0002 = 8 (well over the limit — reinforces not-A).

**Surprises, explained (both worth lead-engineer eyes):**

1. **T-0002 `required_missing` is `["B1","D1"]` (mechanical), narrower than the template prose's semantic "D1, D3, F2".** This is the pinned mechanical rule working exactly as specified, not a bug:
   - `satisfied(f) = specified/implied OR (unspecified AND f has a §5 default)`. The §5 default set includes **D3, D4, F4** (unconditional). So on T-0002, **D3** (unspecified) is *mechanically credited* by its close-vs-touch default, and the **F2|F4 exit pair** is satisfied because **F4** has a default — even though semantically there is no entry trigger to disambiguate and no exit to default. The human author judged D3/F2 missing on meaning; the mechanical rule credits them on §5-membership.
   - **B1** *is* mechanically missing (unspecified, and B1 has **no** §5 default) — the prose omitted it because "WIT tests ES" is treated as the instrument, but mechanically an unspecified B1 with no default flags. **D1** is missing both ways.
   - **Net: the class is B under either reading** (required_missing non-empty and ≥1 testable claim), so routing is unaffected. Only the *set* differs. If we want the mechanical `required_missing` to match human semantics, the fix would be to make **D3/D4 defaults conditional on an entry trigger existing** (like G1's daily-setup condition) — a deliberate policy change I did **not** make (the prompt pinned the rule). Flagging for review.

2. **`score` (66 / 21) is the prompt's weighted-B–H metric, not the prose's unweighted 17/25 (68%) and 7/25 (28%).** Different definitions by design: my formula weights required fields ×2 over B–H only and credits **status** (specified/implied), not §5-defaults. Directionally consistent (A ≫ B); reported as the "softer defined metric" per the prompt.

## 4. Exact required-field mapping + §2-vs-§6 reconciliation

**Required set (named constants in `completeness.py`, cited to WIT-02 §3):**
- `REQUIRED_BASE = {B1, B2, D1, D2, D3, D4, F1}` — each individually required.
- `EXIT_PAIR = (F2, F4)` — satisfied if **either** is satisfied; if neither, the token **`"F2|F4"`** is added to `required_missing`.
- `satisfied(f)` = `status ∈ {specified, implied}` **or** (`status == unspecified` **and** `f` has a §5 default).
- **§5 defaults:** `UNCONDITIONAL_DEFAULTS = {E1, H1, H2, F5, F4, D3, D4, B3}`; **G1** is *conditional* — its default applies only "when a daily setup is implied," which I encode deterministically as **G1 has a default iff `G1.assumption` is non-null** (the extractor records the daily-setup default). This is why T-0001 (G1 implied, daily setup) and T-0002 (G1 unspecified, no daily setup) diverge on G1.
- `assumption_fills` = count over **B–H** of fields that are `unspecified` **and** have a §5 default. Class A ⇔ `required_missing` empty **and** `assumption_fills ≤ 6`. Class B ⇔ not A **and** ≥1 `claims[]` with `testable == true`. Class C ⇔ otherwise.
- **Score weights:** `REQUIRED_WEIGHT_FIELDS = {B1,B2,D1,D2,D3,D4,F1,F2,F4}` weight 2 (both members of the exit pair carry the heavy weight); all other B–H fields weight 1; `specified/implied` = full credit, `unspecified` = 0; `score = round(100·earned/total)`.

**§2-vs-§6 reconciliation (per prompt):** §6 wins for structure. A2/A3 remain **field objects** (status/value/source_quote/assumption like every field), but the machine-readable rows live in the **top-level `claims[]` and `consistency_flags[]` arrays**. A reconciliation `$comment` is at the top of the schema file. **Field-count note:** §2's header says "25 fields" but its field tables enumerate **27 ids** (A1–A3, B1–B3, C1–C3, D1–D4, E1, F1–F5, G1–G2, H1–H2, I1, J1–J2, K1). I included **all 27** (the tables are authoritative for the field set) and documented the 25-vs-27 discrepancy in the schema `$comment` and here.

## 5. Test suite result + anything unexpected
- New: `test_completeness.py` — **10 passed** (schema field count, both fixtures validate, bad-status + missing-quote rejection, J-exemption, T-0001→A, T-0002→B, exact `required_missing`, score range + A>B, stored-vs-recomputed completeness match, and a Class-C path when testability is stripped).
- **Full suite: 152 passed** (142 prior + 10 new), 0 failed. No regression.
- Unexpected: only the two items in §3 (T-0002 mechanical `required_missing` narrower than prose; weighted score ≠ prose count) — both explained, neither changes the class routing. No dependency added, no audit-gate run needed.

WIT-P3b — Completed

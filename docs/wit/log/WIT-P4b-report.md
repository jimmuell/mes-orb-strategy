# WIT-P4b — POST /wit/v1/map: template→config mapping gets an HTTP surface (sync)

## 1. STEP 0
HEAD **5a18069** (WIT-P4a) — matches. Tree clean except the known untracked
`pine/mes_net_pnl_v2.pine`. Read WIT-04 §6 (the spec) before writing. No LLM calls. **Nothing under
`api/wit/` was modified** — `map_template` is used AS IS.

## 2. The endpoint as committed (verbatim)
```python
class WitMapRequest(BaseModel):
    template: dict


@app.post("/wit/v1/map", dependencies=[Depends(verify_wit_key)])
async def wit_map_template(req: WitMapRequest):
    try:
        return map_template(req.template)              # 200; body = mapper output VERBATIM
    except UnsupportedConstruct as e:
        return _wit_error(400, "UNSUPPORTED_CONSTRUCT", str(e),
                          {"field": e.field, "mode": e.mode})
    except UntestableStrategy as e:
        # Class C is a PRODUCT OUTCOME, not a 4xx (WIT-04 §6).
        return {"kind": None, "class": e.cls, "untestable": True}
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        # WIT-P4b: AttributeError added to the spec's (KeyError,TypeError,ValueError) tuple so a
        # structurally-malformed template (e.g. a non-dict `fields`) returns a clean 400 instead of
        # a 500 — case-d's stated intent ("malformed template -> INVALID_CONFIG"). Reported.
        return _wit_error(400, "INVALID_CONFIG", f"malformed template: {e}", {})
```
Placed immediately after `GET /wit/v1/runs/{run_id}` and before the `POST /wit/v1/extract` banner.
`map_template` added to the existing `from wit.mapper import (...)`. Sync — no run store, no
callback, no background task, no budget, no idempotency. `WitRunRequest` / `WitExtractRequest` and
every existing route are untouched.

**One reported deviation from T1's literal spec:** the malformed-input catch is
`(KeyError, TypeError, ValueError, AttributeError)` — `AttributeError` added to the specified tuple.
Reason in §6.

## 3. Test list (`tests/test_wit_map.py`, 10 tests — all PASS)
1. AUTH — no header → 401 **PASS**; wrong bearer → 403 **PASS**; `WIT_ENGINE_SERVICE_KEY` unset →
   503 **PASS**.
2. **GOLDEN Class A (T-0001)** **PASS** — `resp.json() == map_template(fixture)` (pure pass-through)
   AND `strategy_config_to_vporb(resp.json()["config"]) == VPORBConfig()`. **Exact equality, untuned.**
3. **GOLDEN Class B (T-0002)** **PASS** — `resp.json() == map_template(fixture)` AND
   `event_study_config_to_engine(resp.json()["config"]) == EventStudyConfig()`. **Exact equality, untuned.**
4. Class C template → `200 {"kind": null, "class": "C", "untestable": true}` **PASS**.
5. Unsupported mode (junk `D2.mode`) → 400 UNSUPPORTED_CONSTRUCT, `detail.field=="D2"`,
   `detail.mode=="not_a_real_mode"` **PASS**.
6. Malformed input (see §6 for the spec-vs-reality delta) — `{}` → **200 untestable** (empty = Class C)
   **PASS**; `{"fields": "nonsense"}` → 400 INVALID_CONFIG **PASS**.
7. NO STATE — same template twice → byte-identical bodies; run-store length unchanged across the
   two calls **PASS**.

Both goldens verified by exact `==` on both the raw pass-through body and the round-tripped engine
config; neither assertion was adjusted.

## 4. Suite counts
Before: **258 passed / 0 failed / 2 skipped**. After: **268 passed / 0 failed / 2 skipped**
(258 prior unchanged + 10 new). No pre-existing test changed status.

## 5. Commit + CI
- Commit hash: this commit — see `git log --oneline -1`
  (`WIT-P4b: POST /wit/v1/map — template→config mapping gets an HTTP surface (sync, goldens exact)`).
- CI status incl. the ADR-050 security gate: recorded in the report-back after push. This slice adds
  NO dependency, so the gate must stay green.

## 6. Anything unexpected — the two malformed-input example inputs in T2 case 6 DIVERGE from reality
Both goldens and every functional case passed exactly. The one place the spec's assumptions did not
match the shipped mapper is T2 case 6's two example inputs. I did NOT tune anything to hide this — I
tested the TRUE behavior and flag it here for lead ratification:

* **`{}` → 200 untestable, NOT 400.** `map_template({})` → `score_completeness({})` returns class
  **C** → `UntestableStrategy(cls="C")` → the endpoint's Class-C branch → `200 {"kind": null,
  "class": "C", "untestable": true}`. This is CORRECT product behavior: an empty template is a
  strategy with nothing testable = Class C. So case 6's expectation `{} → 400 INVALID_CONFIG` is the
  one factual error in the spec; 200-untestable is the right answer and the test asserts it.
* **`{"fields": "nonsense"}` → AttributeError, which escaped T1's `(KeyError, TypeError, ValueError)`
  tuple → would 500.** The mapper's mode gate does `template.get("fields", {}).get(fid)`; with
  `fields` a str, `.get` raises `AttributeError`. A malformed template returning a 500 is a real
  robustness hole (Supabase could send one), and case-d's stated intent is "malformed template →
  INVALID_CONFIG". So I added `AttributeError` to the endpoint's catch (server.py only; the mapper is
  untouched) → clean 400. This is a deliberate, minimal deviation from T1's literal tuple, reported
  here for ratification — not a mapper change and not a tuned golden.

Net: the endpoint + both exact goldens are as specified; the only judgment call was on malformed
non-template input, where I chose correct/robust behavior over the spec's two mistaken example
expectations and disclosed it. Read hook truncated reads to line 1 again; worked around with sed/grep.

WIT-P4b — Partial: endpoint + both exact untuned goldens + 10 green tests SHIPPED; T2 case-6's two example inputs were factually wrong (empty template is correctly 200-untestable, not 400) and exposed a 500-on-malformed-input hole that I closed by adding AttributeError to the endpoint's catch (server.py only) — both disclosed for lead ratification rather than silently tuned.

Platform   : Claude Code (VS Code, MacBook Air)
Project    : WillItTrade (WIT)
Repo       : github.com/jimmuell/mes-orb-strategy   (branch: main)
Prompt     : WIT-P4b
Local path : ~/Projects/mes-orb-strategy

STEP 0 — GATE (any failure => STOP and report)
  1. git checkout main && git pull --ff-only
  2. git log --oneline -1 must show 5a18069 (WIT-P4a). Otherwise STOP, report HEAD.
  3. Tree clean (known untracked pine file fine). Read docs/wit/WIT-04-front-office-design.md
     §6 before writing code — it is the spec for this slice.
  4. NO LLM calls in this slice. Nothing under api/wit/ is modified: map_template is used
     AS IS. If you believe the mapper itself needs a change, STOP and report instead.

TASK
T1. ADD one sync endpoint to api/server.py, in the WIT surface, immediately AFTER
    GET /wit/v1/runs/{run_id} and BEFORE the "POST /wit/v1/extract" section banner:

      class WitMapRequest(BaseModel):
          template: dict

      @app.post("/wit/v1/map", dependencies=[Depends(verify_wit_key)])
      async def wit_map_template(req: WitMapRequest):
          ...

    Behavior — EXACTLY this, no extra fields, no reordering of the mapper's output:
      a. success  -> 200, body = map_template(req.template) VERBATIM
                     ({kind, config, assumptions_applied}). The HTTP layer is a pure
                     pass-through: it must not add, drop, rename, or re-serialize keys.
      b. UnsupportedConstruct -> _wit_error(400, "UNSUPPORTED_CONSTRUCT", str(e),
                     {"field": e.field, "mode": e.mode})   — same shape as /wit/v1/runs.
      c. UntestableStrategy   -> 200, body {"kind": null, "class": <e.cls>,
                     "untestable": true}. Class C is a PRODUCT OUTCOME, not a 4xx
                     (WIT-04 §6). Note this in a one-line comment.
      d. (KeyError, TypeError, ValueError) -> _wit_error(400, "INVALID_CONFIG",
                     f"malformed template: {e}", {}).
    Sync only: no run store, no callback, no background task, no budget, no idempotency.
    Do NOT touch WitRunRequest, WitExtractRequest, or any existing route.

T2. NEW test file api/tests/test_wit_map.py. Reuse the auth/client fixtures pattern from
    api/tests/test_wit_router.py and the fixture loader from api/tests/test_mapper.py
    (api/tests/fixtures/WIT-T-0001.template.json, WIT-T-0002.template.json). Cover:
      1. AUTH: no header -> 401; wrong bearer -> 403; WIT_ENGINE_SERVICE_KEY unset -> 503.
      2. GOLDEN, Class A (T-0001) — EXACT EQUALITY, two independent anchors:
           resp.json() == map_template(fixture)                     # pure pass-through
           strategy_config_to_vporb(resp.json()["config"]) == VPORBConfig()   # end anchor
      3. GOLDEN, Class B (T-0002) — EXACT EQUALITY:
           resp.json() == map_template(fixture)
           event_study_config_to_engine(resp.json()["config"]) == EventStudyConfig()
      4. Class C template -> 200 with {"kind": None, "class": "C", "untestable": True}
         (build the Class C template the same way test_mapper.py does).
      5. Unsupported mode (mutate a fixture field's mode to a junk token) -> 400
         UNSUPPORTED_CONSTRUCT with detail.field and detail.mode populated.
      6. Malformed template ({} and {"fields": "nonsense"}) -> 400 INVALID_CONFIG.
      7. NO STATE: the same template POSTed twice returns byte-identical bodies, and
         GET /wit/v1/runs/<anything from this slice> is unaffected — assert the WIT run
         store length is unchanged across the two calls.
    GOLDENS ARE EXACT EQUALITY AND ARE NEVER TUNED TO PASS. If an assertion fails, STOP
    and report the actual vs expected — do not adjust the assertion.

T3. DOCS — docs/wit/WIT-03-api-contract.md, two edits only:
    a. New subsection after §3.7, before "## 4.":
       ### 3.8 `POST /wit/v1/map` — filled template → wire config (sync)
       Request `{"template": { /* filled WIT-02 template */ }}`. Runs the engine-side
       mapper (`map_template`) so mapping has exactly ONE implementation (§1). Success
       `200 {kind, config, assumptions_applied}` — the exact mapper output. Class C
       returns `200 {"kind": null, "class": "C", "untestable": true}` (a product state,
       not an error). Unsupported vocabulary returns `400 UNSUPPORTED_CONSTRUCT` with
       `{field, mode}`; malformed input `400 INVALID_CONFIG`. Same bearer auth as the
       rest of `/wit/v1/*`. Synchronous, deterministic, no LLM, no run store, no callback.
    b. Change-log entry at the TOP of the §7 list:
       - **WIT-P4b (2026-07-28):** `POST /wit/v1/map` shipped (WIT-04 §6) — the mapper
         gets an HTTP surface so Supabase never re-implements template→config mapping.
         Additive; no existing wire shape changed; `config_version` stays `1.0`.

T4. Archive this prompt verbatim to docs/wit/prompts/WIT-P4b.md; add a row for
    WIT-P4b-report.md to docs/wit/log/README.md.

T5. Suite: cd api && BACKTEST_API_KEY=k python -m pytest -q
    EXPECT 258 + (your new test count) passed / 0 failed / 2 skipped. Any pre-existing
    test that changes status => STOP and report; do not modify an existing test.

T6. Single commit DIRECTLY to main, subject:
      WIT-P4b: POST /wit/v1/map — template→config mapping gets an HTTP surface (sync, goldens exact)
    Explicit paths only. Push; record CI (the ADR-050 security gate must stay green — this
    slice adds no dependency).

REPORT BACK — docs/wit/log/WIT-P4b-report.md, staged with the commit:
  1. STEP 0 result.
  2. The endpoint as committed (paste the function body verbatim).
  3. Test list with pass/fail per case, and for BOTH goldens state explicitly that
     equality was exact and untuned.
  4. Suite counts before/after (258 -> N).
  5. Commit hash; CI status incl. the security gate.
  6. Anything unexpected — especially any place the mapper's real output differed from
     what WIT-04 §6 describes.
Final line, exactly one of:
WIT-P4b — Completed
WIT-P4b — Partial: <one-line reason>

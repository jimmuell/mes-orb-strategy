# WIT-P4b — Lead ratification of the two disclosed judgment calls (lead engineer, Cowork chat, 2026-07-28)

Trigger: WIT-P4b reported `Partial`, having found two factual errors in the prompt's T2 case 6
rather than tuning tests to match a wrong spec. Both calls are RATIFIED; WIT-P4b is CLOSED as
complete. This is the STOP-and-report discipline working as designed — the spec was the thing
that was wrong.

## 1. Empty template `{}` returns 200 untestable, NOT 400 — RATIFIED

`score_completeness({})` classes an empty template as **C**, so `map_template` raises
`UntestableStrategy(cls="C")` and the endpoint returns
`200 {"kind": null, "class": "C", "untestable": true}`. This is CORRECT product behavior and is
what WIT-04 §6 intends: Class C is a product outcome, not an error, and "a template with nothing
in it" is the purest Class C there is. The prompt's expectation of `400 INVALID_CONFIG` was a
lead error. The shipped test asserts the true behavior.

Consequence for the front office: `POST /wit/v1/map` distinguishes "this strategy is not
testable" (200, `untestable: true`) from "this input is not a template" (400, `INVALID_CONFIG`)
— the callback handler must branch on the 200 BODY, not on the status code alone.

## 2. `AttributeError` added to the endpoint's catch tuple — RATIFIED

A structurally-malformed template (e.g. `{"fields": "nonsense"}`) makes the mapper's mode gate
call `.get` on a str, raising `AttributeError`, which escaped the specified
`(KeyError, TypeError, ValueError)` tuple and would have returned **500**. A 500 on malformed
input from the front office is a real robustness hole, and case (d)'s stated intent was
"malformed template -> INVALID_CONFIG". Catching `AttributeError` in `api/server.py` only — the
mapper untouched, no golden moved — is the minimal correct fix. RATIFIED as shipped.

## 3. Standing note

Neither call altered a golden, a threshold, or the mapper. Both were disclosed before
ratification rather than absorbed silently. That is the required behavior when the spec and the
engine disagree: the engine's true behavior wins the test, and the lead rules on the spec.

## 4. Status

WIT-P4b: **COMPLETE**. `POST /wit/v1/map` is the sanctioned mapping surface for the front office.

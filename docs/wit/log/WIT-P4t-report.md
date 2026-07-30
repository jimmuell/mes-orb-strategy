# WIT-P4t — v1 verdict block in result payloads; no edge claim until the stats layer ships

## STEP 0
Gate passed: remote `jimmuell/mes-orb-strategy`, path `/Users/jameslmueller/Projects/mes-orb-strategy`,
HEAD `da1224a` (WIT-P4r) after `git pull --ff-only`.

## What shipped
New pure module **`api/wit/verdict.py`** — `derive_verdict(kind, metrics) -> {"code","label","reason"}`,
implementing the rule ratified 2026-07-30. No I/O, no engine access; reads the metrics dict the caller
already built. Codes are drawn from a two-element closed set; labels come from a fixed map so no branch
can hand-write a claim string:
```python
_INCONCLUSIVE = "tested_inconclusive"
_NO_EDGE = "tested_no_edge"
_LABEL = {_INCONCLUSIVE: "Tested — inconclusive", _NO_EDGE: "Tested — no edge demonstrated"}
```
- **event_study** → always `tested_inconclusive`, reason "event-study claim verdicts await the
  statistical confidence layer".
- **backtest**:
  - `trades` None/0, or `profit_factor` None, or `net_pnl` None → `tested_inconclusive`
    ("insufficient completed trades or metrics to render a verdict").
  - `profit_factor < 1.0` or `net_pnl <= 0` → `tested_no_edge`
    (`f"profit factor {pf:.2f} and net P/L {net:+,.0f} over {trades:,} trades across the full test window"`).
  - otherwise (positive raw result) → `tested_inconclusive`
    (`f"positive result (profit factor {pf:.2f} over {trades:,} trades) — statistical confidence analysis
    (edge vs. luck) is not yet part of v1, so no edge claim is made"`).

**HARD RULE enforced by construction:** the only codes reachable are `tested_no_edge` and
`tested_inconclusive`; the only place the word "edge" appears in a label is the exact phrase
"no edge demonstrated"; a positive raw result is reported as *inconclusive*, never as edge.

## Wiring (`server.py` only)
- `_backtest_result` adds `"verdict": derive_verdict("backtest", metrics)`.
- `_event_study_result` adds `"verdict": derive_verdict("event_study", {})`.
- Import: `from wit.verdict import derive_verdict`. Nothing else in either payload changed. The
  mapper Class-C / untestable path (which carries no run result) was NOT touched.

## Tests (`tests/test_verdict.py`, 7)
- `test_negative_pf_below_one_is_no_edge_with_pf_in_reason` — PF 0.90 / -9672 / 4158 → `tested_no_edge`,
  reason contains "0.90".
- `test_positive_result_is_inconclusive_and_makes_no_edge_claim` — PF 1.30 / +5000 / 100 →
  `tested_inconclusive`, reason contains "no edge claim is made".
- `test_nonpositive_net_with_pf_ge_one_is_no_edge` — net 0 (PF 1.0) and net −1 (PF 1.5) both →
  `tested_no_edge`.
- `test_zero_trades_or_none_metrics_is_inconclusive_insufficient` — trades 0 / None / missing metrics →
  `tested_inconclusive` ("insufficient").
- `test_event_study_is_always_inconclusive`.
- `test_exhaustive_no_path_ever_claims_edge` — grid of pf×net×trades (incl. None, negatives, 0, 1e9)
  over both kinds: every code ∈ {tested_no_edge, tested_inconclusive}; any "edge" in a label ⇒ exact
  "Tested — no edge demonstrated"; no reason contains a positive-edge claim phrase; and BOTH codes are
  reached (guard not vacuous).
- `test_router_backtest_payload_carries_verdict` — real `/wit/v1/runs` happy path (stubbed runner, no
  network): the stored `result["verdict"]` has exactly keys {code,label,reason}, code
  `tested_inconclusive` (PF 4.48 positive → no edge claim).

## Report-back item 1 — WIT-0001 anchor verdict
`derive_verdict("backtest", {"profit_factor": 0.9027, "net_pnl": -5976.89, "trades": 2561})` returns:
- **code:** `tested_no_edge`
- **label:** `Tested — no edge demonstrated`
- **reason:** `profit factor 0.90 and net P/L -5,977 over 2,561 trades across the full test window`

## Report-back item 2 — suite + goldens
- Before (HEAD da1224a): **301 passed / 2 skipped**.
- After: **308 passed / 2 skipped** (301 + 7 new; zero failures; no existing test adjusted).
- **Both anchor goldens BYTE-IDENTICAL:** mapper G1 (T-0001) / G2 (T-0002) pass unchanged; `mapper.py`
  untouched (empty `git diff`). This slice edits only `server.py` + adds `wit/verdict.py` and the test.

## Commit
- Subject: `WIT-P4t: v1 verdict block in result payloads — no edge claim until the stats layer ships`
- Hash + URL: recorded in the report-back after push.

WIT-P4t — Completed

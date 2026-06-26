# Architecture Decision Records — mes-orb-strategy

Decisions that govern the live FastAPI backtest engine (`api/`) and its dependencies.

> ADR numbers continue from the back-tester sequence (016, 017, 019 live in that repo's
> `docs/DECISIONS.md`). The records below are **mes-orb-strategy** decisions and live here.
> Renumber only if they collide with a future local sequence.

---

## ADR-018 — Engine economics are true MES $5/point; engine and validator move in lockstep

**Status:** Accepted.

**Context:** The engine computed pnl as `qty*(exit-entry)` with no contract multiplier
(effectively $1/point); every dollar KPI was 5× too small for MES.

**Decision:** Apply `MES_POINT_VALUE = 5.0` at every dollar site, AND set the validation
instrument to `point_value=5.0` **in the same change**.

**Consequence:** dollar KPIs are real MES dollars; `total_commission` and `net_profit_pct`
also scale ×5 (dollar fields); `pnl_pct` and all ratios are invariant (scale-invariant);
`max_drawdown_pct` shifts by a path-dependent factor — not a flat ×5 (e.g. ~×4.9 for the
EMA-crossover demo on the 6-month test set).

**RULE:** the engine's `MES_POINT_VALUE` (`api/engine/engine.py`) and
`_ENGINE_INSTRUMENT.point_value` (`api/server.py`) must always agree, or the
signal-vs-exposure rank is meaningless — change them together.

---

## ADR-020 — Pin: numpy>=1.26,<3, pandas>=2.2,<3, Python pinned to 3.12 for the engine

**Status:** Accepted.

**Context:** Railway build failed — `numpy>=1.24` (engine) vs `numpy>=1.26` (backtester) +
loose `pandas>=2.0` caused pip `ResolutionImpossible`; separately `.python-version` pinned
3.11 while backtester requires `>=3.12`.

**Decision:** tighten the floors (`numpy>=1.26,<3`, `pandas>=2.2,<3`) and pin
`.python-version` to **exactly 3.12** (Railway resolves 3.12.x).

**Consequence:** reproducible, resolvable builds.
(mes-orb-strategy `api/requirements.txt` + `api/.python-version`.)

---

## ADR-021 — Untrusted signal-code execution: AST allowlist + timeout, in-process (NOT a true sandbox)

**Status:** Accepted.

**Context:** `/run` executes LLM-generated signal code on the live engine; PR #1 hardened
this path, but the decisions lived only in code + the merged PR body.

**Decision:** API key required (no default; **503 if `BACKTEST_API_KEY` unset**, 401 if
wrong); CORS restricted to an env allowlist (`ALLOWED_ORIGINS`); `signal_code` gated by an
**AST allowlist** (no imports, no dunder/underscore attrs, no `__` in strings, denied-name
set; fail-closed) plus a **SIGALRM walltime timeout**.

**Consequence / honest residual risk:** this is NOT a true sandbox — code still runs
**in-process**, so a novel CPython escape or a long in-C call isn't fully contained, and
there is no memory rlimit.

**Follow-up (open):** subprocess/rlimit isolation.

---

## Economics & dependency pointer

Economics: pnl uses `MES_POINT_VALUE = 5.0` ($5/point). The validation instrument
(`_ENGINE_INSTRUMENT` in `api/server.py`) MUST use the same `point_value` — change them
together (ADR-018).
Second engine copy `backtest/engine/engine.py` is intentionally still $1/point to preserve
documented Run 0xx figures (confirmed: 0 occurrences of `MES_POINT_VALUE` there vs. 64 in
`api/engine`); consolidate deliberately later.

Dependency: `backtester` is pip-installed from the back-tester repo, pinned to a commit.
Build requires `numpy>=1.26,<3`, `pandas>=2.2,<3`, Python >=3.12 (pinned to 3.12), and
network access to GitHub. To adopt a newer backtester, bump the pinned sha in a deliberate PR.

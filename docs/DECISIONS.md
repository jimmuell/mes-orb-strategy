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

## ADR-023 — Constant point-denominated stops & targets (alongside % stops)

**Status:** Accepted.

**Context:** `take_profit_pct`/`stop_loss_pct` were the only constant exit levels exposed through
config and the API. Futures traders size exits in points/ticks, not percent, and a percent stop on
multi-year MES is unintuitive (the "0.1% ≈ 5pt" confusion behind the earlier stop-loss
investigation). The engine already supports point offsets internally (`_check_tpsl_fill` offset
branch), but only via per-bar signal-emitted columns — there was no constant config-level point stop.

**Decision:** Add `take_profit_points` / `stop_loss_points` (float, default 0.0 = disabled) to
`BacktestConfig`. `_check_tpsl_fill` is **not** modified — its existing offset input is reused. At
both call sites the constant feeds the offset slot when no per-bar offset column is present:
`bar_sl_off = bar["sl_offset"] if has_sl_off else config.stop_loss_points`. The two fields are
exposed on `BacktestRequest` and passed into `BacktestConfig` in `server.py`, and echoed in `kpis`
as `received_stop_loss_points`/`received_take_profit_points`.

**Consequence / precedence:** Effective per-trade exit priority is (1) per-bar absolute price column,
(2) per-bar offset column **or** `config.*_points`, (3) `config.*_pct`. A signal's own dynamic offset
still wins over the config constant; the config constant wins over percent. If both a points stop and
a pct stop are set, **points wins** (offset > pct in the primitive); the UI makes them mutually
exclusive, the engine keeps a deterministic documented tiebreak. Canonical engine unit is **index
points** (1 pt = 1.0 price unit = $5); tick and per-contract dollar display are handled at the UI
(pts ×0.25 → ticks; pts ×$5 → $/contract).

**RULE:** point stops feed the existing offset slot — never add a parallel offset code path in
`_check_tpsl_fill`. The math has one home.

---

## ADR-024 — Adverse slippage model (constant ticks on every fill)

**Status:** Accepted.

**Context:** `slippage_ticks: int = 0` had lived on `BacktestConfig` since the start but was a
dead field (zero usages), and was not even exposed on `BacktestRequest`. Backtests filled at the
exact bar Open/Close, overstating edge — real futures fills cross the spread and slip, especially
on stop exits.

**Decision:** One helper, `_apply_slippage(price, side, config)`, applied at the moment each
`fill_price` is assigned. `side="buy"` (long entry / short cover) adds `slippage_ticks * MES_TICK_SIZE`;
`side="sell"` (long exit / short entry) subtracts it. TP/SL fills inherit the position's exit side
(long→sell, short→buy). `MES_TICK_SIZE = 0.25` is a new module constant pinned in lockstep with
`_ENGINE_INSTRUMENT.tick_size` (same discipline as `MES_POINT_VALUE` ↔ `point_value`). `slippage_ticks`
is exposed on `BacktestRequest` and passed into `BacktestConfig` in `server.py`, and echoed in `kpis`
as `received_slippage_ticks`.

**Consequence:** `slippage_ticks = 0` is byte-identical to the prior engine (`price ± 0.0 == price`),
so determinism, the signal cache, and the ADR-023 suite are unaffected. The model is uniform —
**every** order including TP limits slips adverse, matching TradingView's `slippage` property; a
limit-order-exempt refinement is deferred to a future ADR. `__version__` bumped to `24.0.0`.

**RULE:** slippage has one home — `_apply_slippage` at the fill-price assignment. Never scatter
`± slip` arithmetic across the pnl/commission math; wrap `fill_price` once and let the block consume it.

---

## ADR-025 — Protective stop/target is live from the entry bar

**Status:** Accepted.

**Context:** The point/percent stop & target (`stop_loss_points`/`take_profit_points`/`*_pct`) were only evaluated on bars **after** entry (`i > entry_bar_idx`) in both `run_backtest` and `run_backtest_long_short`. A resting protective stop should be live the instant the position exists — including the entry bar — matching TradingView's broker emulator. As written, large same-bar adverse moves and short-hold strategies bypassed the stop entirely, so a configured stop did not cap losses.

**Decision:** Treat a configured stop/target as a resting protective order that is live from the moment of entry. Change the TP/SL gate in **both** run functions from `i > entry_bar_idx` to `i >= entry_bar_idx`, so the existing intrabar `_check_tpsl_fill` runs on the entry bar too (the entry has already filled earlier in the same iteration; `entry_bar_idx` and the position's entry price are set). `_check_tpsl_fill` is **not** modified — on the entry bar its gap-at-open branch is inert (for a long, `tp_level = entry+off > open` and `sl_level = entry−off < open`, where `open == entry_price`), so it correctly falls through to intrabar hit detection on the bar's High/Low. The math keeps one home (ADR-023 RULE).

**Consequence / precedence:** The protective stop/target now fires on any open bar, entry bar included, the moment the bar's range reaches the level; a gap beyond the level still fills at Open (unchanged gap-through). On a bar where a pending signal exit is scheduled, the realistic market-on-open timing is preserved (that fill is the first event of the bar and is never worse than the stop — if the open gapped past the stop, the stop also fills at Open via gap-through; otherwise the open fill is nearer entry than the stop). Net effect: a hard stop reliably caps loss without ever forcing a worse fill than a pending market exit — the faithful implementation of "hard stop wins." When no stop/target is configured (`stop_loss_points`/`take_profit_points`/`*_pct` all 0), `tp_sl_active` is False and the block never runs, so this is **byte-identical** to the prior engine — the signal cache, determinism, and the ADR-023/024 suites are unaffected. Runs that **do** set a stop/target change (intended). `__version__` → `25.0.0`.

**RULE:** the protective stop/target is live from the entry bar. Never reintroduce an entry-bar skip, and never add a parallel level-calc path — the math stays in `_check_tpsl_fill`.

---

## ADR-026 — Teachable comparison: `POST /run/compare` (stop dimension)

Recorded in full in [`ADR-026_teachable_comparison.md`](ADR-026_teachable_comparison.md).
Runs the user's config and a stop-neutralized variant against the same signal in one
logical run and reports exact dollar deltas (`teaching`/`same_signal`). Additive — `/run`
is byte-identical; `__version__` → `25.1.0`.

---

## ADR-027 — Significance judgment on `/run/compare` teaching deltas (CI on the delta)

Recorded in full in [`ADR-027_compare_significance.md`](ADR-027_compare_significance.md).
Judges whether each teaching delta is distinguishable from noise via a 95% percentile-
bootstrap CI on the paired per-trade delta — the **same** `run_bootstrap` machinery as the
single-run "Edge vs Luck" CI (seed 42, 10k iters). Adds `delta_ci_low`/`delta_ci_high`/
`significance` (saved/cost/inconclusive)/`n_resamples`/`sufficient_data` to each teaching
entry. Additive; `__version__` → `25.2.0`.

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

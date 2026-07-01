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

## ADR-022 — Engine date bounds normalize to the bar-index timezone (not hardcoded UTC)

**Status:** Accepted.

**Context:** `run_backtest` and `run_backtest_long_short` (in `api/engine/engine.py`) built
`start`/`end` from the config date strings as tz-naive `pd.Timestamp`s, then compared them against
the bar index — which is tz-aware UTC in production (bars arrive from the API). The `data_first >
start` guard and the per-bar `start <= bar_date <= end` range check therefore mixed tz-aware and
tz-naive timestamps, raising `TypeError: Cannot compare tz-naive and tz-aware timestamps`, and the
run died before producing KPIs (the true source of the persistent "null verdict").

**Decision:** Immediately after `start`/`end` are constructed, normalize them to **the bar index's
own timezone** — `tz_localize` when the bound is naive, `tz_convert` when aware, and strip to naive
when the index itself is naive. Applied in **both** functions, ahead of every comparison site. The
bars are never altered (the validation layer relies on their tz info).

**Consequence:** Fixes the production aware-UTC crash AND preserves the local/bundled CSV path,
whose index is tz-naive — hardcoding UTC would have crashed that path in reverse. Verified locally
across tz-aware-UTC, tz-naive, and ET-aware indices (PR #8, commit `732989b`).

The frozen second copy `backtest/engine/engine.py` carries the same latent bug (no normalization;
comparison sites present) — reported, intentionally left unfixed; consolidate deliberately.

**Code anchors (function names are the durable anchor; line numbers drift):** in
`api/engine/engine.py`, `run_backtest` and `run_backtest_long_short`; the `data_first > start`
guard and the per-bar `start <= bar_date <= end` check in each; normalization applied just above
each block.

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

## ADR-028 — `/run/compare` returns the standard Edge-vs-Luck validation (primary result)

Recorded in full in [`ADR-028_compare_validation.md`](ADR-028_compare_validation.md).
`/run/compare` previously omitted the standard `validate()`/`summarize()` verdict, so the app
showed "No validation verdict" for stop runs. Now computes it for the **primary** (user's)
config only — reusing `/run`'s exact machinery — and returns top-level `validation` /
`validation_error` (same field names as `BacktestResponse`). Gated on `run_validation`; variant
not validated. Additive (teaching/significance unchanged); `__version__` → `25.3.0`.

---

## ADR-029 — Take-profit dimension on TEACH-COMPARE (mirror the stop instance)

Recorded in full in [`ADR-029_compare_take_profit.md`](ADR-029_compare_take_profit.md).
`teaching` is a list of per-dimension blocks; this appends a SECOND block — `take_profit` —
after the unchanged `stop` block. Mirrors the stop instance: a take-profit-neutralized variant
(`take_profit_points=0`, `take_profit_pct=0`), a third `_serialize_run` on the same signal df
(`same_signal` now spans all three runs), the reused paired-delta significance, and a WINNER
stat (`primary_best_win`/`variant_best_win` = `max(pnl)`) instead of the stop's worst-loss.
Validation stays primary-only. Downstream: `context.teaching` consumers must iterate the list.
Additive; `__version__` → `25.4.0`.

---

## ADR-030 — Flat per-round-trip commission

**Status:** Accepted (v25.5.0)

**Context:** Commission was percent-of-notional per side (`commission_rate`).
On MES that is ~$25/side and silently destroys results. Three AMP daily
statements (21-APR / 11-JUN / 12-JUN 2026; 106 / 25 / 2 round-trips) show the
true all-in cost is a flat **$1.24 per round-trip** — exchange + clearing +
NFA + CQG routing + commission — identical across all three days. A
"Liquidation Fee" ($2.50/event) appears only when AMP force-flattens a
position; it is situational, not a per-trade cost, and is excluded. The $45/mo
data fee is fixed overhead and excluded from per-trade math.

**Decision:** Add `commission_mode` ("percent" | "flat_per_rt") and
`commission_per_rt` (default 1.24). All commission math routes through one
helper, `_commission_for_side(trade_value, config)`. Flat mode charges
`commission_per_rt / 2` on each side (half-split): entry + exit = one
round-trip; an open trade is charged exactly half, keeping accounting
symmetric. Percent mode is the default and is byte-identical to prior
behavior. `commission_per_rt = 0.0` yields a commission-neutralized run,
enabling a future "what did commission cost me" teaching dimension.

**Consequence:** `commission_mode="percent"` is byte-identical → signal cache,
determinism, and the ADR-023/024/025 suites are unaffected. Flat is additive
and opt-in. Helper has one home; no bare `* commission_rate` survives outside it.

---

## ADR-031 — Commission dimension on TEACH-COMPARE (mirror stop / take-profit)

Recorded in full in [`ADR-031_compare_commission.md`](ADR-031_compare_commission.md).
Appends a THIRD `teaching` block — `commission` — after the unchanged `stop` and
`take_profit` blocks. Mirrors the prior instances: a commission-neutralized variant
(`commission_per_rt=0`, `commission_pct=0`), a fourth `_serialize_run` on the same signal df
(`same_signal` now spans all four runs), the reused paired-delta significance, and the
distinctive stats `total_commission` (= `variant_net − primary_net`, the fees removed from P&L)
and `flips_profitability`. In flat mode the fee doesn't change which trades happen, so the delta
is the exact total commission and the bootstrap trivially reports "cost" — the correct, honest
result. Additive; `__version__` → `25.6.0`.

---

## ADR-032 — Direction dimension on TEACH-COMPARE ("what your short trades did")

Recorded in full in [`ADR-032_compare_direction.md`](ADR-032_compare_direction.md).
Appends a FOURTH `teaching` block — `direction` — after stop / take_profit / commission. Unlike
the others, the neutralizer toggles the run's **direction param** (`long_short ↔ long_only`), not
the config; a fifth `_serialize_run` on the same signal df (`same_signal` spans all five runs).
Toggling adds/removes the SHORT trades while longs stay identical, so `_paired_deltas` (which drops
unmatched trades) is **not** used — the delta IS the shorts, bootstrapped directly via
`_delta_significance`. Stats: `short_trade_count`, `short_net`, `flips_profitability`, signed so
`delta_net` reads naturally for both primary directions. The `long_short` variant is guarded
against missing `short_entry`/`short_exit` columns (falls back to primary → neutral) so a missing
column can't 500 all cards (ADR-031 lesson). Additive; `__version__` → `25.7.0`.

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

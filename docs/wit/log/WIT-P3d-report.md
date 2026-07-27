# WIT-P3d — /wit/v1/* router: submit, status, signed callback, idempotency

Prompt: **WIT-P3d** — the WIT run surface, wiring scorer + mapper + runners into the live API. Additive; legacy `/run*` untouched. On `wit-phase3` (no branch, no merge).

---

## 1. STEP 0 result
- On `wit-phase3`: **yes**. HEAD = **`5c179ec` (WIT-P3c-3)**: **yes**.
- Tree clean: **yes** — only the known untracked `pine/mes_net_pnl_v2.pine` (ignored); LFS clean.

## 2. Files + env vars + reuse

**Created:** `api/wit/config_hash.py`, `api/wit/run_store.py`, `api/tests/test_wit_router.py`, this report.
**Modified:** `api/callback_writer.py` (added `WITCallbackWriter` + `get_wit_callback_writer`; legacy `CallbackWriter` untouched), `api/server.py` (appended the `/wit/v1/*` block before `__main__`; the legacy endpoints + `verify_api_key` are unchanged), `docs/wit/WIT-03-api-contract.md` (§3.4 + §7 change-log), `contract/modes.md` († markers).

**New env vars (both fail-closed, read dynamically so config/tests take effect without re-import):**
- **`WIT_ENGINE_SERVICE_KEY`** — Bearer auth for `/wit/v1/*` (WIT-03 §2). **Unset → 503** ("not configured"); **missing/malformed `Authorization: Bearer`** header → **401**; **present but wrong** → **403**. A separate key — never `BACKTEST_API_KEY`.
- **`WIT_CALLBACK_HMAC_SECRET`** — signs outbound callbacks: `X-WIT-Signature = hex(HMAC-SHA256(exact_body_bytes, secret))`. If **unset, callbacks are disabled** (`get_wit_callback_writer` → None); the run still reaches a terminal state and the **poll fallback** (`GET /wit/v1/runs/{id}`) covers it.

**Reused vs newly written:**
- **Reused verbatim:** `is_allowed_callback_url` (SSRF guard — https-only, `.supabase.co` suffix, no redirects); the `_run_async_job` **pattern** (`asyncio.to_thread` off the event loop, `wait_for` + `shield` heartbeat loop, GUARANTEED terminal state); `BackgroundTasks`; `_HEARTBEAT_SECONDS`.
- **Newly written (WIT-specific, parallel to legacy — reported per the prompt):** a **parallel `_run_wit_job`** rather than overloading `_run_async_job` (which is bound to the compare/`BacktestRequest` payload — a parallel fn is cleaner and keeps the legacy path risk-free); **`WITCallbackWriter`** (HMAC-signs the exact bytes, vs the legacy shared-secret header); **`WITRunStore`**; **`verify_wit_key`** (Bearer, vs legacy `X-API-Key`). The signal-code/`exec` path exists nowhere on this surface (WIT-03 §1).

## 3. §3.6 gaps — promised blocks the engine can't yet produce (omitted/null, never faked)

For **kind `backtest`** (`run_vp_orb` output):
| §3.6 field | Status | Why |
|---|---|---|
| `metrics.expectancy_r` | **null** | `run_vp_orb` computes `avg_trade` in $, not R-expectancy |
| `confidence.bootstrap` (CIs) | **omitted** | `run_vp_orb` does not bootstrap (that lives in `analysis.py`, not the single-run path) |
| `confidence.edge_vs_luck` | **omitted** | not produced by `run_vp_orb` |
| `regimes` | **omitted** | not produced by `run_vp_orb` |
| `trades_url` | **null** | no signed-URL infrastructure (Supabase-side) |
| `sweep_results` | **omitted** | single run; sweeps are P3f |
| `metrics` (trades/net_pnl/PF/max_dd/win_rate/avg_trade), `equity_curve`, `provenance` | **populated** | from `kpis` + `kpis["equity_curve"]`; non-finite (e.g. inf PF) coerced to null |

For **kind `event_study`**: the result carries the runner's **native** output under `event_study` (per-cell conditional stats + day-clustered CIs — `run_config`'s dict), which is what §3.6 means by "event-study results replace `metrics` with conditional distributions + CIs." It is **not** reshaped into the backtest `metrics/confidence` blocks. `provenance` is populated.

Nothing is fabricated — every gap above is an explicit null/omission.

## 4. Idempotency + config_hash

- **`config_hash`** = `sha256(json.dumps(wire_config, sort_keys=True, separators=(",",":")))` — canonical JSON of the **wire** config (sorted keys, compact separators), so key order / whitespace never change the hash, and it survives engine refactors (`api/wit/config_hash.py`). Computed by the **router** at submit, not the mapper (per the P3c design).
- **Store shape** (`WITRunStore`, `api/wit/run_store.py`): a `dict` keyed `run_id` + an idempotency index keyed **`(evaluation_id, config_hash) → run_id`**, guarded by one `threading.Lock`. `register()` is atomic get-or-create and returns `(run_id, is_new)`; when `is_new` is False the router launches **no** job and returns the existing run (WIT-03 §3.1). Verified by `test_idempotent_resubmit_same_run` (same run_id, exactly one job launched) and `test_different_config_new_run`.
- **Restart-lossy disclosure (honest):** the store is **in-process**; a Railway restart/redeploy loses all run state — in-flight runs drop and their `run_id`s become 404. The poll fallback + the caller's own Supabase `runs` row (WIT-03 §6) cover it; callbacks are best-effort. Documented in `run_store.py`'s module docstring and here. A durable store is a later slice.

## 5. Doc fixes

**(a) WIT-03 §3.4 `session.trade_window` — exact old→new:**
```
OLD:  "session": { "tz": "America/New_York", "trade_window": ["09:30","11:00"], "force_flat": "15:55" }, // ET wall-clock, matching the engine; same instants as the prior CT example …
NEW:  "session": { "tz": "America/New_York", "trade_window": ["09:45","10:55"], "force_flat": "15:55" }, // trade_window = entry-eligibility window [first_eligible_bar_start, last_eligible_bar_start], ET wall-clock; force_flat = last RTH bar start. Example values are VP-ORB's (the mapper emits them from C1.params, P3c-2).
```

**(b) `contract/modes.md` tokens marked `†`** ("declared, not engine-supported in v1 → UNSUPPORTED_CONSTRUCT"): `bias` **none**, **orb_break**; `setup` **opening_range**; `entry.level` **orb_high_low**; `order` **market_next_open**; `stop` **structure**; `target` **level**, **none**; `time_exit` **fixed_time**, **none**; `filters` **regime/calendar**; `regime` **none**. The `*` legend was replaced by the `†` legend, and the UNSUPPORTED_CONSTRUCT prose updated to reference `†`.

**§7 change-log line added** for both (a) and (b); no wire-shape change, `config_version` stays `1.0`.

## 6. Test inventory + full suite

`api/tests/test_wit_router.py` (FastAPI `TestClient`, runners stubbed, **no network** — callbacks captured by patching `WITCallbackWriter.post`): **15 passed**
| Case | Result |
|---|---|
| backtest 202 happy path + terminal callback, **HMAC verifies** against secret | ✅ |
| event_study 202 happy path (stubbed) | ✅ |
| idempotent resubmit → same run_id, **exactly one job** | ✅ |
| different config → new run_id | ✅ |
| missing service key → **503** | ✅ |
| missing bearer → **401** | ✅ |
| wrong bearer → **403** | ✅ |
| disallowed callback host → 400 INVALID_CONFIG | ✅ |
| unknown mode / non-ET tz → **UNSUPPORTED_CONSTRUCT** (field in detail) | ✅ |
| `sensitivity_sweep` kind → UNSUPPORTED_CONSTRUCT | ✅ |
| malformed wire → INVALID_CONFIG | ✅ |
| GET unknown run_id → **404** | ✅ |
| budget exceeded (stub sleeps past tiny `max_wall_seconds`) → **failed BUDGET_EXCEEDED** | ✅ |
| stub raises → **failed INTERNAL** with truncated traceback (never hung "running") | ✅ |
| legacy `/run` with a WIT bearer → not 200 (separate auth, additive) | ✅ |

- **Full suite: 178 passed** (163 prior + 15 new), 0 failed. No regression.
- **Anything unexpected:** (i) FastAPI `TestClient` runs `BackgroundTasks` synchronously after the response returns, so the terminal state is visible on the immediate `GET` — convenient and deterministic for these tests. (ii) No dependency added (`hmac`/`hashlib`/`datetime`/`math`/`json`/`threading`/`uuid` are stdlib); `requirements.txt` untouched, no audit-gate run needed. (iii) full §8.7 gating of legacy routes remains P3g (as scoped); the WIT surface simply has no `signal_code` field.

WIT-P3d — Completed

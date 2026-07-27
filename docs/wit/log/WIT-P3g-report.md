# WIT-P3g — security hardening: constant-time auth, exec-endpoint kill switch

Prompt: **WIT-P3g** — clear every security item logged this session (constant-time compares + exec kill switch + §8.6 note). `api/server.py` + tests only; no deps, no schema/contract/mapper changes. On `wit-phase3` (no branch, no merge).

---

## 1. STEP 0 result
- On `wit-phase3`: **yes**. HEAD = **`4a71293`** (P3d timing-attack fix) above **`f8b5b7d`** (WIT-P3d): **yes**.
- Tree clean: **yes** — only the known untracked `pine/mes_net_pnl_v2.pine` (ignored); LFS clean.

## 2. The two compare_digest changes

Both now use `hmac.compare_digest` with **both sides encoded to UTF-8 bytes** (str-mode `compare_digest` raises `TypeError` on non-ASCII → a 500; bytes make it total). Added a top-level `import hmac` and removed the redundant `import hmac as _hmac` from the WIT block (single import now).

- **Legacy `verify_api_key`** (`server.py:206`): `x_api_key != API_KEY` → `hmac.compare_digest(x_api_key.encode("utf-8"), API_KEY.encode("utf-8"))`. Behavior otherwise identical — 503 when `BACKTEST_API_KEY` unset, 401 on missing/wrong.
- **WIT `verify_wit_key`** (`server.py:~1765`): previously `compare_digest(token, key)` (str/str — crashed 500 on a non-ASCII key); now `compare_digest(token.encode("utf-8"), key.encode("utf-8"))`. Behavior identical — 503 unset, 401 missing/malformed bearer, 403 wrong.

**All prior auth tests pass unchanged** — the 15 WIT router tests (503/401/403 cases) and the legacy suite are green; the full suite is 181 passed (see §4).

## 3. Kill-switch implementation

**Mechanism chosen: a shared FastAPI dependency** `enforce_exec_enabled` (cleaner than four per-handler top-of-body checks — one function, added to each decorator's `dependencies=[...]`). Placed **before** `verify_api_key` in the list so a disabled deployment refuses **before** any credential check (a disabled endpoint is off for everyone).

```python
async def enforce_exec_enabled():
    if os.environ.get("DISABLE_EXEC_ENDPOINTS", "").strip().lower() in ("1", "true"):
        raise HTTPException(status_code=403,
            detail="Code-execution endpoints are disabled on this deployment (EXEC_DISABLED)")
```
- **Env flag `DISABLE_EXEC_ENDPOINTS`** — truthy `"1"`/`"true"` (case-insensitive); default absent/off; read **dynamically** (per-deployment flip, no re-import).
- **Exactly the four `signal_code`-accepting endpoints gated:** `POST /run` (`:549`), `/run/async` (`:929`), `/profile` (`:958`), `/run/compare` (`:1282`) — each now `dependencies=[Depends(enforce_exec_enabled), Depends(verify_api_key)]`.
- **NEVER gated (proven by grep + test):** `/wit/v1/runs`, `/wit/v1/runs/{id}` (Bearer auth only), and the unauthenticated probes `/health`, `/ping`, `/env`. Verified none of these carry `enforce_exec_enabled`.
- **Purpose (in the code comment):** the future WIT Railway service sets this flag so the arbitrary-code path is **dead code** there — structured configs only (WIT-03 §1/§8.7). Default OFF ⇒ the TradingGYM deployment is byte-identical to today.

## 4. Flag-ON / flag-OFF test results + full suite

Extended **`api/tests/test_wit_router.py`** (the only test file touched) with 3 kill-switch cases:
| Test | Asserts | Result |
|---|---|---|
| `test_exec_endpoints_403_when_disabled` | flag ON → all four (`/run`, `/run/async`, `/run/compare`, `/profile`) return **403** with `EXEC_DISABLED` in detail | ✅ |
| `test_exec_disabled_does_not_gate_wit_or_probes` | flag ON (`"true"`) → `/wit/v1/runs` POST (stubbed) **202** + GET succeeds; `/health`,`/ping`,`/env` still **200** | ✅ |
| `test_exec_endpoints_not_gated_when_flag_off` | flag absent → `/run` with wrong key → **401** (reaches auth), body has **no** `EXEC_DISABLED` (no drift) | ✅ |

The existing `test_legacy_run_still_needs_x_api_key_not_bearer` is the additional flag-OFF no-drift proof (default env, `/run` → 401).

- `test_wit_router.py`: **18 passed** (15 prior + 3 new).
- **Full suite: 181 passed** (178 prior + 3 new), 0 failed. No regression. No dependency added (`hmac` is stdlib); `requirements.txt` untouched.

## 5. §8.6 — `backtest/` retirement plan (docs only; nothing deleted this slice)

**What `backtest/` is:** the **frozen legacy engine** (`backtest/engine`, `$1/point`) + the Run 001–014 optimization strategies (`backtest/strategies/mes_orb_strategy.py`) + engine-internals docs (`BACKTESTING.md`, `MEMORY.md`) + local data. It's the historical artifact that produced the documented Run 014 numbers, deliberately kept at `$1/point` while `api/engine` is the live `$5/point` truth (`api/engine/engine.py:36`, `MES_POINT_VALUE = 5.0`).

**What imports it — nothing live.** Definitive grep: **zero** `import backtest` / `from backtest.` in `api/` or `dashboard/`.
- **Critical distinction to avoid a false alarm:** `api/server.py` and `api/wit/analysis.py` import **`backtester`** — that is the pip-installed validation **package** (`.venv/.../site-packages/backtester`, the git dep from ADR-049), **not** the local `backtest/` directory. They are unrelated; retiring `backtest/` does not touch `backtester`.
- CI never runs `backtest/` (workflow is `working-directory: api` → `pytest`, `ci.yml:23,35`).

**Safe removal order (backlog seed — do NOT execute here):**
1. **Re-confirm isolation** at removal time: `grep -rn "from backtest\.\|import backtest\b" --include=*.py .` (excluding `.venv`, `backtester`) returns empty; confirm CI scope unchanged.
2. **Preserve the record, not the code:** the Run 001–014 numbers live in `backtest-results/results.md` (historical, `$1/point`); keep them as documented history — they will no longer be re-derivable once the engine that produced them is gone, so add a one-line "computed under the retired `backtest/engine` at `$1/point`" caveat there.
3. **Rescue any still-useful prose** from `backtest/BACKTESTING.md` + `backtest/MEMORY.md` that isn't already in `docs/` (engine order-of-operations, sanitization lessons) → fold into `docs/` or `api/`’s docs.
4. **Delete in one PR:** `backtest/engine/`, `backtest/strategies/`, `backtest/BACKTESTING.md`, `backtest/MEMORY.md`, `backtest/requirements.txt`, `backtest/CLAUDE.md`; decide on `backtest/data/` (drop if duplicated by `data/raw/`; it's LFS, so removing reclaims LFS budget).
5. **Update references** (docs only, non-breaking): `docs/DECISIONS.md`, `docs/ADR-041`, `docs/ADR-026`, root `CLAUDE.md` — replace "second engine copy / `backtest/`" pointers with "retired; `api/engine` is the single computational truth (`$5/point`)."
6. **Result:** the `$1/pt` vs `$5/pt` 5× foot-gun is eliminated and there is one engine. Low risk — nothing live imports it — so the only real work is doc updates + the historical-caveat on results.md.

## 6. Anything unexpected
- The near-miss worth flagging: a naive "does anything import backtest?" grep hits the **`backtester`** package lines and looks alarming — they are the installed validation lib, not `backtest/`. The definitive check excludes `backtester` and returns empty. Documented in §5 so the removal PR doesn't panic.
- `hmac.compare_digest` on `str` (my P3d fix) worked for the ASCII test key but would 500 on a non-ASCII key — the bytes-encoding here closes that. No behavior change for ASCII keys (all tests unchanged).
- Files touched: `api/server.py`, `api/tests/test_wit_router.py`, `docs/wit/log/WIT-P3g-report.md`. No new deps; no schema/contract/mapper changes.

WIT-P3g — Completed

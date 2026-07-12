# ADR-048 — Pin the environment: dev and prod resolve to identical versions

**Status:** Accepted (v25.23.0)

## Why (this is the root cause, not the pandas bug)

ADR-047 fixed an 80× O(n²) that was linear on the dev laptop and quadratic in production —
**same code**. The reason it hid for weeks: nobody had inventoried dev vs prod. `requirements.txt`
said `pandas>=2.2,<3`, so the laptop resolved to **pandas 3.0** and Railway to **pandas 2.x** — both
"valid" — and a pandas-3 `get_indexer` that is O(1) is O(n) on pandas 2. A loose pin changed
**algorithmic complexity** silently. The omission (no pinning, no inventory) *is* the root cause.

## Full inventory — dev vs prod (what was actually running)

| Package | DEV (was) | PROD (Railway 3.12) | Diverged? |
|---|---|---|---|
| **Python** | 3.14.3 | 3.12.6 | ✗ minor |
| **pandas** | **3.0.2** | **2.3.3** | ✗✗ **MAJOR — the O(n²)** |
| numpy | 2.4.4 | 2.5.1 | ✗ |
| fastapi | 0.136.1 | 0.139.0 | ✗ |
| uvicorn | 0.46.0 | 0.51.0 | ✗ |
| starlette | 1.0.0 | 1.3.1 | ✗ |
| anyio | 4.13.0 | 4.14.1 | ✗ |
| pydantic | 2.13.3 | 2.13.4 | ✗ |
| requests | 2.33.1 | 2.34.2 | ✗ |
| pyarrow / httpx | 24.0.0 / 0.28.1 | same | ✓ |

**Nine of eleven diverged.** One silently changed complexity; assume the rest are latent risks.

**Where Railway's Python comes from:** `api/.python-version = 3.12`. It is pinned — not a platform
default — but Nixpacks resolves the **minor** and floats the **patch** (`/env` reports the live patch;
[Railway supports `.python-version`](https://station.railway.com/questions/can-i-set-my-python-version-for-my-deplo-019590cc), builder-dependent). Patch drift is low-risk; the minor pin is what prevents a repeat of the 3.14-vs-3.12 gap.

## Decision

1. **Pin every runtime dep to exact `==`** in `requirements.txt` (and `requirements-dev.txt`),
   including the ASGI transitives that drifted (starlette/pydantic/anyio). Railway installs from
   `requirements.txt`, so these are honored in prod.
2. **Standardise on PROD's versions (pandas 2.x)** and move **dev** to match — production is the
   environment that must not break. Rebuilt the dev venv as **Python 3.12.6 + the pinned set**; dev
   and prod now resolve **identically** (verified by `pip freeze` on both).
   - *Risk of the alternative (move prod to pandas 3.0):* a major-version bump of the live engine's
     core dependency — larger blast radius, must be a deliberate, separately-verified change. Not now.
3. **`GET /env`** reports the running container's Python + package versions, so drift is visible at a
   glance and checkable after every deploy. No auth (versions aren't secret; matches `/ping`).

## Verify

- **Result-safe:** the engine is byte-identical across py3.14/pandas-3 and py3.12/pandas-2 (net,
  trades, max-DD, quality all identical on a 1-yr run), and the golden-snapshot test (values captured
  under pandas 3) passes under pandas 2. The pins do not touch computation, so the app's 1-week
  (+$817.66 / 16 trades) and 1-year (-$2,244.27 / 1,225 trades) results are unchanged.
- **Dev == prod:** both resolve to `python 3.12.6, pandas 2.3.3, numpy 2.5.1, pyarrow 24.0.0,
  fastapi 0.139.0, uvicorn 0.51.0, starlette 1.3.1, pydantic 2.13.4, anyio 4.14.1, requests 2.34.2`.
- **Full suite:** 125 passed under the rebuilt 3.12/pandas-2 venv.

## Railway noise (Task 3)

`/profile` at a fixed 1-yr range, 3× back-to-back on the same build (25.22.0): **1915 / 2184 /
2748 ms → 1.43× spread**, `cpu_throttle_ratio` swinging 0.97–1.37. Railway is **noisy**. The earlier
"24s → 48s" 2× jump (25.20.0 → 25.21.0) was **variance, not a regression** (ADR-046 was a no-op and
couldn't slow anything; at 24–48s absolute a ~1.4× machine swing + burst-throttle state doubles it).
**Standing rule: every performance claim needs 3 runs + a median, never one sample.**

## Process rule (Task 4)

For any performance/environment mystery: **search first** (ten minutes; report what you found or that
you found nothing). Our bug wasn't a single documented pandas issue, but "batch index lookups instead
of per-row `get_indexer`/`.loc`" is a textbook, version-sensitive anti-pattern (pandas
[#17754](https://github.com/pandas-dev/pandas/issues/17754), [#64363](https://github.com/pandas-dev/pandas/issues/64363)) — a search would have pointed there hours earlier, for free.

**RULE:** dev and prod run the SAME pinned versions, always. Widen a pin only with a deliberate
re-test under the deployed Python (3.12) confirming byte-identical results. Check `/env` after deploy.

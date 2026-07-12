# ADR-045 — `/profile` diagnostic endpoint (locate the Railway superlinearity)

**Status:** Accepted (v25.20.0)

## Problem

ADR-044's ~15× local speedup became ~2.9× on Railway (1-year: 69.6s → 24.0s, measured), and the
Railway curve is **superlinear** in range: ~2–3s flat up to 90 days, then a jump to 24s at 365 days
(4× data → 8× time), and the 6-year run never finished.

**The lesson:** a local benchmark told us something that was not true in production ("merged ≠ live"
again). So this ADR does **not** ship a speculative fix off local numbers — it ships the instrument
to measure the problem **on Railway**.

## What the local profile already rules out

A per-stage timing of the real app path (`_execute_compare_sync`, the compare pipeline) at 90d vs
365d, locally:

| stage | 90d | 365d | ratio |
|---|---|---|---|
| signal-gen + slice | ~0.1s | ~0.07s | flat (fixed cost) |
| primary run (1×) | 0.06s | 0.23s | ~3.8× (linear) |
| 6 variants + teaching | 0.63s | 1.83s | ~2.9× |
| total | **0.80s** | **2.16s** | **2.68×** |
| peak RSS | 317 MB | 317 MB | flat |

Locally the pipeline is **sub-linear** (2.68× for 4× data), RSS is flat, and a CPU-throttle probe
shows no throttling. **The superlinearity is therefore not algorithmic — it is environmental** (a
memory/GC threshold, or Railway Hobby CPU-burst throttling — the flat-then-cliff shape is the
throttling signature). Which one requires Railway measurement.

## Decision — `POST /profile` (API-key gated, additive, read-only)

Runs the compare pipeline and returns, with **production** numbers:

- **Per-stage wall time** — derived from the existing `_progress` hooks (no engine change):
  `signal_gen+slice` (start→20), `primary_run` (20→50), `variants+teaching` (50→80),
  `validation` (80→95), `serialize_finalize` (95→end).
- **`peak_rss_mb`** — `getrusage` peak RSS. If this grows with range → **memory-bound** (the evidence
  needed before any plan-size discussion).
- **`cpu_probe_before_ms` / `cpu_probe_after_ms` / `cpu_throttle_ratio`** — a fixed busy-loop run
  before and after the backtest. If `after ≫ before` on Railway → the process was **CPU-throttled**
  during the run (burst credits exhausted) — the flat-then-cliff cause. This directly discriminates
  throttling from memory.

`/run`, `/run/compare`, `/run/async` are untouched. `/profile` holds the request, so it inherits
Railway's ~60s proxy limit — use it for ranges up to ~1 year; for 6-year use `/run/async` (the
ADR-044 heartbeat + terminal callback now make it complete or fail loudly rather than stall).

## How to use it (on Railway, after deploy)

```
curl -s -X POST https://<engine>/profile \
  -H "x-api-key: $KEY" -H "Content-Type: application/json" \
  -d '{"signal_code":"...ORB...","direction":"long_short","run_validation":false,
       "start_date":"2024-04-01","end_date":"2025-04-01"}' | jq
```

Read the result: **RSS climbing with range → memory**; **`cpu_throttle_ratio` ≫ 1 → CPU-burst
throttling**; which **stage** balloons tells us where. Then the fix (a follow-up ADR) targets the
*confirmed* cause — not a guess.

**RULE:** performance claims for the deployed engine must be measured in the deployed environment.
Local numbers narrow hypotheses; they do not confirm a production fix.

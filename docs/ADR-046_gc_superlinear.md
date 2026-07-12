# ADR-046 — The Railway superlinearity is GC; disable it during a run

**Status:** Accepted (v25.21.0) — fix shipped with an in-deploy A/B to confirm on Railway.

## What `/profile` (ADR-045) measured on Railway (engine 25.20.0, ORB-size long/short workload)

| range | trades | total | primary_run | variants+teaching | peak_rss_mb | cpu_throttle_ratio |
|---|---|---|---|---|---|---|
| 1 mo | 89 | 0.65s | 45 ms | 520 ms | 380 | 1.17 |
| 3 mo | 314 | 1.81s | 241 ms | 1,438 ms | 380 | 0.96 |
| 1 yr | 1,243 | 23.8s | 3,162 ms | 20,562 ms | 463 | 1.04 |

Trade counts (89/314/1243) match the app's real workload (95/274/1234), so this is a faithful probe.

**Both instrument hypotheses are ruled out by the numbers:**
- **Not CPU throttling** — `cpu_throttle_ratio ≈ 1.0` at every size (the busy-loop probe is identical
  before vs after the 24s run). A plan upgrade would not help.
- **Not memory-bound** — peak RSS ~460 MB at 1 yr, nowhere near the 8 GB cap, and barely grows.

**What's actually superlinear is the compute itself:** `primary_run` (a *single* sim loop) goes
45 → 241 → 3162 ms; from 3mo→1yr that is 4× the data for **13× the time** (~O(n²)). But this exact
loop is **linear locally** (188/403/813 ms at 1/2/4 yr on Python 3.14). Same code — superlinear on
Railway, linear on the laptop, no throttling, flat RSS.

## Diagnosis

The one environment difference is **Python 3.12 (Railway) vs 3.14 (local)**. Python **3.13 made the
cyclic GC incremental**; the older non-incremental generational GC does **O(n²)** work when a loop
retains many container objects, because full (gen-2) collections re-scan the whole growing live set.
Our sim loop retains exactly that: an `equity_curve` of **one dict per bar** plus per-trade `Trade`
objects and materialized `Timestamp`s — ×7 runs in the compare pipeline (~72k dicts/run at 1 yr).
On 3.13+ the incremental collector spreads that work out and it stays linear — which is why the
laptop (3.14) never reproduced the cliff, and forcing aggressive GC thresholds locally didn't either.

## Fix — disable GC for the duration of a run (`_no_gc` context manager)

Wrap `/run`, `/run/compare`, `/run/async`, and `/profile` compute in `gc.disable()` … `gc.enable()`
(restoring the prior state). **Result-preserving:** GC only reclaims reference *cycles*, and the run
creates none — every object is freed by refcount at return; peak RSS is unchanged. Python 3.13+ is
unaffected (GC already incremental); on 3.12 this removes the O(n²) term.

## Confirming it on Railway (not the laptop)

Locally the fix shows ~no speedup (3.14's GC is already cheap), so `/profile` gained a
**`disable_gc` query toggle** and a **`gc_collections`** field to A/B it **on the deployed engine**:

```
/profile?disable_gc=false  (GC on, the 25.20.0 behavior)   -> expect ~24s at 1yr, nonzero gc_collections
/profile?disable_gc=true   (ADR-046 fix)                    -> expect ~2-3s at 1yr, gc_collections [0,0,0]
```

If gc-off collapses the 1-year time, the cause and the fix are confirmed with production numbers.
This is run post-deploy; the fix is low-risk and reversible if it does not.

**Alternative root-cause fix (recommended follow-up):** bump Railway's `.python-version` 3.12 → 3.13
(incremental GC — the reason the laptop is fast). `gc.disable()` is the safer *immediate* fix (zero
dependency-compat risk); the Python bump fixes it at the source.

**RULE:** long allocation-heavy loops on Python ≤3.12 must run with GC disabled (no cycles created,
so it's safe). Confirm engine performance in the deployed environment, never on the laptop.

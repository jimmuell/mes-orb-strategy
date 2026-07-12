# ADR-047 — The real Railway superlinearity: O(n²) `get_indexer` in the churn guard

**Status:** Accepted (v25.22.0). **Supersedes the diagnosis in ADR-046** (GC was not the cause).

## How ADR-046 was refuted by its own instrument

ADR-046 shipped a `gc.disable()` fix on the theory that Python 3.12's GC was doing O(n²) work.
Running the `/profile` A/B **on Railway** (25.21.0) killed that theory:

```
1yr disable_gc=false (GC on):  47.7s   gc_collections [0,0,0]
1yr disable_gc=true  (GC off): 45.5s   gc_collections [0,0,0]
```

**`gc_collections = [0,0,0]` at every range (1mo/3mo/1yr)** — GC never ran on Railway at all — and
GC-on vs GC-off were identical. `gc.disable()` was a **no-op**. Good that we A/B'd before trusting it.
(`cpu_throttle_ratio ≈ 1.0` and flat RSS had already ruled out throttling and memory in ADR-045/046.)

## Finding the real cause — reproduce the Railway environment

The one difference that mattered: the **laptop ran pandas 3.0.2 / numpy 2.4 on Python 3.14**, while
Railway installs **pandas < 3 / numpy < 3 on Python 3.12** (per `requirements.txt` pins). Built a
matching local env (`python3.12` + `pandas 2.3.3`) and the O(n²) **reproduced immediately**:

| range | bars | py3.12/pandas2 (before) | µs/bar |
|---|---|---|---|
| 1 yr | 70,883 | 3,726 ms | 52.6 |
| 2 yr | 141,806 | 14,730 ms | 103.9 |
| 4 yr | 283,047 | 61,859 ms | 218.5 |

Per-bar cost **doubles as bars double** → clean O(n²) (linear on the 3.14/pandas-3 laptop, which is
why local never saw it). `cProfile` under 3.12 pinned it exactly: **`_quality_metrics` = 14.7s of
15.2s**, inside it **pandas `datetimes.astype` 11.6s (8,052 calls) + `Index._get_indexer` 2.6s
(≈1 call/trade)**. The sim loop (`run_backtest_long_short` itself) was 0.15s — ADR-044 is fine.

## Cause

The ADR-042 churn guard called **`df.index.get_indexer([entry, exit])` once per trade**. On
**pandas 2.x** each `get_indexer` on a `DatetimeIndex` `astype`s the whole index (O(n)); trades grow
∝ n, so it's **O(trades × n) = O(n²)**. Pandas 3.0 made `get_indexer` cheap, masking it on the laptop.

## Fix

Resolve **all** trade dates in **one batched `get_indexer`** call — O(n) instead of O(n²), returning
the identical positions:

```python
pos = df.index.get_indexer([t.entry_date for t in closed] + [t.exit_date for t in closed])
```

**Confirmed under 3.12/pandas 2.x** — O(n²) → O(n), per-bar cost flat (2.2/2.7/2.7 µs):

| range | before | after | speedup |
|---|---|---|---|
| 1 yr | 3,726 ms | 159 ms | 23× |
| 2 yr | 14,730 ms | 382 ms | 39× |
| 4 yr | 61,859 ms | **777 ms** | **80×** |

**Byte-identical:** the batched result equals the per-trade result to the digit (verified), and the
existing `test_quality_metrics` values are unchanged. New regression guard asserts `get_indexer` is
called ≤1× regardless of trade count.

## Also in this change

Removed ADR-046's production `gc.disable()` wraps (`/run`, `/run/compare`, `/run/async`) — a confirmed
no-op that carried a "no reference cycles forever" assumption. Kept `/profile`'s `disable_gc` toggle +
`gc_collections` field: they're what *proved* GC wasn't the cause. `__version__` → **25.22.0**.

**Post-deploy confirmation (to run on Railway):** `/profile` at 1yr should drop from ~48s to ~2–3s;
6-yr (≈6× a 1-yr, ~10–15s now) should complete well under the proxy. I'll run it and report.

**RULE:** never call `df.index.get_indexer` (or any full-index pandas op) once per trade/row — batch
it. And measure performance in the deployed environment: the laptop's pandas 3.0 hid an O(n²) that
production's pandas 2.x exposed.

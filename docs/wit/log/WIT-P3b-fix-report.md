# WIT-P3b-fix — gate §5 assumption-credit on a stated entry trigger

Prompt: **WIT-P3b-fix** — close the "assume-your-way-into-Class-A" hole. One task, scorer-only change. On `wit-phase3` (no branch, no merge).

---

## 1. STEP 0 result
- On `wit-phase3`: **yes**. HEAD = **`84ef303`** (WIT-P3b): **yes**.
- Tree clean: **yes** — only the known untracked `pine/mes_net_pnl_v2.pine` (ignored); LFS clean.

## 2. The gating change (precise)

Changed **only** the default-credit gating in `api/wit/extraction/completeness.py`. Schema, score formula, `REQUIRED_BASE`, `EXIT_PAIR`, weights, and Class A/B/C rules are **untouched**.

- **`UNCONDITIONAL_DEFAULTS`** — removed **D3, D4, F4**; now **`{E1, H1, H2, F5, B3}`** (peripheral mechanics/costs that never depend on the entry).
- **D3 has no default at all.** The §5 close-vs-touch default disambiguates an *existing* trigger; it can't invent one. A trigger that is stated is already satisfied via its `status` (specified/implied), so D3 needs no default. A fully `unspecified` D3 = no trigger → never credited.
- **New `has_entry(template)`** := D3 status is `specified`/`implied` (a trigger is actually stated).
- **New `ENTRY_CONDITIONAL_DEFAULTS = {D4, F4}`** — order mechanics ("market on trigger") and time-exit ("session close if no target/stop pathway exits") both presuppose an entry. Their default is creditable — in **both** `_has_default`/`_satisfied` **and** the `assumption_fills` count — **only when `has_entry` is true**. When `has_entry` is false, D4 and F4 get no default credit.
- **Unchanged:** G1 stays conditional on `G1.assumption` being non-null; E1/H1/H2/F5/B3 unconditional; weights, required set, exit pair, score formula, and class rules all identical.

Net: peripheral mechanics/costs may still be assumed; **the core entry can never be manufactured by a default.**

## 3. Recomputed scorer output (both anchors)

```
WIT-T-0001:  {score: 66, class: "A", required_missing: []}                      assumption_fills = 6
WIT-T-0002:  {score: 21, class: "B", required_missing: ["B1","D1","D3","D4","F2|F4"]}  assumption_fills = 5
```

- **T-0001 — UNCHANGED ✅**: A, 66, `[]`, `assumption_fills == 6`. D3 is `specified` → `has_entry` true → F4's entry-conditional default still credits, so the count and class are exactly as before. The fix does not disturb the Class-A anchor.
- **T-0002 — new `required_missing` = `["B1","D1","D3","D4","F2|F4"]`** (was `["B1","D1"]`). D3 is `unspecified` → `has_entry` false, so: D3 (no default) is missing; D4 (entry-conditional, uncredited) is missing; and the **F2|F4** exit pair is missing (F2 has no default, F4's entry-conditional default is uncredited). `assumption_fills` drops **8 → 5** (B3, E1, F5, H1, H2 remain; D3/D4/F4 no longer counted). **Class stays "B", score stays 21** — both as the prompt specified. This is the fuller, more honest set: the candle-formation source genuinely states no trigger, no order mechanics, and no exit.

## 4. New regression test

**`test_no_stated_trigger_never_class_A`** — builds a minimal full 27-field template with **B1, B2, D1, D2, F1, F2 `specified`** but **D3 (trigger) and D4 `unspecified`**, then asserts:
- `"D3" in required_missing` (an unspecified trigger is missing, never defaulted),
- `"D4" in required_missing` (order mechanics can't default without a trigger),
- `class != "A"` (a setup with no stated trigger must never route to Class A).

**Result: PASSED.** This locks the hole shut — the exact false-Class-A path (setup present, trigger absent) is now a permanent guard.

## 5. Full suite result + anything unexpected

- `test_completeness.py`: **11 passed** (10 prior + 1 new regression). T-0001 anchor assertions unchanged and green; T-0002 assertion updated to the new set + `assumption_fills == 5`.
- **Full suite: 153 passed** (152 prior + 1 new), 0 failed. No regression anywhere.
- Nothing unexpected. Score formula and weights untouched, so both scores are stable (66 / 21); only the default-credit gating moved, exactly as scoped. `api/requirements.txt` untouched (no deps); no audit-gate run needed.

WIT-P3b-fix — Completed

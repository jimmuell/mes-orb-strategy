# ADR-050 — Pin the Python patch, and put the security audit in CI with teeth

**Status:** Accepted (v25.25.0)

## Why

ADR-048/049 pinned every Python *package* to `==` and locked the full transitive closure — but two
holes remained, and both are the same species of bug that cost us the ADR-047 day: *something we run
in prod is not something we control or verify.*

1. **The Python patch floated.** `api/.python-version` pinned only the **minor** (`3.12`). Railway's
   Nixpacks floated it to **3.12.13**; a freshly-rebuilt dev venv came up **3.12.6**. Dev and prod
   drifted apart on day one — the exact failure mode ADR-048 existed to kill, one level down.
2. **The audit was a one-time act, not a gate.** ADR-049 ran `pip-audit` by hand and pinned `h11`.
   Nothing stops the *next* transitive bump from reintroducing a CRITICAL. CodeRabbit flagged the
   h11 CRITICAL on PR #44 and **it merged anyway** — a warning nobody is forced to act on is not a
   control.

## Part 1 — Python patch: DECISION = pin it (option a)

**Chosen: pin the exact patch. `api/.python-version = 3.12.13`.** Dev moved to match prod (rebuilt
the venv on 3.12.13 via `uv python install 3.12.13`), *not* the reverse.

Rejected the alternative (accept the float) even though the risk is genuinely low — a patch release
won't change algorithmic complexity, and 3.12.6→3.12.13 is bugfix-only. Two reasons the low risk
doesn't earn a pass:

- The whole ADR-048/049 thesis is **"know and control exactly what we run."** A floating patch is,
  by definition, unknown until we look — and it had *already* silently diverged (prod .13, dev .6)
  the first time we looked. "Probably fine" is the phrase that cost us the ADR-047 day.
- Pinning costs us nothing we want. We now own the bump: change one file, rebuild, re-run the suite,
  confirm byte-identical, ship. That is the same deliberate-bump discipline we already apply to every
  package pin. CI enforces the pin via `python-version-file: api/.python-version`, so dev == CI == prod.

**What would make the float acceptable (and doesn't hold here):** if CI rebuilt on the *same*
floating resolver as prod on every run, so drift was impossible-by-construction. It doesn't — dev,
CI, and Railway resolve independently — so the only way to guarantee equality is to name the version.

## Part 2 — pip-audit as a CI gate with teeth (the one that matters)

**`.github/workflows/ci.yml`** runs on every PR into `main`, two required jobs:

- **`test`** — the 125-test engine suite under Python **3.12.13** (from `api/.python-version`).
- **`audit-gate`** — `python scripts/audit_gate.py api/requirements.txt` against the **locked runtime
  set**.

**`scripts/audit_gate.py`** runs `pip-audit`, then classifies each finding's severity from OSV
(CVSS v3 base score computed from the vector; else the DB's own label) and enforces:

| Severity | Action |
|---|---|
| **HIGH / CRITICAL** | **FAIL the build** (exit 1). Not a warning. |
| MEDIUM / LOW / NONE | Reported, does not block. |
| UNKNOWN | Blocks (conservative) unless allow-listed. |
| In `ALLOWLIST` | Reported as an accepted exception **with its written reason**; does not block. |

The allow-list is a dict in the gate script (`{vuln_id: "reason"}`), currently **empty**. An accepted
finding is a *decision on the record* (a reason in code, reviewed in the PR), never a silently-ignored
warning. This is the ADR-049 rule — "accept a finding only with a written reason" — made executable.

**Proof of teeth (a guard nobody has seen fail is not a guard):**

```
A) real runtime lock (api/requirements.txt):   ✅ no known vulnerabilities        exit 0
B) deliberate CRITICAL (h11==0.9.0):           ❌ BLOCK [CRITICAL] PYSEC-2026-348  exit 1
```

Ran both locally under a standard CPython 3.12 (the same interpreter class CI uses). The gate went
**red** on the deliberately-reintroduced CRITICAL — the exact advisory ADR-049 fixed — then the test
input was removed. The lock passes clean.

**Local-run caveat:** `pip-audit -r <file>` spins up a helper venv whose `ensurepip` **SIGABRTs under
the uv-managed python-build-standalone** 3.12.13 build. It works fine under `actions/setup-python`
(a standard build), which is what CI uses. To run the gate locally, use a standard-build Python
(`/opt/homebrew/bin/python3.12 -m venv …`) rather than the uv venv. This is a uv-build quirk, not a
gate defect.

## Verify

- Dev Python **3.12.13** == prod (`/env` on Railway reports 3.12.13 post-deploy).
- Full suite **125 passed** under 3.12.13 + the full lock.
- **Result-safe:** no computational code changed (only the version string + tests + CI + gate). The
  golden-snapshot test still passes → 1-week **+$817.66 / 16 trades** and 1-year
  **-$2,244.27 / 1,225 trades** unchanged.
- Gate proven red-then-green (above).

**RULE:** pin the Python **patch**, not just the minor — an unpinned patch is an unaudited runtime.
Every PR runs `pip-audit` against the runtime lock; **HIGH/CRITICAL fails the build**; a finding is
accepted only via a written allow-list entry with a reason.

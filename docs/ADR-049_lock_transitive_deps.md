# ADR-049 — Lock the full transitive closure (pin h11; end half-pinning)

**Status:** Accepted (v25.24.0)

## Why

ADR-048 pinned the **9 direct** deps to `==` "so nothing drifts" — but left the **transitive**
closure to the resolver. `h11` (uvicorn's HTTP/1.1 parser) was unpinned and drifted to **0.9.0** in
prod, which accepts malformed Chunked-Encoding bodies — **CRITICAL PYSEC-2026-348 /
GHSA-vqfr-h8mv-ghfj**, on an internet-facing API. CodeRabbit flagged it on PR #44 and it merged
anyway. The irony is the lesson: **half-pinning is exactly the hole ADR-048 was meant to close.**

## Task 1 — pin h11

`h11==0.16.0` is the patched release (advisory affects `<0.16.0`) and is what uvicorn 0.51.0 **and**
httpx 0.28.1 resolve to on a fresh install — so it's compatible with both. Pinned.

## Task 2 — full audit, then lock everything (not half-pin)

`pip-audit` against the actual installed set (dev == prod, per ADR-048):

| Package | Version | Advisory | Disposition |
|---|---|---|---|
| h11 | (unpinned → 0.9.0 in prod) | PYSEC-2026-348 (CRITICAL) | **pinned `==0.16.0`** |
| pytest | 8.4.2 | PYSEC-2026-1845 | **bumped `==9.0.3`** (dev/test-only, not shipped) |

**Decision: full lock, not "pin the security-relevant few."** `requirements.txt` now pins the entire
runtime **transitive closure** (35 packages, generated from a clean `python3.12 -m venv … && pip
install <direct> && pip freeze`), so no transitive can silently resolve to a vulnerable version ever
again. Railway installs from `requirements.txt`, so it honors the lock directly — no build-config
change needed. **Post-fix `pip-audit` on runtime + dev: "No known vulnerabilities found."**

## Task 3 — is h11 on the production request path? **No — installed but idle.** (Confidence: high.)

- In the runtime closure, `h11` is `Required-by: uvicorn` **only**. `httpx` (the other h11 consumer)
  is **dev/test-only** (TestClient) — it's not in the runtime set; prod's outbound calls use
  `requests` (urllib3).
- The Procfile runs `uvicorn server:app` with **no `--http` flag** → `--http auto` → uvicorn uses
  **httptools** (installed via `uvicorn[standard]`, present as `httptools==0.8.0`) to parse inbound
  HTTP/1.1. `h11` is uvicorn's *fallback* parser, used only with `--http h11` or if httptools is
  absent.
- ⇒ The malformed-chunked-encoding defect in h11 0.9.0 is **not reachable on the prod request path**.
  This lowers urgency but does **not** change that it must be pinned — defense in depth: if httptools
  is ever dropped from `[standard]`, `--http h11` is set, or httpx enters the runtime, h11 goes live.

## Verify

- `pip-audit` (runtime + dev): **clean**.
- Full suite **125 passed** under Python 3.12 / pandas 2.3.3 / pytest 9.0.3 + the full lock.
- **Result-safe:** no computational code changed; the golden-snapshot test (values captured under
  pandas 3) still passes under pandas 2 — so 1-week **+$817.66 / 16 trades** and 1-year
  **-$2,244.27 / 1,225 trades** are unchanged.
- `/env` now also reports `h11`, `httptools`, `uvloop`, `websockets`, `urllib3` — post-deploy it must
  show `h11: 0.16.0` on Railway.

**RULE:** pin the **full** transitive closure, not just direct deps — an unpinned transitive is an
unaudited transitive. Re-run `pip-audit` on every dependency change; accept a finding only with a
written reason (e.g. dev-only, not on the request path) recorded here.

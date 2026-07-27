# WIT-P3a — RECON: server wiring, deploy state, extraction-function design

Prompt: **WIT-P3a** — read-only recon + this one report. No engine code, no new endpoints, no dependency installs. Branch `wit-phase3` off `main`.

---

## 1. STEP 0 result

| Check | Result |
|---|---|
| `git remote -v` | `origin  https://github.com/jimmuell/mes-orb-strategy.git` (fetch+push) — engine repo ✓ |
| `pwd` | `/Users/jameslmueller/Projects/mes-orb-strategy` — ends in `mes-orb-strategy` ✓ |
| `git status` | Clean tree. Only entry: untracked `pine/mes_net_pnl_v2.pine` (predates all WIT work; never staged). **`git lfs status` shows nothing to commit/push — no smudge, no genuine edits.** ✓ |
| `git log --oneline -8` | HEAD = **`de6c503` (P2e)**; **`c0bfa05` (P2d)** beneath; **`b90444d` (P2c merge)** below that. Both close-out commits present, history matches. ✓ |

Branch created: `git switch -c wit-phase3` → on `wit-phase3`. All four gates passed.

---

## 2. Area A — Server / API wiring

**Framework: FastAPI 0.139.0** (`api/requirements.txt:17`), served by `uvicorn[standard]==0.51.0` (`:18`), pydantic 2.13.4 (`:42`), starlette 1.3.1 (`:51`). App object created at `api/server.py:117` (`app = FastAPI(...)`); CORS middleware added at `:132` (origins from `ALLOWED_ORIGINS` env, `:129`). Routes are registered with **plain `@app.<verb>` decorators — no `APIRouter`, no route prefixing.**

**Current route inventory (`api/server.py`):**

| Route | Line | Auth | Notes |
|---|---|---|---|
| `GET /health` | 478 | none | liveness |
| `GET /ping` | 491 | none | version + data-path probe (`:495–500`) |
| `GET /env` | 506 | none | version inventory (ADR-049) |
| `POST /run` | 531 | `verify_api_key` | sync backtest; **takes `signal_code` and `exec()`s it** |
| `POST /run/async` | 910 | `verify_api_key` | 202 + BackgroundTasks + callback (ADR-037/040) |
| `POST /profile` | 939 | `verify_api_key` | diagnostic (ADR-045) |
| `POST /run/compare` | 1262 | `verify_api_key` | six teaching cards |

**Auth:** `verify_api_key` (`:205`) compares the `X-API-Key` header to the `BACKTEST_API_KEY` env var (`:141`); **fail-closed** — returns 503 if the key is unset (`:206–214`), 401/403 on mismatch (`:215`).

**Request/response conventions: pydantic v2 `BaseModel`.** Models: `BacktestRequest` (`:219`), `BacktestResponse` (`:242`), `AsyncBacktestRequest(BacktestRequest)` (`:255`), `CompareResponse` (`:1006`). `BacktestRequest.signal_code` is a required field (`:220`) — **raw Python that the engine executes** (see security note below).

**`api/wit/` is library-only — NOT wired into the server.** `grep` for `import wit / from wit / vp_orb / event_study / volume_profile / path_metrics` in `server.py` returns **zero hits**. The Phase-1/2 modules (`analysis.py`, `config.py`, `event_study.py`, `event_study_report.py`, `path_metrics.py`, `volume_profile.py`, `vp_orb_runner.py`) are imported only by `api/tests/` and each other. **No WIT computation is exposed over HTTP today.**

**`api/callback_writer.py` — the async-callback seed (ADR-040), 68 lines, fully implemented:**
- `CallbackWriter.update_run(run_id, fields)` (`:47`) POSTs `{"run_id", "fields"}` to a caller-supplied edge-function URL with an `X-Callback-Secret` header (`:49–58`), `allow_redirects=False` so the secret can't bounce hosts, `raise_for_status()` on non-2xx.
- `is_allowed_callback_url(url)` (`:22`) — **SSRF guard**: https-only, hostname must equal/end-with the allowed suffix (default `.supabase.co`, `CALLBACK_ALLOWED_HOST_SUFFIX` overridable, `:19`); parsed-hostname check defeats `https://ok.supabase.co@evil.com`.
- `get_callback_writer(url, secret)` (`:62`) → writer or `None` if either missing.
- **Called by:** `server.py:51` (import), `server.py:914` (inside `/run/async`); and monkeypatched in `tests/test_run_async.py:198,223`.

**Async / background machinery (exists, and is substantial):**
- `/run/async` (`:910`) uses FastAPI **`BackgroundTasks.add_task(_run_async_job, req, writer)`** (`:924`), returns `202 {"run_id","status":"accepted"}` immediately.
- `_run_async_job` (`:847`) runs the compute **off the event loop** via `asyncio.to_thread(_execute_compare_sync, …)` (`:871–872`), with `asyncio.wait_for` + `asyncio.shield` around a **heartbeat** (`_HEARTBEAT_SECONDS`, env, `:778`) that re-posts `running` while compute proceeds (`:875–887`), and a **terminal-state guarantee** — success → mapped columns, any error/crash → `failed` + truncated traceback (`:889–909`).
- No Celery/RQ/external queue; concurrency is in-process (`asyncio` + `BackgroundTasks`). `asyncio` imported at `:25`.

**How much of the WIT-03 async/callback contract already exists:** the **transport layer is ~80% there** — background acceptance, progress heartbeat, SSRF-guarded callback writer, guaranteed terminal state. What's missing is everything **WIT-03-shaped**: it is all bound to the **`BacktestRequest`/compare payload**, not the WIT-03 `POST /wit/v1/runs` body (`StrategyConfig`/`EventStudyConfig`), and there is **no** `config_hash` idempotency, **no** `kind` routing, **no** `/wit/v1/*` path, **no** `GET /wit/v1/runs/{id}` status endpoint.

**Security note (bears on WIT-03 §1/§8.7):** `/run`, `/run/async`, `/run/compare`, `/profile` all accept `signal_code` and execute it — `validate_signal_code` AST allowlist (`server.py:378`), `SAFE_BUILTINS` namespace (`:855`-region), `_run_user_code` / `exec` via `getattr` indirection (`:602`, `:1057`), `SIGNAL_EXEC_TIMEOUT` (`:404`). WIT-03 §1 requires **"structured configs only, never code… exec() endpoints disabled for WIT traffic."** So WIT cannot reuse these endpoints as-is; it needs a new structured-config surface with the exec path off.

---

## 3. Area B — Deployment / Railway state

**Deploy config = Procfile only (buildpack/Nixpacks style).** `api/Procfile` (1 line):
```
web: uvicorn server:app --host 0.0.0.0 --port ${PORT:-8090}
```
Verified **absent**: `railway.json`, `railway.toml`, `Dockerfile`, `nixpacks.toml`, `runtime.txt` (checked repo root **and** `api/`). So the deploy is a **Railway/Heroku-style buildpack**: Railway detects Python, installs `api/requirements.txt`, and runs the Procfile `web` process. `${PORT}` is injected by the platform; local default `8090`.

**Start command / entrypoint:** prod and local are the same command — `uvicorn server:app` with `working-directory: api` (implied by the Procfile living in `api/` and importing `server:app`). No separate prod entrypoint.

**Python pin:** `api/.python-version` = **`3.12.13`** (exact patch, ADR-050) — CI and Railway both key off this.

**Env vars / secrets (all read via `os.environ`, none hardcoded):**
| Var | Where | Default / behavior |
|---|---|---|
| `BACKTEST_API_KEY` | `server.py:141` | **required**; unset → 503 fail-closed |
| `PORT` | `Procfile` | platform-injected; local `8090` |
| `DATA_PATH` | `server.py:142` | default `api/data/ES_test_6mo.txt` (the 6-mo fixture) |
| `ALLOWED_ORIGINS` | `server.py:129` | CORS allowlist (comma-sep) |
| `SIGNAL_EXEC_TIMEOUT` | `server.py:404` | `10` s |
| `ASYNC_HEARTBEAT_SECONDS` | `server.py:778` | `5` s |
| `CALLBACK_ALLOWED_HOST_SUFFIX` | `callback_writer.py:19` | `.supabase.co` |
| `callback_url` / `callback_secret` | per-request body (`server.py:258–260`) | never stored/logged |

**CI vs deploy — CI does NOT deploy.** `.github/workflows/ci.yml` is the only workflow. Triggers: PR into `main` + push to `main` (`:8–12`). Two jobs: **`test`** (pytest under 3.12.13, `:18–35`) and **`audit-gate`** (`scripts/audit_gate.py` on the locked `requirements.txt`, `:37–50`). **No deploy/ship/railway/ssh step** — the only "railway" token is a *comment* about the Python pin (`:28`). Deployment is therefore **Railway's own GitHub auto-deploy on push to `main`, configured in the Railway dashboard, not in-repo** (see Uncertain below).

---

## 4. Area C — Extraction-function design (proposal, NOT code)

Sources read: `WIT-02` §1–6 (extraction target, completeness classes, machine schema), `WIT-03` §4 (extraction contract), §6 (Supabase schema), §8 (engine backlog); both transcripts (`WIT-S-0001`, `WIT-S-0002`); both hand-filled templates (`WIT-T-0001` = **Class A, 17/25 ≈68%**, `WIT-T-0002` = **Class B, ~7/25 ≈28%**).

**State of the art in the repo:** **nothing extraction-related exists yet.** No `schema/` or `contract/` dir; **`schema/strategy-template.v1.json` (referenced by WIT-02 §6 and WIT-03 §4) does not exist**; no completeness scorer, no mapper, no LLM SDK in `requirements.txt`/`requirements-dev.txt`. `api/wit/` holds only the computational runners.

**The architectural fact to respect:** WIT-03 §4 places the *LLM call* in a **Supabase edge function `wit-extract`** (`{transcript, source_meta}` → structured LLM → template JSON → validate vs schema, ≤2 retries → completeness scorer → `{template, completeness, class}`), and explicitly says the **completeness scorer is a pure function that lives in the engine repo**, "shared via published package or duplicated with golden tests." Extraction result is persisted **before** any run (instant-feedback UX).

### Proposed design

**1. Where it lives.** Build a **provider-agnostic extraction *core* as an engine library** so the logic is CI-testable here regardless of who invokes the LLM:
```
schema/strategy-template.v1.json          # canonical JSON Schema (WIT-02 §6 shape) — the keystone
api/wit/extraction/
  __init__.py
  schema.py         # load + jsonschema-validate a template against v1
  prompt.py         # system+user prompt builder from the WIT-02 field spec
  provider.py       # thin LLM adapter (Anthropic) — structured output + retry
  completeness.py   # PURE scorer: template JSON -> {score, class A|B|C, required_missing}
  extract.py        # orchestrator: transcript -> validated template -> scored result
api/tests/
  fixtures/WIT-T-0001.template.json        # hand template transcribed to canonical JSON
  fixtures/WIT-T-0002.template.json
  test_completeness.py                     # scorer goldens (no network)
  test_extraction_golden.py               # LLM regression (gated; see below)
```
Rationale: the two golden transcripts + templates live here, the scorer *must* live here (WIT-03 §4), and the mapper (P3c) consumes the same schema. The Supabase `wit-extract` function then either calls an engine `/wit/v1/extract` endpoint or re-implements the prompt against the **same** schema+goldens (WIT-03's "duplicated with golden tests" path). **Recommendation: engine owns the extraction core; exposing `/wit/v1/extract` is optional and can follow.**

**2. Signature.**
```python
def extract_template(transcript: str, source_meta: dict, *, model: str, max_retries: int = 2) -> ExtractionResult
# ExtractionResult = {template: dict(WIT-02 JSON), completeness: {score, class, required_missing}, raw_meta}
```
Pure-core helpers `validate_template(dict) -> list[error]` and `score_completeness(dict) -> Completeness` are independently callable (and are what CI tests without a network).

**3. Provider + structured output.** Provider = **Anthropic Claude** (repo is Anthropic-native; no SDK pinned yet — a P3e addition, dev-gated). Enforce structure by **tool-use / forced JSON tool call whose input_schema = `strategy-template.v1.json`**, then **post-validate** with `jsonschema`; on validation failure, feed the errors back for **≤2 retries** (WIT-03 §4). Belt-and-suspenders: schema-constrained generation *and* a hard validator, because "the gaps ARE the report" (WIT-02) — a hallucinated `specified` is worse than an honest `unspecified`.

**4. Prompt strategy (high level).** One system prompt encoding WIT-02 §1 field conventions + §4 extraction rules: extract only what is said; `source_quote` mandatory for every `specified`/`implied`; **no charitable completion** (vague ⇒ `unspecified`); enforce **setup≠trigger** separation; capture **all** performance claims verbatim into A2 incl. unfalsifiable ones; populate A3 consistency flags (arithmetic, timeframe); record multiple readings into `interpretations` rather than silently choosing. **Class is an *output*, not an input** — the model fills fields; the deterministic scorer (§5) assigns A/B/C from `required_missing`, so classification never depends on the LLM's mood.

**5. Completeness scorer (pure, the CI-testable heart).** Implements WIT-02 §3: weighted score over sections **B–H**; **required-to-execute fields = B1, B2, D1–D4, F1, plus (F2 or F4)**; **Class A** = all required `specified`/`implied` and ≤6 assumption-fills; **Class B** = an isolable conditional claim but no full entry→exit loop; **Class C** = required fields unspecified and not assumable. Emits `{score, class, required_missing[]}` — exactly the WIT-03 `completeness` block and the `templates.completeness_score`/`class` columns.

**6. Golden regression tests — what "match" means.** The hand-filled `.md` templates are prose, so step one is **transcribing each into canonical WIT-02 JSON fixtures** (`WIT-T-0001/2.template.json`), reviewed by the lead engineer as the ground truth. Then two test tiers:
- **Scorer goldens (deterministic, always in CI, no network):** feed each fixture to `score_completeness`; assert **exact** `class` (A for T-0001, B for T-0002) and **exact** `required_missing` set, and `score` within ±1 field. This locks the routing logic that everything downstream depends on.
- **Extraction regression (LLM, network — gated, run on demand not every CI):** run `extract_template` on each transcript and compare to the fixture with a **scored rubric, not byte-equality** (LLM prose varies):
  - **Hard asserts:** resulting **class** correct; **per-field `status`** correct for the execution-required fields (B1,B2,D1–D4,F1,F2/F4); **`required_missing`** set correct; every `specified`/`implied` carries a non-empty `source_quote` that is a **substring of the transcript** (grounding check).
  - **Tolerant compare:** free-text `value`/`source_quote` by semantic/substring overlap, not exact string; count of A2 claims within ±1; A3 flags present for the known contradictions.
  - Report a **per-field match score**; fail the rubric below a threshold. This makes the two videos a genuine, meaningful regression suite while tolerating benign wording drift.

**7. Error / partial-extraction handling.** Schema-invalid after retries → return the **last candidate + validation errors**, marked `status:"extraction_failed"` (edge function surfaces `INVALID_CONFIG`-style state; never a silent pass). Partial extraction is **normal, not an error** — missing fields become `unspecified`, which is precisely what the scorer turns into `required_missing` and the class. Oversized transcripts: token-cap → chunk or reject with guidance (WIT-03 §5). The scorer's `{class, required_missing}` is the direct input to the completeness scorecard shown to users and to run-routing (Class A→backtest mapper, B→event study, C→untestable report).

**This is a written proposal only — no extraction code was created in this prompt.**

---

## 5. Verified vs. uncertain

**Verified from files:**
- FastAPI 0.139.0, decorator-registered routes, 7 endpoints, `X-API-Key` fail-closed auth, pydantic v2 models — all with `server.py` line cites.
- `api/wit/` is not imported by `server.py` (library-only).
- `callback_writer.py` fully implements the SSRF-guarded callback POST; `/run/async` implements BackgroundTasks + heartbeat + terminal-state (ADR-037/040).
- `/run*` endpoints exec `signal_code` (the path WIT-03 says to disable for WIT).
- Deploy = `api/Procfile` uvicorn command; **no** Dockerfile/railway.*/nixpacks/runtime.txt; Python pinned `3.12.13`; env-var inventory.
- CI (`ci.yml`) tests + audits only — **no deploy job**.
- **No** `schema/strategy-template.v1.json`, **no** extraction/mapper/completeness/LLM code anywhere; **no** LLM SDK pinned.
- Golden anchors: T-0001 Class A 17/25; T-0002 Class B ~7/25.

**Uncertain / not verifiable from the repo (stated, not inferred):**
- **Whether the engine is actually deployed on Railway right now, and at what URL** — the Railway service, its GitHub-auto-deploy binding, and prod env-var values live in the **Railway dashboard**, not in any repo file. Prior ADRs/CLAUDE.md reference a live Railway prod + `/env`/`/ping`, but I did not (and can't, read-only, no network) confirm the live deployment from files.
- The Supabase side (edge functions `backtest-callback`, `wit-extract`, DB tables in WIT-03 §6) lives in a **different repo/project** — not present here; characterized only from WIT-03.
- Which exact Claude model + token budget to use for extraction — a P3e decision (no SDK/config exists yet).
- Prod values of any secret (correctly — none are in-repo).

---

## 6. Proposed slice plan for the build prompts

Break WIT-03 §8 into one-task-each prompts. **P3b is the keystone** (schema + scorer + golden fixtures); the mapper and the extraction core both depend only on it and can proceed in parallel; the router depends on the mapper.

| Prompt | Deliverable | Depends on | Notes |
|---|---|---|---|
| **P3b — schema + completeness scorer** | `schema/strategy-template.v1.json`; transcribe both hand templates → JSON golden fixtures; `api/wit/extraction/{schema,completeness}.py` (pure); `test_completeness.py` goldens | STEP-0 branch | No LLM, no network, no new routes. Locks routing (A/B/C). Everything below validates against this. |
| **P3c — template→config mapper** | `api/wit/mapper.py`: WIT-02 JSON → `StrategyConfig`(VP-ORB)/`EventStudyConfig`; `UNSUPPORTED_CONSTRUCT` on unknown modes; golden-file tests from the two templates (reuse `vp_orb_runner`, `event_study`) | **P3b** | The engine mode vocabulary v1 (WIT-03 §3.4). Runners already exist (P1b/P2b). |
| **P3e — extraction core** | `api/wit/extraction/{prompt,provider,extract}.py`; Anthropic SDK (dev-gated); ≤2-retry structured output; golden extraction regression harness on the 2 transcripts | **P3b** | Parallelizable with P3c. Adds the only new dependency (LLM SDK) — through the ADR-050 audit gate. |
| **P3d — `/wit/v1/*` router + async** | `POST /wit/v1/runs` (structured config, **exec path OFF**), `GET /wit/v1/runs/{id}`; reuse `BackgroundTasks` + `callback_writer`; `config_hash` idempotency; error codes; `kind` routing → mapper → runner | **P3c** (calls mapper) | Reuses ADR-037/040 transport; adds WIT-03 payload shape + idempotency. |
| **P3f — sensitivity sweep runner** | Bounded sweep job on the shared queue budget; reuse `event_study_report` grid + VP-ORB sweeps | **P3d** | WIT-03 §8.5. |
| **P3g — WIT security hardening** (housekeeping) | Formally gate `signal_code`/`exec` endpoints off for WIT traffic; plan to retire `backtest/` duplicate (§8.6/8.7) | after P3d | Can be folded into P3d or done last. |

**Recommended order:** **P3b → (P3c ∥ P3e) → P3d → P3f → P3g.** Rationale: the schema + scorer + golden fixtures (P3b) are the single dependency everything shares; the mapper (P3c) and extraction (P3e) touch disjoint files and only need P3b, so they run concurrently; the router (P3d) is the integration point that needs the mapper; the sweep runner and security hardening follow. Every prompt stays additive, one-task, PR-per-slice, and passes the existing CI gate.

WIT-P3a — Completed

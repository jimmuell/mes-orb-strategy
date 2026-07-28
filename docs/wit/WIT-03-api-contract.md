# WIT — API Contract (Supabase ↔ Engine boundary)

> **Founding document 3 of 3.** The load-bearing seam of the system. Lovable builds the frontend against these shapes with fixtures; Claude Code implements the engine side exactly as written. **Neither side improvises.** Changes to this contract go through the lead engineer (Claude/Cowork) and are versioned. The canonical machine copy (OpenAPI + JSON Schemas) lives in the engine repo at `contract/`; this document owns the semantics.

**Scope note:** this contract covers Handoff 2 (Supabase edge functions ↔ Railway engine). Handoff 1 (browser ↔ Supabase) is Lovable-native and governed by the Supabase schema in §6.

---

## 1. Principles

1. **Structured configs only, never code.** The public product removes the engine's arbitrary-code path entirely; `exec()` endpoints are disabled for WIT traffic. This is the security model.
2. **Async by default.** A backtest over 18 years takes real time. Submit → job id → callback (+ poll fallback). No long-lived HTTP waits; no UI spinner tied to a connection.
3. **Deterministic & reproducible.** Every run records engine version, dataset version, config hash, and seed (bootstrap seed fixed, 10k iterations — same discipline as the existing compare framework). Same inputs ⇒ same outputs, forever, for library permalinks.
4. **Verdict-grade defaults.** Costs default per WIT-02 §5; a run with zero costs is refused for published reports (allowed only with `context: "diagnostic"`).

## 2. Authentication

- Supabase → Engine: `Authorization: Bearer <ENGINE_SERVICE_KEY>` (secret held in Supabase edge-function env; rotated quarterly).
- Engine → Supabase callback: signed with `X-WIT-Signature` (HMAC-SHA256 of body, shared secret); edge function verifies before accepting results.
- No end-user credentials ever reach the engine; the engine knows `evaluation_id`s, not users.

## 3. Endpoints (engine, `/wit/v1/*`)

### 3.1 `POST /wit/v1/runs` — submit a lab run
Request:
```json
{
  "evaluation_id": "uuid",            // Supabase-side key; idempotency token
  "kind": "backtest | event_study",
  "callback_url": "https://<supabase>/functions/v1/wit-run-callback",
  "config": { /* StrategyConfig (3.4) or EventStudyConfig (3.5) */ },
  "sweep": true,  // optional; variant grids are ENGINE-OWNED (backtest 5 cells, event_study 17, cap MAX_SWEEP_CELLS=18) — clients never specify variants
  "budget": { "max_wall_seconds": 600 }
}
```
Response `202`: `{ "run_id": "wr_...", "status": "queued", "estimated_seconds": 90 }`
Idempotent on `evaluation_id` + config hash: resubmission returns the existing run.
Sweep runs extend the idempotency key internally (`config_hash + ":sweep"`, never echoed); provenance carries the plain wire hash.

### 3.2 `GET /wit/v1/runs/{run_id}` — status/result (poll fallback)
`{ "run_id": "", "status": "queued|running|succeeded|failed", "progress": {"stage": "loading_data|simulating|validating"}, "result": { ... }, "error": { ... } }`
**Progress stages are real pipeline stages.** Never invent theater steps (TradeVerdict lesson).

### 3.3 Callback — `POST {callback_url}`
Body: same shape as 3.2 terminal state. Retries: 5× exponential backoff; poll fallback covers missed callbacks.

### 3.4 `StrategyConfig` (Class A) — the template→engine mapping
Derived deterministically from a filled WIT-02 template by the **mapper** (engine-side module, so mapping bugs are engine bugs with tests):
```json
{
  "config_version": "1.0",
  "instrument": { "symbol": "ES", "tick_size": 0.25, "tick_value": 1.25, "proxy_for": "NQ|null" },
  "data": { "dataset": "ES_5min_continuous", "granularity_needed": "5min|1min", "window": {"start": "2016-07-01", "end": "2026-07-01"} },
  "session": { "tz": "America/New_York", "trade_window": ["09:45","10:55"], "force_flat": "15:55" }, // trade_window = entry-eligibility window [first_eligible_bar_start, last_eligible_bar_start], ET wall-clock; force_flat = last RTH bar start. Example values are VP-ORB's (the mapper emits them from C1.params, P3c-2).
  "filters": { "regime": [...], "calendar": [...] },
  "bias":    { "mode": "vp_value_area_break", "params": {"range_minutes": 15, "va_pct": 70} },
  "setup_entry": { "trigger": "bar_close_beyond_level", "level": "va_high_low", "order": "market_on_close" },
  "sizing":  { "mode": "fixed_contracts", "value": 1 },
  "exits":   { "stop": {"mode": "level_offset", "ref": "poc", "ticks": 2}, "target": {"mode": "r_multiple", "value": 2.0}, "management": [], "time_exit": "force_flat", "same_bar_policy": "stop_first" },
  "risk_controls": { "max_trades_per_day": 1, "reentry": "none" },
  "costs":   { "commission_per_side": 0.62, "slippage_ticks": 1 },
  "assumptions_applied": ["sizing", "slippage", "..."]   // echoed for the report
}
```
`bias`/`setup_entry`/`exits` modes are an **enumerated, versioned vocabulary** (`contract/modes.md`). A template needing a mode the engine lacks fails fast with `UNSUPPORTED_CONSTRUCT` + the missing mode name — which becomes the engine backlog, one construct at a time (v1 vocabulary: the ORB family, level-offset stops, R-multiple targets, volume-profile levels).

### 3.5 `EventStudyConfig` (Class B)
```json
{ "event": {"definition": "bar body >= k * trailing-median body", "params": {"k": 1.5, "spike_eff": 0.50, "spike_giveback_cap": 0.20, "pullback_p": 0.40}},
  "conditions": ["regime_chop", "regime_trend"],
  "outcomes": {"horizons_bars": [1, 3, 5, 10], "measures": ["fwd_return", "giveback_pct"]},
  "data": { "...": "as 3.4" } }
```

### 3.6 Result payload (terminal `succeeded`)
```json
{
  "kind": "backtest",
  "metrics": { "trades": 0, "net_pnl": 0, "profit_factor": 0, "max_drawdown": 0, "win_rate": 0, "avg_trade": 0, "expectancy_r": 0 },
  "confidence": { "bootstrap": {"metric_cis": {"net_pnl": [0,0]}, "iterations": 10000, "seed": 42},
                   "edge_vs_luck": {"verdict": "edge|luck|inconclusive", "detail": {}} },
  "regimes": { "scheme": {"per_regime": {"label": {"n": 0, "expectancy": 0, "win_rate": 0}}} },
  "equity_curve": [ {"t": "date", "equity": 0} ],
  "trades_url": "signed URL, CSV, 24h expiry — Supabase stores a copy",
  "sensitivity": { "<variant_name>": { /* metrics… — same shape as a single-run result */ } },  // sweep runs only
  "sweep": { "requested": 0, "completed": 0, "skipped": [] },  // sweep runs only
  "provenance": { "engine_version": "", "dataset_version": "", "config_hash": "", "completed_at": "" }
}
```
Event-study results replace `metrics` with per-condition conditional distributions + CIs.
For sweep runs, skipped cells are ALWAYS disclosed in `sweep.skipped` (never silent); the primary runs first and if it exceeds the wall budget the whole run fails `BUDGET_EXCEEDED` exactly like a single run.

### 3.7 Errors
`{"error": {"code": "", "message": "", "detail": {}}}` — codes: `INVALID_CONFIG`, `UNSUPPORTED_CONSTRUCT`, `DATA_UNAVAILABLE`, `BUDGET_EXCEEDED`, `INTERNAL`. `UNSUPPORTED_CONSTRUCT` and `BUDGET_EXCEEDED` are *user-visible product states* ("this strategy needs a feature our lab doesn't support yet"), not silent failures.

## 4. Extraction contract (Supabase-internal, documented here for one-source-of-truth)

**Updated WIT-P3r (2026-07-28) — the ENGINE owns extraction; this supersedes the Supabase edge-function placement below.** The LLM call and the whole extraction stack live in the engine repo (one implementation of the product's core trick, and the mode vocabulary is generated at runtime from `contract/modes.md` in *this* repo — P3m-a). Supabase's `wit-extract` merely calls the engine and stores the result. Route: `POST /wit/v1/extract` — input `{evaluation_id, callback_url, transcript, source_meta{title,url,channel}[, budget]}`; same bearer auth, run store, idempotency (internal content-hash of transcript+source_meta), heartbeat + guaranteed-terminal-state, and signed callback as `/wit/v1/runs`. It runs the **k=3 ensemble** (`extract_template_ensemble`, env `WIT_EXTRACT_K`) and the terminal callback carries `{template, completeness, raw_meta}` where `raw_meta.ensemble_meta` holds the unanimous/majority/tie counts + per-run demotions/downgrades; failure carries the `extraction_failed` errors. Kill switch: `WIT_DISABLE_EXTRACT` (503s the route). Transcript cap 200 KB (`WIT_EXTRACT_MAX_CHARS`). Per-call cost = 3 extractions.

*Historical (pre-P3r placement, kept for context):* Edge function `wit-extract`: input `{transcript, source_meta}` → LLM (structured output enforced) → **WIT-02 template JSON** (validates against `schema/strategy-template.v1.json`; ≤2 retry loop on validation failure) → completeness scorer (pure function, engine repo, shared via published package or duplicated with golden tests) → `{template, completeness, class}`. Extraction result is stored *before* any run is submitted — instant-feedback UX depends on this ordering.

## 5. Limits & cost control

- Per-run wall-clock budget (default 600s) enforced engine-side.
- Queue: per-user 1 concurrent run (free) / 3 (paid); global cap with backpressure (`429` + `retry_after`).
- LLM extraction: token cap per submission; oversized transcripts chunked or rejected with guidance.
- Metering: Supabase records LLM tokens + engine seconds per evaluation → informs pricing (WIT-01 §7).

## 6. Supabase schema (Handoff-1 anchor; Lovable + edge functions build against this)

- `evaluations` — id, user_id, source_url, transcript_hash, status (`extracting|scored|running|complete|failed`), class, visibility (`public|private`), created_at.
- `templates` — evaluation_id, template_version, template_json, completeness_score, class.
- `runs` — evaluation_id, engine_run_id, kind, config_hash, status, result_json, trades_csv_path, provenance.
- `reports` — evaluation_id, slug (library permalink), verdict, headline_json, published_at.
- `usage` — user_id, period, evaluations_used, tokens, engine_seconds.
- (Stripe tables per Supabase/Stripe standard wiring.)

## 7. Versioning & change control

- Path-versioned engine API (`/wit/v1/`); additive changes free, breaking changes bump the path.
- `template_version`, `config_version`, `engine_version`, `dataset_version` all recorded per run; library permalinks must re-render forever from stored payloads (never recompute old reports silently).
- Contract changes: PR against `contract/` + this doc, approved by lead engineer before either builder implements. Fixtures for Lovable regenerate from the OpenAPI examples at each version.

### Change log
- **WIT-P3r (2026-07-28):** §4 updated — engine-owned extraction endpoint `POST /wit/v1/extract` (k=3 ensemble) supersedes the Supabase edge-function placement (decided P3m-a). §8 item 8 added (✓). `anthropic` moved from `requirements-dev.txt` into the shipped runtime lock with its transitive closure (distro, docstring-parser, httpx, httpcore, jiter, sniffio), pinned; ADR-050 audit gate clean. No wire-shape change to §3; `config_version` stays `1.0`.
- **WIT-P3l (2026-07-28):** WIT-02 §2 field count corrected 25→27. §3.1/§3.6 aligned to the shipped sweep surface (boolean `sweep` flag, engine-owned grids, `sensitivity`/`sweep` result blocks). Extraction layer shipped engine-side per §4 (P3e-1/2): forced `emit_strategy_template` tool call with the template schema, ≤2-retry validation loop, scorer owns class; anthropic SDK dev-only — audited runtime lock untouched. Doc-to-implementation alignment only; wire `config_version` stays `1.0`.
- **WIT-P3d (2026-07-27):** (a) §3.4 `session.trade_window` semantics pinned — *entry-eligibility window* `[first_eligible_bar_start, last_eligible_bar_start]`, ET wall-clock; illustrative example updated to `["09:45","10:55"]` to match what real VP-ORB configs carry (the mapper emits from `C1.params`, P3c-2). (b) `contract/modes.md` — every token the engine cannot yet realize marked `†` ("declared, not engine-supported in v1 → UNSUPPORTED_CONSTRUCT") so the vocabulary never over-promises (P3e's extraction prompt is generated from it). No wire-shape change; `config_version` stays `1.0`.
- **WIT-P3c-1 (2026-07-27):** corrected the §3.4/§3.5 examples to match the engine — §3.5 event `k*ATR` → `k * trailing-median body` with the three path thresholds (`spike_eff`/`spike_giveback_cap`/`pullback_p`); §3.4 `session` re-expressed in ET wall-clock (`America/New_York`, `09:30`/`11:00`/`15:55`) — **same instants** as the prior CT example (representation alignment, not a time change). Wire shapes unchanged; `config_version` stays `1.0`. Machine copies added at `contract/{modes,strategy-config.v1,event-study-config.v1}`.

## 8. Engine-side work implied (Claude Code backlog seed)

1. `/wit/v1/*` router + job queue + callback writer (patterns exist: ADR-037 async, callback_writer.py). **✓ shipped P3d.**
2. Config mapper (template → StrategyConfig) with golden-file tests from the two calibration videos. **✓ shipped P3c-2.**
3. Mode vocabulary v1 incl. **volume-profile levels (POC/VAH/VAL) from 1-min composition** — the one genuinely new computational feature (approximation disclosure per WIT-02 B3).
4. Event-study runner (intrabar path features composed from finer bars). **✓ shipped P3c-3.**
5. Sensitivity sweep runner (bounded variants, shared queue budget). **✓ shipped P3f.**
6. Retire `backtest/` duplicate engine; `api/engine` is the single computational truth.
7. Disable code-execution endpoints for WIT traffic. **✓ shipped P3g (`DISABLE_EXEC_ENDPOINTS=1` kill switch; left unannotated in P3l).**
8. Engine-owned extraction endpoint `POST /wit/v1/extract` (k=3 ensemble via `extract_template_ensemble`); `anthropic` promoted from dev-only into the SHIPPED runtime lock (ADR-050 audit gate green). Supersedes §4's Supabase edge-function placement (decided P3m-a). **✓ shipped P3r.**

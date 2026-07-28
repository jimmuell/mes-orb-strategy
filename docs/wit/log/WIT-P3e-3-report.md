# WIT-P3e-3 — Report Back

Prompt: **WIT-P3e-3** — run the gated golden extraction tier and grade it. On `main`. Docs-only.

1. **STEP 0 result:** HEAD `34caa99` (WIT-P3k close-out) — **yes**. `ANTHROPIC_API_KEY` present in the test process — **yes** (never printed), **but it is rejected by the live API** (see §5). Key never revealed anywhere.
2. **Model id used:** none successfully — the in-code default `claude-opus-4-8` could **not** be verified because authentication fails **before** any model lookup (a clean `401 authentication_error` from `api.anthropic.com`). So `claude-opus-4-8`'s validity on the public API is **still unverified (n/a — blocked at auth)**.
3. **WIT-S-0001 (expected class A):** **NOT GRADED** — `extract_template` raised `anthropic.AuthenticationError: 401 API key is invalid` on the first (and every) attempt; no template was produced, so class / required_missing / per-field score / grounding / claims could not be evaluated.
4. **WIT-S-0002 (expected class B):** **NOT GRADED** — same `401 API key is invalid`; no template produced.
5. **Verdict:** **Neither rubric ran — blocked by an invalid API credential, not a code or content failure.** The extraction path itself is proven end-to-end wired (prompt → forced `emit_strategy_template` tool → provider → live Messages API → clean 401); only the key is bad.

## Diagnosis (credential + environment isolation)
Safe structural checks (no key fragment revealed): the key is **well-formed console format** (`sk-ant-api…`, length 108, no surrounding whitespace) — it is NOT an OAuth/session token — yet the API returns `401 "API key is invalid"`, i.e. the account/key is stale, revoked, or wrong.

**Why Jim's export didn't help:** `~/.zshrc` (line 15) exports `ANTHROPIC_API_KEY`, and **Claude Code's Bash tool initializes a fresh shell from the user profile on every call** — so Jim's interactive `export ANTHROPIC_API_KEY=…` in his own terminal never propagates into the executor's subprocess. The test process only ever reads the `~/.zshrc` key, which is the one being rejected. (This matches the harness reminder that `ANTHROPIC_API_KEY` was already set and takes precedence over the claude.ai login.)

## What's left (for Jim — one of these unblocks it)
- **Option A (recommended):** update `~/.zshrc` line 15 with a valid console key from console.anthropic.com (`sk-ant-api-…`), open a fresh terminal, and re-run this prompt — the executor's Bash will then source the valid key.
- **Option B (grade it now in your own shell where your export is live):** paste this into the prompt with the leading `!` so it runs in your session:
  `! cd ~/Projects/mes-orb-strategy/api && WIT_RUN_LLM_TESTS=1 BACKTEST_API_KEY=k python -m pytest tests/test_extraction_golden.py -v`
  If any test then fails on CONTENT (rubric/grounding/class), that is the real finding — capture it verbatim; do not tune fixtures/thresholds/engine.
- Either way, also confirm `claude-opus-4-8` resolves on the public API; if not, set `WIT_EXTRACTION_MODEL` to a valid current id and note the in-code default needs a future-slice update.

No code, fixtures, thresholds, or engine were changed (per the STOP-and-report rule). No dependency touched.

WIT-P3e-3 — Partial: live rubric ungraded — the ANTHROPIC_API_KEY visible to the test process (from ~/.zshrc) is rejected 401 by the API, and Claude Code's Bash cannot see Jim's interactive export; awaiting a valid key in ~/.zshrc or a `!`-run in Jim's own shell.

Addendum: live baseline completed manually in Jim's terminal 2026-07-27 (D2 grounding fail on T-0001; class A-vs-B fail on T-0002); graded results + fixes in WIT-P3e-4.

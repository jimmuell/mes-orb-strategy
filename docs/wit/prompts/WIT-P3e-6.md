Platform   : Claude Code (VS Code, MacBook Air)
Project    : WillItTrade (WIT)
Repo       : github.com/jimmuell/mes-orb-strategy   (branch: main)
Prompt     : WIT-P3e-6
Local path : ~/Projects/mes-orb-strategy

STEP 0 — GATE (any failure => STOP and report; do not proceed)
  1. git checkout main && git pull --ff-only
  2. git log --oneline -1 must show 20b8976 (WIT-P3e-5: basis discipline). Any other HEAD
     => STOP, report actual HEAD.
  3. git status --porcelain clean (known untracked pine/mes_net_pnl_v2.pine is fine).
     Confirm origin URL and local path match the header.
  4. ANTHROPIC_API_KEY set AND live (set:<bool> len:<n>, one claude-haiku-4-5 max_tokens=1
     call, no 401; never print the key). Live runs close this slice.
  5. HARD LIMITS unchanged: api/tests/fixtures/*.json byte-identical; completeness.py,
     scorer constants, golden asserts/thresholds untouched. STOP-and-report beats forcing.

CONTEXT
  P3e-5 lead review (Cowork chat, 2026-07-28). Findings from the two disagreeing live runs:
  (1) provider.py sets NO temperature on the Messages call — the extraction has been
  sampling at the API default; a grader must be pinned to 0. This is the primary variance
  source. (2) By the P3o adjudication's own definitions, basis "generalized_practice" can
  only ever support status "implied" — "specified" requires executability AS STATED, i.e.
  basis "stated_rule". The graded run's only failure (F1 specified vs fixture implied) is
  exactly this pairing left unenforced. (3) The diagnostic run under-credited B2: a
  capability fact the source states outright ("works on any timeframe") was zeroed because
  it sounds like a marketing claim. Three changes, all small; deterministic-first.

TASK
T1. provider.py: pin temperature=0 on the extraction Messages call. One-line comment citing
    P3e-6: "grader, not writer — determinism over creativity".
T2. extract.py: coherence downgrade, deterministic, pre-scoring, alongside apply_demotions:
    a REQUIRED field with status "specified" and basis "generalized_practice" is downgraded
    to status "implied" (never blocked, never retried). Record it in the result alongside
    demotions, as downgrades: [{field, from_status, to_status, basis}] (empty list when
    none). Scorer untouched (specified and implied both satisfy — this changes the exact
    status, which the golden's hard assert grades, not satisfaction).
T3. prompt.py rule 9, additive clarifiers only (rules 1-8 + existing rule-9 text + all
    pinned phrases unchanged):
      - "Status/basis pairing: 'specified' pairs only with basis 'stated_rule';
        'generalized_practice' supports at most 'implied'. The engine enforces this."
      - "A capability or scope fact the source states outright (e.g. which markets or
        timeframes it works on) is a STATED fact for B-section fields — basis 'stated_rule'
        — even when the same sentence also belongs in claims[] as a claim."
    Anchor-contamination check as in P3e-5: no transcript phrases embedded ("works on any
    timeframe" as used above is generic English; verify the exact rule text you add has 0
    verbatim-substring hits >= 12 chars against both transcripts; report the check).
T4. Tests (CI-safe, fake provider) — at least: (1) specified + generalized_practice on a
    required field => downgraded to implied + recorded, class unchanged; (2) specified +
    stated_rule => untouched, downgrades empty; (3) implied + generalized_practice =>
    untouched; (4) prompt test: new pairing/capability phrases present, prior pinned
    phrases still present. Existing tests: adjust fake-template plumbing only if the new
    downgrade trips them; fixtures on disk untouched.
T5. Full CI-safe suite: cd api && BACKTEST_API_KEY=k python -m pytest -q
    Expected: (219 + new) passed / 0 failed / 2 skipped. Record exact counts. Failure => STOP.
T6. LIVE runs (~cents): run the graded golden TWICE back-to-back:
      WIT_RUN_LLM_TESTS=1 python -m pytest tests/test_extraction_golden.py -q   (x2)
    Report per run, per case: pass/fail + failing assert if any, class, required_missing,
    demotions, downgrades, retries. With temperature 0 the two runs should agree; if they
    disagree anywhere, say so loudly — that itself is a finding. If T-0002 fails in BOTH
    runs on the same assert, produce the 27-row diagnostic (scratchpad outside the repo
    tree, uncommitted, table verbatim in the report). DO NOT tune anything in response to
    outcomes — report facts.
T7. Handoff + archive + index (docs/wit/):
  a) SESSION-HANDOFF.md: "main =" line -> "main = the WIT-P3e-6 commit (temperature pinned
     to 0; specified/generalized_practice coherence downgrade; B-fact clarifier); prior
     20b8976 (P3e-5)." Arc: append " → P3e-6 determinism + coherence."
  b) Replace the ENTIRE "▶ RESUME HERE — P3e-5 basis discipline shipped..." block (through
     "...(draft in the Notion tracker row).") with:
      ▶ RESUME HERE — P3e-6 shipped; live golden x2: [FILL IN ACTUAL: per-run, per-case
      results incl. class/asserts/demotions/downgrades; state plainly whether the two runs
      agreed]. If T-0002 passed in both runs: extraction quality is DONE for v1 — next
      slice = POST /wit/v1/extract (decided at P3m-a: engine exposes extraction, Supabase
      calls it; auth + budget like other /wit/v1 routes; returns {template, completeness,
      raw_meta}; anthropic moves from requirements-dev.txt to the SHIPPED runtime lock and
      must pass the ADR-050 audit gate). If T-0002 still failed in both runs: STOP — lead
      review in Cowork chat with the diagnostic; candidate next lever is a k-sample
      majority vote on required-field statuses, decided by the lead, not improvised.
      Jim's lane unchanged: Railway deploy confirm + WIT_ENGINE_SERVICE_KEY,
      WIT_CALLBACK_HMAC_SECRET, DISABLE_EXEC_ENDPOINTS=1; FirstRateData confirmation email
      (draft in the Notion tracker row).
  c) Archive this prompt verbatim to docs/wit/prompts/WIT-P3e-6.md; add the
     WIT-P3e-6-report.md row to docs/wit/log/README.md.
T8. Single commit DIRECTLY to main (T5 gates; live outcome does not gate the commit),
    subject:
      WIT-P3e-6: extraction determinism — temperature 0, basis/status coherence downgrade, B-fact clarifier
    Explicit paths only. Push; record CI.

REPORT BACK — write verbatim to docs/wit/log/WIT-P3e-6-report.md, staged with the commit:
  1. STEP 0 results. 2. Per-file changes + contamination check result. 3. New tests + suite
  counts. 4. LIVE x2 results per the T6 spec (+ diagnostic table if produced). 5. Commit
  hash; CI. 6. Anything unexpected.
Final line, exactly one of:
WIT-P3e-6 — Completed
WIT-P3e-6 — Partial: <one-line reason>

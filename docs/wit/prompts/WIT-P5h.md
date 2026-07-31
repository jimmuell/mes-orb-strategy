Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P5h

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK — make the extraction cache actually work, and make it faithful

  SUPERSEDES WIT-P5g, which was never run. Do not run WIT-P5g.

  Three defects in the WIT-P5f cache path. Live evidence 2026-07-31: three accounts
  audited the same transcript; all three ran a full extraction (236s, 180s, 281s) and
  all three template rows have source_transcript_hash NULL and
  reused_from_template_id NULL. The cache never hits.

  DEFECT A — the cache can never populate. applyEngineEvent passes transcriptHash
  null to advanceFromTemplate. That is the ONLY path that creates a template row on a
  cache miss, so every stored template has a null hash, so findCachedTemplate can
  never match. Every audit is a miss, permanently.

  DEFECT B — the reused template is re-mapped instead of reused. advanceFromTemplate
  calls /wit/v1/map on the cached template and re-derives wire_config, ignoring the
  stored one. EXTRACTOR_VERSION fences extraction only, so a future change to the
  engine's mapper would silently change the config and therefore the numbers.

  DEFECT C — a cache hit reports success even when nothing was queued.
  advanceFromTemplate returns { outcome: "applied", detail: "map_failed" |
  "run_submit_failed" | "map_shape_invalid" } when an engine call fails but the status
  write succeeds. submitExtract treats only outcome === "error" as failure, so those
  return ok:true, submit-evaluation sets committed = true and returns 201, and the
  WIT-P5c refund never fires. The user is charged for an audit that never started.

  SCOPE — create or modify ONLY these paths:
    supabase/migrations/<new timestamp>.sql                new
    supabase/functions/_shared/extraction-cache.ts         modify
    supabase/functions/_shared/evaluation-chain.ts         modify

  DO NOT TOUCH: submit-evaluation, poll-runs, engine-callback, publish-report,
  get-entitlements, _shared/metering.ts, any existing migration, any file under src/.

  FORBIDDEN IN THIS TASK: RLS policies, GRANT, REVOKE, ALTER ROLE, SECURITY DEFINER
  functions. If you conclude you need one, STOP and report.

  1. Migration — backfill, then constrain so this cannot fail silently again.
       UPDATE public.templates t
          SET source_transcript_hash = e.transcript_hash
         FROM public.evaluations e
        WHERE e.id = t.evaluation_id
          AND t.source_transcript_hash IS NULL
          AND char_length(e.transcript_hash) = 64;

       DELETE is NOT permitted. If any templates row still has a NULL or non-64-char
       source_transcript_hash after the backfill, STOP and report the row count
       instead of proceeding to the constraint.

       ALTER TABLE public.templates
         ALTER COLUMN source_transcript_hash SET NOT NULL;
       ALTER TABLE public.templates
         ADD CONSTRAINT templates_source_transcript_hash_len
         CHECK (char_length(source_transcript_hash) = 64);

     The constraint exists because an empty-string hash would match every other
     empty-string hash and hand users each other's templates.
     Issue no grants and create no policies.

  2. extraction-cache.ts
     a. Widen CachedTemplate and the select to include:
          wire_config: unknown;
          assumptions: unknown;
     b. findCachedTemplate returns null immediately, without querying, when
        transcriptHash is not exactly 64 characters. Existing filters otherwise
        unchanged: same hash, same EXTRACTOR_VERSION, template_json not null,
        wire_config not null, oldest row wins.

  3. evaluation-chain.ts — fix Defect A.
     In applyEngineEvent, the evaluation lookup currently selects "id, source_title".
     Add transcript_hash to that select. Then, in the extract-succeeded branch, pass
     that value to advanceFromTemplate instead of null.
     If the fetched transcript_hash is not exactly 64 characters, do NOT insert a
     template. Instead call recordEvaluationError with
       { code: "TRANSCRIPT_HASH_MISSING",
         message: "evaluation has no usable transcript hash; template not cacheable",
         detail: { engine_run_id } }
     and return { outcome: "error", detail: "transcript_hash_missing" }.
     reusedFromTemplateId stays null on this path — this template is an original.

  4. evaluation-chain.ts — extract the run-queueing tail into a shared helper.
     Inside advanceFromTemplate, the block from the /wit/v1/runs call through setting
     the evaluation to 'running' becomes:

       async function queueRunFromWire(
         supabase, evaluationId: string, kind: string, config: unknown,
         engineRunId: string | null,
       ): Promise<ApplyOutcome>

     A pure move: every error check, every recordEvaluationError envelope, every log
     line and every returned detail string identical to today, including
     "run_submit_failed", "run_submit_missing_run_id", "child_run_persist_failed",
     "running_status_persist_failed_after_run_queued" and the success detail
     "extract_ok_run_queued". advanceFromTemplate calls it and returns its result, and
     is otherwise UNCHANGED — it still maps, still handles untestable, still stores
     wire_config.

  5. evaluation-chain.ts — fix Defect B with a cache path that never re-maps.

       export async function advanceFromCachedTemplate(
         supabase, evaluationId: string, cached: CachedTemplate,
         transcriptHash: string,
       ): Promise<ApplyOutcome>

     a. Insert the templates row with template_json, completeness, ensemble_meta,
        wire_config AND assumptions copied verbatim from `cached`, plus
        source_transcript_hash = transcriptHash,
        extractor_version = EXTRACTOR_VERSION,
        reused_from_template_id = cached.template_id.
        Same error handling and same detail string as the existing template insert.
     b. Set the evaluation to 'scored' with class from completeness?.class, reusing
        the existing error handling and detail string.
     c. Read kind and config off cached.wire_config, shape { kind, config }. If either
        is missing, mark the evaluation failed with error_json
        { code: "CACHED_WIRE_INVALID", message: "cached wire_config is missing kind or
        config" } and return { outcome: "error", detail: "cached_wire_invalid" }.
     d. Call queueRunFromWire with engineRunId null and return its result.
     It makes NO call to /wit/v1/map. The untestable branch cannot arise:
     findCachedTemplate only returns rows whose wire_config is non-null.

  6. evaluation-chain.ts — fix Defect C in submitExtract.
     On a cache hit call advanceFromCachedTemplate instead of advanceFromTemplate,
     then classify the outcome rather than assuming success:

       - "applied" with detail "extract_ok_run_queued" -> { ok: true, cached: true }
       - "error"                                       -> { ok: false, status: 500,
             envelope: { code: "CACHE_ADVANCE_FAILED", message: outcome.detail } }
       - "applied" with ANY other detail               -> { ok: false, status: 502,
             envelope: { code: "CACHE_ADVANCE_NOT_QUEUED", message: outcome.detail } }

     Do not modify submit-evaluation — its existing `if (!result.ok)` handling already
     refunds correctly once submitExtract stops reporting success.

  DEPLOY AND VERIFY
    Edge functions auto-deploy on edit; the migration applies when you run it. No
    frontend change, no Publish.
    Verify and report, WITHOUT deleting or altering any existing row beyond the
    backfill in step 1:
      - typecheck clean
      - the migration applied; report how many rows the backfill updated
      - report every templates row as: evaluation_id, source_transcript_hash,
        extractor_version, reused_from_template_id
      - confirm NOT NULL and the length constraint are both present on
        templates.source_transcript_hash
      - confirm no call to /wit/v1/map exists on the cache-hit path
      - confirm queueRunFromWire is called from exactly two places
      - confirm the policy count for schema public is still 9 and no grant changed

REPORT BACK
  1. Files created and modified, and the migration filename.
  2. Rows updated by the backfill, and the full templates listing described above.
  3. The three outcome-to-result mappings as implemented.
  4. Confirmation that queueRunFromWire was a pure move, and how you checked.
  5. Confirmation that the extract-succeeded path still maps and still handles
     untestable.
  6. Policy count and confirmation that no grant changed.
  7. Anything you could not do without a policy or a grant, or "clean".
  Final line, exactly: WIT-P5h — Completed

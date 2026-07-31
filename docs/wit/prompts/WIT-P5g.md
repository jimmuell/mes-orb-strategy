Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P5g

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK — freeze the cached config, and stop charging for a cache-hit audit that failed

  Two defects in the WIT-P5f cache path.

  DEFECT A — the reused template is re-mapped instead of reused. advanceFromTemplate
  calls /wit/v1/map on the cached template and re-derives wire_config. The stored
  wire_config is ignored. EXTRACTOR_VERSION fences extraction only, so a future
  change to the engine's mapper would silently change the config, and therefore the
  numbers, for every cached audit. The requirement is that a transcript always yields
  the same numbers. Reuse the stored wire_config and assumptions; do not re-map.

  DEFECT B — a cache hit reports success even when nothing was queued.
  advanceFromTemplate returns { outcome: "applied", detail: "map_failed" |
  "run_submit_failed" | "map_shape_invalid" } when the engine call fails but the
  status write succeeds. submitExtract only treats outcome === "error" as failure, so
  those cases return ok:true, submit-evaluation sets committed = true and returns 201,
  and the WIT-P5c refund never fires. The user is charged for an audit that failed
  before any engine work started.

  SCOPE — modify ONLY these paths:
    supabase/functions/_shared/extraction-cache.ts        modify
    supabase/functions/_shared/evaluation-chain.ts        modify

  DO NOT TOUCH: submit-evaluation, poll-runs, engine-callback, publish-report,
  get-entitlements, _shared/metering.ts, any migration, any file under src/.

  FORBIDDEN IN THIS TASK: RLS policies, GRANT, REVOKE, ALTER ROLE, SECURITY DEFINER
  functions, any SQL migration, any database schema change. If you conclude you need
  one, STOP and report.

  1. extraction-cache.ts — widen CachedTemplate and the select.
     Add to the type and to the selected columns:
       wire_config: unknown;
       assumptions: unknown;
     The existing filters are unchanged: same hash, same EXTRACTOR_VERSION,
     template_json not null, wire_config not null, oldest row wins.

  2. evaluation-chain.ts — extract the run-queueing tail into a shared helper.
     Inside advanceFromTemplate, the block that starts at the /wit/v1/runs call and
     ends by setting the evaluation to 'running' becomes:

       async function queueRunFromWire(
         supabase, evaluationId: string, kind: string, config: unknown,
         engineRunId: string | null,
       ): Promise<ApplyOutcome>

     A pure move: every error check, every recordEvaluationError envelope, every log
     line and every returned detail string identical to today, including
     "run_submit_failed", "run_submit_missing_run_id", "child_run_persist_failed",
     "running_status_persist_failed_after_run_queued" and the success detail
     "extract_ok_run_queued". advanceFromTemplate calls it and returns its result.
     advanceFromTemplate is otherwise UNCHANGED — the extract-succeeded path must
     still map, still handle untestable, still store wire_config, exactly as now.

  3. evaluation-chain.ts — new cache-hit path that never re-maps.

       export async function advanceFromCachedTemplate(
         supabase, evaluationId: string, cached: CachedTemplate,
         transcriptHash: string,
       ): Promise<ApplyOutcome>

     It must:
       a. insert the templates row with template_json, completeness, ensemble_meta,
          wire_config AND assumptions all copied verbatim from `cached`, plus
          source_transcript_hash = transcriptHash,
          extractor_version = EXTRACTOR_VERSION,
          reused_from_template_id = cached.template_id.
          Reuse the same error handling and the same detail string as the existing
          template insert.
       b. set the evaluation to 'scored' with class from completeness?.class, reusing
          the existing error handling and detail string.
       c. read kind and config off the cached wire_config, which has the shape
          { kind, config }. If either is missing, mark the evaluation failed with
          error_json { code: "CACHED_WIRE_INVALID", message: "cached wire_config is
          missing kind or config" } and return
          { outcome: "error", detail: "cached_wire_invalid" }.
       d. call queueRunFromWire with engineRunId null and return its result.
     It makes NO call to /wit/v1/map. The untestable branch cannot arise here:
     findCachedTemplate only returns rows whose wire_config is non-null, which means
     the source audit was testable.

  4. submitExtract — use the new path, and report failure honestly.
     On a cache hit call advanceFromCachedTemplate instead of advanceFromTemplate.
     Then classify the outcome rather than assuming success:

       - outcome "applied" with detail "extract_ok_run_queued"  -> { ok: true, cached: true }
       - outcome "error"                                        -> { ok: false, status: 500,
             envelope: { code: "CACHE_ADVANCE_FAILED", message: outcome.detail } }
       - outcome "applied" with ANY other detail                -> { ok: false, status: 502,
             envelope: { code: "CACHE_ADVANCE_NOT_QUEUED", message: outcome.detail } }

     The third case is the fix for Defect B: no engine work was queued, so the caller
     must see a failure and the WIT-P5c refund must fire. Do not modify
     submit-evaluation to achieve this — its existing `if (!result.ok)` handling
     already does the right thing once submitExtract stops lying.

  DEPLOY AND VERIFY
    Edge functions auto-deploy on edit. No migration, no frontend change, no Publish.
    Verify and report:
      - typecheck clean
      - no call to /wit/v1/map exists on the cache-hit path
      - queueRunFromWire is called from exactly two places
      - the extract-succeeded path still maps and still handles untestable
      - confirm the policy count for schema public is still 9 and no grant changed
      - confirm no migration was created and no schema change was made

REPORT BACK
  1. Files modified.
  2. The three outcome-to-result mappings as you implemented them.
  3. Confirmation that queueRunFromWire was a pure move, and how you checked.
  4. Confirmation that the extract-succeeded path is unchanged.
  5. Policy count, and confirmation of no schema change and no grant change.
  6. Anything you could not do without a policy, a grant or a migration, or "clean".
  Final line, exactly: WIT-P5g — Completed

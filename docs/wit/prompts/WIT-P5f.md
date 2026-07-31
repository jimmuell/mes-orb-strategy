Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P5f

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK — make audits reproducible: extract each transcript once, reuse it forever

  Requirement being implemented: the same transcript must always produce the same
  template, the same wire config and therefore the same numbers, for every user, on
  every run. Extraction is the only non-deterministic step in the pipeline; mapping
  and backtesting are pure functions of their input. Therefore extraction is cached
  on the transcript, and never repeated for a transcript already extracted.

  SCOPE — create or modify ONLY these paths:
    supabase/migrations/<new timestamp>.sql                 new
    supabase/functions/_shared/extraction-cache.ts          new
    supabase/functions/_shared/evaluation-chain.ts          modify
    supabase/functions/submit-evaluation/index.ts           modify

  DO NOT TOUCH: publish-report, get-entitlements, _shared/metering.ts,
  _shared/transcript.ts, _shared/video-meta.ts, engine-callback/index.ts,
  poll-runs/index.ts, any file under src/, or any existing migration.

  FORBIDDEN IN THIS TASK: RLS policies, GRANT, REVOKE, ALTER ROLE, SECURITY DEFINER
  functions, and any change to grants or policies on any table. If you conclude you
  need one to finish, STOP and report instead of writing it.

  1. Migration
       ALTER TABLE public.templates
         ADD COLUMN extractor_version text NOT NULL DEFAULT 'wit-extract-v1';
       ALTER TABLE public.templates
         ADD COLUMN source_transcript_hash text;
       ALTER TABLE public.templates
         ADD COLUMN reused_from_template_id uuid;
       CREATE INDEX IF NOT EXISTS templates_cache_lookup_idx
         ON public.templates (source_transcript_hash, extractor_version);
     Backfill source_transcript_hash on existing rows from their evaluation:
       UPDATE public.templates t
          SET source_transcript_hash = e.transcript_hash
         FROM public.evaluations e
        WHERE e.id = t.evaluation_id
          AND t.source_transcript_hash IS NULL;
     Issue no grants and create no policies. templates already carries table-wide
     SELECT for authenticated; the new columns inherit it and that is intended.

  2. New file supabase/functions/_shared/extraction-cache.ts

       export const EXTRACTOR_VERSION = "wit-extract-v1";

     Bumping that constant is how a future change to the extraction model or prompt
     invalidates every cached template. Put that sentence in a comment above it.

       export async function sha256Hex(input: string): Promise<string>
         Move the existing implementation from submit-evaluation verbatim so both
         sides hash identically. submit-evaluation imports it from here afterwards
         and keeps no local copy.

       export type CachedTemplate = {
         template_id: string;
         template_json: unknown;
         completeness: unknown;
         ensemble_meta: unknown;
       };

       export async function findCachedTemplate(
         admin, transcriptHash: string,
       ): Promise<CachedTemplate | null>
         Returns the OLDEST templates row (order by created_at ascending, limit 1)
         where source_transcript_hash = transcriptHash
           AND extractor_version = EXTRACTOR_VERSION
           AND template_json IS NOT NULL
           AND wire_config IS NOT NULL
         Oldest, not newest: the first successful extraction of a transcript is the
         canonical one and must stay canonical as rows accumulate.
         A database error throws. No row returns null.

  3. Refactor evaluation-chain.ts — extract the post-extraction advance into a
     reusable function, changing NO behaviour.

     In applyEngineEvent's `run.kind === "extract"` + `status === "succeeded"`
     branch, the code currently does: insert the templates row, set the evaluation
     to 'scored', call /wit/v1/map, handle the untestable branch, store wire_config,
     call /wit/v1/runs, insert the child run row, set the evaluation to 'running'.

     Move everything from the templates insert onward into a new exported function:

       export async function advanceFromTemplate(
         supabase, evaluationId: string, template: unknown, completeness: any,
         ensembleMeta: unknown, transcriptHash: string | null,
         reusedFromTemplateId: string | null,
       ): Promise<ApplyOutcome>

     It writes source_transcript_hash, extractor_version (EXTRACTOR_VERSION) and
     reused_from_template_id on the templates row it inserts. Every existing
     error-check, every recordEvaluationError envelope, every status transition and
     every returned detail string is preserved EXACTLY as it is today — this step is
     a pure move, not a rewrite. applyEngineEvent then calls it, passing
     transcriptHash null and reusedFromTemplateId null, and returns its result
     unchanged.

     After this step the extract-succeeded path must behave identically to today.
     Confirm that in the report.

  4. Modify submitExtract in evaluation-chain.ts — check the cache first.

     submitExtract is the single funnel for extraction: it is called from
     submit-evaluation on both paths and from poll-runs when a transcript job
     resolves. Putting the check here covers every entry point.

     At the very top of submitExtract, before any fetch to the engine:
       a. hash the transcript with sha256Hex
       b. call findCachedTemplate
       c. on a HIT: do NOT call the engine. Call advanceFromTemplate with the cached
          template_json, completeness and ensemble_meta, the transcript hash, and the
          cached template_id as reusedFromTemplateId. Log
          console.log("submit_extract cache_hit", { evaluation_id, template_id }).
          Return the new result shape below.
       d. on a MISS: proceed exactly as today, and log
          console.log("submit_extract cache_miss", { evaluation_id }).

     Widen the return type to a discriminated union:
       export type SubmitExtractResult =
         | { ok: true; cached: false; engine_run_id: string }
         | { ok: true; cached: true }
         | { ok: false; status: number; envelope: any };

     If advanceFromTemplate returns an outcome of "error", the cache path must return
     { ok: false, status: 500, envelope: { code: "CACHE_ADVANCE_FAILED",
       message: <the outcome detail> } } rather than claiming success.

     Update EVERY caller so it still compiles and behaves correctly, including
     poll-runs — poll-runs is on the do-not-touch list for edits of substance, but if
     it reads engine_run_id off this result you MUST adjust that read. If that turns
     out to require more than a type-narrowing guard in poll-runs, STOP and report
     instead of restructuring poll-runs.

  5. submit-evaluation: no logic change beyond importing sha256Hex from
     extraction-cache.ts and deleting its local copy. The quota reservation, the
     refund invariant from WIT-P5c, the QUOTA_EXCEEDED shape and every status code
     stay exactly as they are. A cache hit still consumes one audit from the user's
     quota — they received an audit.

  DEPLOY AND VERIFY
    Edge functions auto-deploy on edit; the migration applies when you run it. No
    frontend change, so no Publish is required.
    Verify and report, without changing any data that already exists:
      - typecheck clean
      - the migration applied; templates has the three new columns and the index
      - the backfill populated source_transcript_hash for both existing template rows
      - report the two existing rows as: evaluation_id, source_transcript_hash,
        extractor_version — and state whether their two hashes are equal or different
      - confirm the policy count for schema public is still 9 and no grant changed
      - confirm advanceFromTemplate is called from exactly two places: the
        extract-succeeded branch and the cache-hit branch

REPORT BACK
  1. Files created and modified, and the migration filename.
  2. The two existing template rows as described above, and whether their hashes match.
  3. Confirmation that the extract-succeeded path is behaviourally unchanged, and
     what you did to satisfy yourself of that.
  4. How poll-runs consumes the new return type.
  5. The policy count and confirmation that no grant changed.
  6. Anything you could not do without writing a policy or a grant, or "clean".
  Final line, exactly: WIT-P5f — Completed

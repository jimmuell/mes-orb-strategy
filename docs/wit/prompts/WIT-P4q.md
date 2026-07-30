Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P4q

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK

  Capture the video's title, channel and thumbnail when a YouTube link is submitted. Today
  a link submission stores nothing but the URL, so evaluations are headed by a raw link,
  the dashboard lists links, report permalinks fall back to "strategy-audit", and the
  engine reads the transcript with no source context.

  Touch ONLY supabase/functions/_shared/video-meta.ts (new),
  supabase/functions/submit-evaluation/index.ts (edit), and one migration containing
  exactly the two statements below. No frontend file, no other edge function, no
  row-level-security, grant or role SQL.

  Migration (exactly these two statements, nothing more):

    ALTER TABLE public.evaluations ADD COLUMN source_thumbnail_url text;

    ALTER TABLE public.evaluations ADD COLUMN source_channel_url text;

  1. New helper — supabase/functions/_shared/video-meta.ts

    Export fetchVideoMeta(url) using YouTube's public oEmbed endpoint:

      GET https://www.youtube.com/oembed?url=<encoded>&format=json

    No API key, no quota, no cost. A 200 returns {title, author_name, author_url,
    thumbnail_url, ...}; map those to {title, channel, channelUrl, thumbnailUrl}.

    It must be FAIL-SOFT and never block a submission: use a short timeout (5 seconds,
    via AbortController), and on any timeout, non-200, network error or unparseable body
    return all-null fields rather than throwing. A missing title is a cosmetic loss; a
    failed submission is not acceptable. Log only whether metadata was obtained — never
    the body.

  2. submit-evaluation — use it on the link path only

    On the source_url path, after the URL passes isSupportedVideoUrl and BEFORE the
    evaluations row is inserted, call fetchVideoMeta. Store title, channel, channel URL
    and thumbnail on the row.

    Precedence: anything the CALLER supplied wins. If the request body already carries
    source_title or source_channel, keep those and do not overwrite them with oEmbed
    values — the caller may know better.

    The pasted-transcript path is unchanged: no fetch, no metadata lookup.

    The engine's extract call already sends source_meta {title, url, channel}. Make sure
    it now sends the resolved values rather than nulls, so the extractor gets the source
    context it is designed to use.

  3. Do not change behavior on failure

    If metadata cannot be fetched the submission proceeds exactly as it does today, with
    null title and channel. Nothing about the chain, the statuses, or the response codes
    changes. Do not add retries.

DEPLOY / VERIFY

  Edge functions auto-deploy. Verify by submitting the YouTube URL
  https://youtu.be/BtyU2DEzUpM in Preview and confirming the new evaluation row carries a
  real title, channel, channel URL and thumbnail URL. Report the four values you got. Do
  not Publish the frontend; this slice has no frontend change.

REPORT BACK

  List: the helper as written including the timeout and the fail-soft paths; where in
  submit-evaluation it is called and the precedence rule; the exact migration SQL run,
  verbatim; the four metadata values captured for the test submission; confirmation that
  the pasted-transcript path is untouched and that a metadata failure cannot fail a
  submission; any deviation; anything you noticed but did not change. End with exactly
  one line:

  WIT-P4q — Completed

  or

  WIT-P4q — Partial: <what's left>

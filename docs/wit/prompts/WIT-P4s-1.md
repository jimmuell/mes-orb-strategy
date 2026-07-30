Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P4s-1

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK — three fixes to the /review detail view. Frontend only: no edge-function
changes, no SQL, no migrations, nothing outside the review route and its
components.

  1. Ensemble agreement section renders nothing because the real ensemble_meta
     keys differ from what the code expects. The live shape is:
       {"k":3, "ok_runs":3, "unanimous_fields":23, "majority_fields":4,
        "tie_fields":0, "medoid_index":0, "per_run":[...]}
     Render prominently, directly under the verdict block:
       - unanimous_fields, majority_fields, tie_fields as the three counts,
         labeled Unanimous / Majority / Ties.
       - A caption line: "k=<k> independent readings, <ok_runs> completed".
     If ensemble_meta is null or any of the three count keys is missing, render
     the section with the message "Ensemble vote data unavailable — investigate
     before approving" in a warning style. NEVER render nothing: this section is
     the reviewer's primary evidence and silent absence is the failure mode this
     fix removes.

  2. The Reviewer notes section renders four times (four headings, multiple
     textareas). Render it exactly once, above the action buttons.

  3. Assumptions the lab applied: currently raw codes (E1, F4, ...). Reuse the
     same field-id -> readable-label/default-description mapping the honest-gaps
     section already uses, rendering "<code> <label> — <default applied>", e.g.
     "E1 Position sizing — fixed 1 contract". For ids with no entry in that
     mapping, use these labels:
       initial_capital  -> "Initial capital — $10,000 simulated account"
       J1_window        -> "Test window — full available data range"
       B3_granularity   -> "Profile granularity — lab default"
     Any other unmapped id renders as its raw code (never hidden).

  DO NOT touch: the publish-report edge function, any other route, any shared
  component used outside /review.

  DEPLOY / PUBLISH:
    Frontend only — after the edit, Publish -> Update to the live URL.

  VERIFY (you):
    - Typecheck and production build pass.
    - On the existing draft report's detail view: the three vote counts render
      as 23 / 4 / 0 with the k=3 caption; exactly one Reviewer notes section;
      the assumptions list shows readable lines, none hidden.
    - Do not approve or publish anything; the report stays draft.

REPORT BACK (exactly this):
  1. The three fixes confirmed on the draft's detail view, published: y/n.
  2. Typecheck/build results.
  3. Anything else you noticed or changed.
  Final line, exactly: WIT-P4s-1 — Completed

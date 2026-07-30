Platform:    Lovable Project (paste this code into this platform)

Project:     WillItTrade Web

Repo:        jimmuell/strategy-verdict-lab   (Lovable project 6e5983e8-cf92-4fa6-bf7e-cf416ae2d2d9)

Prompt:      WIT-P4p

Local path:  /Users/jameslmueller/Projects/strategy-verdict-lab

TASK

  The first completed audit renders a false number. Fix the units and the rounding on the
  live result card.

  Touch ONLY src/routes/evaluation.$id.tsx. No edge function, no migration, no SQL, no
  other route. Do NOT change src/data/fixtures.ts or the fixture-driven demo routes.

  1. Win rate — the engine already reports a percentage

    The card multiplies win_rate by 100. The engine emits it ALREADY as a percentage:
    the completed run stores win_rate = 35.81048581048581, which the card renders as
    "3581.0%". The published WIT-0001 report's 34.3% likewise comes from an engine value
    of 34.32.

    Render win_rate as a percentage directly — value.toFixed(1) + "%" — with no
    multiplication. Confirm in the report which evaluation you checked and what it now
    reads.

    The fixtures module uses the opposite convention (0.343 for 34.3%). That is the demo
    surface and stays as it is; do not "harmonise" the two. Add a short comment on the
    live formatter saying the engine's unit is percent, so nobody re-introduces the
    multiply.

  2. Average trade — do not round away the number

    formatMoney uses maximumFractionDigits: 0, so an average trade of -$2.33 renders as
    "-$2". Per-trade figures are small by nature and the cents are the signal. Show two
    decimal places for avg_trade specifically; leave the large aggregates (net P/L, max
    drawdown) rounded to whole dollars as they are.

  3. Equity curve — verify it actually draws

    The completed run stores 4,709 daily points, starting {"t":"2008-01-02", equity:
    10066.26} and ending {"t":"2026-04-08", equity: 328.15}. Open that evaluation in
    Preview and confirm the line renders across the full width with a sensible vertical
    axis — the series rises to roughly $15,700 before falling to $328, so the axis must
    span the real range.

    If it does NOT render correctly at that point count, fix the chart configuration —
    but change nothing about the data itself, and say exactly what was wrong. If it
    renders fine, say so and change nothing.

  4. Audit every other number on this card for the same class of error

    For each metric rendered — trades, net_pnl, profit_factor, max_drawdown, win_rate,
    avg_trade — state the engine's unit and the display treatment, and confirm they
    agree. Report any other mismatch you find; fix only unit or rounding errors on this
    card, and list anything else rather than changing it.

DEPLOY / VERIFY

  Verify in Preview against the completed evaluation, then Publish → Update.

REPORT BACK

  List: the win-rate change and what the card now reads for that evaluation; the avg
  trade change; whether the equity curve rendered and what you changed if anything; the
  unit-by-unit audit table for all six metrics; any deviation; anything you noticed but
  did not change. End with exactly one line:

  WIT-P4p — Completed

  or

  WIT-P4p — Partial: <what's left>

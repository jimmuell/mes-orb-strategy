"""v1 verdict derivation for WIT result payloads (WIT-P4t).

Ratified rule (2026-07-30): a v1 result may report that a strategy was TESTED and that it showed
NO edge, or that the outcome is INCONCLUSIVE — but it may NEVER claim an edge. Statistical
confidence (edge-vs-luck) is not part of v1, so a positive raw result is reported as inconclusive,
not as evidence of edge.

HARD RULE: the only codes this module may ever return are "tested_no_edge" and "tested_inconclusive".
No code, label, or reason may assert edge ("evidence of edge", "edge demonstrated", "promising", …).
The single permitted occurrence of the word "edge" in a label is the exact phrase "no edge
demonstrated"; in reasons it appears only inside "no edge claim is made".

Pure function — no I/O, no engine access; reads a metrics dict the caller already built.
"""
from __future__ import annotations

_INCONCLUSIVE = "tested_inconclusive"
_NO_EDGE = "tested_no_edge"

_LABEL = {
    _INCONCLUSIVE: "Tested — inconclusive",
    _NO_EDGE: "Tested — no edge demonstrated",
}


def _verdict(code: str, reason: str) -> dict:
    return {"code": code, "label": _LABEL[code], "reason": reason}


def derive_verdict(kind: str, metrics: dict) -> dict:
    """Return {"code","label","reason"} for a result payload. `kind` is "backtest" or
    "event_study"; `metrics` is the backtest metrics dict (ignored for event studies)."""
    if kind == "event_study":
        return _verdict(_INCONCLUSIVE,
                        "event-study claim verdicts await the statistical confidence layer")

    # kind == "backtest"
    pf = metrics.get("profit_factor")
    net = metrics.get("net_pnl")
    trades = metrics.get("trades")

    if trades is None or trades == 0 or pf is None or net is None:
        return _verdict(_INCONCLUSIVE,
                        "insufficient completed trades or metrics to render a verdict")

    if pf < 1.0 or net <= 0:
        return _verdict(_NO_EDGE,
                        f"profit factor {pf:.2f} and net P/L {net:+,.0f} over {trades:,} trades "
                        f"across the full test window")

    return _verdict(_INCONCLUSIVE,
                    f"positive result (profit factor {pf:.2f} over {trades:,} trades) — "
                    f"statistical confidence analysis (edge vs. luck) is not yet part of v1, "
                    f"so no edge claim is made")

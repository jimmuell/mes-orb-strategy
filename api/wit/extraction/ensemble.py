"""k-sample extraction ensemble (WIT-P3e-7): run extract_template k times and deterministically
merge the FINISHED templates by per-field majority vote.

Why: claude-opus-4-8 deprecates temperature (P3e-6), so single-shot extraction varies run-to-run
on borderline fields. Each run already passes schema + grounding + claims-grounding + demotion +
downgrade; this module only VOTES over completed runs — it never relaxes a gate. Ties break toward
the LEAST-crediting status (unspecified > implied > specified), so the honest gap wins ties. The
deterministic scorer assigns the class exactly as in extract_template. This is the product
extraction path the future /wit/v1/extract endpoint calls.
"""
from __future__ import annotations

import copy
from collections import Counter

from wit.extraction.extract import (extract_template, grounding_errors,
                                     claims_grounding_errors, claims_quotes_match)
from wit.extraction.schema import validate_template, FIELD_IDS
from wit.extraction.completeness import score_completeness

# Crediting order (WIT-P3o): specified > implied > unspecified. Ties resolve to the MINIMUM
# credit — the conservative, honest-gap reading.
_CREDIT = {"specified": 2, "implied": 1, "unspecified": 0}


def _vote_status(statuses: list[str]) -> tuple[str, str]:
    """Return (winning_status, kind) where kind in {unanimous, majority, tie}. Majority wins;
    on a tie among the top-count statuses, the least-crediting tied status wins."""
    counts = Counter(statuses)
    top = max(counts.values())
    winners = [s for s, c in counts.items() if c == top]
    if len(set(statuses)) == 1:
        return statuses[0], "unanimous"
    if len(winners) == 1:
        return winners[0], "majority"
    # tie (includes 1/1/1): least-crediting among the tied winners
    return min(winners, key=lambda s: _CREDIT[s]), "tie"


def _field_donor(fid: str, voted: str, runs: list[dict], medoid_i: int) -> dict:
    """The field OBJECT for the voted status: medoid's if its status matches the vote, else the
    lowest-index run whose status matches. A donor always exists (the vote picks a status some
    run produced)."""
    med = runs[medoid_i]["template"]["fields"][fid]
    if med.get("status") == voted:
        return med
    for run in runs:
        f = run["template"]["fields"][fid]
        if f.get("status") == voted:
            return f
    raise RuntimeError(f"ensemble bug: no donor for voted status {voted!r} on {fid}")


def _merge_claims(runs: list[dict], medoid_i: int) -> list[dict]:
    """Group claims across ok runs by quote overlap (claims_quotes_match); keep EVERY group
    (exhaustiveness — each member is already grounded). Representative = medoid's member if the
    group has one, else the lowest-index member. testable = majority across the group; tie => the
    representative's own flag."""
    groups: list[list[tuple[int, dict]]] = []
    for ri, run in enumerate(runs):
        for c in run["template"].get("claims", []):
            for g in groups:
                if any(claims_quotes_match(c.get("quote"), m[1].get("quote")) for m in g):
                    g.append((ri, c))
                    break
            else:
                groups.append([(ri, c)])

    merged: list[dict] = []
    for g in groups:
        med_members = [c for (ri, c) in g if ri == medoid_i]
        rep = med_members[0] if med_members else min(g, key=lambda t: t[0])[1]
        flags = Counter(bool(c.get("testable")) for (_, c) in g)
        if flags[True] > flags[False]:
            testable = True
        elif flags[False] > flags[True]:
            testable = False
        else:
            testable = bool(rep.get("testable"))
        mc = copy.deepcopy(rep)
        mc["testable"] = testable
        merged.append(mc)
    return merged


def extract_template_ensemble(transcript: str, source_meta: dict, *, k: int = 3,
                              model: str | None = None, api_key: str | None = None) -> dict:
    runs: list[dict] = []
    failures: list[dict] = []
    for i in range(k):
        r = extract_template(transcript, source_meta, model=model, api_key=api_key)
        if r.get("status") == "ok":
            runs.append(r)
        else:
            failures.append({"run": i, "errors": r.get("errors")})

    if len(runs) < 2:
        return {"status": "extraction_failed",
                "template": runs[0]["template"] if runs else None,
                "errors": [f"run {f['run']}: {e}" for f in failures for e in (f["errors"] or [])],
                "ensemble_meta": {"k": k, "ok_runs": len(runs)}}

    # ── per-field vote over the ok runs ──
    voted: dict[str, str] = {}
    kinds: dict[str, str] = {}
    for fid in FIELD_IDS:
        statuses = [run["template"]["fields"][fid]["status"] for run in runs]
        voted[fid], kinds[fid] = _vote_status(statuses)

    # ── medoid = ok run agreeing with the vote in the most fields; tie => lowest index ──
    medoid_i, best_agree = 0, -1
    for i, run in enumerate(runs):
        agree = sum(1 for fid in FIELD_IDS
                    if run["template"]["fields"][fid]["status"] == voted[fid])
        if agree > best_agree:
            best_agree, medoid_i = agree, i
    medoid_tpl = runs[medoid_i]["template"]

    # ── build the merged template ──
    merged = {
        "template_version": medoid_tpl.get("template_version"),
        "source": copy.deepcopy(medoid_tpl.get("source")),
        "fields": {},
        "claims": _merge_claims(runs, medoid_i),
        "consistency_flags": copy.deepcopy(medoid_tpl.get("consistency_flags", [])),
        "interpretations": copy.deepcopy(medoid_tpl.get("interpretations", [])),
        "completeness": {"score": 0, "class": "A", "required_missing": []},
    }
    for fid in FIELD_IDS:
        obj = copy.deepcopy(_field_donor(fid, voted[fid], runs, medoid_i))
        obj["status"] = voted[fid]  # exact (already matches by construction)
        merged["fields"][fid] = obj

    # ── re-check before scoring: this must hold by construction; a violation is a bug ──
    verrs = validate_template(merged)
    if verrs:
        raise RuntimeError(f"ensemble merge produced an invalid template: {verrs}")
    gerrs = grounding_errors(merged, transcript) + claims_grounding_errors(merged, transcript)
    if gerrs:
        raise RuntimeError(f"ensemble merge produced an ungrounded template: {gerrs}")
    merged["completeness"] = score_completeness(merged)

    ensemble_meta = {
        "k": k,
        "ok_runs": len(runs),
        "medoid_index": medoid_i,
        "unanimous_fields": sum(1 for f in FIELD_IDS if kinds[f] == "unanimous"),
        "majority_fields": sum(1 for f in FIELD_IDS if kinds[f] == "majority"),
        "tie_fields": sum(1 for f in FIELD_IDS if kinds[f] == "tie"),
        "per_run": [{"retries": run["raw_meta"].get("retries"),
                     "demotions": run.get("demotions", []),
                     "downgrades": run.get("downgrades", [])} for run in runs],
    }
    return {"status": "ok", "template": merged, "completeness": merged["completeness"],
            "demotions": [], "downgrades": [],  # merge stage itself demotes/downgrades nothing;
            "raw_meta": {"model": runs[medoid_i]["raw_meta"].get("model"), "ensemble_k": k},
            "ensemble_meta": ensemble_meta}

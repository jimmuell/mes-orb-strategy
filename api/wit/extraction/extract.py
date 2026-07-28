"""Extraction orchestrator (WIT-P3e-2): transcript -> validated WIT-02 template.

Flow: build prompts -> provider.extract_once -> validate_template -> (retry feeding errors
back, <= max_retries) -> on success score_completeness + write the completeness block + fill
source. Class is NEVER taken from the model: we overwrite completeness with the deterministic
scorer's output (WIT-02 §3/§4). On terminal failure returns status "extraction_failed" with the
last candidate + validation errors — never a silent pass.

The production call lives in the Supabase wit-extract edge function; the model default here only
drives the local golden harness (P3e-2).
"""
from __future__ import annotations

import hashlib
import os
import re

from wit.extraction import provider
from wit.extraction.prompt import build_system_prompt, build_user_prompt
from wit.extraction.schema import validate_template, FIELD_IDS
from wit.extraction.completeness import score_completeness

# Statuses that REQUIRE a grounded, verbatim source_quote (WIT-02 §4.1). J fields are
# WIT-authored (validation plan) and are exempt — never grounding-checked.
_GROUNDED_STATUSES = {"specified", "implied"}

# WIT-P3e-5 BASIS DISCIPLINE. Every REQUIRED field that is specified/implied must DECLARE a
# basis; the two "example/tendency" bases cannot support a satisfied status and are
# deterministically demoted to unspecified before scoring.
_REQUIRED_BASIS_FIELDS = ("B1", "B2", "D1", "D2", "D3", "D4", "F1", "F2", "F4")
_DEMOTING_BASES = {"narrated_example", "tendency_or_claim"}

# Current, capable Claude model id (extraction quality matters for the grounding rubric).
# Overridable per deployment via WIT_EXTRACTION_MODEL. Recorded in the WIT-P3e-2 report.
DEFAULT_MODEL = os.environ.get("WIT_EXTRACTION_MODEL") or "claude-opus-4-8"


def _norm(s: str) -> str:
    # IDENTICAL to the golden test's _norm (test_extraction_golden.py): collapse all
    # whitespace runs to a single space, strip, lowercase. Grounding here and grading
    # there MUST use the same normalization or a live extraction could pass one and fail
    # the other.
    return re.sub(r"\s+", " ", s or "").strip().lower()


def grounding_errors(template: dict, transcript: str) -> list[str]:
    """Anti-hallucination check (WIT-02 §4.1): every non-J field whose status is
    specified/implied must carry a non-empty source_quote that, after normalization, is a
    verbatim substring of the transcript. Returns a list of actionable error strings (empty
    == fully grounded). Mirrors the golden test's grounding assert exactly."""
    errs: list[str] = []
    fields = template.get("fields")
    if not isinstance(fields, dict):
        return errs  # structural validation owns this case; nothing to ground
    ntx = _norm(transcript)
    for fid in FIELD_IDS:
        if fid[0] == "J":  # WIT-authored validation plan — no transcript quote required
            continue
        f = fields.get(fid)
        if not isinstance(f, dict) or f.get("status") not in _GROUNDED_STATUSES:
            continue
        q = f.get("source_quote")
        if not q:
            errs.append(
                f"fields.{fid}.source_quote is empty but status is {f.get('status')!r} — "
                "a specified/implied field MUST quote the transcript verbatim; copy the exact "
                "span the rule comes from, or set status to 'unspecified'.")
        elif _norm(q) not in ntx:
            errs.append(
                f"fields.{fid}.source_quote is not a verbatim substring of the transcript — "
                "copy the quote character-for-character from the transcript, including caption "
                "typos; do not fix spelling, punctuation, or numbers; a shorter exact span is "
                "fine.")
    return errs


def claims_grounding_errors(template: dict, transcript: str) -> list[str]:
    """Every claims[] entry must carry a non-empty quote that, after normalization, is a
    verbatim substring of the transcript (WIT-P3o flagged this gap: fields were grounded at
    runtime, claims were not). Returns actionable error strings; empty == fully grounded."""
    errs: list[str] = []
    claims = template.get("claims")
    if not isinstance(claims, list):
        return errs  # structural validation owns the shape
    ntx = _norm(transcript)
    for i, c in enumerate(claims):
        if not isinstance(c, dict):
            continue  # structural validation owns malformed entries
        q = c.get("quote")
        if not q or _norm(q) not in ntx:
            errs.append(
                f"claims[{i}].quote (claim {c.get('claim')!r}) is not a verbatim substring of "
                "the transcript — copy it character-for-character; a shorter exact span is fine.")
    return errs


def missing_basis_errors(template: dict) -> list[str]:
    """WIT-P3e-5: a REQUIRED field that is specified/implied must DECLARE a basis. Missing
    basis is a retry error (feeds the loop) naming the field."""
    errs: list[str] = []
    fields = template.get("fields")
    if not isinstance(fields, dict):
        return errs
    for fid in _REQUIRED_BASIS_FIELDS:
        f = fields.get(fid)
        if not isinstance(f, dict):
            continue
        if f.get("status") in _GROUNDED_STATUSES and not f.get("basis"):
            errs.append(
                f"fields.{fid} is {f.get('status')} but declares no basis — REQUIRED fields must "
                "set basis to one of stated_rule|generalized_practice|narrated_example|"
                "tendency_or_claim (BASIS DISCIPLINE).")
    return errs


def apply_demotions(template: dict) -> list[dict]:
    """WIT-P3e-5 deterministic enforcement: ANY field whose declared basis cannot support a
    satisfied status (narrated_example / tendency_or_claim) is demoted to unspecified BEFORE
    scoring — no retry, no failure. Returns the demotions [{field, from_status, basis}] in
    FIELD_IDS order (empty when none). The scorer then sees the demoted template."""
    demotions: list[dict] = []
    fields = template.get("fields")
    if not isinstance(fields, dict):
        return demotions
    for fid in FIELD_IDS:
        f = fields.get(fid)
        if not isinstance(f, dict):
            continue
        if f.get("status") in _GROUNDED_STATUSES and f.get("basis") in _DEMOTING_BASES:
            demotions.append({"field": fid, "from_status": f["status"], "basis": f["basis"]})
            f["status"] = "unspecified"
    return demotions


def _finalize_source(template: dict, source_meta: dict, transcript: str) -> None:
    sm = source_meta or {}
    thash = sm.get("transcript_hash") or hashlib.sha256(
        (transcript or "").encode("utf-8")).hexdigest()
    template["source"] = {"url": sm.get("url"), "title": sm.get("title"),
                          "channel": sm.get("channel"), "transcript_hash": thash}


def extract_template(transcript: str, source_meta: dict, *, model: str | None = None,
                     max_retries: int = 2, api_key: str | None = None) -> dict:
    model = model or DEFAULT_MODEL
    system = build_system_prompt()
    base_user = build_user_prompt(transcript, source_meta)
    user = base_user
    errors: list[str] = []
    last_candidate = None

    for attempt in range(max_retries + 1):
        res = provider.extract_once(system, user, model=model, api_key=api_key)
        template = res.get("template")
        last_candidate = template
        if not isinstance(template, dict):
            errors = ["tool output was not a JSON object"]
        else:
            # WE own source + completeness — the model must not decide the class. Force a
            # valid placeholder completeness so structural validation never fails on it; the
            # real class is computed after validation passes.
            _finalize_source(template, source_meta, transcript)
            template["completeness"] = {"score": 0, "class": "A", "required_missing": []}
            errors = validate_template(template)
            # Grounding + claims-grounding + basis-declaration are gates on success EQUAL to
            # schema validity: schema-valid but hallucinated/under-declared output must
            # retry/fail exactly like a structural error. Checked in order so each layer's
            # errors aren't buried under the previous layer's noise.
            if not errors:
                errors = grounding_errors(template, transcript)
            if not errors:
                errors = claims_grounding_errors(template, transcript)
            if not errors:
                errors = missing_basis_errors(template)
            if not errors:
                # Deterministic demotion runs AFTER all retry gates pass and BEFORE scoring:
                # a satisfied field whose basis cannot support it becomes unspecified, so
                # over-crediting a narrated example cannot survive to the class.
                demotions = apply_demotions(template)
                template["completeness"] = score_completeness(template)
                return {"status": "ok", "template": template,
                        "completeness": template["completeness"],
                        "demotions": demotions,
                        "raw_meta": {"model": model, "retries": attempt,
                                     "usage": res.get("usage")}}
        # retry: feed the validation/grounding errors back into the user turn
        user = (base_user + "\n\nYour previous output FAILED validation with these errors — "
                "fix them and re-emit the COMPLETE template:\n"
                + "\n".join(f"- {e}" for e in errors))

    return {"status": "extraction_failed", "template": last_candidate, "errors": errors}

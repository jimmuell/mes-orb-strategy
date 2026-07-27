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

from wit.extraction import provider
from wit.extraction.prompt import build_system_prompt, build_user_prompt
from wit.extraction.schema import validate_template
from wit.extraction.completeness import score_completeness

# Current, capable Claude model id (extraction quality matters for the grounding rubric).
# Overridable per deployment via WIT_EXTRACTION_MODEL. Recorded in the WIT-P3e-2 report.
DEFAULT_MODEL = os.environ.get("WIT_EXTRACTION_MODEL") or "claude-opus-4-8"


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
            if not errors:
                template["completeness"] = score_completeness(template)
                return {"status": "ok", "template": template,
                        "completeness": template["completeness"],
                        "raw_meta": {"model": model, "retries": attempt,
                                     "usage": res.get("usage")}}
        # retry: feed the validation errors back into the user turn
        user = (base_user + "\n\nYour previous output FAILED validation with these errors — "
                "fix them and re-emit the COMPLETE template:\n"
                + "\n".join(f"- {e}" for e in errors))

    return {"status": "extraction_failed", "template": last_candidate, "errors": errors}

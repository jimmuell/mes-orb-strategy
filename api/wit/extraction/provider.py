"""Anthropic provider for WIT extraction (WIT-P3e-2) — the ONLY module that touches the SDK.

The `anthropic` import is LAZY (inside `extract_once`), so importing this module never requires
the SDK — the Railway runtime never installs it (anthropic is dev/CI-only, requirements-dev.txt).
The live production extraction call runs in the Supabase `wit-extract` edge function; this module
drives the local golden harness (P3e-2) and is the reference implementation of the call.

Structured output = a single forced tool call whose input_schema is derived from the WIT-02
template schema. That schema is GUIDANCE for the model only — the hard gate is our own
validate_template() in the orchestrator.
"""
from __future__ import annotations

import copy
import os

from wit.extraction.schema import load_schema, _BASIS_ENUM

TOOL_NAME = "emit_strategy_template"
# API input_schema is standard JSON Schema; strip the meta keys the Messages API rejects while
# keeping the structure ($defs/$ref/required/etc.).
_STRIP_META = ("$schema", "$id", "$comment", "title")
_MAX_OUTPUT_TOKENS = 8192


def build_tool() -> dict:
    # DEEP copy: the field $def is mutated below to offer `basis`, and load_schema() is
    # lru_cached — a shallow copy would corrupt the shared schema used by validate_template.
    schema = copy.deepcopy({k: v for k, v in load_schema().items() if k not in _STRIP_META})
    # WIT-P3e-5: offer the optional evidence declaration. The field $def has
    # additionalProperties:false, so the model can only emit `basis` if it is declared here.
    # It stays OUT of the $def's `required`, so omitting it is schema-valid (the orchestrator's
    # missing-basis check — not the tool schema — enforces it on REQUIRED fields).
    field_def = schema.get("$defs", {}).get("field")
    if isinstance(field_def, dict) and isinstance(field_def.get("properties"), dict):
        field_def["properties"]["basis"] = {
            "type": "string",
            "enum": sorted(_BASIS_ENUM),
            "description": "WIT-P3e-5 evidence declaration for REQUIRED specified/implied fields "
                           "(BASIS DISCIPLINE). narrated_example / tendency_or_claim do NOT "
                           "support specified/implied and are demoted to unspecified.",
        }
    return {
        "name": TOOL_NAME,
        "description": "Emit the filled WIT-02 strategy template as structured JSON. Fill every "
                       "field; do not set completeness.class (a scorer assigns it).",
        "input_schema": schema,
    }


def extract_once(system_prompt: str, user_prompt: str, *, model: str,
                 api_key: str | None = None) -> dict:
    """One Messages API call forcing the emit_strategy_template tool. Returns
    {"template": <dict>, "usage": {...}}. No retry / no validation here."""
    import anthropic  # LAZY — importing this module must not require the SDK

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set — extract_once needs a live key")

    client = anthropic.Anthropic(api_key=key)
    tool = build_tool()
    resp = client.messages.create(
        model=model,
        max_tokens=_MAX_OUTPUT_TOKENS,
        system=system_prompt,
        tools=[tool],
        tool_choice={"type": "tool", "name": TOOL_NAME},
        messages=[{"role": "user", "content": user_prompt}],
    )
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == TOOL_NAME:
            return {"template": block.input,
                    "usage": {"input_tokens": resp.usage.input_tokens,
                              "output_tokens": resp.usage.output_tokens}}
    raise RuntimeError(f"model did not return a {TOOL_NAME} tool_use block")

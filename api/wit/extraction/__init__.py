"""WIT extraction package (WIT-03 §4).

P3b scope — the completeness FOUNDATION, no LLM and no network:
  - schema.py       : load schema/strategy-template.v1.json + validate_template()
  - completeness.py : the pure routing scorer (Class A|B|C + required_missing + score)

The LLM extraction core (prompt/provider/extract) and the template->config mapper
are later prompts (P3e / P3c) and are intentionally NOT here.
"""

from wit.extraction.schema import load_schema, validate_template, FIELD_IDS
from wit.extraction.completeness import score_completeness

__all__ = ["load_schema", "validate_template", "FIELD_IDS", "score_completeness"]

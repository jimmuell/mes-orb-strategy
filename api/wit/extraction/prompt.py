"""Extraction prompt builder (WIT-P3e-1) — pure, no new dependency, no network.

Builds the system + user prompts for transcript -> WIT-02 template extraction. The
supported mode vocabulary is parsed at runtime from `contract/modes.md` so that file
stays the SINGLE SOURCE OF TRUTH: a token marked `†` there (declared but not
engine-supported in v1) is NEVER offered to the model. The LLM tool/input_schema and
the live provider call are P3e-2 — nothing here calls a model.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache

from wit.extraction.schema import FIELD_IDS

_HERE = os.path.dirname(os.path.abspath(__file__))
_API = os.path.dirname(os.path.dirname(_HERE))
_REPO = os.path.dirname(_API)
MODES_PATH = os.path.join(_REPO, "contract", "modes.md")

_DAGGER = "†"  # † — "declared, not engine-supported in v1"
# a backtick-wrapped token, capturing whether a † immediately follows the closing backtick
_TOKEN_RE = re.compile(r"`([^`]+)`(" + _DAGGER + r"?)")


@lru_cache(maxsize=1)
def _read_modes() -> str:
    with open(MODES_PATH, encoding="utf-8") as fh:
        return fh.read()


def _cells(line: str) -> list[str]:
    # a markdown table row "| a | b | c |" -> ["a","b","c"]. Split on UNESCAPED pipes only —
    # a cell may contain an escaped `\|` (e.g. stop params `{ref: poc\|va\|orb, ticks}`);
    # splitting on those would fragment the row and misalign the columns.
    parts = re.split(r"(?<!\\)\|", line.strip())
    parts = [p.replace(r"\|", "|").strip() for p in parts]
    # drop the leading/trailing empty cells produced by the outer pipes
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def _param_keys(cell: str) -> list[str]:
    """Extract the typed param KEYS from a modes.md params cell, e.g.
    `{range_start, range_end, value_area_pct, granularity}` -> those 4;
    `{ref: poc|va|orb, ticks}` -> [ref, ticks]. `—` -> []."""
    m = re.search(r"\{([^}]*)\}", cell)
    if not m:
        return []
    keys = []
    for part in m.group(1).split(","):
        k = part.split(":")[0].strip().strip("`").strip()
        if k:
            keys.append(k)
    return keys


@lru_cache(maxsize=1)
def _parse_modes() -> dict[str, dict]:
    """Parse BOTH mode tables → dimension -> {supported, unsupported, field, param_keys}.
    Tokens are PER-DIMENSION (never a global set); a token is supported iff NOT immediately
    followed by †. `field` and `param_keys` come from the Field and params columns so
    contract/modes.md stays the single source of truth for those too."""
    out: dict[str, dict] = {}
    dim_col = tok_col = field_col = param_col = None
    in_table = False
    for raw in _read_modes().splitlines():
        line = raw.rstrip()
        is_row = line.lstrip().startswith("|")
        if is_row and "v1 mode tokens" in line:
            cells = _cells(line)
            dim_col = cells.index("Dimension")
            tok_col = cells.index("v1 mode tokens")
            field_col = cells.index("Field")
            param_col = next(i for i, c in enumerate(cells) if "params" in c)
            in_table = True
            continue
        if not is_row:
            in_table = False
            continue
        if not in_table or set(line.strip("| ")) <= {"-", ":", " "}:
            continue  # separator row |---|---|
        cells = _cells(line)
        if dim_col is None or max(dim_col, tok_col, field_col, param_col) >= len(cells):
            continue
        dm = re.search(r"`([^`]+)`", cells[dim_col])
        if not dm:
            continue
        dimension = dm.group(1)
        rec = out.setdefault(dimension, {"supported": [], "unsupported": [],
                                         "field": cells[field_col],
                                         "param_keys": _param_keys(cells[param_col])})
        for tok, dagger in _TOKEN_RE.findall(cells[tok_col]):
            key = "unsupported" if dagger == _DAGGER else "supported"
            if tok not in rec[key]:
                rec[key].append(tok)
    return out


def supported_modes() -> dict[str, list[str]]:
    """dimension -> list of ENGINE-SUPPORTED v1 mode tokens (†-marked tokens excluded).
    Only dimensions that have at least one supported token are returned."""
    return {d: list(r["supported"]) for d, r in _parse_modes().items() if r["supported"]}


def unsupported_modes() -> dict[str, list[str]]:
    """dimension -> list of declared-but-not-engine-supported (†) tokens — the backlog view."""
    return {d: list(r["unsupported"]) for d, r in _parse_modes().items() if r["unsupported"]}


# ---------------------------------------------------------------------------
# 27-field spec (WIT-02 §2), grouped A–K, one line each. Ids are the authoritative
# FIELD_IDS from the schema; the assert below guarantees full coverage.
# ---------------------------------------------------------------------------
_SECTION_TITLES = {
    "A": "Identity & Claims", "B": "Market & Data",
    "C": "Permission filters — 'may I trade today?'", "D": "Direction & Setup",
    "E": "Position sizing", "F": "Exits", "G": "Risk controls",
    "H": "Costs & execution", "I": "Optimization surface",
    "J": "Validation plan (WIT-authored — no source_quote required)",
    "K": "Documentation",
}
_FIELD_SPEC = {
    "A1": ("name_and_source", "video title/URL/channel; strategy nickname"),
    "A2": ("claimed_performance", "EVERY performance assertion, verbatim, incl. unfalsifiable ones"),
    "A3": ("internal_consistency_flags", "contradictions inside the source itself"),
    "B1": ("instrument", "what the guru trades + what WIT tests on; tick size/value"),
    "B2": ("timeframe", "decision chart timeframe(s)"),
    "B3": ("data_requirements", "granularity the strategy needs beyond its chart"),
    "C1": ("session_rules", "trading window, entry cutoff, forced-flat time, timezone"),
    "C2": ("regime_filters", "volatility/trend-quality gates (ATR/ADX/VIX/chop)"),
    "C3": ("calendar_filters", "skip FOMC/CPI/holidays/weekdays"),
    "D1": ("directional_bias", "how long vs short is decided"),
    "D2": ("setup", "the opportunity pattern (ORB, pullback, VWAP bounce, gap fill…)"),
    "D3": ("entry_trigger", "the exact executable moment; a setup is NOT a trigger"),
    "D4": ("order_mechanics", "market/limit/stop; act on close vs intrabar; fill assumptions"),
    "E1": ("position_sizing", "contracts / %-risk / ATR-sized"),
    "F1": ("initial_stop", "where the trade is wrong; distance in points or ATR"),
    "F2": ("profit_target", "fixed dollar amount, an R-multiple, or absent"),
    "F3": ("trade_management", "break-even moves, trailing, scale-outs"),
    "F4": ("time_exit", "max hold / end-of-session flatten"),
    "F5": ("stop_target_same_bar_policy", "which fills first when both touched in one bar"),
    "G1": ("trade_frequency_limits", "max trades/day, re-entry, one-position-at-a-time"),
    "G2": ("loss_limits", "daily/weekly stop-trading rules"),
    "H1": ("commission", "per side/contract"),
    "H2": ("slippage", "ticks per side"),
    "I1": ("parameters", "every tunable the source exposes + stated defaults"),
    "J1": ("test_design", "window, in/out-of-sample, metrics, regime schemes (WIT fills)"),
    "J2": ("interpretation_set", "the reasonable codifications tested when ambiguous (WIT fills)"),
    "K1": ("untestable_remainder", "the discretionary residue that cannot be tested"),
}
assert set(_FIELD_SPEC) == set(FIELD_IDS), "field spec must cover all 27 schema field ids"

_RULES = """\
EXTRACTION RULES (WIT-02 §1/§4) — follow exactly:
1. Extract ONLY what the source states or directly implies. NEVER charitably complete a
   vague rule: if a rule is vague or absent, its status is "unspecified" — do not guess it.
2. Every field whose status is "specified" or "implied" MUST carry a non-empty source_quote
   that is a VERBATIM SUBSTRING of the transcript (word-for-word). The sole exception is the
   J section (validation plan), which is WIT-authored and needs no source_quote.
3. Keep the SETUP (D2) and the ENTRY TRIGGER (D3) SEPARATE — a setup is not an entry trigger.
   Do not conflate the two.
4. Capture EVERY performance claim verbatim into claims[] (including unfalsifiable/anecdotal
   ones). Record internal contradictions (e.g. risk:reward arithmetic, timeframe) into
   consistency_flags[].
5. CLASS IS AN OUTPUT, NOT AN INPUT: do NOT decide A/B/C and do NOT set completeness.class —
   just fill the fields honestly; a deterministic scorer assigns the class afterward.
6. Record genuine alternate readings of an ambiguous rule in interpretations[] rather than
   silently choosing one.
Field conventions: each field object is {value, status, source_quote, assumption[, mode, params]};
status ∈ {specified, implied, unspecified}."""


def _field_spec_block() -> str:
    lines = ["THE 27-FIELD TEMPLATE (fill every field; WIT-02 §2):"]
    cur = None
    for fid in FIELD_IDS:
        section = fid[0]
        if section != cur:
            cur = section
            lines.append(f"  {section}. {_SECTION_TITLES[section]}")
        name, purpose = _FIELD_SPEC[fid]
        lines.append(f"    {fid} ({name}): {purpose}")
    return "\n".join(lines)


def _vocab_block() -> str:
    recs = _parse_modes()
    lines = [
        "CONFIG-RELEVANT MODE VOCABULARY (contract/modes.md — the ONLY tokens you may use):",
        "For each dimension below, on the named template field(s) set `mode` to one of the listed",
        "supported tokens and fill the typed `params` keys. If the strategy needs a construct not",
        "listed here, leave mode null and describe it in `value` — do NOT invent a mode token, and",
        "NEVER use a token not listed.",
    ]
    for dim in sorted(d for d, r in recs.items() if r["supported"]):
        r = recs[dim]
        params = f" params {{{', '.join(r['param_keys'])}}}" if r["param_keys"] else ""
        lines.append(f"    {dim} (field {r['field']}): mode ∈ {{{', '.join(r['supported'])}}}{params}")
    return "\n".join(lines)


def build_system_prompt() -> str:
    return "\n\n".join([
        "You are WIT's strategy extractor. Read a trading-strategy transcript and fill the "
        "WIT-02 template as strict JSON. You judge nothing and score nothing — you only record "
        "what the source says, faithfully and auditable to the transcript.",
        _RULES,
        _field_spec_block(),
        _vocab_block(),
        "Output: a WIT-02 template object with `fields` (all 27 ids), `claims[]`, "
        "`consistency_flags[]`, `interpretations[]`, and `source`. Do not set completeness.class.",
    ])


def build_user_prompt(transcript: str, source_meta: dict) -> str:
    sm = source_meta or {}
    meta = "\n".join(f"  {k}: {sm.get(k)}"
                     for k in ("url", "title", "channel", "transcript_hash"))
    return (f"SOURCE META:\n{meta}\n\n"
            f"TRANSCRIPT (extract only from the text below; source_quotes must be verbatim "
            f"substrings of it):\n\"\"\"\n{transcript}\n\"\"\"")

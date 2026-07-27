"""Completeness scorer — the WIT routing keystone (pure, deterministic).

Turns a filled WIT-02 template into `{score, class, required_missing}` — the
`completeness` block of the template and the `templates.completeness_score/class`
columns (WIT-03 §4/§6). Class + required_missing are the HARD contract (they
route the evaluation: A -> costed backtest, B -> event study, C -> untestable
report). `score` is a softer defined metric.

All load-bearing numbers are NAMED CONSTANTS below, cited to WIT-02 §3/§5. The
routing logic is lead-engineer-pinned (P3b prompt) — do not tune it silently.

ROUTING-INTEGRITY GATE (WIT-P3b-fix): §5 defaults may fill PERIPHERAL mechanics
and costs, but must NEVER manufacture the core entry. The close-vs-touch default
(D3) disambiguates an entry trigger that already exists — it can't invent one — so
a fully `unspecified` D3 (no trigger) gets NO default credit. The defaults that
presuppose a trigger — order mechanics (D4) and time-exit (F4) — are creditable
ONLY when a trigger is actually stated (`has_entry`). Otherwise a template with a
setup but no stated trigger could falsely assume its way into Class A.
"""
from __future__ import annotations

# ── WIT-02 §3: required-to-execute fields ───────────────────────────────────
# "B1, B2, D1-D4, F1, plus F2 or F4". The base set are individually required;
# F2/F4 are an OR-pair (either satisfies the exit requirement).
REQUIRED_BASE = frozenset({"B1", "B2", "D1", "D2", "D3", "D4", "F1"})
EXIT_PAIR = ("F2", "F4")            # satisfied if EITHER is satisfied; else "F2|F4" is missing

# ── WIT-02 §5: Default Assumption Policy — fields that HAVE a v1 default ──────
# Unconditional defaults (peripheral mechanics/costs that never depend on the
# entry): sizing (E1), commission (H1), slippage (H2), same-bar policy (F5),
# VP/intrabar data (B3). NOTE: D3 is deliberately ABSENT — the close-vs-touch
# default resolves an EXISTING trigger; an unspecified trigger must not be
# default-credited (WIT-P3b-fix). A trigger that is stated is already satisfied
# via its status, so D3 needs no default.
UNCONDITIONAL_DEFAULTS = frozenset({"E1", "H1", "H2", "F5", "B3"})
# Entry-conditional defaults: order mechanics (D4, "market on trigger") and
# time-exit (F4, "session close if no target/stop pathway exits") both presuppose
# an entry. Creditable ONLY when has_entry is true (WIT-02 §5 + WIT-P3b-fix).
ENTRY_CONDITIONAL_DEFAULTS = frozenset({"D4", "F4"})
# Conditional default: G1 re-entry/one-trade-per-day default applies ONLY "when a
# daily setup is implied" (WIT-02 §5). That signal is recorded by the extractor
# populating G1.assumption; so G1 has a default iff its assumption field is set.
CONDITIONAL_DEFAULT_FIELD = "G1"

# ── WIT-02 §3: score weighting over sections B-H (A, I-K are metadata) ───────
# Required-to-execute fields "weigh heaviest": weight 2. Both members of the
# F2/F4 exit pair carry the heavy weight. All other B-H fields weight 1.
REQUIRED_WEIGHT_FIELDS = frozenset({"B1", "B2", "D1", "D2", "D3", "D4", "F1", "F2", "F4"})
HEAVY_WEIGHT = 2
LIGHT_WEIGHT = 1
SCORED_SECTIONS = "BCDEFGH"        # B-H inclusive; A, I, J, K excluded (metadata)

_SATISFIED_STATUSES = {"specified", "implied"}
ASSUMPTION_FILL_LIMIT = 6          # WIT-02 §3: Class A allows <= 6 assumption fills


def _field(template: dict, fid: str) -> dict:
    f = template.get("fields", {}).get(fid)
    return f if isinstance(f, dict) else {"status": "unspecified", "assumption": None}


def _has_entry(template: dict) -> bool:
    """True iff an entry trigger is actually stated — D3 status is specified/implied.
    D3 has no §5 default (WIT-P3b-fix), so this is purely 'the source gave a trigger'."""
    return _field(template, "D3").get("status") in _SATISFIED_STATUSES


def _has_default(fid: str, field: dict, has_entry: bool) -> bool:
    if fid in UNCONDITIONAL_DEFAULTS:
        return True
    if fid in ENTRY_CONDITIONAL_DEFAULTS:
        return has_entry           # D4/F4 default credit gated on a stated trigger
    if fid == CONDITIONAL_DEFAULT_FIELD:
        return field.get("assumption") is not None
    return False


def _satisfied(fid: str, field: dict, has_entry: bool) -> bool:
    """A field is satisfied if the source states/implies it, OR it is unspecified
    but a §5 default fills it (WIT-02 §3/§5). Default credit for entry-conditional
    fields (D4/F4) requires has_entry (WIT-P3b-fix)."""
    status = field.get("status")
    if status in _SATISFIED_STATUSES:
        return True
    return status == "unspecified" and _has_default(fid, field, has_entry)


def score_completeness(template: dict) -> dict:
    """Return {'score': int, 'class': 'A'|'B'|'C', 'required_missing': [ids]}."""
    has_entry = _has_entry(template)

    # required_missing: base fields not satisfied, plus the F2|F4 pair token.
    required_missing: list[str] = []
    for fid in sorted(REQUIRED_BASE):
        if not _satisfied(fid, _field(template, fid), has_entry):
            required_missing.append(fid)
    f2, f4 = EXIT_PAIR
    if not (_satisfied(f2, _field(template, f2), has_entry)
            or _satisfied(f4, _field(template, f4), has_entry)):
        required_missing.append("|".join(EXIT_PAIR))

    # assumption_fills: B-H fields that are unspecified AND have a §5 default.
    assumption_fills = 0
    for fid in _bh_field_ids(template):
        fobj = _field(template, fid)
        if fobj.get("status") == "unspecified" and _has_default(fid, fobj, has_entry):
            assumption_fills += 1

    # class routing (WIT-02 §3)
    is_class_a = (not required_missing) and assumption_fills <= ASSUMPTION_FILL_LIMIT
    if is_class_a:
        cls = "A"
    elif _has_testable_claim(template):
        cls = "B"
    else:
        cls = "C"

    return {
        "score": _weighted_score(template),
        "class": cls,
        "required_missing": required_missing,
    }


def assumption_fills(template: dict) -> int:
    """Exposed for tests/reporting: count of B-H unspecified fields with a §5 default
    (entry-conditional defaults counted only when a trigger is stated — WIT-P3b-fix)."""
    has_entry = _has_entry(template)
    n = 0
    for fid in _bh_field_ids(template):
        fobj = _field(template, fid)
        if fobj.get("status") == "unspecified" and _has_default(fid, fobj, has_entry):
            n += 1
    return n


def _weighted_score(template: dict) -> int:
    """Weighted completeness over B-H only. required fields weight 2, others 1;
    specified/implied = full credit, unspecified = 0.
        score = round(100 * earned / total_weight)
    Note: score credits STATUS only (specified/implied) — a field satisfied via a
    §5 default still scores 0, by design (an assumption is disclosed, not evidence)."""
    total = 0
    earned = 0
    for fid in _bh_field_ids(template):
        w = HEAVY_WEIGHT if fid in REQUIRED_WEIGHT_FIELDS else LIGHT_WEIGHT
        total += w
        if _field(template, fid).get("status") in _SATISFIED_STATUSES:
            earned += w
    return round(100 * earned / total) if total else 0


def _bh_field_ids(template: dict) -> list[str]:
    ids = list(template.get("fields", {}).keys())
    if not ids:  # be robust to a fields-less dict
        from wit.extraction.schema import FIELD_IDS as _ALL
        ids = list(_ALL)
    return [f for f in ids if f and f[0] in SCORED_SECTIONS]


def _all_bh_and_required(template: dict) -> set[str]:
    return set(_bh_field_ids(template)) | REQUIRED_BASE | set(EXIT_PAIR)


def _has_testable_claim(template: dict) -> bool:
    for c in template.get("claims", []) or []:
        if isinstance(c, dict) and c.get("testable") is True:
            return True
    return False

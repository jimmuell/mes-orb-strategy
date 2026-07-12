#!/usr/bin/env python3
"""ADR-050 CI security gate — make shipping a known-vulnerable dependency IMPOSSIBLE, not
'please be careful'.

Runs `pip-audit` against a locked requirements file (the shipped runtime set), classifies each
finding's severity from OSV (CVSS v3 base score, or the DB's own label), and:

  - HIGH or CRITICAL  -> FAIL the build (exit 1). Cannot be skimmed past.
  - MEDIUM / LOW / NONE -> report, do not block.
  - UNKNOWN severity  -> treated as blocking (conservative) unless allow-listed.
  - Anything in ALLOWLIST -> reported as an accepted exception (with its written reason),
    does not block. A silently-ignored warning is a hole; an allow-list entry is a decision.

Usage:  python scripts/audit_gate.py api/requirements.txt
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import urllib.request

# Accepted findings: {vuln_id: "written reason"}. Empty = nothing accepted. Add ONLY with a
# reason (e.g. "dev-only, not shipped" / "not reachable on the request path — see ADR-049").
ALLOWLIST: dict[str, str] = {}

BLOCK = {"HIGH", "CRITICAL", "UNKNOWN"}

# CVSS v3.1 base-score metric weights
_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20}
_AC = {"L": 0.77, "H": 0.44}
_UI = {"N": 0.85, "R": 0.62}
_PR_U = {"N": 0.85, "L": 0.62, "H": 0.27}
_PR_C = {"N": 0.85, "L": 0.68, "H": 0.50}
_CIA = {"N": 0.0, "L": 0.22, "H": 0.56}


def _roundup(x: float) -> float:
    return math.ceil(x * 10) / 10.0


def cvss_base(vector: str) -> float | None:
    """CVSS v3.x base score from a vector string, or None if unparseable."""
    try:
        parts = dict(p.split(":", 1) for p in vector.split("/") if ":" in p)
        scope_changed = parts.get("S") == "C"
        pr_tab = _PR_C if scope_changed else _PR_U
        iss = 1 - (1 - _CIA[parts["C"]]) * (1 - _CIA[parts["I"]]) * (1 - _CIA[parts["A"]])
        if scope_changed:
            impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
        else:
            impact = 6.42 * iss
        expl = 8.22 * _AV[parts["AV"]] * _AC[parts["AC"]] * pr_tab[parts["PR"]] * _UI[parts["UI"]]
        if impact <= 0:
            return 0.0
        raw = (1.08 if scope_changed else 1.0) * (impact + expl)
        return _roundup(min(raw, 10.0))
    except Exception:
        return None


def label(score: float | None) -> str:
    if score is None:
        return "UNKNOWN"
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    if score > 0.0:
        return "LOW"
    return "NONE"


def osv_severity(vuln_id: str, aliases: list[str]) -> str:
    """Best-effort severity label for a vuln, from OSV (CVSS preferred, then DB label)."""
    for vid in [vuln_id, *aliases]:
        try:
            with urllib.request.urlopen(f"https://api.osv.dev/v1/vulns/{vid}", timeout=20) as r:
                data = json.load(r)
        except Exception:
            continue
        for sev in data.get("severity", []) or []:
            if str(sev.get("type", "")).startswith("CVSS"):
                lab = label(cvss_base(sev.get("score", "")))
                if lab != "UNKNOWN":
                    return lab
        ds = (data.get("database_specific") or {}).get("severity")
        if ds:
            up = str(ds).upper()
            return {"MODERATE": "MEDIUM"}.get(up, up)
    return "UNKNOWN"


def main() -> int:
    reqfile = sys.argv[1] if len(sys.argv) > 1 else "api/requirements.txt"
    print(f"[audit-gate] pip-audit against {reqfile}", flush=True)
    proc = subprocess.run(
        [sys.executable, "-m", "pip_audit", "--format", "json", "--progress-spinner", "off",
         "-r", reqfile],
        capture_output=True, text=True)
    if not proc.stdout.strip():
        print("[audit-gate] pip-audit produced no output:\n" + proc.stderr, file=sys.stderr)
        return 2
    report = json.loads(proc.stdout)

    findings = []
    for dep in report.get("dependencies", []):
        for v in dep.get("vulns", []) or []:
            findings.append((dep["name"], dep.get("version", "?"), v["id"],
                             v.get("aliases", []) or [], v.get("fix_versions", []) or []))

    if not findings:
        print("[audit-gate] ✅ no known vulnerabilities in the runtime lock")
        return 0

    blocking = []
    print(f"[audit-gate] {len(findings)} finding(s):")
    for name, ver, vid, aliases, fixes in findings:
        if vid in ALLOWLIST:
            print(f"  · ACCEPTED  {name} {ver} {vid} — {ALLOWLIST[vid]}")
            continue
        sev = osv_severity(vid, aliases)
        fix = f" fix: {', '.join(fixes)}" if fixes else " (no fix available)"
        mark = "BLOCK" if sev in BLOCK else "report"
        print(f"  · {mark:6} [{sev:8}] {name} {ver} {vid}{fix}")
        if sev in BLOCK:
            blocking.append((name, vid, sev))

    if blocking:
        print(f"\n[audit-gate] ❌ FAIL — {len(blocking)} HIGH/CRITICAL/UNKNOWN finding(s) must be "
              f"fixed (bump the pin) or allow-listed with a written reason in scripts/audit_gate.py")
        return 1
    print("\n[audit-gate] ✅ pass — only sub-HIGH findings (reported, not blocking)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""WIT-0002 report-data builder: primary run + amended sensitivity grid + verdicts.

Candle+path+outcome caches are built once per timeframe; the grid varies ONE
dimension at a time off the primary (A4). Emits per-cell results + C1/C2/C3
verdicts to docs/wit/reports/data/WIT-0002-results.json and the contrast PNG.

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m wit.event_study_report
"""
from __future__ import annotations

import json
import os

import numpy as np

from wit.event_study import (EventStudyConfig, load_1min_rth, build_candles,
                             run_config, HORIZONS)

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
REPORTS = os.path.join(_REPO, "docs", "wit", "reports")
REPORTS_DATA = os.path.join(REPORTS, "data")


# ── verdict logic ──
def _verdict(contrast, ci, claim_direction):
    """claim_direction: 'neg' (claim says contrast<0) or 'pos' (contrast>0)."""
    if any(np.isnan(x) for x in (contrast, ci[0], ci[1])):
        return "Inconclusive"
    if claim_direction == "neg":
        if contrast < 0 and ci[1] < 0:
            return "Supported"
        if contrast > 0 and ci[0] > 0:
            return "Refuted"
    else:
        if contrast > 0 and ci[0] > 0:
            return "Supported"
        if contrast < 0 and ci[1] < 0:
            return "Refuted"
    return "Inconclusive"


def build_grid():
    p = EventStudyConfig()   # primary
    grid = {"primary": p}
    for k in (1.25, 2.0, 3.0):
        grid[f"k={k}"] = p.with_(k=k)
    for n in (10, 40):
        grid[f"N={n}"] = p.with_(n_baseline=n)
    for e in (0.40, 0.60):
        grid[f"E={e}"] = p.with_(spike_eff=e)
    for cap in (0.15, 0.25):
        grid[f"cap={cap}"] = p.with_(spike_giveback_cap=cap)
    for pp in (0.33, 0.50):
        grid[f"P={pp}"] = p.with_(pullback_p=pp)
    grid["regime=insample_median"] = p.with_(regime_mode="insample_median")
    grid["regime=fixed_0.30"] = p.with_(regime_mode="fixed")
    grid["regime=ADX>20"] = p.with_(regime_mode="adx")
    grid["regime_M=40"] = p.with_(regime_er_m=40)
    grid["bucket=percentile"] = p.with_(bucket_mode="percentile")
    grid["timeframe=15min"] = p.with_(timeframe="15min")
    return p, grid


def main():
    p, grid = build_grid()
    print(f"grid: {len(grid)} runs (primary + {len(grid)-1} one-at-a-time variants)", flush=True)

    # caches per timeframe
    print("building caches...", flush=True)
    one5 = load_1min_rth(p.start, p.end)
    caches = {"5min": build_candles(one5, "5min")}
    if any(cfg.timeframe == "15min" for cfg in grid.values()):
        caches["15min"] = build_candles(one5, "15min")
    print(f"  5min candles: {len(caches['5min']):,}  15min: {len(caches['15min']):,}", flush=True)

    runs = {}
    for i, (name, cfg) in enumerate(grid.items(), 1):
        print(f"[{i}/{len(grid)}] {name}", flush=True)
        runs[name] = run_config(caches[cfg.timeframe], cfg)

    prim = runs["primary"]
    tf15 = runs["timeframe=15min"]

    # ── verdicts ──
    c1 = prim["c1_forward_return"]; c1g = prim["c1_giveback"]
    c1_ret_verdict = _verdict(c1["contrast"], c1["ci"], "neg")     # spike underperforms
    c1_give_verdict = _verdict(c1g["contrast"], c1g["ci"], "pos")  # spike gives back MORE
    did = prim["c2_did_chop_minus_trend"]
    c2_verdict = _verdict(did["did"], did["ci"], "neg")            # stronger (more neg) in chop
    c15 = tf15["c1_forward_return"]
    same_sign = (not np.isnan(c1["contrast"]) and not np.isnan(c15["contrast"])
                 and np.sign(c1["contrast"]) == np.sign(c15["contrast"]))
    c3_verdict = ("Supported" if same_sign and c1_ret_verdict != "Inconclusive"
                  else "Refuted" if (not same_sign and not np.isnan(c15["contrast"]))
                  else "Inconclusive")

    # robustness of C1 across the whole grid (sign + significance of the fwd-ret contrast)
    c1_signs = []
    for name, r in runs.items():
        c = r["c1_forward_return"]
        c1_signs.append((name, _verdict(c["contrast"], c["ci"], "neg"), c["contrast"]))
    n_support = sum(1 for _, v, _ in c1_signs if v == "Supported")
    n_refute = sum(1 for _, v, _ in c1_signs if v == "Refuted")
    robust = "robust" if n_support == len(c1_signs) else (
        "fragile" if (n_support and (n_refute or n_support < len(c1_signs))) else "consistent-null")

    out = {
        "window": [p.start, p.end], "primary_config": prim["config"],
        "regime_desc": prim["regime_desc"], "headline_outcome": "fwd_ret_3 (points, signed)",
        "n_grid_runs": len(grid),
        "verdicts": {
            "C1_forward_return": c1_ret_verdict, "C1_giveback": c1_give_verdict,
            "C2_did": c2_verdict, "C3_timeframe": c3_verdict,
            "C1_robustness": robust, "C1_support_count": n_support,
            "C1_refute_count": n_refute, "C1_total_runs": len(c1_signs),
        },
        "primary": prim, "timeframe_15min": tf15,
        "sensitivity": {name: {"config": r["config"],
                               "c1_forward_return": r["c1_forward_return"],
                               "c1_giveback": r["c1_giveback"],
                               "c2_did": r["c2_did_chop_minus_trend"],
                               "bucket_counts": r["bucket_counts"], "n_events": r["n_events"]}
                        for name, r in runs.items()},
    }
    os.makedirs(REPORTS_DATA, exist_ok=True)
    with open(os.path.join(REPORTS_DATA, "WIT-0002-results.json"), "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    _make_png(prim, tf15)
    print("\n=== VERDICTS ===")
    print(json.dumps(out["verdicts"], indent=2))
    print("C1 signs across grid:")
    for name, v, c in c1_signs:
        print(f"  {name:24s} {v:12s} contrast={c:+.4f}")
    return out


def _make_png(prim, tf15):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels, contrasts, los, his = [], [], [], []
    def add(lbl, d):
        labels.append(lbl); contrasts.append(d["contrast"])
        los.append(d["contrast"] - d["ci"][0]); his.append(d["ci"][1] - d["contrast"])
    add("5m pooled", prim["c1_forward_return"])
    add("5m chop", prim["c2_by_regime"]["chop"])
    add("5m trend", prim["c2_by_regime"]["trend"])
    add("15m pooled", tf15["c1_forward_return"])
    add("15m chop", tf15["c2_by_regime"]["chop"])
    add("15m trend", tf15["c2_by_regime"]["trend"])
    x = np.arange(len(labels))
    colors = ["#1f4e79", "#c0504d", "#4f81bd", "#1f4e79", "#c0504d", "#4f81bd"]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(x, contrasts, yerr=[los, his], capsize=5, color=colors, alpha=0.85)
    ax.axhline(0, color="#333", lw=1)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel("Spike − Pullback, forward return +3 (points)")
    ax.set_title("Candle-formation claim (C1): Spike vs Pullback follow-through\n"
                 "signed +3-candle return, 95% day-clustered bootstrap CI")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    os.makedirs(REPORTS, exist_ok=True)
    fig.savefig(os.path.join(REPORTS, "WIT-0002-spike-pullback-contrast.png"), dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    main()

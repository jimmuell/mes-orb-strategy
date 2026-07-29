"""Candle-formation event study (WIT-T-0002, Class B).

Judges a *claim*, not a strategy: do near-monotonic "spike" candles give back /
under-follow-through relative to "pullback" candles that retrace intrabar and
still close big — and is that stronger in chop (C2), and consistent across
timeframes (C3)? **No profitability verdict is produced or implied.**

Design = the approved WIT-P2a design with the P2b amendments:
  A1 regime primary = Kaufman ER(M) split at its TRAILING median (rolling window
     of prior candles only). Sensitivity: in-sample median, fixed ER 0.30, ADX>20.
  A2 headline Spike−Pullback contrasts use a DAY-CLUSTERED bootstrap (resample
     trading days; 10k; seed 42). Per-cell descriptive CIs are iid (labeled).
  A3 sensitivity adds k=3.0 and a percentile-based bucket variant.
  A4 sensitivity varies ONE dimension at a time off the primary config.

Candle + path + forward-outcome columns depend only on the bars, so they are
built once per timeframe and cached; threshold/regime/bucket variants are cheap
re-derivations on the cache.
"""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, replace, field

import numpy as np
import pandas as pd

from backtester.montecarlo.bootstrap import run_bootstrap, _percentile_ci
from backtester.ingest.models import Trade as BtTrade

TICK = 0.25
_ET_RTH_START = dt.time(9, 30)
_ET_RTH_LAST_1MIN = dt.time(15, 59)

# WIT-P4m: 1-min bars now come from the shipped RTH parquet via the shared engine-data resolver
# (env override → api/data), never a _REPO-rooted raw-text path that could not reach the image.
from wit.data_paths import engine_data_path
_NAME_1MIN = "ES_full_1min_rth.parquet"
PARQUET_1MIN = engine_data_path(_NAME_1MIN)   # public: server provenance imports this

HORIZONS = (1, 3, 5, 10)
_SEED = 42
_ITERS = 10_000
_CI = 0.95


@dataclass(frozen=True)
class EventStudyConfig:
    timeframe: str = "5min"           # "5min" | "15min"
    k: float = 1.5                    # body >= k * trailing-median body
    n_baseline: int = 20              # trailing candles for the median-body baseline
    spike_eff: float = 0.50           # spike: efficiency >= this ...
    spike_giveback_cap: float = 0.20  # ... AND retrace_pct <= this
    pullback_p: float = 0.40          # pullback: retrace_pct >= this
    bucket_mode: str = "threshold"    # "threshold" | "percentile" (A3)
    regime_mode: str = "trailing_median"  # trailing_median|insample_median|fixed|adx (A1)
    regime_er_m: int = 20             # Kaufman ER lookback (prior candles)
    regime_trailing_window: int = 390  # trailing window (candles) for the ER median (A1)
    regime_fixed_er: float = 0.30
    regime_adx_len: int = 14
    regime_adx_thresh: float = 20.0
    start: str = "2016-04-11"
    end: str = "2026-04-09"

    def with_(self, **kw) -> "EventStudyConfig":
        return replace(self, **kw)


# ---------------------------------------------------------------------------
# data + candle construction (cached per timeframe)
# ---------------------------------------------------------------------------
def load_1min_rth(start: str, end: str) -> pd.DataFrame:
    # WIT-P4m: the parquet already holds exactly RTH [09:30,15:59], so the RTH filter below is
    # idempotent and the returned frame is identical to the old raw-text path.
    df = pd.read_parquet(engine_data_path(_NAME_1MIN))
    df = df.loc[(df.index >= pd.Timestamp(start)) &
                (df.index <= pd.Timestamp(end) + pd.Timedelta(days=1))]
    t = df.index.time
    return df[(t >= _ET_RTH_START) & (t <= _ET_RTH_LAST_1MIN)]


def _rule_min_sub(timeframe: str) -> tuple[str, int]:
    # 5-min requires all 5 sub-bars; 15-min tolerates 2 missing (>=13/15).
    return ("5min", 5) if timeframe == "5min" else ("15min", 13)


def build_candles(one_min: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Compose TF candles from 1-min sub-bars with path metrics + forward outcomes.

    Path/outcome columns are threshold-independent, so this is the cache the whole
    sensitivity grid reuses.
    """
    from wit.path_metrics import compute_path
    rule, min_sub = _rule_min_sub(timeframe)
    key = one_min.index.floor(rule)
    g = one_min.groupby(key)
    c = g.agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"),
              Close=("Close", "last"), n=("Close", "size"))
    c = c[c["n"] >= min_sub]
    c = c[[x.time() >= _ET_RTH_START for x in c.index]]
    c["day"] = c.index.normalize()
    body = c["Close"] - c["Open"]
    c["body"] = body.abs()
    c["dir"] = np.sign(body).astype(int)

    eff = np.full(len(c), np.nan)
    rpct = np.full(len(c), np.nan)
    rtick = np.full(len(c), np.nan)
    pos = {ts: i for i, ts in enumerate(c.index)}
    for ts, sub in one_min.groupby(key):
        i = pos.get(ts)
        if i is None:
            continue
        pm = compute_path(sub["Open"].iloc[0], sub["Close"].to_numpy(dtype=float), TICK)
        eff[i] = pm.efficiency
        rpct[i] = pm.retrace_pct
        rtick[i] = pm.retrace_ticks
    c["efficiency"] = eff
    c["retrace_pct"] = rpct
    c["retrace_ticks"] = rtick

    _add_forward_outcomes(c)
    return c


def _add_forward_outcomes(c: pd.DataFrame) -> None:
    """Signed forward returns (+1/+3/+5/+10), giveback (+1..+3), P(next against).

    All strictly within the same trading day — a horizon that would cross the
    session close/day boundary is NaN and excluded from that horizon's cell.
    """
    grp = c.groupby("day", sort=False)
    d = c["dir"].to_numpy()
    for h in HORIZONS:
        fwd_close = grp["Close"].shift(-h)
        c[f"fwd_ret_{h}"] = d * (fwd_close - c["Close"])   # points, signed by event dir
    # giveback over +1..+3: adverse excursion from event close as a fraction of body
    fwd_min_low = grp["Low"].shift(-1)
    fwd_max_high = grp["High"].shift(-1)
    for h in (2, 3):
        fwd_min_low = np.minimum(fwd_min_low, grp["Low"].shift(-h))
        fwd_max_high = np.maximum(fwd_max_high, grp["High"].shift(-h))
    body = c["body"].replace(0, np.nan)
    bull = c["dir"] > 0
    give = np.where(bull, (c["Close"] - fwd_min_low), (fwd_max_high - c["Close"]))
    c["giveback"] = np.clip(give / body, 0.0, None)
    # P(next candle closes against the event)
    nxt_open = grp["Open"].shift(-1)
    nxt_close = grp["Close"].shift(-1)
    nxt_dir = np.sign(nxt_close - nxt_open)
    c["next_against"] = (nxt_dir == -c["dir"]).astype(float)
    c.loc[nxt_close.isna(), "next_against"] = np.nan


# ---------------------------------------------------------------------------
# regime (all causal — prior candles only)
# ---------------------------------------------------------------------------
def _kaufman_er(close: pd.Series, m: int) -> pd.Series:
    net = (close - close.shift(m)).abs()
    vol = close.diff().abs().rolling(m).sum()
    return net / vol


def _adx(c: pd.DataFrame, length: int) -> pd.Series:
    up = c["High"].diff()
    dn = -c["Low"].diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([(c["High"] - c["Low"]).abs(),
                    (c["High"] - c["Close"].shift()).abs(),
                    (c["Low"] - c["Close"].shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / length, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=c.index).ewm(alpha=1 / length, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=c.index).ewm(alpha=1 / length, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / length, adjust=False).mean()


def regime_series(c: pd.DataFrame, cfg: EventStudyConfig) -> tuple[pd.Series, str]:
    """Return (regime labels 'chop'/'trend'/NaN, human description of the rule)."""
    if cfg.regime_mode == "adx":
        adx_prior = _adx(c, cfg.regime_adx_len).shift(1)
        lab = np.where(adx_prior > cfg.regime_adx_thresh, "trend", "chop")
        lab = pd.Series(lab, index=c.index).where(adx_prior.notna())
        return lab, f"ADX({cfg.regime_adx_len}) prior candle > {cfg.regime_adx_thresh}"
    er = _kaufman_er(c["Close"], cfg.regime_er_m).shift(1)   # causal
    if cfg.regime_mode == "fixed":
        lab = np.where(er >= cfg.regime_fixed_er, "trend", "chop")
        desc = f"Kaufman ER({cfg.regime_er_m}) prior >= {cfg.regime_fixed_er} (fixed)"
    elif cfg.regime_mode == "insample_median":
        thr = er.median()
        lab = np.where(er >= thr, "trend", "chop")
        desc = f"Kaufman ER({cfg.regime_er_m}), in-sample median split ({thr:.3f})"
    else:  # trailing_median (primary, A1)
        thr = er.rolling(cfg.regime_trailing_window, min_periods=cfg.regime_trailing_window // 2).median()
        lab = np.where(er >= thr, "trend", "chop")
        desc = (f"Kaufman ER({cfg.regime_er_m}), split at its TRAILING median over the "
                f"prior {cfg.regime_trailing_window} candles (rolling, causal)")
    lab = pd.Series(lab, index=c.index).where(er.notna())
    return lab, desc


# ---------------------------------------------------------------------------
# events + buckets
# ---------------------------------------------------------------------------
def event_mask(c: pd.DataFrame, cfg: EventStudyConfig) -> pd.Series:
    baseline = c["body"].rolling(cfg.n_baseline).median().shift(1)   # causal
    return (c["body"] >= cfg.k * baseline) & baseline.notna() & (c["dir"] != 0)


def bucket_series(c: pd.DataFrame, ev: pd.Series, cfg: EventStudyConfig) -> pd.Series:
    from wit.path_metrics import PathMetrics, classify_bucket
    out = pd.Series(index=c.index, dtype=object)
    evc = c[ev]
    if cfg.bucket_mode == "percentile":
        # A3: within-TF quartiles from the in-sample EVENT set (disclosed in-sample —
        # trailing quartiles per candle are impractical/noisy at this event density).
        eff_q75 = evc["efficiency"].quantile(0.75)
        rp_q25 = evc["retrace_pct"].quantile(0.25)
        rp_q75 = evc["retrace_pct"].quantile(0.75)
        pull = evc["retrace_pct"] >= rp_q75
        spike = (~pull) & (evc["efficiency"] >= eff_q75) & (evc["retrace_pct"] <= rp_q25)
        lab = np.where(pull, "pullback", np.where(spike, "spike", "middle"))
        out.loc[evc.index] = lab
        return out
    # threshold mode (primary)
    labels = []
    for eff, rp, body in zip(evc["efficiency"], evc["retrace_pct"], evc["body"]):
        pm = PathMetrics(direction=0, body=float(body), efficiency=float(eff),
                         retrace_price=float("nan"), retrace_ticks=float("nan"),
                         retrace_pct=float(rp))
        labels.append(classify_bucket(pm, spike_eff=cfg.spike_eff,
                                      spike_giveback_cap=cfg.spike_giveback_cap,
                                      pullback_p=cfg.pullback_p))
    out.loc[evc.index] = labels
    return out


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------
def mean_ci_iid(values: np.ndarray) -> tuple[float, float, list[float]]:
    """Per-cell descriptive mean + iid bootstrap CI, reusing run_bootstrap
    (maps each value to a synthetic Trade.pnl; reads expectancy point + CI)."""
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) < 2:
        m = float(v.mean()) if len(v) else float("nan")
        return m, len(v), [float("nan"), float("nan")]
    trades = [BtTrade(trade_id=i + 1, direction="long",
                      entry_time=None, entry_price=0.0, exit_time=None, exit_price=0.0,
                      qty=1, pnl=float(x)) for i, x in enumerate(v)]
    res = run_bootstrap(trades, n_iterations=_ITERS, seed=_SEED, ci_level=_CI)
    return res.expectancy_point, len(v), list(res.expectancy_ci)


def day_clustered_contrast(df: pd.DataFrame, bucket_col: str, val_col: str,
                           group_a: str, group_b: str) -> dict:
    """Spike−Pullback style contrast with a DAY-CLUSTERED percentile bootstrap (A2).

    Resamples trading days with replacement (10k, seed 42) and recomputes
    mean(group_a) − mean(group_b). Fully vectorized via per-day sums/counts.
    """
    sub = df[df[bucket_col].isin([group_a, group_b])][["day", bucket_col, val_col]].dropna()
    a_all = sub[sub[bucket_col] == group_a][val_col]
    b_all = sub[sub[bucket_col] == group_b][val_col]
    n_a, n_b = len(a_all), len(b_all)
    if n_a < 2 or n_b < 2:
        return {"contrast": float("nan"), "ci": [float("nan"), float("nan")],
                "n_a": n_a, "n_b": n_b, "method": "day_clustered"}
    obs = float(a_all.mean() - b_all.mean())
    days = sub["day"].unique()
    D = len(days)
    day_idx = {d: i for i, d in enumerate(days)}
    sum_a = np.zeros(D); cnt_a = np.zeros(D); sum_b = np.zeros(D); cnt_b = np.zeros(D)
    for d, g in sub.groupby("day"):
        i = day_idx[d]
        av = g.loc[g[bucket_col] == group_a, val_col].to_numpy()
        bv = g.loc[g[bucket_col] == group_b, val_col].to_numpy()
        sum_a[i], cnt_a[i] = av.sum(), len(av)
        sum_b[i], cnt_b[i] = bv.sum(), len(bv)
    rng = np.random.default_rng(_SEED)
    pick = rng.integers(0, D, size=(_ITERS, D))
    SA = sum_a[pick].sum(1); NA = cnt_a[pick].sum(1)
    SB = sum_b[pick].sum(1); NB = cnt_b[pick].sum(1)
    ok = (NA > 0) & (NB > 0)
    dist = SA[ok] / NA[ok] - SB[ok] / NB[ok]
    lo, hi = _percentile_ci(dist, _CI)
    return {"contrast": obs, "ci": [lo, hi], "n_a": n_a, "n_b": n_b,
            "method": "day_clustered", "iterations": int(ok.sum()), "seed": _SEED}


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------
# headline outcome for the claim contrasts: signed forward return at +3 candles.
HEADLINE_OUTCOME = "fwd_ret_3"


def run_config(candles: pd.DataFrame, cfg: EventStudyConfig) -> dict:
    """Assemble one study configuration from a cached candle frame.

    Returns per-cell descriptives (iid CIs) + the C1/C2/C3 day-clustered contrasts.
    Does NOT mutate `candles`.
    """
    ev = event_mask(candles, cfg)
    regime, regime_desc = regime_series(candles, cfg)
    buckets = bucket_series(candles, ev, cfg)
    df = candles.copy()
    df["bucket"] = buckets
    df["regime"] = regime
    evdf = df[ev & df["bucket"].notna()].copy()

    # per-cell descriptives (bucket x regime): count + mean forward-return (iid CI)
    cells = {}
    for b in ("spike", "pullback", "middle"):
        for rg in ("chop", "trend"):
            vals = evdf[(evdf["bucket"] == b) & (evdf["regime"] == rg)][HEADLINE_OUTCOME]
            m, n, ci = mean_ci_iid(vals.to_numpy())
            cells[f"{b}|{rg}"] = {"n": n, "mean_fwd_ret_3": m, "ci_iid": ci,
                                  "giveback_mean": float(evdf[(evdf["bucket"] == b) &
                                        (evdf["regime"] == rg)]["giveback"].mean())}

    # C1 — pooled Spike vs Pullback on forward return (day-clustered) + giveback
    c1_ret = day_clustered_contrast(evdf, "bucket", HEADLINE_OUTCOME, "spike", "pullback")
    c1_give = day_clustered_contrast(evdf, "bucket", "giveback", "spike", "pullback")

    # C2 — Spike−Pullback contrast within each regime + DiD (chop − trend)
    c2 = {}
    for rg in ("chop", "trend"):
        sub = evdf[evdf["regime"] == rg]
        c2[rg] = day_clustered_contrast(sub, "bucket", HEADLINE_OUTCOME, "spike", "pullback")
    did = _did_day_clustered(evdf, HEADLINE_OUTCOME)

    # per-horizon pooled contrasts (for the report table)
    horizon_contrasts = {h: day_clustered_contrast(evdf, "bucket", f"fwd_ret_{h}",
                                                    "spike", "pullback") for h in HORIZONS}

    return {
        "config": _cfg_dict(cfg), "regime_desc": regime_desc,
        "n_events": int(len(evdf)),
        "bucket_counts": {b: int((evdf["bucket"] == b).sum())
                          for b in ("spike", "pullback", "middle")},
        "cells": cells,
        "c1_forward_return": c1_ret, "c1_giveback": c1_give,
        "c2_by_regime": c2, "c2_did_chop_minus_trend": did,
        "horizon_contrasts": {str(h): v for h, v in horizon_contrasts.items()},
    }


def _did_day_clustered(evdf: pd.DataFrame, val_col: str) -> dict:
    """Difference-in-differences: (Spike−Pullback)_chop − (Spike−Pullback)_trend,
    day-clustered. Positive-magnitude 'stronger in chop' means MORE NEGATIVE in chop."""
    sub = evdf[evdf["bucket"].isin(["spike", "pullback"])][
        ["day", "bucket", "regime", val_col]].dropna()
    if sub.empty:
        return {"did": float("nan"), "ci": [float("nan"), float("nan")]}

    def cell_sum_cnt(mask):
        s = sub[mask]
        g = s.groupby("day")[val_col].agg(["sum", "count"])
        return g

    days = sub["day"].unique()
    D = len(days); di = {d: i for i, d in enumerate(days)}
    keys = [("spike", "chop"), ("pullback", "chop"), ("spike", "trend"), ("pullback", "trend")]
    S = {k: np.zeros(D) for k in keys}; C = {k: np.zeros(D) for k in keys}
    for (b, rg) in keys:
        g = cell_sum_cnt((sub["bucket"] == b) & (sub["regime"] == rg))
        for d, row in g.iterrows():
            S[(b, rg)][di[d]] = row["sum"]; C[(b, rg)][di[d]] = row["count"]

    def obs_did():
        def mean(b, rg):
            m = (sub["bucket"] == b) & (sub["regime"] == rg)
            return sub[m][val_col].mean()
        return (mean("spike", "chop") - mean("pullback", "chop")) - \
               (mean("spike", "trend") - mean("pullback", "trend"))

    rng = np.random.default_rng(_SEED)
    pick = rng.integers(0, D, size=(_ITERS, D))
    def mm(b, rg):
        return S[(b, rg)][pick].sum(1), C[(b, rg)][pick].sum(1)
    ssc, csc = mm("spike", "chop"); psc, pcc = mm("pullback", "chop")
    sst, cst = mm("spike", "trend"); pst, pct = mm("pullback", "trend")
    ok = (csc > 0) & (pcc > 0) & (cst > 0) & (pct > 0)
    dist = ((ssc[ok] / csc[ok] - psc[ok] / pcc[ok]) - (sst[ok] / cst[ok] - pst[ok] / pct[ok]))
    lo, hi = _percentile_ci(dist, _CI)
    return {"did": float(obs_did()), "ci": [lo, hi], "method": "day_clustered",
            "iterations": int(ok.sum()), "seed": _SEED}


def _cfg_dict(cfg: EventStudyConfig) -> dict:
    return {"timeframe": cfg.timeframe, "k": cfg.k, "n_baseline": cfg.n_baseline,
            "spike_eff": cfg.spike_eff, "spike_giveback_cap": cfg.spike_giveback_cap,
            "pullback_p": cfg.pullback_p, "bucket_mode": cfg.bucket_mode,
            "regime_mode": cfg.regime_mode, "regime_er_m": cfg.regime_er_m,
            "regime_trailing_window": cfg.regime_trailing_window}

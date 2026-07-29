"""VP-ORB strategy runner (WIT-T-0001) — drives the frozen engine unmodified.

Pipeline per RTH trading day:
  1. Build the volume profile over [09:30,09:45) ET (1-min canonical, 5-min for
     the robustness sweep). Skip the day if that window is incomplete.
  2. Direction + entry: the first 5-min bar in [09:45,10:55] (bar-start times;
     the 10:55 bar closes 11:00) whose CLOSE (or whole BODY, sweep) is beyond the
     value area — above VAH → long, below VAL → short. First qualifying break
     only; one trade/day; no re-entry.
  3. Levels: sl = POC ∓ 2 ticks; tp = entry ± 2·|entry−sl| (2R).
  4. Exit resolution (this module, not the engine): walk 5-min bars from the bar
     AFTER entry, honouring gap-through first, then intrabar. same_bar_policy
     decides ties. If nothing hits, force-flat at the day's LAST RTH bar.

Why resolve exits here: the engine's both-touched-in-one-bar heuristic is a
path proxy, not a policy knob. To get deterministic stop-first / target-first
(WIT-T-0001 §J2) WITHOUT touching the engine, we expose ONLY the winning level
on the resolved exit bar — so `_check_tpsl_fill` fills exactly there, at the
engine's own (slippage-adjusted) price, with no ambiguity. Entry fills at the
breakout bar's close via process_orders_on_close (the guru's "enter as the
candle closes"); TP/SL therefore go live from the next bar.
"""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import numpy as np
import pandas as pd

from engine import BacktestConfig, run_backtest_long_short
from wit.config import VPORBConfig, TICK_SIZE
from wit.data_paths import engine_data_path
from wit.volume_profile import build_volume_profile

# WIT-P4m: both market-data files ship at api/data/ and are resolved through the shared
# engine-data resolver (env override → api/data), NEVER a _REPO-rooted path. The 1-min source is
# now the derived, RTH-only parquet (built by tools/build_1min_rth_parquet.py) — it ships in the
# image, unlike the raw LFS text that lived outside api/ and never reached production.
_NAME_5MIN = "ES_full_5min_continuous_UNadjusted.parquet"
_NAME_1MIN = "ES_full_1min_rth.parquet"
PARQUET_5MIN = engine_data_path(_NAME_5MIN)   # import-time resolution (messages / back-compat)
PARQUET_1MIN = engine_data_path(_NAME_1MIN)

_RTH_START = dt.time(9, 30)
_RTH_LAST_START = dt.time(15, 55)   # last RTH 5-min bar start (closes 16:00)


# ---------------------------------------------------------------------------
# Data loading (RTH slices only)
# ---------------------------------------------------------------------------
class EmptyDataWindow(Exception):
    """The resolved test window contains no bars in the dataset (WIT-P4j). Carries the WIT-03 §3.7
    error CODE so the run-job callback surfaces a real code + clean message, never a pandas
    IndexError traceback. DATA_UNAVAILABLE is the exact existing vocabulary code for this."""
    code = "DATA_UNAVAILABLE"

    def __init__(self, start, end, dataset: str):
        self.start, self.end, self.dataset = start, end, dataset
        super().__init__(f"no data in the resolved window {start!r}..{end!r} for dataset "
                         f"{dataset!r} — the window is empty (nothing to backtest)")


class UnsupportedGranularity(Exception):
    """vp_granularity is not a DATA resolution engine v1 can build a profile from (WIT-P4l). Fails
    typed at the TOP of the run, before any data load — never falls through to the 1-min path and
    crashes on an empty placeholder frame. Same error style as EmptyDataWindow; UNSUPPORTED_CONSTRUCT
    is the WIT-03 §3.7 code (an engine-capability limit, not a data-availability gap)."""
    code = "UNSUPPORTED_CONSTRUCT"

    def __init__(self, granularity):
        self.granularity = granularity
        super().__init__(f"vp_granularity {granularity!r} is not supported — engine v1 builds the "
                         f"volume profile from '1min' or '5min' data only")


class EmptyOpeningData(Exception):
    """The 1-min opening frame required for the profile is empty or not timestamped (WIT-P4l). A
    typed data error, never an AttributeError from `.index.normalize()` deep in the daily loop."""
    code = "DATA_UNAVAILABLE"

    def __init__(self, start, end, dataset: str):
        self.start, self.end, self.dataset = start, end, dataset
        super().__init__(f"no usable 1-min opening data in {start!r}..{end!r} for dataset "
                         f"{dataset!r} — empty or non-timestamped frame (cannot build the profile)")


@lru_cache(maxsize=1)
def dataset_date_range() -> tuple[str, str]:
    """The FULL [start, end] date range of the ES 5-min dataset as YYYY-MM-DD strings, read from the
    actual data (never a hardcoded pair) so the v1 default test window self-updates as data extends
    (WIT-P4j). Reads only the parquet index (no data columns); cached once per process."""
    idx = pd.read_parquet(engine_data_path(_NAME_5MIN), columns=[]).index
    return (idx.min().strftime("%Y-%m-%d"), idx.max().strftime("%Y-%m-%d"))


def load_5min(start: str, end: str) -> pd.DataFrame:
    """5-min RTH bars [09:30,15:55] ET, tz-naive index (ET wall-clock)."""
    df = pd.read_parquet(engine_data_path(_NAME_5MIN))
    df = df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end) + pd.Timedelta(days=1))]
    t = df.index.time
    df = df[(t >= _RTH_START) & (t <= _RTH_LAST_START)]
    return df


def load_1min_opening(start: str, end: str, range_start: str, range_end: str) -> pd.DataFrame:
    """1-min bars inside the opening [range_start,range_end) window, all days.

    WIT-P4m: sourced from the shipped RTH parquet (was the raw LFS text). The opening window
    [range_start,range_end) is a strict subset of the parquet's RTH [09:30,15:59] coverage, so the
    same filter yields a frame identical to the old text path (proven in test_shipped_1min_data.py).
    """
    df = pd.read_parquet(engine_data_path(_NAME_1MIN))
    df = df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end) + pd.Timedelta(days=1))]
    t = df.index.time
    rs, re = _parse_hm(range_start), _parse_hm(range_end)
    return df[(t >= rs) & (t < re)]


def _parse_hm(s: str) -> dt.time:
    h, m = s.split(":")
    return dt.time(int(h), int(m))


# ---------------------------------------------------------------------------
# Per-day signal + exit resolution
# ---------------------------------------------------------------------------
@dataclass
class DayPlan:
    date: str
    direction: str
    entry_bar: pd.Timestamp
    entry_price: float
    sl_price: float
    tp_price: float
    poc: float
    vah: float
    val: float
    exit_bar: pd.Timestamp
    exit_reason: str          # "tp" | "sl" | "time"
    exposed_level: str        # "tp_price" | "sl_price" | "" (time exit uses a signal)


def _opening_profile(date: str, five_day: pd.DataFrame, one_min_open: pd.DataFrame,
                     cfg: VPORBConfig):
    """Return (profile, ok) for the day's opening window at the chosen granularity."""
    if cfg.vp_granularity == "5min":
        rs, re = _parse_hm(cfg.range_start), _parse_hm(cfg.range_end)
        t = five_day.index.time
        win = five_day[(t >= rs) & (t < re)]
        if len(win) < cfg.min_opening_bars_5min:
            return None, False
        return build_volume_profile(win, TICK_SIZE, cfg.value_area_pct), True
    # canonical: 1-min
    day_open = one_min_open[one_min_open.index.normalize() == pd.Timestamp(date)]
    if len(day_open) < cfg.min_opening_bars:
        return None, False
    return build_volume_profile(day_open, TICK_SIZE, cfg.value_area_pct), True


def _qualifies(row, direction: str, level: float, mode: str) -> bool:
    if direction == "long":
        return (row.Close > level) if mode == "close" else (min(row.Open, row.Close) > level)
    else:
        return (row.Close < level) if mode == "close" else (max(row.Open, row.Close) < level)


def build_signals_for_day(date: str, five_day: pd.DataFrame, one_min_open: pd.DataFrame,
                          cfg: VPORBConfig) -> Optional[dict]:
    """Compute the day's trade plan, or None if the day is skipped / no break.

    Returns a dict (also the DayPlan fields) so tests can assert on it directly.
    """
    vp, ok = _opening_profile(date, five_day, one_min_open, cfg)
    if not ok or vp is None:
        return None

    ews, ewl = _parse_hm(cfg.entry_window_start), _parse_hm(cfg.entry_window_last_bar)
    t = five_day.index.time
    entry_candidates = five_day[(t >= ews) & (t <= ewl)]

    direction = None
    entry_row = None
    for ts, row in entry_candidates.iterrows():
        if _qualifies(row, "long", vp.vah, cfg.entry_mode):
            direction, entry_row = "long", (ts, row)
            break
        if _qualifies(row, "short", vp.val, cfg.entry_mode):
            direction, entry_row = "short", (ts, row)
            break
    if direction is None:
        return None

    entry_ts, row = entry_row
    entry_price = float(row.Close)
    off = cfg.stop_offset_ticks * TICK_SIZE
    if direction == "long":
        sl = round(vp.poc - off, 10)
        r = entry_price - sl
        tp = round(entry_price + cfg.rr_target * r, 10)
    else:
        sl = round(vp.poc + off, 10)
        r = sl - entry_price
        tp = round(entry_price - cfg.rr_target * r, 10)

    # Degenerate stop (entry on the wrong side of its own stop): skip — not a
    # tradeable setup as taught. Rare but must not create a zero/negative-R trade.
    if r <= 0:
        return None

    exit_ts, reason, exposed = _resolve_exit(five_day, entry_ts, direction, sl, tp, cfg)

    return {
        "date": date, "direction": direction,
        "entry_bar": entry_ts, "entry_price": entry_price,
        "sl_price": sl, "tp_price": tp,
        "poc": vp.poc, "vah": vp.vah, "val": vp.val,
        "exit_bar": exit_ts, "exit_reason": reason, "exposed_level": exposed,
    }


def _resolve_exit(five_day: pd.DataFrame, entry_ts: pd.Timestamp, direction: str,
                  sl: float, tp: float, cfg: VPORBConfig):
    """Walk bars AFTER entry. Gap-through first, then intrabar; ties by policy.

    Returns (exit_ts, reason, exposed_level_col). Time exit → last RTH bar,
    reason 'time', exposed '' (engine exits via a close signal there).
    """
    after = five_day[five_day.index > entry_ts]
    for ts, b in after.iterrows():
        o, h, l = float(b.Open), float(b.High), float(b.Low)
        if direction == "long":
            if o >= tp:                       # gap up through target at open
                return ts, "tp", "tp_price"
            if o <= sl:                       # gap down through stop at open
                return ts, "sl", "sl_price"
            tp_hit, sl_hit = h >= tp, l <= sl
        else:
            if o <= tp:
                return ts, "tp", "tp_price"
            if o >= sl:
                return ts, "sl", "sl_price"
            tp_hit, sl_hit = l <= tp, h >= sl
        if tp_hit and sl_hit:
            if cfg.same_bar_policy == "target_first":
                return ts, "tp", "tp_price"
            return ts, "sl", "sl_price"        # stop_first (primary, conservative)
        if sl_hit:
            return ts, "sl", "sl_price"
        if tp_hit:
            return ts, "tp", "tp_price"
    # nothing hit -> force-flat at the day's last RTH bar
    last_ts = five_day.index[-1]
    return last_ts, "time", ""


# ---------------------------------------------------------------------------
# Full run — assemble columns and drive the engine unmodified
# ---------------------------------------------------------------------------
@dataclass
class RunResult:
    kpis: dict
    trades: list
    df: pd.DataFrame
    plans: list[DayPlan]
    config: VPORBConfig


def run_vp_orb(cfg: VPORBConfig, five: pd.DataFrame | None = None,
               one_min_open: pd.DataFrame | None = None) -> RunResult:
    # WIT-P4l: vp_granularity must be a resolution the runner can build a profile from. Fail typed
    # at the TOP, BEFORE any data load — instead of falling through to the 1-min path with an empty
    # placeholder frame and crashing on `.index.normalize()` (the 'ticks_per_row_1' bug). Both the
    # loader branch below and _opening_profile now handle exactly {"1min","5min"} and nothing else.
    if cfg.vp_granularity not in ("1min", "5min"):
        raise UnsupportedGranularity(cfg.vp_granularity)

    if five is None:
        five = load_5min(cfg.start_date, cfg.end_date)
    if cfg.vp_granularity == "1min":
        if one_min_open is None:
            one_min_open = load_1min_opening(cfg.start_date, cfg.end_date,
                                             cfg.range_start, cfg.range_end)
        # WIT-P4l: the 1-min path indexes by timestamp (`.index.normalize()`); an empty or
        # non-DatetimeIndex frame is a typed data error, never a pandas AttributeError.
        if len(one_min_open) == 0 or not isinstance(one_min_open.index, pd.DatetimeIndex):
            raise EmptyOpeningData(cfg.start_date, cfg.end_date, _NAME_1MIN)
    else:  # "5min" — the 1-min frame is never used; a stable empty placeholder keeps the type
        if one_min_open is None:
            one_min_open = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    # WIT-P4j: an empty 5-min frame (e.g. a window outside the data) must fail with a clean, typed
    # engine error naming the window + dataset — never reach run_backtest_long_short's df.index[0]
    # and crash with a pandas IndexError.
    if len(five) == 0:
        raise EmptyDataWindow(cfg.start_date, cfg.end_date, _NAME_5MIN)

    df = five.copy()
    for c in ("long_entry", "long_exit", "short_entry", "short_exit"):
        df[c] = False
    df["sl_price"] = 0.0
    df["tp_price"] = 0.0

    plans: list[DayPlan] = []
    for date, day in df.groupby(df.index.normalize()):
        dstr = pd.Timestamp(date).strftime("%Y-%m-%d")
        plan = build_signals_for_day(dstr, day, one_min_open, cfg)
        if plan is None:
            continue
        e_ts, x_ts = plan["entry_bar"], plan["exit_bar"]
        ecol = "long_entry" if plan["direction"] == "long" else "short_entry"
        df.at[e_ts, ecol] = True
        if plan["exposed_level"]:                     # tp/sl exit: expose ONLY the winner
            df.at[x_ts, plan["exposed_level"]] = plan[plan["exposed_level"]]
        else:                                         # time exit: close signal at last RTH bar
            xcol = "long_exit" if plan["direction"] == "long" else "short_exit"
            df.at[x_ts, xcol] = True
        plans.append(DayPlan(
            date=dstr, direction=plan["direction"], entry_bar=e_ts,
            entry_price=plan["entry_price"], sl_price=plan["sl_price"],
            tp_price=plan["tp_price"], poc=plan["poc"], vah=plan["vah"], val=plan["val"],
            exit_bar=x_ts, exit_reason=plan["exit_reason"], exposed_level=plan["exposed_level"]))

    bt = BacktestConfig(
        initial_capital=cfg.initial_capital,
        commission_mode="flat_per_rt",
        commission_per_rt=2 * cfg.commission_per_side,   # $/round-trip = 2 sides
        slippage_ticks=cfg.slippage_ticks,
        qty_type="fixed", qty_value=1.0,                 # 1 MES contract
        pyramiding=1,
        start_date=cfg.start_date, end_date=cfg.end_date,
        process_orders_on_close=True,                    # enter/exit-signal at bar close
    )
    kpis = run_backtest_long_short(df, bt)
    return RunResult(kpis=kpis, trades=kpis.get("trades", []), df=df, plans=plans, config=cfg)

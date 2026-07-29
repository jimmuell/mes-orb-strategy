#!/usr/bin/env python3
"""Build the shipped RTH 1-minute parquet from the raw text source of truth (WIT-P4m).

WHY THIS EXISTS
    The engine's two 1-minute consumers — the Class-A volume-profile runner
    (`vp_orb_runner.load_1min_opening`) and the Class-B event study
    (`event_study.load_1min_rth`) — historically read
    `data/raw/ES_full_1min_continuous_UNadjusted.txt`. That path is (a) built from the
    REPO root, which does not exist under Railway's `/api` deploy root, and (b) an
    LFS-stored text file that sits OUTSIDE `api/`, so it never entered the image at all.
    Result: NEITHER compute path could ever run in production (sixth live failure,
    2026-07-29, `FileNotFoundError: '/data/raw/ES_full_1min_continuous_UNadjusted.txt'`).

    This tool derives a deployable parquet — `api/data/ES_full_1min_rth.parquet` — that
    ships inside the image as a REGULAR git blob (like the 5-minute parquet already does;
    `.gitattributes` routes *.txt/*.csv to LFS but not *.parquet). The raw text remains
    the source of truth; the parquet is derived and regenerable by re-running this script.

WHAT IT PRODUCES
    RTH-only bars, [09:30, 15:59] ET inclusive — the exact window both consumers already
    filter to (the opening [09:30,09:45) window used by the VP runner is a strict subset).
    RTH-only, not the full 24h session, keeps the file proportionate to the shipped 5-min
    parquet. Columns, dtypes and timestamp semantics are IDENTICAL to what the current
    text loaders produce (float64 OHLC, int64 Volume, tz-naive DatetimeIndex named
    'timestamp') so results are bit-for-bit identical — proven by the equality test in
    tests/test_shipped_1min_data.py.

DETERMINISTIC & RE-RUNNABLE
    Reads the whole raw file, filters RTH, sorts by timestamp, writes parquet. No sampling,
    no randomness, no timestamps-of-run baked in. Re-running on the same raw input yields a
    byte-stable frame.

RUN
    cd api && .venv/bin/python tools/build_1min_rth_parquet.py
"""
from __future__ import annotations

import datetime as dt
import os

import pandas as pd

# Locations. The builder is a dev/regeneration tool, so reading the raw source of truth
# from the repo root is legitimate here (the runtime RULE — no _REPO-rooted DATA path —
# applies to the server/engine loaders, not to this offline regenerator).
_HERE = os.path.dirname(os.path.abspath(__file__))          # .../api/tools
_API = os.path.dirname(_HERE)                               # .../api
_REPO = os.path.dirname(_API)                               # repo root
RAW_1MIN = os.path.join(_REPO, "data", "raw", "ES_full_1min_continuous_UNadjusted.txt")
OUT_PARQUET = os.path.join(_API, "data", "ES_full_1min_rth.parquet")

# RTH 1-min window — matches event_study._ET_RTH_START / _ET_RTH_LAST_1MIN exactly.
_RTH_START = dt.time(9, 30)
_RTH_LAST = dt.time(15, 59)

_COLS = ["Open", "High", "Low", "Close", "Volume"]


def build() -> pd.DataFrame:
    """Read raw text, filter to RTH, return the frame the parquet is written from."""
    df = pd.read_csv(
        RAW_1MIN, header=None,
        names=["timestamp", *_COLS],
        parse_dates=["timestamp"],
    ).set_index("timestamp")
    # RTH [09:30, 15:59] inclusive — the superset both engine consumers read.
    t = df.index.time
    df = df[(t >= _RTH_START) & (t <= _RTH_LAST)]
    # Deterministic order (raw is chronological already; make it explicit and stable).
    df = df.sort_index()
    return df


def main() -> None:
    if not os.path.isfile(RAW_1MIN) or os.path.getsize(RAW_1MIN) < 1_000_000:
        raise SystemExit(
            f"raw 1-min source missing or looks like an LFS pointer: {RAW_1MIN}\n"
            f"run `git lfs pull` for that path first — do NOT synthesise data.")

    df = build()
    os.makedirs(os.path.dirname(OUT_PARQUET), exist_ok=True)
    df.to_parquet(OUT_PARQUET, engine="pyarrow")   # regular blob; snappy default

    size = os.path.getsize(OUT_PARQUET)
    print(f"wrote {OUT_PARQUET}")
    print(f"  rows:       {len(df):,}")
    print(f"  date range: {df.index.min()} -> {df.index.max()}")
    print(f"  dtypes:     {dict(df.dtypes.astype(str))}")
    print(f"  index:      {type(df.index).__name__} name={df.index.name!r} tz={df.index.tz}")
    print(f"  size:       {size:,} bytes ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()

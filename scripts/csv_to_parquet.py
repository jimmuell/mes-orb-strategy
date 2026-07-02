#!/usr/bin/env python3
"""ADR-035 — convert the full 18-yr ES 5-min CSV to a compact Parquet for the live engine.

Why: the live engine ran OOM loading the full CSV (timestamp parsing + float64 spike).
Parquet ships pre-parsed and downcast, loading lean. Prices are multiples of 0.25 and MES
range stays < ~10k, so float32 represents every OHLC value EXACTLY (to the tick) — verified
by a mandatory round-trip check that falls back to float64 if any value mismatches.

Reads the CSV with the SAME logic as engine `load_firstrate_data` (no header; columns
timestamp,Open,High,Low,Close,Volume; timestamps -> DatetimeIndex).

Usage:  python scripts/csv_to_parquet.py
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

SRC = "data/raw/ES_full_5min_continuous_UNadjusted.txt"
DST = "api/data/ES_full_5min_continuous_UNadjusted.parquet"
_OHLC = ["Open", "High", "Low", "Close"]


def _load_csv(path: str) -> pd.DataFrame:
    """Mirror engine.load_firstrate_data (no-header branch)."""
    df = pd.read_csv(
        path, header=None,
        names=["timestamp", "Open", "High", "Low", "Close", "Volume"],
        parse_dates=["timestamp"],
    )
    df.set_index("timestamp", inplace=True)
    return df


def main() -> None:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(here, SRC)
    dst = os.path.join(here, DST)

    print(f"Reading {SRC} ...")
    csv = _load_csv(src)

    out = csv.copy()
    # Downcast prices to float32; Volume to int32 if integer-valued, else float32.
    for col in _OHLC:
        out[col] = out[col].astype(np.float32)
    vol = csv["Volume"]
    if np.array_equal(vol.to_numpy(), vol.to_numpy().astype(np.int64)):
        out["Volume"] = vol.astype(np.int32)
    else:
        out["Volume"] = vol.astype(np.float32)
        print("  NOTE: non-integer Volume found -> stored Volume as float32.")

    out.to_parquet(dst, engine="pyarrow", compression="snappy", index=True)

    # --- REQUIRED round-trip exactness check (to the tick) ---
    rt = pd.read_parquet(dst, engine="pyarrow")
    mismatch = False
    for col in _OHLC:
        if not np.array_equal(rt[col].to_numpy(dtype=np.float64),
                              csv[col].to_numpy(dtype=np.float64)):
            mismatch = True
            print(f"  ROUND-TRIP MISMATCH in {col} at float32 — falling back to float64.")

    if mismatch:
        out = csv.copy()  # keep prices float64
        vol = csv["Volume"]
        out["Volume"] = (vol.astype(np.int32)
                         if np.array_equal(vol.to_numpy(), vol.to_numpy().astype(np.int64))
                         else vol.astype(np.float32))
        out.to_parquet(dst, engine="pyarrow", compression="snappy", index=True)
        rt = pd.read_parquet(dst, engine="pyarrow")
        for col in _OHLC:
            assert np.array_equal(rt[col].to_numpy(dtype=np.float64),
                                  csv[col].to_numpy(dtype=np.float64)), \
                f"{col} still mismatches at float64 — aborting, do not ship."
        print("  Round-trip EXACT at float64.")
    else:
        print("  Round-trip EXACT at float32 (every OHLC value matches the CSV to the tick).")

    # index + volume integrity
    assert rt.index.equals(csv.index), "index mismatch after round-trip"
    assert np.array_equal(rt["Volume"].to_numpy(dtype=np.float64),
                          csv["Volume"].to_numpy(dtype=np.float64)), "Volume mismatch"

    size_mb = os.path.getsize(dst) / (1024 * 1024)
    print(f"\nWrote {DST}")
    print(f"  size:  {size_mb:.2f} MB")
    print(f"  rows:  {len(rt):,}")
    print(f"  span:  {rt.index[0]} -> {rt.index[-1]}")
    print(f"  dtypes: {dict(rt.dtypes.astype(str))}")


if __name__ == "__main__":
    main()

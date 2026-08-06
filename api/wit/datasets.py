"""Dataset catalog (WIT-P5o) — resolves a dataset id to the PAIR of files it reads.

A dataset is two files, not one: the engine reads a 5-minute continuous file for the trading
bars (it filters regular hours out of that file itself, in code — see vp_orb_runner.load_5min)
and a 1-minute regular-hours file for the opening range only (vp_orb_runner.load_1min_opening).
A catalog entry therefore resolves an id to TWO filenames.

Catalog sources, in order:
  1. The BUILT-IN DEFAULT below — always present, describes the ES pair that runs today.
  2. An OPTIONAL datasets.json in the directory returned by data_paths.resolve_engine_data_dir()
     (the Railway volume in production, api/data in a checkout). An entry whose id equals the
     built-in id OVERRIDES it; every other entry is added.

Failure rules (deliberate — see WIT-P5o):
  - Catalog file ABSENT: the built-in default is the whole catalog. No warning, no error.
  - Catalog file PRESENT but malformed/invalid: a loud DatasetCatalogError naming the file and
    the offending entry or key. NEVER falls back to the built-in — falling back would run ES
    data under some other dataset's declared name, exactly the defect this module removes.
  - An entry whose files are not on disk: the catalog still loads; resolving that id raises
    DatasetFilesMissing. available() simply excludes it.

Not cached across calls (data_paths.resolve_data_root() sets the precedent: re-resolving is a
handful of dict/isdir checks, and staying live keeps env overrides and tests honest).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from wit.data_paths import resolve_engine_data_dir

_CATALOG_FILENAME = "datasets.json"

# WIT-P5q: valid values for bars_granularity — the granularity of a dataset's OWN bars_5min file
# (that field is misnamed from WIT-P5o but stays as-is; renaming it is bigger churn than this
# prompt is scoped for). Deliberately a SEPARATE tuple from mapper.py's _VP_GRANULARITIES — same
# vocabulary, different concept (this describes what a dataset's file actually IS; that one picks
# how the opening profile is built) — no cross-module import for it.
_BARS_GRANULARITIES = ("1min", "5min")

_REQUIRED_KEYS = {"id", "label", "bars_5min", "opening_1min", "symbol", "point_value", "tick_size",
                 "bars_granularity"}
_STRING_KEYS = {"id", "label", "bars_5min", "opening_1min", "symbol", "bars_granularity"}
_NUMERIC_KEYS = {"point_value", "tick_size"}
_FILENAME_KEYS = {"bars_5min", "opening_1min"}


@dataclass(frozen=True)
class DatasetSpec:
    id: str
    label: str
    bars_5min: str
    opening_1min: str
    symbol: str
    point_value: float
    tick_size: float
    bars_granularity: str
    description: str = ""


# Describes exactly the pair running today — see api/data/. Never mutated; an entry in
# datasets.json sharing this id overrides it in the loaded catalog, but this object itself
# always resolves the same way regardless of what any catalog file says.
BUILT_IN_DEFAULT = DatasetSpec(
    id="ES_5min_continuous",
    label="ES continuous futures — 5-min bars (RTH-filtered) + 1-min opening range",
    bars_5min="ES_full_5min_continuous_UNadjusted.parquet",
    opening_1min="ES_full_1min_rth.parquet",
    symbol="MES",
    point_value=5.0,
    tick_size=0.25,
    bars_granularity="5min",   # what it has always actually been (WIT-P5q makes it explicit)
)


class DatasetCatalogError(Exception):
    """datasets.json is present but malformed or fails validation. Names the file and the
    offending entry or key. Never caught anywhere to fall back to the built-in default."""


class UnknownDataset(Exception):
    """resolve() was asked for an id the catalog does not carry. Never falls back to the built-in
    default — a user who asks for one dataset and silently gets another is the worst outcome
    this system can produce."""
    code = "DATA_UNAVAILABLE"

    def __init__(self, dataset_id: str, available_ids: list[str]):
        self.dataset_id = dataset_id
        self.available_ids = available_ids
        super().__init__(
            f"unknown dataset id {dataset_id!r} — available ids: {available_ids}")


class DatasetFilesMissing(Exception):
    """resolve() found the id in the catalog, but one or both of its files are not on disk."""
    code = "DATA_UNAVAILABLE"

    def __init__(self, dataset_id: str, missing: list[str]):
        self.dataset_id = dataset_id
        self.missing = missing
        super().__init__(
            f"dataset {dataset_id!r} is catalogued but its file(s) are missing: {missing}")


def _fail(path: str, msg: str):
    raise DatasetCatalogError(f"{path}: {msg}")


def _validate_entry(entry: object, index: int, path: str) -> DatasetSpec:
    if not isinstance(entry, dict):
        _fail(path, f"datasets[{index}] must be an object, got {type(entry).__name__}")
    missing = _REQUIRED_KEYS - entry.keys()
    if missing:
        _fail(path, f"datasets[{index}] missing required key(s): {sorted(missing)}")
    for key in _STRING_KEYS:
        v = entry[key]
        if not isinstance(v, str) or not v:
            _fail(path, f"datasets[{index}].{key} must be a non-empty string, got {v!r}")
    for key in _NUMERIC_KEYS:
        v = entry[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
            _fail(path, f"datasets[{index}].{key} must be a positive number, got {v!r}")
    for key in _FILENAME_KEYS:
        v = entry[key]
        if os.path.basename(v) != v or not v or ".." in v:
            _fail(path, f"datasets[{index}].{key} must be a plain filename "
                        f"(no path separators, no '..'), got {v!r}")
    if entry["bars_granularity"] not in _BARS_GRANULARITIES:
        _fail(path, f"datasets[{index}].bars_granularity must be one of {_BARS_GRANULARITIES}, "
                    f"got {entry['bars_granularity']!r}")
    description = entry.get("description", "")
    if not isinstance(description, str):
        _fail(path, f"datasets[{index}].description must be a string, got {description!r}")
    return DatasetSpec(
        id=entry["id"], label=entry["label"], bars_5min=entry["bars_5min"],
        opening_1min=entry["opening_1min"], symbol=entry["symbol"],
        point_value=float(entry["point_value"]), tick_size=float(entry["tick_size"]),
        bars_granularity=entry["bars_granularity"],
        description=description,
    )


def _load_catalog() -> dict[str, DatasetSpec]:
    """{id: DatasetSpec} — the built-in default plus any datasets.json entries. An entry whose
    id equals the built-in id OVERRIDES it; everything else is added."""
    catalog = {BUILT_IN_DEFAULT.id: BUILT_IN_DEFAULT}
    path = os.path.join(resolve_engine_data_dir(), _CATALOG_FILENAME)
    if not os.path.isfile(path):
        return catalog

    with open(path) as fh:
        try:
            raw = json.load(fh)
        except json.JSONDecodeError as e:
            _fail(path, f"not valid JSON — {e}")

    if not isinstance(raw, dict) or raw.get("version") != 1:
        _fail(path, 'must be a JSON object with "version": 1')
    datasets = raw.get("datasets")
    if not isinstance(datasets, list):
        _fail(path, '"datasets" must be a list')

    seen_ids: set[str] = set()
    for i, entry in enumerate(datasets):
        spec = _validate_entry(entry, i, path)
        if spec.id in seen_ids:
            _fail(path, f"duplicate dataset id {spec.id!r}")
        seen_ids.add(spec.id)
        catalog[spec.id] = spec   # built-in id -> overridden; any other id -> added
    return catalog


def resolve(dataset_id: str | None) -> DatasetSpec:
    """id -> DatasetSpec. None or "" resolves to the built-in default. An unknown id raises
    UnknownDataset naming the ids that ARE available — never falls back silently. An id that IS
    catalogued but whose files are not on disk raises DatasetFilesMissing."""
    catalog = _load_catalog()
    resolved_id = dataset_id if dataset_id else BUILT_IN_DEFAULT.id
    if resolved_id not in catalog:
        raise UnknownDataset(resolved_id, sorted(catalog.keys()))
    spec = catalog[resolved_id]
    data_dir = resolve_engine_data_dir()
    missing = [f for f in (spec.bars_5min, spec.opening_1min)
              if not os.path.isfile(os.path.join(data_dir, f))]
    if missing:
        raise DatasetFilesMissing(resolved_id, missing)
    return spec


def available() -> list[DatasetSpec]:
    """The specs whose BOTH files exist on disk — the single source of truth a later slice will
    expose over HTTP. No endpoint is added in this prompt."""
    catalog = _load_catalog()
    data_dir = resolve_engine_data_dir()
    return [spec for spec in catalog.values()
           if all(os.path.isfile(os.path.join(data_dir, f))
                  for f in (spec.bars_5min, spec.opening_1min))]

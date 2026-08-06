"""WIT-P5o — dataset catalog: resolves an id to its two files, honoured end to end.

Every test points WIT_ENGINE_DATA_DIR at a tmp_path so real api/data (and any real
datasets.json, which does not exist today) is never touched.

Run:  cd api && BACKTEST_API_KEY=k .venv/bin/python -m pytest tests/test_datasets.py -q
"""
from __future__ import annotations

import json
import os

import pandas as pd
import pytest

from wit import datasets
from wit.config import VPORBConfig, POINT_VALUE, TICK_SIZE
from wit.data_paths import engine_data_path, resolve_engine_data_dir
from wit.vp_orb_runner import (DatasetEconomicsUnsupported, PARQUET_5MIN, PARQUET_1MIN,
                               dataset_date_range, run_vp_orb)


def _write_catalog(data_dir, payload):
    with open(os.path.join(data_dir, "datasets.json"), "w") as fh:
        json.dump(payload, fh)


def _touch(data_dir, name, content=b""):
    with open(os.path.join(data_dir, name), "wb") as fh:
        fh.write(content)


def _symlink_builtin(tmp_path):
    """Symlink the real built-in ES files into tmp_path (called BEFORE WIT_ENGINE_DATA_DIR is
    overridden, so resolve_engine_data_dir() still finds the real api/data). resolve() checks
    file existence for every id, including the built-in one — an isolated tmp catalog dir needs
    these symlinks for the built-in id to resolve successfully at all."""
    real_dir = resolve_engine_data_dir()
    for name in (datasets.BUILT_IN_DEFAULT.bars_5min, datasets.BUILT_IN_DEFAULT.opening_1min):
        os.symlink(os.path.join(real_dir, name), os.path.join(tmp_path, name))


def _entry(**over):
    base = {"id": "OTHER", "label": "Other dataset", "bars_5min": "other_5min.parquet",
           "opening_1min": "other_1min.parquet", "symbol": "MES",
           "point_value": 5.0, "tick_size": 0.25}
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# no catalog file present -> built-in default is the whole catalog
# ---------------------------------------------------------------------------
def test_builtin_default_resolves_with_no_catalog_file(tmp_path, monkeypatch):
    _symlink_builtin(tmp_path)
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    assert datasets.resolve(None) == datasets.BUILT_IN_DEFAULT


def test_builtin_default_resolves_for_empty_string_id(tmp_path, monkeypatch):
    _symlink_builtin(tmp_path)
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    assert datasets.resolve("") == datasets.BUILT_IN_DEFAULT


# ---------------------------------------------------------------------------
# a valid catalog file adds an entry; an entry with the built-in id overrides it
# ---------------------------------------------------------------------------
def test_valid_catalog_adds_an_entry(tmp_path, monkeypatch):
    _symlink_builtin(tmp_path)
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _touch(tmp_path, "other_5min.parquet")
    _touch(tmp_path, "other_1min.parquet")
    _write_catalog(tmp_path, {"version": 1, "datasets": [_entry()]})
    spec = datasets.resolve("OTHER")
    assert spec.id == "OTHER"
    assert spec.bars_5min == "other_5min.parquet"
    assert spec.opening_1min == "other_1min.parquet"
    assert datasets.resolve(None) == datasets.BUILT_IN_DEFAULT   # catalog ADDS, doesn't replace


def test_entry_with_builtin_id_overrides_it(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _touch(tmp_path, "override_5min.parquet")
    _touch(tmp_path, "override_1min.parquet")
    override = _entry(id=datasets.BUILT_IN_DEFAULT.id, bars_5min="override_5min.parquet",
                      opening_1min="override_1min.parquet")
    _write_catalog(tmp_path, {"version": 1, "datasets": [override]})
    spec = datasets.resolve(None)
    assert spec.id == datasets.BUILT_IN_DEFAULT.id
    assert spec.bars_5min == "override_5min.parquet"          # overridden, not the built-in file
    assert spec != datasets.BUILT_IN_DEFAULT


# ---------------------------------------------------------------------------
# malformed catalog -> raises, NEVER falls back to the built-in
# ---------------------------------------------------------------------------
def test_malformed_catalog_bad_version_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _write_catalog(tmp_path, {"version": 2, "datasets": []})
    with pytest.raises(datasets.DatasetCatalogError, match="version"):
        datasets.resolve(None)


def test_malformed_catalog_datasets_not_a_list_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _write_catalog(tmp_path, {"version": 1, "datasets": "not-a-list"})
    with pytest.raises(datasets.DatasetCatalogError, match="datasets"):
        datasets.resolve(None)


def test_malformed_catalog_missing_key_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    bad = _entry()
    del bad["symbol"]
    _write_catalog(tmp_path, {"version": 1, "datasets": [bad]})
    with pytest.raises(datasets.DatasetCatalogError, match="symbol"):
        datasets.resolve(None)


def test_malformed_catalog_wrong_type_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _write_catalog(tmp_path, {"version": 1, "datasets": [_entry(point_value="five")]})
    with pytest.raises(datasets.DatasetCatalogError, match="point_value"):
        datasets.resolve(None)


@pytest.mark.parametrize("point_value", [0, -5.0])
def test_malformed_catalog_nonpositive_point_value_raises(tmp_path, monkeypatch, point_value):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _write_catalog(tmp_path, {"version": 1, "datasets": [_entry(point_value=point_value)]})
    with pytest.raises(datasets.DatasetCatalogError, match="point_value"):
        datasets.resolve(None)


def test_malformed_catalog_nonpositive_tick_size_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _write_catalog(tmp_path, {"version": 1, "datasets": [_entry(tick_size=0)]})
    with pytest.raises(datasets.DatasetCatalogError, match="tick_size"):
        datasets.resolve(None)


def test_malformed_catalog_path_separator_filename_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _write_catalog(tmp_path, {"version": 1, "datasets": [_entry(bars_5min="sub/dir.parquet")]})
    with pytest.raises(datasets.DatasetCatalogError, match="bars_5min"):
        datasets.resolve(None)


def test_malformed_catalog_dotdot_filename_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _write_catalog(tmp_path, {"version": 1, "datasets": [_entry(opening_1min="../escape.parquet")]})
    with pytest.raises(datasets.DatasetCatalogError, match="opening_1min"):
        datasets.resolve(None)


def test_malformed_catalog_duplicate_ids_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _write_catalog(tmp_path, {"version": 1, "datasets": [_entry(), _entry()]})
    with pytest.raises(datasets.DatasetCatalogError, match="duplicate"):
        datasets.resolve(None)


def test_malformed_catalog_never_falls_back_even_for_the_builtin_id(tmp_path, monkeypatch):
    """A malformed catalog raises even when resolving the BUILT-IN id — it must never silently
    fall back and run ES data under whatever name the caller asked for."""
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _write_catalog(tmp_path, {"version": 1, "datasets": [_entry(point_value=-1)]})
    with pytest.raises(datasets.DatasetCatalogError):
        datasets.resolve(datasets.BUILT_IN_DEFAULT.id)


# ---------------------------------------------------------------------------
# unknown id -> raises, names the ids that ARE available
# ---------------------------------------------------------------------------
def test_unknown_id_raises_naming_available_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    with pytest.raises(datasets.UnknownDataset) as exc:
        datasets.resolve("NOT_A_REAL_DATASET")
    assert exc.value.code == "DATA_UNAVAILABLE"
    assert exc.value.dataset_id == "NOT_A_REAL_DATASET"
    assert exc.value.available_ids == [datasets.BUILT_IN_DEFAULT.id]
    assert "NOT_A_REAL_DATASET" in str(exc.value)
    assert datasets.BUILT_IN_DEFAULT.id in str(exc.value)


# ---------------------------------------------------------------------------
# catalogued but files missing -> excluded from available(), raises on resolve
# ---------------------------------------------------------------------------
def test_entry_with_missing_files_excluded_from_available_and_raises_on_resolve(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _write_catalog(tmp_path, {"version": 1, "datasets": [_entry()]})   # no files touched
    ids = {s.id for s in datasets.available()}
    assert "OTHER" not in ids
    with pytest.raises(datasets.DatasetFilesMissing) as exc:
        datasets.resolve("OTHER")
    assert exc.value.code == "DATA_UNAVAILABLE"
    assert exc.value.dataset_id == "OTHER"
    assert set(exc.value.missing) == {"other_5min.parquet", "other_1min.parquet"}


def test_entry_available_once_both_files_present(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _touch(tmp_path, "other_5min.parquet")
    _touch(tmp_path, "other_1min.parquet")
    _write_catalog(tmp_path, {"version": 1, "datasets": [_entry()]})
    ids = {s.id for s in datasets.available()}
    assert "OTHER" in ids


# ---------------------------------------------------------------------------
# economics guard — a dataset whose economics differ is refused, not silently run
# ---------------------------------------------------------------------------
def test_dataset_with_different_economics_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _touch(tmp_path, "other_5min.parquet")
    _touch(tmp_path, "other_1min.parquet")
    _write_catalog(tmp_path, {"version": 1, "datasets": [_entry(point_value=50.0, tick_size=0.1)]})
    cfg = VPORBConfig(dataset="OTHER")
    with pytest.raises(DatasetEconomicsUnsupported) as exc:
        run_vp_orb(cfg)
    assert exc.value.code == "UNSUPPORTED_CONSTRUCT"
    assert exc.value.dataset_id == "OTHER"
    assert exc.value.point_value == 50.0
    assert exc.value.tick_size == 0.1
    assert str(POINT_VALUE) in str(exc.value) and str(TICK_SIZE) in str(exc.value)


def test_dataset_with_matching_economics_is_not_refused_by_the_guard(tmp_path, monkeypatch):
    """Same economics as the baked constants -> the guard itself does not fire. The (empty,
    unreadable) placeholder parquet then fails downstream with a DIFFERENT exception — that
    failure is expected and irrelevant here; only the guard's behaviour is under test."""
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _touch(tmp_path, "other_5min.parquet")
    _touch(tmp_path, "other_1min.parquet")
    _write_catalog(tmp_path, {"version": 1,
                              "datasets": [_entry(point_value=POINT_VALUE, tick_size=TICK_SIZE)]})
    cfg = VPORBConfig(dataset="OTHER")
    with pytest.raises(Exception) as exc:
        run_vp_orb(cfg)
    assert not isinstance(exc.value, DatasetEconomicsUnsupported)


# ---------------------------------------------------------------------------
# dataset_date_range — per-dataset ranges, not one globally cached range
# ---------------------------------------------------------------------------
def _tiny_bars(start: str) -> pd.DataFrame:
    idx = pd.date_range(start, periods=3, freq="5min")
    return pd.DataFrame({"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0, "Volume": 1},
                        index=idx)


def test_dataset_date_range_returns_per_dataset_ranges(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _tiny_bars("2020-01-02").to_parquet(os.path.join(tmp_path, "a_5min.parquet"))
    _tiny_bars("2021-06-01").to_parquet(os.path.join(tmp_path, "b_5min.parquet"))
    _touch(tmp_path, "a_1min.parquet")
    _touch(tmp_path, "b_1min.parquet")
    _write_catalog(tmp_path, {"version": 1, "datasets": [
        _entry(id="RANGE_A", bars_5min="a_5min.parquet", opening_1min="a_1min.parquet"),
        _entry(id="RANGE_B", bars_5min="b_5min.parquet", opening_1min="b_1min.parquet"),
    ]})
    a_range = dataset_date_range("RANGE_A")
    b_range = dataset_date_range("RANGE_B")
    assert a_range == ("2020-01-02", "2020-01-02")
    assert b_range == ("2021-06-01", "2021-06-01")
    assert a_range != b_range                                # different ids -> different ranges
    assert dataset_date_range("RANGE_A") == a_range           # re-call for A still returns A's range


# ---------------------------------------------------------------------------
# a config with no dataset specified behaves identically to today
# ---------------------------------------------------------------------------
def test_config_with_no_dataset_specified_behaves_identically_to_today():
    cfg = VPORBConfig()
    assert cfg.dataset == datasets.BUILT_IN_DEFAULT.id
    spec = datasets.resolve(cfg.dataset)
    assert spec == datasets.BUILT_IN_DEFAULT
    assert engine_data_path(spec.bars_5min) == PARQUET_5MIN
    assert engine_data_path(spec.opening_1min) == PARQUET_1MIN

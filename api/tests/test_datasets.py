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
from wit.vp_orb_runner import (DatasetEconomicsUnsupported, VpGranularityUnsupportedForDataset,
                               PARQUET_5MIN, PARQUET_1MIN, dataset_date_range, load_5min,
                               run_vp_orb)


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
    # WIT-P5q: bars_granularity is now required — defaults to "5min" here (test-fixture change,
    # not a production one; the prompt that added the field expects this).
    base = {"id": "OTHER", "label": "Other dataset", "bars_5min": "other_5min.parquet",
           "opening_1min": "other_1min.parquet", "symbol": "MES",
           "point_value": 5.0, "tick_size": 0.25, "bars_granularity": "5min"}
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


# ---------------------------------------------------------------------------
# WIT-P5q — bars_granularity: required field, validated, drives the RTH cutoff and a new guard
# ---------------------------------------------------------------------------
def test_malformed_catalog_missing_bars_granularity_raises(tmp_path, monkeypatch):
    """Mirrors test_malformed_catalog_missing_key_raises's missing-"symbol" case exactly."""
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    bad = _entry()
    del bad["bars_granularity"]
    _write_catalog(tmp_path, {"version": 1, "datasets": [bad]})
    with pytest.raises(datasets.DatasetCatalogError, match="bars_granularity"):
        datasets.resolve(None)


def test_malformed_catalog_invalid_bars_granularity_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _write_catalog(tmp_path, {"version": 1, "datasets": [_entry(bars_granularity="15min")]})
    with pytest.raises(datasets.DatasetCatalogError, match="bars_granularity"):
        datasets.resolve(None)


def test_builtin_default_bars_granularity_is_5min():
    assert datasets.BUILT_IN_DEFAULT.bars_granularity == "5min"


# ── load_5min's RTH cutoff is derived from the spec, not a bare 5-minute-shaped constant ──
def _one_bar_at(ts: str) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(ts)])
    return pd.DataFrame({"Open": 100.0, "High": 100.0, "Low": 100.0, "Close": 100.0, "Volume": 1},
                        index=idx)


def test_load_5min_cutoff_includes_1559_for_1min_dataset(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _one_bar_at("2024-01-02 15:59:00").to_parquet(os.path.join(tmp_path, "bars.parquet"))
    spec = datasets.DatasetSpec(id="X", label="x", bars_5min="bars.parquet",
                                opening_1min="bars.parquet", symbol="MES",
                                point_value=5.0, tick_size=0.25, bars_granularity="1min")
    out = load_5min("2024-01-02", "2024-01-02", spec)
    assert pd.Timestamp("2024-01-02 15:59:00") in out.index   # NOT dropped


def test_load_5min_cutoff_excludes_1559_for_5min_dataset(tmp_path, monkeypatch):
    """Identical synthetic bar, only bars_granularity differs -> proves the derivation reads
    the spec, not a hardcoded always-15:59 (or always-15:55) cutoff."""
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _one_bar_at("2024-01-02 15:59:00").to_parquet(os.path.join(tmp_path, "bars.parquet"))
    spec = datasets.DatasetSpec(id="X", label="x", bars_5min="bars.parquet",
                                opening_1min="bars.parquet", symbol="MES",
                                point_value=5.0, tick_size=0.25, bars_granularity="5min")
    out = load_5min("2024-01-02", "2024-01-02", spec)
    assert pd.Timestamp("2024-01-02 15:59:00") not in out.index   # dropped — past the 5-min cutoff


# ── the new guard: vp_granularity="5min" has nothing real to build from for a 1-min dataset ──
def test_vp_granularity_5min_refused_for_1min_primary_dataset(tmp_path, monkeypatch):
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _touch(tmp_path, "oneminute_5min.parquet")
    _touch(tmp_path, "oneminute_1min.parquet")
    _write_catalog(tmp_path, {"version": 1, "datasets": [
        _entry(id="ONE_MIN_PRIMARY", bars_5min="oneminute_5min.parquet",
              opening_1min="oneminute_1min.parquet", bars_granularity="1min")]})
    cfg = VPORBConfig(dataset="ONE_MIN_PRIMARY", vp_granularity="5min")
    with pytest.raises(VpGranularityUnsupportedForDataset) as exc:
        run_vp_orb(cfg)
    assert exc.value.code == "UNSUPPORTED_CONSTRUCT"
    assert exc.value.dataset_id == "ONE_MIN_PRIMARY"
    assert exc.value.bars_granularity == "1min"
    assert exc.value.vp_granularity == "5min"


def test_vp_granularity_1min_not_refused_for_1min_primary_dataset(tmp_path, monkeypatch):
    """Same 1-min-primary dataset, vp_granularity='1min' -> the NEW guard does not fire (a
    different failure, e.g. an unreadable placeholder parquet, is fine and expected downstream —
    only the guard's own behaviour is under test)."""
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _touch(tmp_path, "oneminute_5min.parquet")
    _touch(tmp_path, "oneminute_1min.parquet")
    _write_catalog(tmp_path, {"version": 1, "datasets": [
        _entry(id="ONE_MIN_PRIMARY", bars_5min="oneminute_5min.parquet",
              opening_1min="oneminute_1min.parquet", bars_granularity="1min")]})
    cfg = VPORBConfig(dataset="ONE_MIN_PRIMARY", vp_granularity="1min")
    with pytest.raises(Exception) as exc:
        run_vp_orb(cfg)
    assert not isinstance(exc.value, VpGranularityUnsupportedForDataset)


def test_vp_granularity_unaffected_for_synthetic_5min_primary_dataset(tmp_path, monkeypatch):
    """A 5-minute-primary dataset (synthetic) must not trip the new guard at EITHER
    vp_granularity value."""
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _touch(tmp_path, "fivemin_5min.parquet")
    _touch(tmp_path, "fivemin_1min.parquet")
    _write_catalog(tmp_path, {"version": 1, "datasets": [
        _entry(id="FIVE_MIN_PRIMARY", bars_5min="fivemin_5min.parquet",
              opening_1min="fivemin_1min.parquet", bars_granularity="5min")]})
    for vp_g in ("1min", "5min"):
        cfg = VPORBConfig(dataset="FIVE_MIN_PRIMARY", vp_granularity=vp_g)
        with pytest.raises(Exception) as exc:
            run_vp_orb(cfg)   # placeholder files aren't readable parquet -> fails downstream
        assert not isinstance(exc.value, VpGranularityUnsupportedForDataset), vp_g


def test_vp_granularity_5min_unaffected_for_builtin_dataset():
    """The REAL built-in (5-minute-primary) dataset at vp_granularity="5min" — the one thing
    every published sweep (WIT-0001's "vp_5min" cell) already relies on — must not move. A short
    window keeps this fast; no existing test actually executes run_vp_orb this way (test_sweeps.py
    only checks the sweep-grid dataclass, never runs it), so this is new, real-data coverage."""
    cfg = VPORBConfig(vp_granularity="5min", start_date="2024-01-02", end_date="2024-03-28")
    res = run_vp_orb(cfg)
    assert res.kpis["total_trades"] >= 0   # completes; no VpGranularityUnsupportedForDataset


# ── end-to-end proof against the REAL shipped 1-minute file, not only synthetic tmp_path data ──
def test_real_1min_file_as_primary_bars_runs_end_to_end(tmp_path, monkeypatch):
    """api/data/ES_full_1min_rth.parquet ALREADY EXISTS and is already the built-in dataset's own
    opening_1min file — this test points a temporary catalog entry's bars_5min AND opening_1min at
    that same real file with bars_granularity="1min", and proves the wiring (cutoff derivation +
    guard + the ordinary load/run path) works against real data, not only synthetic fixtures."""
    real_dir = resolve_engine_data_dir()
    real_1min = datasets.BUILT_IN_DEFAULT.opening_1min   # "ES_full_1min_rth.parquet"
    os.symlink(os.path.join(real_dir, real_1min), os.path.join(tmp_path, real_1min))
    monkeypatch.setenv("WIT_ENGINE_DATA_DIR", str(tmp_path))
    _write_catalog(tmp_path, {"version": 1, "datasets": [
        {"id": "ES_1min_rth_verify", "label": "1-min RTH as primary bars (verify)",
         "bars_5min": real_1min, "opening_1min": real_1min, "symbol": "MES",
         "point_value": 5.0, "tick_size": 0.25, "bars_granularity": "1min"}]})

    cfg = VPORBConfig(dataset="ES_1min_rth_verify", vp_granularity="1min",
                      start_date="2026-01-01", end_date="2026-04-09")   # short window, keep it fast
    res = run_vp_orb(cfg)
    k = res.kpis
    assert isinstance(k["net_profit"], float)
    assert isinstance(k["total_trades"], int)
    assert k["total_trades"] >= 0
    assert k["actual_start_date"] and k["actual_end_date"]

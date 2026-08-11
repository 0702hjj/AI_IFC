# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""ModelRegistry tests: caching, atomic save roundtrip, per-path locks, LRU."""

from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path

import ifcopenshell
import pytest

from app.config import load_settings
from app.registry import ModelRegistry
from conftest import FIXTURE_IFC

WALL_GUID = "3ZYW59sxj8lei475l7EhLU"


def _make_models(tmp_path: Path, count: int) -> list:
    paths = []
    for i in range(count):
        dst = tmp_path / f"model-{i}.ifc"
        shutil.copy(FIXTURE_IFC, dst)
        paths.append(dst)
    return paths


def _entity_count(path: Path) -> int:
    f = ifcopenshell.open(str(path))
    return len(list(f))


def test_load_caches_by_path(ifc_path: Path) -> None:
    reg = ModelRegistry()
    m1 = reg.load(str(ifc_path))
    m2 = reg.load(str(ifc_path))
    assert isinstance(m1, ifcopenshell.file)
    assert m1 is m2


def test_save_roundtrip(ifc_path: Path) -> None:
    reg = ModelRegistry()
    model = reg.load(str(ifc_path))
    expected = len(list(model))
    reg.save(str(ifc_path))
    assert _entity_count(ifc_path) == expected


def test_save_is_atomic(ifc_path: Path) -> None:
    reg = ModelRegistry()
    reg.load(str(ifc_path))
    reg.save(str(ifc_path))
    assert ifc_path.exists()
    assert not Path(str(ifc_path) + ".tmp").exists()


def test_lock_per_path(ifc_path: Path, tmp_path: Path) -> None:
    reg = ModelRegistry()
    lock_a1 = reg.lock(str(ifc_path))
    lock_a2 = reg.lock(str(ifc_path))
    lock_b = reg.lock(str(tmp_path / "other.ifc"))
    assert isinstance(lock_a1, type(threading.RLock()))
    assert lock_a1 is lock_a2
    assert lock_a1 is not lock_b


def test_save_holds_lock(ifc_path: Path) -> None:
    reg = ModelRegistry()
    reg.load(str(ifc_path))
    acquired = reg.lock(str(ifc_path)).acquire(blocking=False)
    assert acquired
    try:
        done = threading.Event()

        def _save() -> None:
            reg.save(str(ifc_path))
            done.set()

        t = threading.Thread(target=_save)
        t.start()
        assert not done.wait(timeout=0.5)
    finally:
        reg.lock(str(ifc_path)).release()
        t.join(timeout=5)
    assert done.is_set()


def test_unload(ifc_path: Path) -> None:
    reg = ModelRegistry()
    m1 = reg.load(str(ifc_path))
    reg.unload(str(ifc_path))
    m2 = reg.load(str(ifc_path))
    assert m1 is not m2


class TestLruEviction:
    def test_evicts_least_recently_used(self, tmp_path: Path) -> None:
        reg = ModelRegistry(max_models=2)
        p1, p2, p3 = _make_models(tmp_path, 3)
        reg.load(str(p1))
        reg.load(str(p2))
        reg.load(str(p3))
        keys = set(reg._models)
        assert os.path.abspath(str(p1)) not in keys
        assert os.path.abspath(str(p2)) in keys
        assert os.path.abspath(str(p3)) in keys

    def test_load_refreshes_recency(self, tmp_path: Path) -> None:
        reg = ModelRegistry(max_models=2)
        p1, p2, p3 = _make_models(tmp_path, 3)
        reg.load(str(p1))
        reg.load(str(p2))
        reg.load(str(p1))  # touch p1: p2 becomes the oldest
        reg.load(str(p3))
        keys = set(reg._models)
        assert os.path.abspath(str(p2)) not in keys
        assert os.path.abspath(str(p1)) in keys

    def test_evicted_model_reloads_with_saved_content(self, tmp_path: Path) -> None:
        reg = ModelRegistry(max_models=2)
        p1, p2, p3 = _make_models(tmp_path, 3)
        m1 = reg.load(str(p1))
        m1.by_guid(WALL_GUID).Name = "改名"
        reg.save(str(p1))
        reg.load(str(p2))
        reg.load(str(p3))  # evicts p1
        assert os.path.abspath(str(p1)) not in reg._models

        m1b = reg.load(str(p1))
        assert m1b is not m1
        assert m1b.by_guid(WALL_GUID).Name == "改名"

    def test_capacity_never_exceeded(self, tmp_path: Path) -> None:
        reg = ModelRegistry(max_models=3)
        for path in _make_models(tmp_path, 20):
            reg.load(str(path))
            assert len(reg._models) <= 3

    def test_default_capacity_is_eight(self) -> None:
        assert ModelRegistry()._max_models == 8


class TestMaxModelsSetting:
    def test_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EDIT_SERVICE_MAX_MODELS", raising=False)
        assert load_settings().max_models == 8

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDIT_SERVICE_MAX_MODELS", "3")
        assert load_settings().max_models == 3


class TestDiffTimeoutSetting:
    def test_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EDIT_SERVICE_DIFF_TIMEOUT_S", raising=False)
        assert load_settings().diff_timeout_s == 60

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDIT_SERVICE_DIFF_TIMEOUT_S", "3")
        assert load_settings().diff_timeout_s == 3

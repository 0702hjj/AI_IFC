"""ModelRegistry tests: caching, atomic save roundtrip, per-path locks."""

from __future__ import annotations

import os
import threading
from pathlib import Path

import ifcopenshell

from app.registry import ModelRegistry


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
    assert isinstance(lock_a1, type(threading.Lock()))
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

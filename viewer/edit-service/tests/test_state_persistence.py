# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Staging/pending persistence: state survives a simulated service restart.

A "restart" is a brand new app instance (new TestClient against
``create_app()``) pointing at the same ``VIEWER_DATA_DIR``. All persistence
writes are synchronous atomic writes (tmp + os.replace), so no polling is
needed before asserting on files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.design_staging import DesignStaging, StagingRegistry
from app.main import create_app
from app.pending import PendingStore
from conftest import MODEL_ID

WALL_GUID = "3ZYW59sxj8lei475l7EhLU"


def _design(**overrides):
    d = {"meta": {"name": "t"}, "frame": {"storeys": {"1F": 0.0}}, "floors": {}}
    d.update(overrides)
    return d


@pytest.fixture()
def restart(data_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """Return a factory creating a fresh app (simulated restart) on the same data dir."""

    def _make() -> TestClient:
        monkeypatch.setenv("VIEWER_DATA_DIR", str(data_dir))
        return TestClient(create_app())

    return _make


def _staging_file(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "staging.json"


def _pending_file(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "pending.json"


class TestStagingPersistence:
    def test_staging_written_atomically(self, client: TestClient, data_dir: Path) -> None:
        client.put(f"/models/{MODEL_ID}/design", json={"design": _design(a=1)})
        path = _staging_file(data_dir)
        assert path.is_file()
        assert not Path(str(path) + ".tmp").exists()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["history"][0]["a"] == 1
        assert payload["cursor"] == 0

    def test_staging_survives_restart_and_undo_redo_still_works(
        self, restart, data_dir: Path
    ) -> None:
        client = restart()
        client.put(f"/models/{MODEL_ID}/design", json={"design": _design(a=1)})
        client.put(f"/models/{MODEL_ID}/design", json={"design": _design(a=2)})
        client.post(f"/models/{MODEL_ID}/design/undo")

        client2 = restart()
        body = client2.get(f"/models/{MODEL_ID}/design").json()
        assert body["design"]["a"] == 1
        assert body["staged"] == 1
        assert body["canUndo"] is True
        assert body["canRedo"] is True

        r = client2.post(f"/models/{MODEL_ID}/design/undo")
        assert r.status_code == 200
        assert "a" not in r.json()["design"]  # back to base
        r = client2.post(f"/models/{MODEL_ID}/design/redo")
        assert r.json()["design"]["a"] == 1

    def test_base_survives_restart_after_save(self, restart) -> None:
        client = restart()
        client.put(f"/models/{MODEL_ID}/design", json={"design": _design(a=1)})
        client.post(f"/models/{MODEL_ID}/design/save")

        client2 = restart()
        body = client2.get(f"/models/{MODEL_ID}/design").json()
        assert body["staged"] == 0
        assert body["design"]["a"] == 1  # restored base, not empty

    def test_discard_persists(self, restart) -> None:
        client = restart()
        client.put(f"/models/{MODEL_ID}/design", json={"design": _design(a=1)})
        client.post(f"/models/{MODEL_ID}/design/discard")

        client2 = restart()
        assert client2.get(f"/models/{MODEL_ID}/design").json()["staged"] == 0

    def test_registry_roundtrip_without_http(self, tmp_path: Path) -> None:
        reg = StagingRegistry(str(tmp_path))
        st = reg.get(MODEL_ID)
        st.push(_design(a=1))
        st.push(_design(a=2))
        st.undo()

        reg2 = StagingRegistry(str(tmp_path))
        st2 = reg2.get(MODEL_ID)
        assert st2.current()["a"] == 1
        assert st2.staged_count() == 1
        assert st2.can_redo()
        # restored instance keeps persisting
        st2.redo()
        reg3 = StagingRegistry(str(tmp_path))
        assert reg3.get(MODEL_ID).current()["a"] == 2

    def test_corrupt_staging_file_falls_back_to_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "models" / MODEL_ID / "staging.json"
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        st = StagingRegistry(str(tmp_path)).get(MODEL_ID)
        assert st.current() == {}
        assert st.staged_count() == 0


class TestPendingPersistence:
    def test_pending_written_atomically(self, client: TestClient, data_dir: Path) -> None:
        resp = client.put(
            f"/models/{MODEL_ID}/entities/{WALL_GUID}",
            json={"fields": {"Name": "新名字"}},
        )
        assert resp.status_code == 200
        path = _pending_file(data_dir)
        assert path.is_file()
        assert not Path(str(path) + ".tmp").exists()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert [e["id"] for e in payload] == [resp.json()["id"]]

    def test_pending_survives_restart(self, restart) -> None:
        client = restart()
        resp = client.put(
            f"/models/{MODEL_ID}/entities/{WALL_GUID}",
            json={"fields": {"Name": "新名字"}, "author": "ai-agent",
                  "provenance": {"source": "AI"}},
        )
        entry = resp.json()

        client2 = restart()
        pending = client2.get(f"/models/{MODEL_ID}/pending").json()
        assert [e["id"] for e in pending] == [entry["id"]]
        assert pending[0]["changes"] == entry["changes"]
        assert pending[0]["provenance"] == {"source": "AI"}

    def test_commit_clears_persisted_pending(self, restart, data_dir: Path) -> None:
        client = restart()
        client.put(
            f"/models/{MODEL_ID}/entities/{WALL_GUID}",
            json={"fields": {"Name": "新名字"}},
        )
        client.post(f"/models/{MODEL_ID}/commit")
        assert not _pending_file(data_dir).exists()
        assert restart().get(f"/models/{MODEL_ID}/pending").json() == []

    def test_discard_clears_persisted_pending(self, restart, data_dir: Path) -> None:
        client = restart()
        client.put(
            f"/models/{MODEL_ID}/entities/{WALL_GUID}",
            json={"fields": {"Name": "新名字"}},
        )
        client.delete(f"/models/{MODEL_ID}/pending")
        assert not _pending_file(data_dir).exists()
        assert restart().get(f"/models/{MODEL_ID}/pending").json() == []

    def test_store_roundtrip_without_http(self, tmp_path: Path) -> None:
        store = PendingStore(str(tmp_path))
        store.append(MODEL_ID, {"id": "e_1", "guid": "g"})
        store2 = PendingStore(str(tmp_path))
        assert store2.get(MODEL_ID) == [{"id": "e_1", "guid": "g"}]
        store2.set(MODEL_ID, [])
        assert not (tmp_path / "models" / MODEL_ID / "pending.json").exists()
        assert PendingStore(str(tmp_path)).get(MODEL_ID) == []

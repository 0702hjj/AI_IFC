# SPDX-License-Identifier: Apache-2.0
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

from app.main import create_app
from app.pending import PendingStore
from app.script_staging import ScriptStaging, StagingRegistry
from conftest import MODEL_ID


def _script(marker: str) -> str:
    return (
        f'PARAMS = {{"marker": "{marker}"}}\n'
        "\n"
        "def build(params, out_path):\n"
        "    open(out_path, 'w').write('IFC:' + params['marker'])\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    import sys\n"
        "    build(PARAMS, sys.argv[1])\n"
    )


@pytest.fixture()
def restart(data_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """Return a factory creating a fresh app (simulated restart) on the same data dir."""

    def _make() -> TestClient:
        monkeypatch.setenv("VIEWER_DATA_DIR", str(data_dir))
        return TestClient(create_app())

    return _make


def _staging_file(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "script_staging.json"


def _pending_file(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "pending.json"


class TestStagingPersistence:
    def test_staging_written_atomically(self, client: TestClient, data_dir: Path) -> None:
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("a")})
        path = _staging_file(data_dir)
        assert path.is_file()
        assert not Path(str(path) + ".tmp").exists()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert '"marker": "a"' in payload["history"][0]
        assert payload["cursor"] == 0

    def test_staging_survives_restart_and_undo_redo_still_works(
        self, restart, data_dir: Path
    ) -> None:
        client = restart()
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("a")})
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("b")})
        client.post(f"/models/{MODEL_ID}/script/undo")

        client2 = restart()
        body = client2.get(f"/models/{MODEL_ID}/script").json()
        assert '"marker": "a"' in body["script"]
        assert body["staged"] == 1
        assert body["canUndo"] is True
        assert body["canRedo"] is True

        r = client2.post(f"/models/{MODEL_ID}/script/undo")
        assert r.status_code == 200
        assert r.json()["script"] is None  # back to (empty) base
        r = client2.post(f"/models/{MODEL_ID}/script/redo")
        assert '"marker": "a"' in r.json()["script"]

    def test_base_survives_restart_after_save(self, restart) -> None:
        client = restart()
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("a")})
        client.post(f"/models/{MODEL_ID}/script/save")

        client2 = restart()
        body = client2.get(f"/models/{MODEL_ID}/script").json()
        assert body["staged"] == 0
        assert '"marker": "a"' in body["script"]  # restored base, not empty

    def test_discard_persists(self, restart) -> None:
        client = restart()
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("a")})
        client.post(f"/models/{MODEL_ID}/script/discard")

        client2 = restart()
        assert client2.get(f"/models/{MODEL_ID}/script").status_code == 404

    def test_registry_roundtrip_without_http(self, tmp_path: Path) -> None:
        reg = StagingRegistry(str(tmp_path))
        st = reg.get(MODEL_ID)
        st.push("s-a")
        st.push("s-b")
        st.undo()

        reg2 = StagingRegistry(str(tmp_path))
        st2 = reg2.get(MODEL_ID)
        assert st2.current() == "s-a"
        assert st2.staged_count() == 1
        assert st2.can_redo()
        # restored instance keeps persisting
        st2.redo()
        reg3 = StagingRegistry(str(tmp_path))
        assert reg3.get(MODEL_ID).current() == "s-b"

    def test_corrupt_staging_file_falls_back_to_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "models" / MODEL_ID / "script_staging.json"
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        st = StagingRegistry(str(tmp_path)).get(MODEL_ID)
        assert st.current() is None
        assert st.staged_count() == 0


class TestPendingPersistence:
    def test_pending_written_atomically(self, data_dir: Path) -> None:
        store = PendingStore(str(data_dir))
        store.append(MODEL_ID, {"id": "e_1", "guid": "g"})
        path = _pending_file(data_dir)
        assert path.is_file()
        assert not Path(str(path) + ".tmp").exists()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert [e["id"] for e in payload] == ["e_1"]

    def test_pending_survives_restart(self, restart, data_dir: Path) -> None:
        # Legacy pending.json (pre-retirement) stays visible via the
        # surviving read-only endpoint after a restart.
        entry = {
            "id": "e_legacy",
            "guid": "g",
            "changes": [{"field": "Name", "oldValue": "a", "newValue": "b"}],
            "author": "ai-agent",
            "provenance": {"source": "AI"},
            "timestamp": "2026-08-08T00:00:00+00:00",
        }
        path = _pending_file(data_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([entry]), encoding="utf-8")

        client = restart()
        pending = client.get(f"/models/{MODEL_ID}/pending").json()
        assert [e["id"] for e in pending] == ["e_legacy"]
        assert pending[0]["changes"] == entry["changes"]
        assert pending[0]["provenance"] == {"source": "AI"}

    def test_discard_clears_persisted_pending(self, restart, data_dir: Path) -> None:
        PendingStore(str(data_dir)).append(MODEL_ID, {"id": "e_1", "guid": "g"})
        client = restart()
        resp = client.delete(f"/models/{MODEL_ID}/pending")
        assert resp.status_code == 200
        assert resp.json() == {"discarded": 1}
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

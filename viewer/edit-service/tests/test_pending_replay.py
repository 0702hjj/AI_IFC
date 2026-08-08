# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Pending replay after restart / LRU eviction (W-0009).

Pending entries restored from ``pending.json`` carry complete edit
instructions (``changes[].field``/``newValue``, ``action: "delete"``), so a
model re-opened from disk replays them before any further mutation or
commit. Entries that fail to replay are marked ``stale``; commit refuses
stale entries instead of silently snapshotting an unmodified IFC.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.element
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.pending import PendingStore
from app.script_staging import StagingRegistry
from conftest import FIXTURE_IFC, MODEL_ID

WALL_GUID = "3ZYW59sxj8lei475l7EhLU"
OTHER_MODEL_ID = "m_aaaaaaaaaaaaaaaa"


@pytest.fixture()
def restart(data_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """Factory creating a fresh app (simulated restart) on the same data dir."""

    def _make(max_models: int = 8) -> TestClient:
        monkeypatch.setenv("VIEWER_DATA_DIR", str(data_dir))
        monkeypatch.setenv("EDIT_SERVICE_MAX_MODELS", str(max_models))
        return TestClient(create_app())

    return _make


def _pending_file(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "pending.json"


def _latest_snapshot(data_dir: Path) -> ifcopenshell.file:
    versions_dir = data_dir / "models" / MODEL_ID / "versions"
    latest = sorted(versions_dir.glob("v*.ifc"))[-1]
    return ifcopenshell.open(str(latest))


def _put_wall_edit(client: TestClient, name: str = "回放名字") -> dict:
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={
            "fields": {"Name": name},
            "psets": {"Pset_WallCommon": {"FireRating": "90"}},
        },
    )
    assert resp.status_code == 200
    return resp.json()


class TestReplayAfterRestart:
    def test_commit_after_restart_replays_fields_and_psets(self, restart, data_dir: Path) -> None:
        client = restart()
        entry = _put_wall_edit(client)

        client2 = restart()
        resp = client2.post(f"/models/{MODEL_ID}/commit")
        assert resp.status_code == 200
        assert resp.json()["committed"] == 1

        snapshot = _latest_snapshot(data_dir)
        entity = snapshot.by_guid(WALL_GUID)
        assert entity.Name == "回放名字"
        psets = ifcopenshell.util.element.get_psets(entity)
        assert psets["Pset_WallCommon"]["FireRating"] == "90"

        history = client2.get(f"/models/{MODEL_ID}/history").json()
        assert [e["id"] for e in history] == [entry["id"]]

    def test_commit_after_restart_replays_delete(self, restart, data_dir: Path) -> None:
        client = restart()
        resp = client.delete(f"/models/{MODEL_ID}/entities/{WALL_GUID}")
        assert resp.status_code == 200

        client2 = restart()
        resp = client2.post(f"/models/{MODEL_ID}/commit")
        assert resp.status_code == 200

        snapshot = _latest_snapshot(data_dir)
        with pytest.raises(RuntimeError):
            snapshot.by_guid(WALL_GUID)

    def test_pending_visible_after_restart_then_applied_on_next_edit(
        self, restart, data_dir: Path
    ) -> None:
        client = restart()
        _put_wall_edit(client, name="第一次")

        client2 = restart()
        assert len(client2.get(f"/models/{MODEL_ID}/pending").json()) == 1
        # A second edit on the restarted service replays the first one first,
        # so the schema endpoint reflects both.
        _put_wall_edit(client2, name="第二次")
        resp = client2.post(f"/models/{MODEL_ID}/commit")
        assert resp.status_code == 200
        snapshot = _latest_snapshot(data_dir)
        assert snapshot.by_guid(WALL_GUID).Name == "第二次"
        psets = ifcopenshell.util.element.get_psets(snapshot.by_guid(WALL_GUID))
        assert psets["Pset_WallCommon"]["FireRating"] == "90"


class TestReplayOnColdReadPath:
    def test_editable_schema_after_restart_reflects_pending(
        self, restart, data_dir: Path
    ) -> None:
        client = restart()
        _put_wall_edit(client, name="冷启动读路径")

        # First request after the restart is a read-only GET: it must still
        # restore pending.json and replay it onto the freshly opened model.
        client2 = restart()
        resp = client2.get(f"/models/{MODEL_ID}/entities/{WALL_GUID}/editable-schema")
        assert resp.status_code == 200
        body = resp.json()
        fields = {f["name"]: f["value"] for f in body["fields"]}
        assert fields["Name"] == "冷启动读路径"
        psets = {p["name"]: p for p in body["psets"]}
        props = {p["name"]: p["value"] for p in psets["Pset_WallCommon"]["properties"]}
        assert props["FireRating"] == "90"


class TestReplayAfterScriptRun:
    def _stage_copy_fixture_script(self, client: TestClient) -> None:
        script = (
            f"PARAMS = {{'src': {str(FIXTURE_IFC)!r}}}\n"
            "\n"
            "def build(params, out_path):\n"
            "    import shutil\n"
            "    shutil.copyfile(params['src'], out_path)\n"
            "\n"
            'if __name__ == "__main__":\n'
            "    import sys\n"
            "    build(PARAMS, sys.argv[1])\n"
        )
        resp = client.put(f"/models/{MODEL_ID}/script", json={"script": script})
        assert resp.status_code == 200

    def test_script_run_marks_pending_for_replay_on_commit(
        self, restart, data_dir: Path
    ) -> None:
        client = restart()
        entry = _put_wall_edit(client, name="脚本覆盖前的编辑")
        self._stage_copy_fixture_script(client)

        # Script run replaces uploads/{id}.ifc and drops the in-memory model;
        # the pending entry must survive that and replay on commit.
        resp = client.post(f"/models/{MODEL_ID}/script/run")
        assert resp.status_code == 200

        resp = client.post(f"/models/{MODEL_ID}/commit")
        assert resp.status_code == 200
        assert resp.json()["committed"] == 1
        snapshot = _latest_snapshot(data_dir)
        assert snapshot.by_guid(WALL_GUID).Name == "脚本覆盖前的编辑"
        history = client.get(f"/models/{MODEL_ID}/history").json()
        assert [e["id"] for e in history] == [entry["id"]]


class TestReplayAfterLruEviction:
    def test_evicted_model_replays_pending_on_commit(
        self, restart, data_dir: Path
    ) -> None:
        shutil.copy(FIXTURE_IFC, data_dir / "uploads" / f"{OTHER_MODEL_ID}.ifc")
        client = restart(max_models=1)
        _put_wall_edit(client)

        # Loading another model evicts the first (max_models=1), dropping its
        # in-memory edits while pending.json keeps the entry.
        resp = client.get(f"/models/{OTHER_MODEL_ID}/entities/{WALL_GUID}/editable-schema")
        assert resp.status_code == 200

        resp = client.post(f"/models/{MODEL_ID}/commit")
        assert resp.status_code == 200
        snapshot = _latest_snapshot(data_dir)
        assert snapshot.by_guid(WALL_GUID).Name == "回放名字"


class TestStaleEntries:
    def _write_bogus_pending(self, data_dir: Path) -> None:
        path = _pending_file(data_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                [
                    {
                        "id": "e_bogus",
                        "guid": "0$notarealguid0000000000",
                        "changes": [
                            {"field": "Name", "oldValue": "x", "newValue": "y"}
                        ],
                        "author": "test",
                        "provenance": {"source": "UI"},
                        "timestamp": "2026-08-08T00:00:00+00:00",
                    }
                ]
            ),
            encoding="utf-8",
        )

    def test_unreplayable_entry_marked_stale_and_commit_refused(
        self, restart, data_dir: Path
    ) -> None:
        self._write_bogus_pending(data_dir)
        client = restart()
        resp = client.post(f"/models/{MODEL_ID}/commit")
        assert resp.status_code == 409
        assert "stale" in resp.json()["detail"]

        pending = client.get(f"/models/{MODEL_ID}/pending").json()
        assert pending[0]["stale"] is True
        # stale flag is persisted so a further restart still sees it
        assert json.loads(_pending_file(data_dir).read_text(encoding="utf-8"))[0][
            "stale"
        ] is True

    def test_discard_clears_stale_and_commit_works_after(
        self, restart, data_dir: Path
    ) -> None:
        self._write_bogus_pending(data_dir)
        client = restart()
        assert client.post(f"/models/{MODEL_ID}/commit").status_code == 409

        resp = client.delete(f"/models/{MODEL_ID}/pending")
        assert resp.status_code == 200
        assert client.get(f"/models/{MODEL_ID}/pending").json() == []

        _put_wall_edit(client)
        resp = client.post(f"/models/{MODEL_ID}/commit")
        assert resp.status_code == 200
        assert _latest_snapshot(data_dir).by_guid(WALL_GUID).Name == "回放名字"


class TestPendingStoreSmallFixes:
    def test_get_is_a_pure_read(self, tmp_path: Path) -> None:
        store = PendingStore(str(tmp_path))
        store.append(MODEL_ID, {"id": "e_1"})
        store2 = PendingStore(str(tmp_path))
        assert store2.get(MODEL_ID) == [{"id": "e_1"}]
        assert MODEL_ID not in store2._pending  # no memory entry from a pure GET
        store2.append(MODEL_ID, {"id": "e_2"})
        assert [e["id"] for e in store2.get(MODEL_ID)] == ["e_1", "e_2"]

    def test_non_list_pending_json_treated_as_empty(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = tmp_path / "models" / MODEL_ID / "pending.json"
        path.parent.mkdir(parents=True)
        path.write_text('{"not": "a list"}', encoding="utf-8")
        store = PendingStore(str(tmp_path))
        with caplog.at_level(logging.WARNING):
            assert store.get(MODEL_ID) == []
        assert any("pending" in r.message.lower() for r in caplog.records)
        # append must not blow up on the bogus file
        store.append(MODEL_ID, {"id": "e_1"})
        assert store.get(MODEL_ID) == [{"id": "e_1"}]


class TestStagingRegistryEviction:
    def test_staging_map_is_bounded(self, tmp_path: Path) -> None:
        reg = StagingRegistry(str(tmp_path), max_staging=2)
        st_a = reg.get("m_aaaaaaaaaaaaaaaa")
        st_a.push("script-a")
        reg.get("m_bbbbbbbbbbbbbbbb")
        reg.get("m_cccccccccccccccc")
        assert len(reg._staging) == 2
        assert "m_aaaaaaaaaaaaaaaa" not in reg._staging
        # evicted staging is restorable from disk
        restored = reg.get("m_aaaaaaaaaaaaaaaa")
        assert restored.current() == "script-a"

    def test_default_capacity(self) -> None:
        assert StagingRegistry()._max_staging >= 8

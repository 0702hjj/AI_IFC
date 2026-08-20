# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Pending replay flagging after restart / LRU eviction / script run (W-0009).

The pending→commit true-edit chain is retired (410, see
test_edits_retired.py), so replay no longer has an HTTP consumer. What
stays alive — and is pinned here — is the internal bookkeeping: restored or
evicted pending entries are flagged ``needs_replay`` (PendingStore), and
the script-run path (``routes_scripts._run_into_uploads``) restores and
flags entries before dropping the in-memory model.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.pending import PendingStore
from app.script_staging import StagingRegistry
from conftest import FIXTURE_IFC, MODEL_ID

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


def _write_pending_entry(data_dir: Path) -> None:
    path = _pending_file(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {
                    "id": "e_legacy",
                    "guid": "3ZYW59sxj8lei475l7EhLU",
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


def _stage_fixture_script(client: TestClient) -> None:
    """暂存一个沙箱内自建 IFC 的脚本。

    W-0047 挂载收窄后沙箱读不到宿主 fixture 文件（不再整根挂载），
    改为沙箱内用 script_lib 构建；本组用例只关心 run 成功 + 打标。
    """
    script = (
        "import sys\n"
        "\n"
        "import ifcopenshell\n"
        "\n"
        "from script_lib import create_skeleton, write_and_validate\n"
        "\n"
        "PARAMS = {'name': 'pending-replay', 'storeys': {'1F': 0.0}}\n"
        "\n"
        "def build(params, out_path):\n"
        "    model = ifcopenshell.file(schema='IFC4')\n"
        "    create_skeleton(model, name=params['name'], storeys=params['storeys'])\n"
        "    write_and_validate(model, out_path)\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    build(PARAMS, sys.argv[1])\n"
    )
    resp = client.put(f"/models/{MODEL_ID}/script", json={"script": script})
    assert resp.status_code == 200


class TestReplayFlagging:
    def test_restore_from_disk_flags_needs_replay(
        self, restart, data_dir: Path
    ) -> None:
        _write_pending_entry(data_dir)
        client = restart()
        store = client.app.state.pending
        assert not store.needs_replay(MODEL_ID)  # nothing restored yet
        store._ensure(MODEL_ID)
        assert store.needs_replay(MODEL_ID)

    def test_script_run_flags_restored_pending_for_replay(
        self, restart, data_dir: Path
    ) -> None:
        _write_pending_entry(data_dir)
        client = restart()
        _stage_fixture_script(client)

        # Script run replaces uploads/{id}.ifc and drops the in-memory model;
        # the restored pending entry must be flagged needs_replay by the run.
        resp = client.post(f"/models/{MODEL_ID}/script/run")
        assert resp.status_code == 200
        assert client.app.state.pending.needs_replay(MODEL_ID)

    def test_lru_eviction_flags_pending_for_replay(
        self, restart, data_dir: Path
    ) -> None:
        shutil.copy(FIXTURE_IFC, data_dir / "uploads" / f"{OTHER_MODEL_ID}.ifc")
        client = restart(max_models=1)
        app = client.app
        store = app.state.pending
        store.append(MODEL_ID, {"id": "e_1", "guid": "g"})
        assert not store.needs_replay(MODEL_ID)

        # Loading another model evicts the first (max_models=1); the on_evict
        # hook must flag its cached pending entries.
        registry = app.state.registry
        registry.load(str(data_dir / "uploads" / f"{MODEL_ID}.ifc"))
        registry.load(str(data_dir / "uploads" / f"{OTHER_MODEL_ID}.ifc"))
        assert store.needs_replay(MODEL_ID)


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

# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""DELETE /models/{id}/entities/{guid}: pending 流、级联、快照、错误路径。"""

from __future__ import annotations

import json
from pathlib import Path

import ifcopenshell
import ifcopenshell.api.root
import pytest
from fastapi.testclient import TestClient

from conftest import MODEL_ID

WALL_GUID = "3ZYW59sxj8lei475l7EhLU"
WINDOW_GUID = "0tA4DSHd50le6Ov9Yu0I9X"
OPENING_GUID = "2bJiss68D6hvLKV8O1xmqJ"
PROJECT_GUID = "28hypXUBvBefc20SI8kfA$"
STOREY_GUID = "2GNgSHJ5j9BRUjqT$7tE8w"


def _open_disk(data_dir: Path) -> ifcopenshell.file:
    return ifcopenshell.open(str(data_dir / "uploads" / f"{MODEL_ID}.ifc"))


def _history_file(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "edit-history.json"


def test_delete_creates_pending_entry_without_touching_disk(
    client: TestClient, data_dir: Path
) -> None:
    resp = client.delete(f"/models/{MODEL_ID}/entities/{WALL_GUID}")
    assert resp.status_code == 200
    entry = resp.json()
    assert entry["guid"] == WALL_GUID
    assert entry["action"] == "delete"
    assert entry["author"] == "local-user"
    assert entry["provenance"] == {"source": "UI"}
    assert entry["id"].startswith("e_")
    assert entry["changes"] == [
        {"field": "__deleted__", "oldValue": "Wall for Test Example", "newValue": None}
    ]

    assert [e["id"] for e in client.get(f"/models/{MODEL_ID}/pending").json()] == [entry["id"]]
    # 内存中已删除，磁盘未动
    assert _open_disk(data_dir).by_guid(WALL_GUID).Name == "Wall for Test Example"
    registry = client.app.state.registry
    live = registry.load(str(data_dir / "uploads" / f"{MODEL_ID}.ifc"))
    assert len(live.by_type("IfcWall")) == 0


def test_delete_commit_cascades_and_snapshots(client: TestClient, data_dir: Path) -> None:
    client.delete(f"/models/{MODEL_ID}/entities/{WALL_GUID}")
    resp = client.post(f"/models/{MODEL_ID}/commit")
    assert resp.status_code == 200
    assert resp.json()["entries"][0]["action"] == "delete"

    model = _open_disk(data_dir)
    assert len(model.by_type("IfcWall")) == 0
    # 级联：开洞实体、开洞关系、Pset_WallCommon 及其归属关系全部清理
    assert len(model.by_type("IfcOpeningElement")) == 0
    assert len(model.by_type("IfcRelVoidsElement")) == 0
    assert not [p for p in model.by_type("IfcPropertySet") if p.Name == "Pset_WallCommon"]
    for rel in model.by_type("IfcRelDefinesByProperties"):
        assert rel.RelatingPropertyDefinition.Name != "Pset_WallCommon"
    # 空间包含：墙从 storey 的 RelatedElements 中移除，窗仍在
    contained = model.by_type("IfcRelContainedInSpatialStructure")[0]
    assert [e.is_a() for e in contained.RelatedElements] == ["IfcWindow"]
    # 版本快照含删除后模型
    versions = client.get(f"/models/{MODEL_ID}/versions").json()
    assert versions["current"] == "v2"
    snap = ifcopenshell.open(
        str(data_dir / "models" / MODEL_ID / "versions" / "v2.ifc")
    )
    assert len(snap.by_type("IfcWall")) == 0
    history = json.loads(_history_file(data_dir).read_text(encoding="utf-8"))
    assert history[0]["action"] == "delete"


def test_delete_window_keeps_type_storey_and_opening_side(
    client: TestClient, data_dir: Path
) -> None:
    client.delete(f"/models/{MODEL_ID}/entities/{WINDOW_GUID}")
    client.post(f"/models/{MODEL_ID}/commit")
    model = _open_disk(data_dir)
    assert len(model.by_type("IfcWindow")) == 0
    # 类型关联清理但类型本身保留；storey 保留
    assert len(model.by_type("IfcWindowType")) == 1
    assert len(model.by_type("IfcBuildingStorey")) == 1
    assert len(model.by_type("IfcRelDefinesByType")) == 0
    assert not [p for p in model.by_type("IfcPropertySet") if p.Name == "Pset_WindowCommon"]
    assert model.by_guid(WALL_GUID) is not None


def test_delete_refuses_project_and_spatial_structure(client: TestClient) -> None:
    for guid in (PROJECT_GUID, STOREY_GUID):
        resp = client.delete(f"/models/{MODEL_ID}/entities/{guid}")
        assert resp.status_code == 422, guid
    assert client.get(f"/models/{MODEL_ID}/pending").json() == []


def test_delete_unknown_guid_returns_404(client: TestClient) -> None:
    resp = client.delete(f"/models/{MODEL_ID}/entities/no-such-guid")
    assert resp.status_code == 404
    assert client.get(f"/models/{MODEL_ID}/pending").json() == []


def test_delete_missing_model_returns_404(client: TestClient) -> None:
    resp = client.delete("/models/m_ffffffffffffffff/entities/x")
    assert resp.status_code == 404


def test_delete_bad_model_id_returns_422(client: TestClient) -> None:
    resp = client.delete("/models/not_a_valid_id/entities/x")
    assert resp.status_code == 422


def test_delete_accepts_author_and_provenance(client: TestClient) -> None:
    resp = client.request(
        "DELETE",
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"author": "ai-agent", "provenance": {"source": "AI"}},
    )
    assert resp.status_code == 200
    entry = resp.json()
    assert entry["author"] == "ai-agent"
    assert entry["provenance"] == {"source": "AI"}


def test_delete_failure_recovers_model_and_drops_pending(
    client: TestClient, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("remove_product exploded")

    monkeypatch.setattr(ifcopenshell.api.root, "remove_product", boom)

    resp = client.delete(f"/models/{MODEL_ID}/entities/{WALL_GUID}")
    assert resp.status_code == 500
    # 恢复：pending 清空、内存模型从磁盘重载（墙回来了，可继续编辑）
    assert client.get(f"/models/{MODEL_ID}/pending").json() == []
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"Name": "改名"}},
    )
    assert resp.status_code == 200
    assert resp.json()["changes"][0]["oldValue"] == "Wall for Test Example"


def test_deleted_entity_subsequent_ops_return_404(client: TestClient) -> None:
    client.delete(f"/models/{MODEL_ID}/entities/{WALL_GUID}")
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"Name": "x"}},
    )
    assert resp.status_code == 404
    resp = client.get(f"/models/{MODEL_ID}/entities/{WALL_GUID}/editable-schema")
    assert resp.status_code == 404

"""Entity edit endpoint tests: pending/commit two-phase flow, history, error paths."""

from __future__ import annotations

import json
from pathlib import Path

import ifcopenshell
from fastapi.testclient import TestClient

from app.main import create_app
from conftest import MODEL_ID

WALL_GUID = "3ZYW59sxj8lei475l7EhLU"
WALL_NAME = "Wall for Test Example"


def _disk_wall_name(data_dir: Path) -> str:
    model = ifcopenshell.open(str(data_dir / "uploads" / f"{MODEL_ID}.ifc"))
    return model.by_guid(WALL_GUID).Name


def _history_file(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "edit-history.json"


def test_put_fields_creates_pending_without_touching_disk(
    client: TestClient, data_dir: Path
) -> None:
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"Name": "新名字"}},
    )
    assert resp.status_code == 200
    entry = resp.json()
    assert entry["guid"] == WALL_GUID
    assert entry["author"] == "local-user"
    assert entry["provenance"] == {"source": "UI"}
    assert entry["id"].startswith("e_")
    assert entry["changes"] == [
        {"field": "Name", "oldValue": WALL_NAME, "newValue": "新名字"}
    ]

    pending = client.get(f"/models/{MODEL_ID}/pending").json()
    assert [e["id"] for e in pending] == [entry["id"]]
    assert _disk_wall_name(data_dir) == WALL_NAME


def test_commit_persists_to_disk_and_history(client: TestClient, data_dir: Path) -> None:
    client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"Name": "新名字"}, "author": "ai-agent",
              "provenance": {"source": "AI"}},
    )
    resp = client.post(f"/models/{MODEL_ID}/commit")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["committed"] == 1
    assert len(payload["entries"]) == 1
    entry = payload["entries"][0]
    assert entry["operation"] == "update"
    assert entry["changes"][0]["oldValue"] == WALL_NAME
    assert entry["changes"][0]["newValue"] == "新名字"
    assert entry["provenance"] == {"source": "AI"}
    assert entry["author"] == "ai-agent"

    assert _disk_wall_name(data_dir) == "新名字"
    assert client.get(f"/models/{MODEL_ID}/pending").json() == []

    history = json.loads(_history_file(data_dir).read_text(encoding="utf-8"))
    assert history == payload["entries"]
    assert client.get(f"/models/{MODEL_ID}/history").json() == payload["entries"]


def test_psets_edit_existing_property(client: TestClient, data_dir: Path) -> None:
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"psets": {"Pset_WallCommon": {"FireRating": "60"}}},
    )
    assert resp.status_code == 200
    assert resp.json()["changes"] == [
        {"field": "Pset_WallCommon.FireRating", "oldValue": "", "newValue": "60"}
    ]
    client.post(f"/models/{MODEL_ID}/commit")
    model = ifcopenshell.open(str(data_dir / "uploads" / f"{MODEL_ID}.ifc"))
    from ifcopenshell.util.element import get_psets

    assert get_psets(model.by_guid(WALL_GUID))["Pset_WallCommon"]["FireRating"] == "60"


def test_psets_create_missing_pset_old_value_null(client: TestClient, data_dir: Path) -> None:
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"psets": {"Pset_Custom": {"Note": "hello"}}},
    )
    assert resp.status_code == 200
    assert resp.json()["changes"] == [
        {"field": "Pset_Custom.Note", "oldValue": None, "newValue": "hello"}
    ]
    client.post(f"/models/{MODEL_ID}/commit")
    model = ifcopenshell.open(str(data_dir / "uploads" / f"{MODEL_ID}.ifc"))
    from ifcopenshell.util.element import get_psets

    assert get_psets(model.by_guid(WALL_GUID))["Pset_Custom"]["Note"] == "hello"


def test_delete_pending_reverts_to_disk_state(client: TestClient) -> None:
    client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"Name": "改名后丢弃"}},
    )
    resp = client.delete(f"/models/{MODEL_ID}/pending")
    assert resp.status_code == 200
    assert client.get(f"/models/{MODEL_ID}/pending").json() == []
    # 重新 PUT 同字段：oldValue 必须是磁盘上的原值，证明内存已回滚
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"Name": "再次修改"}},
    )
    assert resp.json()["changes"][0]["oldValue"] == WALL_NAME


def test_commit_without_pending_returns_409(client: TestClient) -> None:
    resp = client.post(f"/models/{MODEL_ID}/commit")
    assert resp.status_code == 409


def test_bad_model_id_returns_422(client: TestClient) -> None:
    assert client.get("/models/../etc/pending").status_code in (404, 405, 422)
    assert client.get("/models/not_a_valid_id/pending").status_code == 422
    resp = client.put(
        "/models/not_a_valid_id/entities/x",
        json={"fields": {"Name": "x"}},
    )
    assert resp.status_code == 422


def test_missing_model_returns_404(client: TestClient) -> None:
    resp = client.put(
        "/models/m_ffffffffffffffff/entities/x",
        json={"fields": {"Name": "x"}},
    )
    assert resp.status_code == 404


def test_unknown_guid_returns_404(client: TestClient) -> None:
    resp = client.put(
        f"/models/{MODEL_ID}/entities/no-such-guid",
        json={"fields": {"Name": "x"}},
    )
    assert resp.status_code == 404


def test_unknown_attribute_returns_422_without_side_effects(client: TestClient) -> None:
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"NotAField": "x"}},
    )
    assert resp.status_code == 422
    assert client.get(f"/models/{MODEL_ID}/pending").json() == []


def test_bad_provenance_source_returns_422(client: TestClient) -> None:
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"Name": "x"}, "provenance": {"source": "ROBOT"}},
    )
    assert resp.status_code == 422


def test_empty_fields_and_psets_returns_422(client: TestClient) -> None:
    resp = client.put(f"/models/{MODEL_ID}/entities/{WALL_GUID}", json={})
    assert resp.status_code == 422


def test_multi_field_validation_is_atomic(client: TestClient, data_dir: Path) -> None:
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"Name": "好字段", "NotAField": "坏字段"}},
    )
    assert resp.status_code == 422
    assert client.get(f"/models/{MODEL_ID}/pending").json() == []
    assert _disk_wall_name(data_dir) == WALL_NAME
    # 好字段也未应用：随后的合法 PUT 读到的 oldValue 仍是原值
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"Name": "另一个"}},
    )
    assert resp.json()["changes"][0]["oldValue"] == WALL_NAME


def test_wrong_value_type_returns_422_and_rolls_back(client: TestClient) -> None:
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"Description": "先应用的好字段", "Name": [1, 2]}},
    )
    assert resp.status_code == 422
    assert client.get(f"/models/{MODEL_ID}/pending").json() == []
    # 已应用的字段必须回滚：随后的合法 PUT 读到的 oldValue 仍是原值
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"Description": "另一个"}},
    )
    assert resp.json()["changes"][0]["oldValue"] == "Description of Wall"


def test_history_survives_service_restart(client: TestClient, data_dir: Path) -> None:
    client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"Name": "重启前"}},
    )
    client.post(f"/models/{MODEL_ID}/commit")

    new_client = TestClient(create_app())
    history = new_client.get(f"/models/{MODEL_ID}/history").json()
    assert len(history) == 1
    assert history[0]["changes"][0]["newValue"] == "重启前"
    assert history[0]["operation"] == "update"

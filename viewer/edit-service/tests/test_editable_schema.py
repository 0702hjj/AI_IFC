# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""editable-schema endpoint + schema-aware PUT validation (enum 422)."""

from __future__ import annotations

from pathlib import Path

import ifcopenshell
import pytest
from fastapi.testclient import TestClient

from conftest import MODEL_ID

WALL_GUID = "3ZYW59sxj8lei475l7EhLU"
WALL_NAME = "Wall for Test Example"


def _schema(client: TestClient, guid: str = WALL_GUID) -> dict:
    resp = client.get(f"/models/{MODEL_ID}/entities/{guid}/editable-schema")
    assert resp.status_code == 200
    return resp.json()


def _field(payload: dict, name: str) -> dict:
    for f in payload["fields"]:
        if f["name"] == name:
            return f
    raise AssertionError(f"field {name} not in {payload['fields']}")


def test_schema_returns_typed_direct_fields(client: TestClient) -> None:
    payload = _schema(client)
    assert payload["guid"] == WALL_GUID
    assert payload["ifcType"] == "IfcWall"

    name = _field(payload, "Name")
    assert name["kind"] == "string"
    assert name["value"] == WALL_NAME

    desc = _field(payload, "Description")
    assert desc["kind"] == "string"
    assert desc["value"] == "Description of Wall"


def test_schema_enum_field_lists_legal_values(client: TestClient) -> None:
    pdt = _field(_schema(client), "PredefinedType")
    assert pdt["kind"] == "enum"
    assert pdt["value"] is None
    for v in ("STANDARD", "PARTITIONING", "USERDEFINED", "NOTDEFINED"):
        assert v in pdt["enumValues"]


def test_schema_excludes_globalid_entities_and_aggregates(client: TestClient) -> None:
    names = {f["name"] for f in _schema(client)["fields"]}
    assert "GlobalId" not in names
    assert "OwnerHistory" not in names
    assert "ObjectPlacement" not in names
    assert "Representation" not in names


def test_schema_psets_carry_value_kinds(client: TestClient) -> None:
    psets = {p["name"]: p for p in _schema(client)["psets"]}
    wall_common = psets["Pset_WallCommon"]
    props = {p["name"]: p for p in wall_common["properties"]}
    assert "id" not in props

    assert props["FireRating"] == {"name": "FireRating", "kind": "string", "value": ""}
    assert props["IsExternal"] == {"name": "IsExternal", "kind": "bool", "value": True}
    thermal = props["ThermalTransmittance"]
    assert thermal["kind"] == "float"
    assert thermal["value"] == pytest.approx(0.24)


def test_schema_missing_model_returns_404(client: TestClient) -> None:
    resp = client.get("/models/m_ffffffffffffffff/entities/x/editable-schema")
    assert resp.status_code == 404


def test_schema_unknown_guid_returns_404(client: TestClient) -> None:
    resp = client.get(f"/models/{MODEL_ID}/entities/no-such-guid/editable-schema")
    assert resp.status_code == 404


def test_schema_bad_model_id_returns_422(client: TestClient) -> None:
    resp = client.get("/models/not_a_valid_id/entities/x/editable-schema")
    assert resp.status_code == 422


def test_put_invalid_enum_value_returns_422_without_side_effects(client: TestClient) -> None:
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"PredefinedType": "BOGUS"}},
    )
    assert resp.status_code == 422
    assert client.get(f"/models/{MODEL_ID}/pending").json() == []
    # 模型未破坏：随后的合法 PUT 读到的 oldValue 仍是 None
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"PredefinedType": "PARTITIONING"}},
    )
    assert resp.status_code == 200
    assert resp.json()["changes"] == [
        {"field": "PredefinedType", "oldValue": None, "newValue": "PARTITIONING"}
    ]


def test_put_valid_enum_value_commits_to_disk(client: TestClient, data_dir: Path) -> None:
    client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"PredefinedType": "PARTITIONING"}},
    )
    client.post(f"/models/{MODEL_ID}/commit")
    model = ifcopenshell.open(str(data_dir / "uploads" / f"{MODEL_ID}.ifc"))
    assert model.by_guid(WALL_GUID).PredefinedType == "PARTITIONING"


def test_put_mixed_valid_and_invalid_enum_is_atomic(client: TestClient) -> None:
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"Name": "不应残留", "PredefinedType": "BOGUS"}},
    )
    assert resp.status_code == 422
    assert client.get(f"/models/{MODEL_ID}/pending").json() == []
    resp = client.put(
        f"/models/{MODEL_ID}/entities/{WALL_GUID}",
        json={"fields": {"Name": "另一个"}},
    )
    assert resp.json()["changes"][0]["oldValue"] == WALL_NAME

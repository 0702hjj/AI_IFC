# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""User-edit parsing endpoints: upload diff + USER-annotated change log append."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import ifcopenshell
import ifcopenshell.api.root
import pytest
from fastapi.testclient import TestClient

from conftest import FIXTURE_IFC, MODEL_ID

WALL_GUID = "3ZYW59sxj8lei475l7EhLU"
WALL_NAME = "Wall for Test Example"


@pytest.fixture()
def modified_ifc(tmp_path: Path) -> Path:
    """The fixture IFC as modified by a user externally: wall renamed, window removed."""
    dst = tmp_path / "modified.ifc"
    shutil.copy(FIXTURE_IFC, dst)
    model = ifcopenshell.open(str(dst))
    model.by_guid(WALL_GUID).Name = "用户改的墙"
    window = next(iter(model.by_type("IfcWindow")), None)
    assert window is not None
    window_guid = window.GlobalId
    ifcopenshell.api.root.remove_product(model, product=window)
    model.write(str(dst))
    return dst, window_guid


def _post_upload(client: TestClient, path: Path, model_id: str = MODEL_ID):
    return client.post(
        f"/models/{model_id}/diff/upload",
        files={"file": (path.name, path.read_bytes(), "application/octet-stream")},
    )


def test_diff_upload_detects_user_changes_with_labels(
    client: TestClient, modified_ifc
) -> None:
    path, window_guid = modified_ifc
    resp = _post_upload(client, path)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["base"] == "current"
    assert payload["target"] == "upload"
    changed = {c["guid"]: c for c in payload["changed"]}
    assert WALL_GUID in changed
    rename = next(c for c in changed[WALL_GUID]["changes"] if c["field"] == "Name")
    assert rename["old"] == WALL_NAME
    assert rename["new"] == "用户改的墙"
    assert window_guid in payload["removed"]
    labels = payload["labels"]
    assert labels[WALL_GUID] == {"name": "用户改的墙", "type": "IfcWall"}
    assert labels[window_guid]["type"] == "IfcWindow"


def test_diff_upload_identical_file_is_empty(client: TestClient) -> None:
    resp = _post_upload(client, FIXTURE_IFC)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["added"] == [] and payload["removed"] == []
    assert payload["changed"] == []


def test_diff_upload_model_not_found(client: TestClient, tmp_path: Path) -> None:
    resp = _post_upload(client, FIXTURE_IFC, model_id="m_0000000000000000")
    assert resp.status_code == 404


def test_diff_upload_invalid_ifc_returns_422(client: TestClient, tmp_path: Path) -> None:
    bad = tmp_path / "bad.ifc"
    bad.write_bytes(b"this is not an IFC file")
    resp = _post_upload(client, bad)
    assert resp.status_code == 422


def test_user_edits_appends_user_annotated_events(client: TestClient) -> None:
    body = {
        "origin": "ifc-upload",
        "author": "designer-1",
        "events": [
            {
                "guid": WALL_GUID,
                "name": "用户改的墙",
                "kind": "modified",
                "changes": [
                    {"field": "Name", "oldValue": WALL_NAME, "newValue": "用户改的墙"}
                ],
            },
            {"guid": "0v8Kfaaaaaaaaaaaaaaaaa", "name": "", "kind": "removed", "changes": []},
        ],
    }
    resp = client.post(f"/models/{MODEL_ID}/user-edits", json=body)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["appended"] == 2
    entry = payload["entries"][0]
    assert entry["guid"] == WALL_GUID
    assert entry["name"] == "用户改的墙"
    assert entry["kind"] == "modified"
    assert entry["provenance"] == {"source": "USER", "origin": "ifc-upload"}
    assert entry["operation"] == "upload"
    assert entry["author"] == "designer-1"
    assert entry["changes"][0]["newValue"] == "用户改的墙"
    assert entry["id"].startswith("e_") and entry["timestamp"]

    history = client.get(f"/models/{MODEL_ID}/history").json()
    assert history == payload["entries"]


def test_user_edits_dxf_origin(client: TestClient) -> None:
    body = {
        "origin": "dxf-upload",
        "events": [
            {
                "guid": "dxf:WALLS/LINE/1F",
                "name": "layer WALLS",
                "kind": "modified",
                "changes": [{"field": "entityCount", "oldValue": 3, "newValue": 5}],
            }
        ],
    }
    resp = client.post(f"/models/{MODEL_ID}/user-edits", json=body)
    assert resp.status_code == 200
    entry = resp.json()["entries"][0]
    assert entry["provenance"] == {"source": "USER", "origin": "dxf-upload"}


def test_user_edits_empty_events_returns_422(client: TestClient) -> None:
    resp = client.post(
        f"/models/{MODEL_ID}/user-edits",
        json={"origin": "ifc-upload", "events": []},
    )
    assert resp.status_code == 422


def test_user_edits_bad_origin_returns_422(client: TestClient) -> None:
    resp = client.post(
        f"/models/{MODEL_ID}/user-edits",
        json={"origin": "telemetry",
              "events": [{"guid": "g", "kind": "modified", "changes": []}]},
    )
    assert resp.status_code == 422


def test_user_edits_model_not_found(client: TestClient) -> None:
    resp = client.post(
        "/models/m_0000000000000000/user-edits",
        json={"origin": "ifc-upload",
              "events": [{"guid": "g", "kind": "modified", "changes": []}]},
    )
    assert resp.status_code == 404

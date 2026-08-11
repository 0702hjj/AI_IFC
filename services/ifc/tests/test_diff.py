# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Version snapshot + diff endpoint tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import ifcopenshell
import ifcopenshell.api.root
from fastapi.testclient import TestClient

from conftest import MODEL_ID

WALL_GUID = "3ZYW59sxj8lei475l7EhLU"
WALL_NAME = "Wall for Test Example"


def _versions_dir(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "versions"


def _write_rename_versions(data_dir: Path, name: str, *, update_current: bool = False) -> None:
    """Write v1 = original upload, v2 = wall renamed (snapshots written directly).

    The commit endpoint is retired (410); version fixtures are written to
    ``versions/`` by hand instead.
    """
    versions = _versions_dir(data_dir)
    versions.mkdir(parents=True, exist_ok=True)
    uploads = data_dir / "uploads" / f"{MODEL_ID}.ifc"
    shutil.copy(uploads, versions / "v1.ifc")
    model = ifcopenshell.open(str(uploads))
    model.by_guid(WALL_GUID).Name = name
    model.write(str(versions / "v2.ifc"))
    if update_current:
        model.write(str(uploads))


def test_get_versions_lists_snapshots_and_current(client: TestClient, data_dir: Path) -> None:
    resp = client.get(f"/models/{MODEL_ID}/versions")
    assert resp.status_code == 200
    assert resp.json() == {"versions": [], "current": None}

    _write_rename_versions(data_dir, "新名字")
    payload = client.get(f"/models/{MODEL_ID}/versions").json()
    assert [v["version"] for v in payload["versions"]] == ["v1", "v2"]
    assert payload["current"] == "v2"
    assert all(v["createdAt"] for v in payload["versions"])


def test_get_versions_missing_model_returns_404(client: TestClient) -> None:
    assert client.get("/models/m_ffffffffffffffff/versions").status_code == 404


def test_diff_attribute_change(client: TestClient, data_dir: Path) -> None:
    _write_rename_versions(data_dir, "新名字")
    resp = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["base"] == "v1"
    assert payload["target"] == "v2"
    assert payload["added"] == []
    assert payload["removed"] == []
    changed = {c["guid"]: c["changes"] for c in payload["changed"]}
    assert WALL_GUID in changed
    assert {c["field"] for c in changed[WALL_GUID]} == {"Name"}
    assert changed[WALL_GUID] == [
        {"field": "Name", "old": WALL_NAME, "new": "新名字"}
    ]


def _write_versions_with_added_and_removed(data_dir: Path) -> tuple[str, str]:
    """v1 = original + extra wall; v2 = original + different extra wall."""
    versions = _versions_dir(data_dir)
    versions.mkdir(parents=True)
    uploads = data_dir / "uploads" / f"{MODEL_ID}.ifc"

    model = ifcopenshell.open(str(uploads))
    wall_v1 = ifcopenshell.api.root.create_entity(
        model, ifc_class="IfcWall", name="Only in v1"
    )
    model.write(str(versions / "v1.ifc"))

    model = ifcopenshell.open(str(uploads))
    wall_v2 = ifcopenshell.api.root.create_entity(
        model, ifc_class="IfcWall", name="Only in v2"
    )
    model.write(str(versions / "v2.ifc"))
    return wall_v1.GlobalId, wall_v2.GlobalId


def test_diff_added_and_removed_by_guid(client: TestClient, data_dir: Path) -> None:
    removed_guid, added_guid = _write_versions_with_added_and_removed(data_dir)
    resp = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["added"] == [added_guid]
    assert payload["removed"] == [removed_guid]


def test_diff_excludes_geometry_noise(client: TestClient, data_dir: Path) -> None:
    _write_rename_versions(data_dir, "新名字")
    payload = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
    ).json()
    for entry in payload["changed"]:
        for change in entry["changes"]:
            assert "Representation" not in change["field"]
            assert "Geometry" not in change["field"]
            assert "ObjectPlacement" not in change["field"]


def test_diff_target_current_and_no_cache(client: TestClient, data_dir: Path) -> None:
    _write_rename_versions(data_dir, "新名字", update_current=True)
    resp = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "current"}
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["target"] == "current"
    assert WALL_GUID in {c["guid"] for c in payload["changed"]}
    assert not (_versions_dir(data_dir) / "diff-v1-current.json").exists()


def test_diff_result_cached(client: TestClient, data_dir: Path) -> None:
    _write_rename_versions(data_dir, "新名字")
    first = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
    ).json()
    cache_file = _versions_dir(data_dir) / "diff-v1-v2.json"
    assert cache_file.is_file()
    assert json.loads(cache_file.read_text(encoding="utf-8")) == first

    cached = json.loads(cache_file.read_text(encoding="utf-8"))
    cached["added"] = ["sentinel-from-cache"]
    cache_file.write_text(json.dumps(cached), encoding="utf-8")
    second = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
    ).json()
    assert second["added"] == ["sentinel-from-cache"]
    assert second["changed"] == first["changed"]


def test_diff_unknown_version_returns_404(client: TestClient, data_dir: Path) -> None:
    _write_rename_versions(data_dir, "新名字")
    for body in ({"base": "v9", "target": "v2"}, {"base": "v1", "target": "v9"}):
        resp = client.post(f"/models/{MODEL_ID}/diff", json=body)
        assert resp.status_code == 404, body


def test_diff_without_any_commit_returns_404(client: TestClient) -> None:
    resp = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "current"}
    )
    assert resp.status_code == 404


def test_diff_missing_params_returns_422(client: TestClient) -> None:
    assert client.post(f"/models/{MODEL_ID}/diff", json={}).status_code == 422
    assert (
        client.post(f"/models/{MODEL_ID}/diff", json={"base": "v1"}).status_code
        == 422
    )


def test_diff_bad_model_id_returns_422(client: TestClient) -> None:
    assert (
        client.post("/models/not_a_valid_id/diff", json={"base": "v1", "target": "v2"}).status_code
        == 422
    )
    assert client.get("/models/not_a_valid_id/versions").status_code == 422


def test_diff_missing_model_returns_404(client: TestClient) -> None:
    resp = client.post(
        "/models/m_ffffffffffffffff/diff", json={"base": "v1", "target": "v2"}
    )
    assert resp.status_code == 404

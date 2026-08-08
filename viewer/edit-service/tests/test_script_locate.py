# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Locate 端点：GET /models/{id}/script/locate?guid=... — guid → designKey → CallSite。

消费 Task 2 的 ``models/{id}/current.map.json`` 与 uploads IFC 里的
``Pset_AIIFC.designKey``：

- 命中：200 {"found": true, "designKey", "line", "col", "snippet", "origin"}
- 构件存在但无 designKey → 200 {"found": false}
- 有 designKey 但 map 缺失/无该 key → 200 {"found": false, "designKey"}
- guid 不在模型 → 404；模型不存在 → 404
"""

from __future__ import annotations

from pathlib import Path

import ifcopenshell
from fastapi.testclient import TestClient

from tests.conftest import MODEL_ID

LITERAL_KEY_SCRIPT = '''\
import sys

import ifcopenshell

from script_lib import attach_design_key, create_entity, create_skeleton, write_and_validate

PARAMS = {{"key": "{key}"}}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    body, _ = create_skeleton(model)
    w = create_entity(model, "IfcWall", key="s1:wall:1", name="W1")
    attach_design_key(model, w, "s1:wall:1")
    write_and_validate(model, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''

PARAMS_KEY_SCRIPT = '''\
import sys

import ifcopenshell

from script_lib import attach_design_key, create_entity, create_skeleton, write_and_validate

PARAMS = {{"key": "{key}"}}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    body, _ = create_skeleton(model)
    w = create_entity(model, "IfcWall", key=params["key"], name="W1")
    attach_design_key(model, w, params["key"])
    write_and_validate(model, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''


def _uploads_ifc(data_dir: Path) -> Path:
    return data_dir / "uploads" / f"{MODEL_ID}.ifc"


def _save_script(client: TestClient, script: str) -> None:
    client.put(f"/models/{MODEL_ID}/script", json={"script": script})
    r = client.post(f"/models/{MODEL_ID}/script/save", json={})
    assert r.status_code == 200, r.text


def _wall_guid(data_dir: Path) -> str:
    model = ifcopenshell.open(str(_uploads_ifc(data_dir)))
    return model.by_type("IfcWall")[0].GlobalId


def _locate(client: TestClient, guid: str, model_id: str = MODEL_ID):
    return client.get(f"/models/{model_id}/script/locate", params={"guid": guid})


class TestLocateHit:
    def test_locate_hit_literal_origin(
        self, client: TestClient, data_dir: Path
    ):
        _save_script(client, LITERAL_KEY_SCRIPT.format(key="s1:wall:1"))
        guid = _wall_guid(data_dir)

        r = _locate(client, guid)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["found"] is True
        assert body["designKey"] == "s1:wall:1"
        assert body["origin"] == "literal"
        assert body["line"] > 0
        assert body["col"] >= 0
        assert "create_entity" in body["snippet"]

    def test_locate_hit_params_origin(self, client: TestClient, data_dir: Path):
        _save_script(client, PARAMS_KEY_SCRIPT.format(key="s1:wall:2"))
        guid = _wall_guid(data_dir)

        body = _locate(client, guid).json()
        assert body["found"] is True
        assert body["designKey"] == "s1:wall:2"
        assert body["origin"] == "params"

    def test_locate_after_run_without_save(
        self, client: TestClient, data_dir: Path
    ):
        """run（不落版本）也发布 current.map.json，locate 同样命中。"""
        client.put(
            f"/models/{MODEL_ID}/script",
            json={"script": LITERAL_KEY_SCRIPT.format(key="s1:wall:1")},
        )
        r = client.post(f"/models/{MODEL_ID}/script/run")
        assert r.status_code == 200, r.text

        body = _locate(client, _wall_guid(data_dir)).json()
        assert body["found"] is True
        assert body["designKey"] == "s1:wall:1"


class TestLocateMiss:
    def test_locate_unknown_guid_404(self, client: TestClient, data_dir: Path):
        r = _locate(client, "0" * 22)
        assert r.status_code == 404

    def test_locate_unknown_model_404(self, client: TestClient, data_dir: Path):
        r = _locate(client, "0" * 22, model_id="m_ffffffffffffffff")
        assert r.status_code == 404

    def test_locate_no_designkey_returns_not_found(
        self, client: TestClient, data_dir: Path
    ):
        """模型里存在但无 Pset_AIIFC.designKey 的构件（IfcProject）→ found=false。"""
        _save_script(client, LITERAL_KEY_SCRIPT.format(key="s1:wall:1"))
        model = ifcopenshell.open(str(_uploads_ifc(data_dir)))
        project_guid = model.by_type("IfcProject")[0].GlobalId

        r = _locate(client, project_guid)
        assert r.status_code == 200, r.text
        assert r.json() == {"found": False}

    def test_locate_map_miss_returns_designkey_only(
        self, client: TestClient, data_dir: Path
    ):
        """构件有 designKey 但 current.map.json 缺失 → found=false + designKey。"""
        _save_script(client, LITERAL_KEY_SCRIPT.format(key="s1:wall:1"))
        guid = _wall_guid(data_dir)
        map_path = data_dir / "models" / MODEL_ID / "current.map.json"
        assert map_path.is_file()
        map_path.unlink()

        r = _locate(client, guid)
        assert r.status_code == 200, r.text
        assert r.json() == {"found": False, "designKey": "s1:wall:1"}

    def test_locate_key_not_in_map_returns_designkey_only(
        self, client: TestClient, data_dir: Path
    ):
        """current.map.json 存在但不含该 designKey → found=false + designKey。"""
        _save_script(client, LITERAL_KEY_SCRIPT.format(key="s1:wall:1"))
        guid = _wall_guid(data_dir)
        map_path = data_dir / "models" / MODEL_ID / "current.map.json"
        map_path.write_text("{}", encoding="utf-8")

        r = _locate(client, guid)
        assert r.status_code == 200, r.text
        assert r.json() == {"found": False, "designKey": "s1:wall:1"}

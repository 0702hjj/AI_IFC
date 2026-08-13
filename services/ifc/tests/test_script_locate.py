# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Locate 端点：GET /models/{id}/script/locate?guid=... — guid → designKey → CallSite。

消费 Task 2 的 ``models/{id}/current.map.json`` 与 uploads IFC 里的
``Pset_AIIFC.designKey``：

- 命中：200 {"found": true, "designKey", "line", "col", "snippet", "origin",
  "params_keys"}（origin=params 时 params_keys 为该构件引用的 PARAMS 键）
- 构件存在但无 designKey → 200 {"found": false}
- 有 designKey 但 map 缺失/无该 key → 200 {"found": false, "designKey"}
- staging 与 map 分叉（未 run 的暂存/旧版裸 map）→ 200 {"found": false,
  "designKey", "stale": true}（降级提示，不跳错误行）
- guid 不在模型 → 404；模型不存在 → 404
"""

from __future__ import annotations

import json
from pathlib import Path

import ifcopenshell
from fastapi.testclient import TestClient

from app.script_runner import script_hash
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

MULTI_PARAMS_KEY_SCRIPT = '''\
import sys

import ifcopenshell

from script_lib import attach_design_key, create_entity, create_skeleton, write_and_validate

PARAMS = {{"key": "{key}", "wall_name": "W1"}}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    body, _ = create_skeleton(model)
    w = create_entity(model, "IfcWall", key=params["key"], name=params["wall_name"])
    attach_design_key(model, w, params["key"])
    write_and_validate(model, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''

STOREY_SCRIPT = '''\
import sys

import ifcopenshell

from script_lib import create_skeleton, write_and_validate

PARAMS = {"name": "b", "storeys": {"1F": 0.0}}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    _, smap = create_skeleton(model, name=params["name"], storeys=params["storeys"])
    write_and_validate(model, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''

NO_DESIGNKEY_SCRIPT = '''\
import sys

import ifcopenshell
import ifcopenshell.api

from script_lib import create_skeleton, write_and_validate

PARAMS = {"a": 1}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    body, _ = create_skeleton(model)
    col = ifcopenshell.api.run("root.create_entity", model,
                               ifc_class="IfcColumn", name="C1")
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


def _write_map(data_dir: Path, script_text: str, entries: dict) -> None:
    """按发布信封写 current.map.json（scriptHash 绑定 script_text）。"""
    map_path = data_dir / "models" / MODEL_ID / "current.map.json"
    map_path.write_text(
        json.dumps({"scriptHash": script_hash(script_text), "map": entries}),
        encoding="utf-8",
    )


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
        assert body["params_keys"] == []  # W-0022：literal 无 params 引用

    def test_locate_hit_params_origin(self, client: TestClient, data_dir: Path):
        _save_script(client, PARAMS_KEY_SCRIPT.format(key="s1:wall:2"))
        guid = _wall_guid(data_dir)

        body = _locate(client, guid).json()
        assert body["found"] is True
        assert body["designKey"] == "s1:wall:2"
        assert body["origin"] == "params"
        assert body["params_keys"] == ["key"]  # W-0022：params 引用键透传

    def test_locate_hit_params_origin_lists_multiple_keys(
        self, client: TestClient, data_dir: Path
    ):
        """一个构件引用多个 params 键 → 全部列出（多键引用验收标准）。"""
        _save_script(client, MULTI_PARAMS_KEY_SCRIPT.format(key="s1:wall:3"))
        guid = _wall_guid(data_dir)

        body = _locate(client, guid).json()
        assert body["found"] is True
        assert body["designKey"] == "s1:wall:3"
        assert body["origin"] == "params"
        assert body["params_keys"] == ["key", "wall_name"]

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


class TestLocateSkeleton:
    """W-0023：骨架实体（无构件 key，create_skeleton 内部 key）可 locate 定位。"""

    def test_locate_storey_hits_skeleton_callsite(
        self, client: TestClient, data_dir: Path
    ):
        _save_script(client, STOREY_SCRIPT)
        model = ifcopenshell.open(str(_uploads_ifc(data_dir)))
        storey_guid = model.by_type("IfcBuildingStorey")[0].GlobalId

        r = _locate(client, storey_guid)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["found"] is True
        assert body["designKey"] == "skeleton:storey:1F"
        assert "create_skeleton" in body["snippet"]  # 指向用户脚本的 create_skeleton 调用行
        assert body["line"] > 0

    def test_locate_project_hits_skeleton_callsite(
        self, client: TestClient, data_dir: Path
    ):
        _save_script(client, STOREY_SCRIPT)
        model = ifcopenshell.open(str(_uploads_ifc(data_dir)))
        project_guid = model.by_type("IfcProject")[0].GlobalId

        body = _locate(client, project_guid).json()
        assert body["found"] is True
        assert body["designKey"] == "skeleton:project"
        assert "create_skeleton" in body["snippet"]


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
        """模型里存在但无 Pset_AIIFC.designKey 的构件（裸 root.create_entity）
        → found=false。骨架实体（W-0023 起带 designKey）不属于此类。"""
        _save_script(client, NO_DESIGNKEY_SCRIPT)
        model = ifcopenshell.open(str(_uploads_ifc(data_dir)))
        col_guid = model.by_type("IfcColumn")[0].GlobalId

        r = _locate(client, col_guid)
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
        """map 与 staging 同源但不含该 designKey → found=false + designKey。"""
        script = LITERAL_KEY_SCRIPT.format(key="s1:wall:1")
        _save_script(client, script)
        guid = _wall_guid(data_dir)
        _write_map(data_dir, script, {})

        r = _locate(client, guid)
        assert r.status_code == 200, r.text
        assert r.json() == {"found": False, "designKey": "s1:wall:1"}


class TestLocateStale:
    """staging 与 map 分叉 → 200 降级 {"found": false, "stale": true}。"""

    def test_locate_stale_after_unrun_staged_edit(
        self, client: TestClient, data_dir: Path
    ):
        """save 后 PUT 一个未 run 的移位编辑 → stale（map 行号已不可信）。"""
        script = LITERAL_KEY_SCRIPT.format(key="s1:wall:1")
        _save_script(client, script)
        guid = _wall_guid(data_dir)
        r = client.put(
            f"/models/{MODEL_ID}/script",
            json={"script": "# line-shifting edit\n" + script},
        )
        assert r.status_code == 200, r.text

        r = _locate(client, guid)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["found"] is False
        assert body["stale"] is True
        assert body["designKey"] == "s1:wall:1"

    def test_locate_stale_after_undo(
        self, client: TestClient, data_dir: Path
    ):
        """run 后 undo：map 描述 undo 前的脚本 → stale。"""
        script = LITERAL_KEY_SCRIPT.format(key="s1:wall:1")
        _save_script(client, script)
        guid = _wall_guid(data_dir)
        renamed = script.replace('name="W1"', 'name="W2"')
        client.put(f"/models/{MODEL_ID}/script", json={"script": renamed})
        assert client.post(f"/models/{MODEL_ID}/script/run").status_code == 200
        assert client.post(f"/models/{MODEL_ID}/script/undo").status_code == 200

        body = _locate(client, guid).json()
        assert body["found"] is False
        assert body["stale"] is True

    def test_locate_legacy_bare_map_stale(
        self, client: TestClient, data_dir: Path
    ):
        """旧版裸 map（无 scriptHash 信封）→ stale 提示而非 500/误跳。"""
        script = LITERAL_KEY_SCRIPT.format(key="s1:wall:1")
        _save_script(client, script)
        guid = _wall_guid(data_dir)
        map_path = data_dir / "models" / MODEL_ID / "current.map.json"
        bare = {"s1:wall:1": {"line": 9, "col": 8, "snippet": "s", "origin": "literal"}}
        map_path.write_text(json.dumps(bare), encoding="utf-8")

        r = _locate(client, guid)
        assert r.status_code == 200, r.text
        assert r.json() == {
            "found": False,
            "designKey": "s1:wall:1",
            "stale": True,
        }

    def test_locate_hit_after_rerun_clears_stale(
        self, client: TestClient, data_dir: Path
    ):
        """分叉后重新 run：map 与 staging 重新同源，locate 恢复命中。"""
        script = LITERAL_KEY_SCRIPT.format(key="s1:wall:1")
        _save_script(client, script)
        client.put(
            f"/models/{MODEL_ID}/script",
            json={"script": "# edit\n" + script},
        )
        assert client.post(f"/models/{MODEL_ID}/script/run").status_code == 200

        body = _locate(client, _wall_guid(data_dir)).json()
        assert body["found"] is True
        assert body["designKey"] == "s1:wall:1"

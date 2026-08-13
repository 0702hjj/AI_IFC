# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Locate 端点：GET /models/{id}/script/locate?key=... — XDATA key → CallSite。

消费 ``models/{id}/current.map.json``（run/save 发布的信封）；与 IFC 侧不同，
定位入参就是 XDATA key 本身（无 guid→designKey 转换、无 registry）：

- 命中：200 {"found": true, "key", "line", "col", "snippet", "origin",
  "params_keys"}（origin=params 时 params_keys 为该实体引用的 PARAMS 键）
- map 缺失/损坏/无该 key → 200 {"found": false, "key"}
- staging 与 map 分叉（未 run 的暂存/undo/旧版裸 map）→ 200 {"found": false,
  "key", "stale": true}（降级提示，不跳错误行）
- 模型不存在 → 404
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.script_runner import script_hash
from tests.conftest import MODEL_ID

LITERAL_KEY_SCRIPT = '''\
import sys

import ezdxf

from cad_script_lib import add_entity, write_and_validate

PARAMS = {{"key": "{key}"}}

def build(params, out_path):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    add_entity(msp, "TEXT", key="s1:text:1", text="W1", insert=(0, 0))
    write_and_validate(doc, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''

PARAMS_KEY_SCRIPT = '''\
import sys

import ezdxf

from cad_script_lib import add_entity, write_and_validate

PARAMS = {{"key": "{key}"}}

def build(params, out_path):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    add_entity(msp, "TEXT", key=params["key"], text="W1", insert=(0, 0))
    write_and_validate(doc, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''

MULTI_PARAMS_KEY_SCRIPT = '''\
import sys

import ezdxf

from cad_script_lib import add_entity, write_and_validate

PARAMS = {{"key": "{key}", "label": "W1"}}

def build(params, out_path):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    add_entity(msp, "TEXT", key=params["key"], text=params["label"], insert=(0, 0))
    write_and_validate(doc, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''

AUTO_KEY_SCRIPT = '''\
import sys

import ezdxf

from cad_script_lib import add_entity, write_and_validate

PARAMS = {"length": 10}

def build(params, out_path):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    add_entity(msp, "LINE", start=(0, 0), end=(params["length"], 0))
    write_and_validate(doc, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''


def _save_script(client: TestClient, script: str) -> None:
    r = client.put(f"/models/{MODEL_ID}/script", json={"script": script})
    assert r.status_code == 200, r.text
    r = client.post(f"/models/{MODEL_ID}/script/save", json={})
    assert r.status_code == 200, r.text


def _locate(client: TestClient, key: str, model_id: str = MODEL_ID):
    return client.get(f"/models/{model_id}/script/locate", params={"key": key})


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
        _save_script(client, LITERAL_KEY_SCRIPT.format(key="s1:text:1"))

        r = _locate(client, "s1:text:1")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["found"] is True
        assert body["key"] == "s1:text:1"
        assert body["origin"] == "literal"
        assert body["line"] > 0
        assert body["col"] >= 0
        assert "add_entity" in body["snippet"]
        assert body["params_keys"] == []  # literal 无 params 引用

    def test_locate_hit_params_origin(self, client: TestClient, data_dir: Path):
        _save_script(client, PARAMS_KEY_SCRIPT.format(key="s1:text:2"))

        body = _locate(client, "s1:text:2").json()
        assert body["found"] is True
        assert body["key"] == "s1:text:2"
        assert body["origin"] == "params"
        assert body["params_keys"] == ["key"]  # params 引用键透传

    def test_locate_hit_params_origin_lists_multiple_keys(
        self, client: TestClient, data_dir: Path
    ):
        """一个实体引用多个 params 键 → 全部列出（多键引用验收标准）。"""
        _save_script(client, MULTI_PARAMS_KEY_SCRIPT.format(key="s1:text:3"))

        body = _locate(client, "s1:text:3").json()
        assert body["found"] is True
        assert body["key"] == "s1:text:3"
        assert body["origin"] == "params"
        assert body["params_keys"] == ["key", "label"]

    def test_locate_after_run_without_save(
        self, client: TestClient, data_dir: Path
    ):
        """run（不落版本）也发布 current.map.json，locate 同样命中。"""
        client.put(
            f"/models/{MODEL_ID}/script",
            json={"script": LITERAL_KEY_SCRIPT.format(key="s1:text:1")},
        )
        r = client.post(f"/models/{MODEL_ID}/script/run")
        assert r.status_code == 200, r.text

        body = _locate(client, "s1:text:1").json()
        assert body["found"] is True
        assert body["key"] == "s1:text:1"

    def test_locate_hit_auto_key_origin_traced(
        self, client: TestClient, data_dir: Path
    ):
        """自动分配的 key（无 key= 实参 → origin=traced）同样可 locate。"""
        _save_script(client, AUTO_KEY_SCRIPT)

        body = _locate(client, "0:line:1").json()
        assert body["found"] is True
        assert body["key"] == "0:line:1"
        assert body["origin"] == "traced"
        assert "add_entity" in body["snippet"]


class TestLocateMiss:
    def test_locate_unknown_model_404(self, client: TestClient, data_dir: Path):
        r = _locate(client, "s1:text:1", model_id="m_ffffffffffffffff")
        assert r.status_code == 404

    def test_locate_map_missing_returns_key_only(
        self, client: TestClient, data_dir: Path
    ):
        """current.map.json 缺失 → found=false + key（不 500、不 stale）。"""
        _save_script(client, LITERAL_KEY_SCRIPT.format(key="s1:text:1"))
        map_path = data_dir / "models" / MODEL_ID / "current.map.json"
        assert map_path.is_file()
        map_path.unlink()

        r = _locate(client, "s1:text:1")
        assert r.status_code == 200, r.text
        assert r.json() == {"found": False, "key": "s1:text:1"}

    def test_locate_corrupt_map_returns_key_only(
        self, client: TestClient, data_dir: Path
    ):
        """map 文件损坏（非 JSON）→ found=false + key 而非 500。"""
        _save_script(client, LITERAL_KEY_SCRIPT.format(key="s1:text:1"))
        map_path = data_dir / "models" / MODEL_ID / "current.map.json"
        map_path.write_text("not json{", encoding="utf-8")

        r = _locate(client, "s1:text:1")
        assert r.status_code == 200, r.text
        assert r.json() == {"found": False, "key": "s1:text:1"}

    def test_locate_key_not_in_map_returns_key_only(
        self, client: TestClient, data_dir: Path
    ):
        """map 与 staging 同源但不含该 key → found=false + key。"""
        script = LITERAL_KEY_SCRIPT.format(key="s1:text:1")
        _save_script(client, script)
        _write_map(data_dir, script, {})

        r = _locate(client, "s1:text:1")
        assert r.status_code == 200, r.text
        assert r.json() == {"found": False, "key": "s1:text:1"}

    def test_locate_unknown_key_returns_not_found(
        self, client: TestClient, data_dir: Path
    ):
        """真实 map 里查未知 key（模型里不存在该实体）→ found=false。"""
        _save_script(client, LITERAL_KEY_SCRIPT.format(key="s1:text:1"))

        r = _locate(client, "s1:text:nope")
        assert r.status_code == 200, r.text
        assert r.json() == {"found": False, "key": "s1:text:nope"}


class TestLocateStale:
    """staging 与 map 分叉 → 200 降级 {"found": false, "stale": true}。"""

    def test_locate_stale_after_unrun_staged_edit(
        self, client: TestClient, data_dir: Path
    ):
        """save 后 PUT 一个未 run 的移位编辑 → stale（map 行号已不可信）。"""
        script = LITERAL_KEY_SCRIPT.format(key="s1:text:1")
        _save_script(client, script)
        r = client.put(
            f"/models/{MODEL_ID}/script",
            json={"script": "# line-shifting edit\n" + script},
        )
        assert r.status_code == 200, r.text

        r = _locate(client, "s1:text:1")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["found"] is False
        assert body["stale"] is True
        assert body["key"] == "s1:text:1"

    def test_locate_stale_after_undo(
        self, client: TestClient, data_dir: Path
    ):
        """run 后 undo：map 描述 undo 前的脚本 → stale。"""
        script = LITERAL_KEY_SCRIPT.format(key="s1:text:1")
        _save_script(client, script)
        renamed = script.replace('text="W1"', 'text="W2"')
        client.put(f"/models/{MODEL_ID}/script", json={"script": renamed})
        assert client.post(f"/models/{MODEL_ID}/script/run").status_code == 200
        assert client.post(f"/models/{MODEL_ID}/script/undo").status_code == 200

        body = _locate(client, "s1:text:1").json()
        assert body["found"] is False
        assert body["stale"] is True

    def test_locate_legacy_bare_map_stale(
        self, client: TestClient, data_dir: Path
    ):
        """旧版裸 map（无 scriptHash 信封）→ stale 提示而非 500/误跳。"""
        _save_script(client, LITERAL_KEY_SCRIPT.format(key="s1:text:1"))
        map_path = data_dir / "models" / MODEL_ID / "current.map.json"
        bare = {"s1:text:1": {"line": 12, "col": 4, "snippet": "s", "origin": "literal"}}
        map_path.write_text(json.dumps(bare), encoding="utf-8")

        r = _locate(client, "s1:text:1")
        assert r.status_code == 200, r.text
        assert r.json() == {
            "found": False,
            "key": "s1:text:1",
            "stale": True,
        }

    def test_locate_hit_after_rerun_clears_stale(
        self, client: TestClient, data_dir: Path
    ):
        """分叉后重新 run：map 与 staging 重新同源，locate 恢复命中。"""
        script = LITERAL_KEY_SCRIPT.format(key="s1:text:1")
        _save_script(client, script)
        client.put(
            f"/models/{MODEL_ID}/script",
            json={"script": "# edit\n" + script},
        )
        assert client.post(f"/models/{MODEL_ID}/script/run").status_code == 200

        body = _locate(client, "s1:text:1").json()
        assert body["found"] is True
        assert body["key"] == "s1:text:1"

    def test_locate_stale_response_carries_no_position(
        self, client: TestClient, data_dir: Path
    ):
        """stale 降级绝不返回旧行号/列号（防前端跳错误行）。"""
        script = LITERAL_KEY_SCRIPT.format(key="s1:text:1")
        _save_script(client, script)
        client.put(
            f"/models/{MODEL_ID}/script",
            json={"script": "# shift\n" + script},
        )

        body = _locate(client, "s1:text:1").json()
        assert body["stale"] is True
        assert "line" not in body
        assert "col" not in body
        assert "snippet" not in body

# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Map publication: run writes current.map.json; save writes v{n}.map.json lockstep.

run_script 接受 ``map_out`` 把 ScriptMap sidecar 发布到指定路径（默认仍为
``<out>.map.json``）；routes 层把 run/save 的 map 落到
``models/{id}/current.map.json``，save 再随大版本写 ``scripts/v{n}.map.json``
（与 v{n}.py / versions/v{n}.ifc lockstep）。脚本未产出 map 时不写版本 map，
并清掉过期的 current.map.json。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import script_runner, script_versions
from app.config import load_settings
from tests.conftest import MODEL_ID

MAP_SCRIPT = '''\
import sys

import ifcopenshell

from script_lib import create_entity, create_skeleton, write_and_validate

PARAMS = {{"key": "{key}"}}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    body, _ = create_skeleton(model)
    w = create_entity(model, "IfcWall", key=params["key"], name="W1")
    write_and_validate(model, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''


def _map_script(key: str = "s1:wall:1") -> str:
    return MAP_SCRIPT.format(key=key)


NO_MAP_SCRIPT = (
    'PARAMS = {"marker": "plain"}\n'
    "\n"
    "def build(params, out_path):\n"
    "    open(out_path, 'w').write('IFC:' + params['marker'])\n"
    "\n"
    'if __name__ == "__main__":\n'
    "    import sys\n"
    "    build(PARAMS, sys.argv[1])\n"
)


@pytest.fixture()
def settings():
    return load_settings()


def _current_map_path(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "current.map.json"


def _read_current_map(data_dir: Path) -> dict:
    path = _current_map_path(data_dir)
    assert path.is_file()
    return json.loads(path.read_text(encoding="utf-8"))


class TestRunScriptMapOut:
    """run_script 的 map_out 参数：sidecar 发布到指定路径（而非 <out>.map.json）。"""

    def test_map_out_publishes_sidecar_to_custom_path(
        self, settings, tmp_path: Path
    ):
        out = tmp_path / "out.ifc"
        map_out = tmp_path / "sub" / "current.map.json"
        script = _map_script()
        script_runner.run_script(settings, script, str(out), map_out=str(map_out))
        assert map_out.is_file()
        m = json.loads(map_out.read_text(encoding="utf-8"))
        # 发布信封：scriptHash 绑定所跑脚本，map 为调用点条目
        assert m["scriptHash"] == script_runner.script_hash(script)
        entries = m["map"]
        assert "s1:wall:1" in entries
        entry = entries["s1:wall:1"]
        assert entry["origin"] == "params"
        assert entry["line"] > 0
        assert "create_entity" in entry["snippet"]

    def test_map_out_absent_default_sidecar_kept(self, settings, tmp_path: Path):
        """不传 map_out 时保持 Task 1 行为：<out>.map.json sidecar。"""
        out = tmp_path / "out.ifc"
        script_runner.run_script(settings, _map_script(), str(out))
        assert Path(str(out) + ".map.json").is_file()

    def test_map_out_stale_cleanup(self, settings, tmp_path: Path):
        """重跑无 map 的脚本时，map_out 处的旧 map 必须被清掉（防错位）。"""
        out = tmp_path / "out.ifc"
        map_out = tmp_path / "current.map.json"
        script_runner.run_script(
            settings, _map_script(), str(out), map_out=str(map_out)
        )
        assert map_out.is_file()
        script_runner.run_script(
            settings, NO_MAP_SCRIPT, str(out), map_out=str(map_out)
        )
        assert not map_out.exists()

    def test_failed_run_writes_no_map(self, settings, tmp_path: Path):
        out = tmp_path / "out.ifc"
        map_out = tmp_path / "current.map.json"
        fail = (
            'PARAMS = {"a": 1}\n'
            "def build(params, out_path):\n"
            "    raise RuntimeError('boom')\n"
            'if __name__ == "__main__":\n'
            "    import sys\n"
            "    build(PARAMS, sys.argv[1])\n"
        )
        with pytest.raises(Exception):
            script_runner.run_script(settings, fail, str(out), map_out=str(map_out))
        assert not map_out.exists()


class TestSaveMapText:
    """script_versions.save 的 map_text 参数：v{n}.map.json 与 v{n}.py lockstep。"""

    def test_save_writes_map_version(self, data_dir: Path):
        ifc = data_dir / "uploads" / f"{MODEL_ID}.ifc"
        map_text = json.dumps({"k": {"line": 1, "col": 0, "snippet": "s", "origin": "literal"}})
        version = script_versions.save(
            str(data_dir), MODEL_ID, "PARAMS = {}\n", str(ifc), map_text=map_text
        )
        map_file = (
            data_dir / "models" / MODEL_ID / "scripts" / f"{version}.map.json"
        )
        assert map_file.is_file()
        assert json.loads(map_file.read_text(encoding="utf-8")) == {"k": {
            "line": 1, "col": 0, "snippet": "s", "origin": "literal"}}

    def test_save_without_map_text_writes_no_map_file(self, data_dir: Path):
        ifc = data_dir / "uploads" / f"{MODEL_ID}.ifc"
        version = script_versions.save(
            str(data_dir), MODEL_ID, "PARAMS = {}\n", str(ifc)
        )
        assert not (
            data_dir / "models" / MODEL_ID / "scripts" / f"{version}.map.json"
        ).exists()


class TestRunEndpointPublishesCurrentMap:
    def test_run_writes_current_map(self, client: TestClient, data_dir: Path):
        script = _map_script()
        client.put(f"/models/{MODEL_ID}/script", json={"script": script})
        r = client.post(f"/models/{MODEL_ID}/script/run")
        assert r.status_code == 200, r.text
        m = _read_current_map(data_dir)
        assert m["scriptHash"] == script_runner.script_hash(script)
        entry = m["map"]["s1:wall:1"]
        assert entry["line"] > 0
        assert "create_entity" in entry["snippet"]

    def test_run_without_map_script_leaves_no_current_map(
        self, client: TestClient, data_dir: Path
    ):
        client.put(f"/models/{MODEL_ID}/script", json={"script": NO_MAP_SCRIPT})
        r = client.post(f"/models/{MODEL_ID}/script/run")
        assert r.status_code == 200, r.text
        assert not _current_map_path(data_dir).exists()

    def test_rerun_without_map_clears_stale_current_map(
        self, client: TestClient, data_dir: Path
    ):
        client.put(f"/models/{MODEL_ID}/script", json={"script": _map_script()})
        client.post(f"/models/{MODEL_ID}/script/run")
        assert _current_map_path(data_dir).is_file()
        client.put(f"/models/{MODEL_ID}/script", json={"script": NO_MAP_SCRIPT})
        client.post(f"/models/{MODEL_ID}/script/run")
        assert not _current_map_path(data_dir).exists()


class TestSaveEndpointMapLockstep:
    def test_save_writes_map_lockstep(self, client: TestClient, data_dir: Path):
        client.put(f"/models/{MODEL_ID}/script", json={"script": _map_script()})
        r = client.post(f"/models/{MODEL_ID}/script/save", json={})
        assert r.status_code == 200, r.text
        version = r.json()["version"]
        map_file = data_dir / "models" / MODEL_ID / "scripts" / f"{version}.map.json"
        assert map_file.is_file()
        m = json.loads(map_file.read_text(encoding="utf-8"))
        assert m["map"]  # 至少一个 designKey
        assert "s1:wall:1" in m["map"]
        # current.map.json 同步存在且与版本 map 内容一致
        current = _read_current_map(data_dir)
        assert current == m

    def test_save_versions_keep_respective_maps(
        self, client: TestClient, data_dir: Path
    ):
        """两次 save 不同 key：v1/v2 各自的 map 互不覆盖。"""
        client.put(
            f"/models/{MODEL_ID}/script", json={"script": _map_script("s1:wall:1")}
        )
        v1 = client.post(f"/models/{MODEL_ID}/script/save").json()["version"]
        client.put(
            f"/models/{MODEL_ID}/script", json={"script": _map_script("s1:wall:2")}
        )
        v2 = client.post(f"/models/{MODEL_ID}/script/save").json()["version"]

        scripts_dir = data_dir / "models" / MODEL_ID / "scripts"
        m1 = json.loads((scripts_dir / f"{v1}.map.json").read_text(encoding="utf-8"))
        m2 = json.loads((scripts_dir / f"{v2}.map.json").read_text(encoding="utf-8"))
        assert list(m1["map"]) == [
            "skeleton:project", "skeleton:site", "skeleton:building",
            "s1:wall:1",
        ]
        assert list(m2["map"]) == [
            "skeleton:project", "skeleton:site", "skeleton:building",
            "s1:wall:2",
        ]
        # current.map.json 跟随最新一次 run（save 内部重跑）
        assert list(_read_current_map(data_dir)["map"]) == [
            "skeleton:project", "skeleton:site", "skeleton:building",
            "s1:wall:2",
        ]

    def test_save_without_map_writes_no_version_map(
        self, client: TestClient, data_dir: Path
    ):
        client.put(f"/models/{MODEL_ID}/script", json={"script": NO_MAP_SCRIPT})
        r = client.post(f"/models/{MODEL_ID}/script/save")
        assert r.status_code == 200, r.text
        version = r.json()["version"]
        assert not (
            data_dir / "models" / MODEL_ID / "scripts" / f"{version}.map.json"
        ).exists()
        assert not _current_map_path(data_dir).exists()

    def test_failed_save_produces_no_map(
        self, client: TestClient, data_dir: Path
    ):
        fail = (
            'PARAMS = {"a": 1}\n'
            "def build(params, out_path):\n"
            "    raise RuntimeError('map-save-fail')\n"
            'if __name__ == "__main__":\n'
            "    import sys\n"
            "    build(PARAMS, sys.argv[1])\n"
        )
        client.put(f"/models/{MODEL_ID}/script", json={"script": fail})
        r = client.post(f"/models/{MODEL_ID}/script/save")
        assert r.status_code == 422
        assert not _current_map_path(data_dir).exists()
        assert script_versions.list_scripts(str(data_dir), MODEL_ID) == []

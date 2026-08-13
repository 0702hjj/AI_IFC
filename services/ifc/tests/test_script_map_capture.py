# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""ScriptMap capture: create_entity records callsites; write_and_validate dumps map.

端到端验证（经 run_script 沙箱子进程）：脚本用 script_lib.create_entity 建构件时，
出口写 ``<out>.map.json`` sidecar，条目含 line/col/snippet/origin。
origin 三态：字面量 key → "literal"；params 引用 → "params"；解析失败（多行调用等）
→ "traced"（可定位、不可自动改写）。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app import diffing, script_runner
from app.config import load_settings

LITERAL_SCRIPT = '''\
import os
import sys

import ifcopenshell

from script_lib import create_entity, create_skeleton, write_and_validate

PARAMS = {"wall_name": "W1"}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    body, _ = create_skeleton(model)
    w = create_entity(model, "IfcWall", key="s1:wall:1", name=params["wall_name"])
    write_and_validate(model, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''

PARAMS_KEY_SCRIPT = '''\
import os
import sys

import ifcopenshell

from script_lib import create_entity, create_skeleton, write_and_validate

PARAMS = {"key": "s1:wall:1"}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    body, _ = create_skeleton(model)
    keys = {"w": params["key"]}
    w = create_entity(model, "IfcWall", key=keys["w"], name="W1")
    write_and_validate(model, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''

DIRECT_PARAMS_SCRIPT = '''\
import os
import sys

import ifcopenshell

from script_lib import create_entity, create_skeleton, write_and_validate

PARAMS = {"key": "s1:wall:1", "wall_name": "W1"}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    body, _ = create_skeleton(model)
    w = create_entity(model, "IfcWall", key=params["key"], name=params["wall_name"])
    write_and_validate(model, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''

MULTILINE_SCRIPT = '''\
import os
import sys

import ifcopenshell

from script_lib import create_entity, create_skeleton, write_and_validate

PARAMS = {"a": 1}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    body, _ = create_skeleton(model)
    w = create_entity(
        model, "IfcWall", key="s1:wall:1", name="W1")
    write_and_validate(model, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''

NO_LIB_SCRIPT = '''\
PARAMS = {"a": 1}

def build(params, out_path):
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("ISO-10303-21;")

if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1])
'''


@pytest.fixture()
def settings():
    return load_settings()


def _read_map(out: Path) -> dict:
    """读取发布的 sidecar 信封（{"scriptHash", "map"}），返回调用点条目。"""
    map_path = Path(str(out) + ".map.json")
    assert map_path.is_file()
    envelope = json.loads(map_path.read_text(encoding="utf-8"))
    return envelope["map"]


class TestMapSidecar:
    def test_literal_key_origin(self, settings, tmp_path: Path):
        out = tmp_path / "out.ifc"
        script_runner.run_script(settings, LITERAL_SCRIPT, str(out))
        m = _read_map(out)
        assert "s1:wall:1" in m
        entry = m["s1:wall:1"]
        assert entry["origin"] == "literal"
        assert entry["line"] > 0
        assert entry["col"] >= 0
        assert "create_entity" in entry["snippet"]
        # W-0022：literal 即使其他参数引用 params，params_keys 也置空（键非 params 驱动）
        assert entry["params_keys"] == []

    def test_params_reference_key_origin(self, settings, tmp_path: Path):
        out = tmp_path / "out.ifc"
        script_runner.run_script(settings, PARAMS_KEY_SCRIPT, str(out))
        entry = _read_map(out)["s1:wall:1"]
        assert entry["origin"] == "params"
        assert entry["line"] > 0
        # 间接下标（keys["w"]，params 引用在上一行）→ 调用行无可提取键
        assert entry["params_keys"] == []

    def test_direct_params_ref_records_params_keys(self, settings, tmp_path: Path):
        """W-0022：调用行直接引用 params 键 → params_keys 落多键列表。"""
        out = tmp_path / "out.ifc"
        script_runner.run_script(settings, DIRECT_PARAMS_SCRIPT, str(out))
        entry = _read_map(out)["s1:wall:1"]
        assert entry["origin"] == "params"
        assert entry["params_keys"] == ["key", "wall_name"]

    def test_multiline_call_degrades_to_traced(self, settings, tmp_path: Path):
        out = tmp_path / "out.ifc"
        script_runner.run_script(settings, MULTILINE_SCRIPT, str(out))
        entry = _read_map(out)["s1:wall:1"]
        assert entry["origin"] == "traced"
        assert entry["line"] > 0

    def test_rerun_without_map_clears_stale_sidecar(self, settings, tmp_path: Path):
        """产物重跑后无 sidecar 时，上一轮留下的旧 map 必须被清掉（防错位）。"""
        out = tmp_path / "out.ifc"
        script_runner.run_script(settings, LITERAL_SCRIPT, str(out))
        assert Path(str(out) + ".map.json").is_file()
        script_runner.run_script(settings, NO_LIB_SCRIPT, str(out))
        assert not Path(str(out) + ".map.json").exists()

    def test_map_entries_follow_insertion_order(self, settings, tmp_path: Path):
        out = tmp_path / "out.ifc"
        script_runner.run_script(settings, LITERAL_SCRIPT, str(out))
        assert list(_read_map(out)) == [
            "skeleton:project", "skeleton:site", "skeleton:building",
            "s1:wall:1",
        ]

    def test_map_contains_skeleton_entries(self, settings, tmp_path: Path):
        """W-0023：create_skeleton 骨架实体走 create_entity → 进 map，可 locate。

        骨架调用点指向用户脚本里的 create_skeleton 调用行（snippet 含
        create_skeleton，非 script_lib 内部行）。origin 锁 ``"traced"``
        （2026-08-11 用户裁决）：调用行无 key 关键字参数，无法自动改写，
        只能定位（与 literal/params 的「可改写」语义区分）。
        """
        out = tmp_path / "out.ifc"
        script_runner.run_script(settings, LITERAL_SCRIPT, str(out))
        m = _read_map(out)
        for key in ("skeleton:project", "skeleton:site", "skeleton:building"):
            entry = m[key]
            assert entry["line"] > 0
            assert "create_skeleton" in entry["snippet"]
            assert entry["origin"] == "traced"

    def test_rerun_same_script_map_bytes_identical(
        self, settings, tmp_path: Path
    ):
        """spec §8 留白：同一脚本两次 run，.map.json（含骨架条目）字节一致。"""
        out1, out2 = tmp_path / "a.ifc", tmp_path / "b.ifc"
        script_runner.run_script(settings, LITERAL_SCRIPT, str(out1))
        script_runner.run_script(settings, LITERAL_SCRIPT, str(out2))
        m1 = Path(str(out1) + ".map.json").read_bytes()
        m2 = Path(str(out2) + ".map.json").read_bytes()
        assert m1 and m1 == m2


class TestSkeletonSemanticDeterminism:
    """W-0023：骨架确定性 → 同一脚本两次 run 的 IFC 语义 diff 为空（I5）。"""

    def test_two_runs_same_script_semantic_diff_empty(
        self, settings, tmp_path: Path
    ):
        out1, out2 = tmp_path / "m1.ifc", tmp_path / "m2.ifc"
        script_runner.run_script(settings, LITERAL_SCRIPT, str(out1))
        script_runner.run_script(settings, LITERAL_SCRIPT, str(out2))
        assert diffing.compute_diff(str(out1), str(out2)) == {
            "added": [], "removed": [], "changed": [],
        }

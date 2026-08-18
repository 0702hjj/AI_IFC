"""pack.py 测试（T42）：mission 渲染 + state 登记。"""

import json
from pathlib import Path

import pytest

from flowops.pack import pack_mission, init_state, register_mission


class TestPackMission:
    def test_mission_dir_created(self, tmp_path):
        node = "podium.rooms"
        result = pack_mission(node, project_dir=str(tmp_path), inputs={})
        mission_dir = tmp_path / "missions" / node
        assert mission_dir.exists()
        assert (mission_dir / "mission.json").exists()

    def test_mission_json_fields(self, tmp_path):
        """mission.json 字段对齐 architecture §5 状态机。"""
        node = "podium.rooms"
        pack_mission(node, project_dir=str(tmp_path), inputs={})
        mission = json.loads((tmp_path / "missions" / node / "mission.json").read_text())
        assert mission["node"] == node
        assert mission["status"] == "pending"
        assert mission["attempts"] == 0
        assert "depends_on" in mission
        assert "covers" in mission
        assert "inputs" in mission

    def test_mission_prompt_rendered(self, tmp_path):
        """prompt.md 渲染（含 zone 包指针）。"""
        node = "podium.rooms"
        pack_mission(node, project_dir=str(tmp_path),
                     inputs={"zone_pack": "derived/podium.json#floors[f1]"})
        prompt = (tmp_path / "missions" / node / "prompt.md").read_text()
        assert "derived/podium.json" in prompt

    def test_mission_depends_on(self, tmp_path):
        node = "tower.rooms"
        pack_mission(node, project_dir=str(tmp_path),
                     inputs={}, depends_on=["podium.rooms"])
        mission = json.loads((tmp_path / "missions" / node / "mission.json").read_text())
        assert mission["depends_on"] == ["podium.rooms"]


class TestState:
    def test_init_state(self, tmp_path):
        state = init_state(str(tmp_path))
        path = tmp_path / "state.json"
        assert path.exists()
        assert state["skeleton"] == "drafting"
        assert state["missions"] == []
        assert state["presented"] == []
        assert state["current_breakpoint"] is None

    def test_register_mission(self, tmp_path):
        init_state(str(tmp_path))
        register_mission("podium.rooms", project_dir=str(tmp_path))
        state = json.loads((tmp_path / "state.json").read_text())
        assert state["missions"] == ["podium.rooms"]

    def test_state_idempotent(self, tmp_path):
        """二次 pack 幂等（不覆盖已有状态）。"""
        init_state(str(tmp_path))
        register_mission("podium.rooms", project_dir=str(tmp_path))
        register_mission("podium.rooms", project_dir=str(tmp_path))
        state = json.loads((tmp_path / "state.json").read_text())
        assert state["missions"] == ["podium.rooms"]  # 不重复


class TestPackKnowledge:
    """2026-08-11：pack 注入设计知识（goldlib push 预筛）。"""

    def test_knowledge_injected_to_prompt(self, tmp_path):
        """knowledge 段写进 prompt.md（worker 照抄改参数）。"""
        from flowops.pack import pack_mission
        m = pack_mission(
            "podium.rooms", str(tmp_path), inputs={"zone_pack": "x"},
            knowledge=[{"kind": "pattern", "pain": "P2-3",
                        "dsl": "{\"wall\": 0, \"along_m\": 6.0, \"type\": \"door\"}"}],
        )
        prompt = (tmp_path / "missions" / "podium.rooms" / "prompt.md").read_text(encoding="utf-8")
        assert "注入的设计知识" in prompt
        assert "pattern 片段（P2-3）" in prompt
        assert "\"along_m\": 6.0" in prompt

    def test_no_knowledge_skips_section(self, tmp_path):
        """无 knowledge → 不生成该段。"""
        from flowops.pack import pack_mission
        m = pack_mission("podium.rooms", str(tmp_path), inputs={})
        prompt = (tmp_path / "missions" / "podium.rooms" / "prompt.md").read_text(encoding="utf-8")
        assert "注入的设计知识" not in prompt

    def test_extract_pattern_dsl(self, tmp_path):
        """从 pattern 源文件提取 DSL 片段（`DSL 片段:` 到下一个 `##`）。"""
        from aidxfv3.cli import _extract_pattern_dsl
        src = tmp_path / "p.md"
        src.write_text(
            "## pattern: 测试\n"
            "适用条件: {}\n"
            "DSL 片段:\n"
            "  {\"loc\": {\"on_edge\": \"S\"}}\n"
            "决策依据: 说明\n", encoding="utf-8")
        assert "\"on_edge\": \"S\"" in _extract_pattern_dsl(str(src))

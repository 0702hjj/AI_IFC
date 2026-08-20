"""design/orchestrator + steps 测试（T50/T51）：自包含 + 零 docs/ 路径 + patterns 可入库。"""

import json
import re
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parent.parent

# 规范文档目录（design + orchestrator，原 prompts/ 拆解后）
_SPEC_DIRS = ("references/design", "references/orchestrator")


class TestSpecsSelfContained:
    """T50 验收：规范文档自包含 + 零外部路径。"""

    def test_specs_no_docs_path(self):
        """零 docs/ 路径（P2 自包含：skill 拷走即用时 docs 不在）。"""
        specs = []
        for d in _SPEC_DIRS:
            specs += list((SKILL_ROOT / d).rglob("*.md"))
        assert len(specs) >= 7, "设计/编排规范文档齐（design 4 + orchestrator 3）"
        for p in specs:
            content = p.read_text(encoding="utf-8")
            assert "docs/buildingplan" not in content, f"{p} 引用了 docs/"

    def test_design_contract_files_exist(self):
        design = SKILL_ROOT / "references" / "design"
        assert (design / "rooms.md").exists()
        assert (design / "details.md").exists()
        assert (design / "output_contract.md").exists()
        assert (design / "work_area.md").exists()

    def test_design_specs_include_shared(self):
        """设计规范 include 契约（单点维护）。"""
        for name in ("rooms.md", "details.md"):
            f = SKILL_ROOT / "references" / "design" / name
            assert f.exists(), f"缺 {name}"
            assert "output_contract" in f.read_text() or "work_area" in f.read_text()

    def test_rules_in_rooms(self):
        """R-01~R-09 设计期注入列已进 rooms.md。"""
        f = (SKILL_ROOT / "references" / "design" / "rooms.md").read_text()
        for rid in ("R-01", "R-02", "R-03", "R-04", "R-05", "R-07", "R-08", "R-09"):
            assert rid in f, f"rooms.md 缺 {rid}"

    def test_orchestrator_three(self):
        for name in ("skeleton.md", "breakpoint.md", "dispatch.md"):
            assert (SKILL_ROOT / "references" / "orchestrator" / name).exists()

    def test_breakpoint_uses_question_tool(self):
        """断点提问复用 aiplan 方式：question 工具弹框 + 交互分层 + 修改协议。"""
        f = (SKILL_ROOT / "references" / "orchestrator" / "breakpoint.md").read_text()
        assert "question" in f                       # question 工具
        assert "custom" in f                          # 允许自定义
        assert "改同板块" in f or "修改协议" in f       # 修改协议（复用 aiplan）
        assert "交互分层" in f                         # 连问/精问/直落
        assert "建筑师语言" in f or "不暴露字段名" in f   # 回显规范

    def test_steps_reference_breakpoint(self):
        """steps 断点引用 breakpoint.md（提问方式单一来源）。"""
        for step in ("step-01-skeleton.md", "step-02-rooms.md"):
            content = (SKILL_ROOT / "steps" / step).read_text(encoding="utf-8")
            assert "breakpoint.md" in content or "question" in content

    def test_state_machine_terms(self):
        """1.3（2026-08-13）：回退规则单处定义 state.json#state_machine——规范文档引用不重复定义。

        旧 rejected/build_reject 态已被 rollback_rules（reject_at_breakpoint 等）取代。
        """
        texts = []
        for d in _SPEC_DIRS:
            for f in (SKILL_ROOT / d).rglob("*.md"):
                texts.append(f.read_text())
        joined = "\n".join(texts)
        # dispatch 引用单处定义
        assert "state_machine.rollback_rules" in joined, "规范文档应引用 state.json 单处定义"
        # 九态词表至少出现（dispatch）
        assert "confirmed" in joined and "dispatched" in joined

    def test_external_interface_documented(self):
        """fix_missing P3：外部接口（bim/前端）在 SKILL.md 落地。"""
        sk = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        assert "bim" in sk and "building.json" in sk

    def test_flywheel_three_gates(self):
        """fix_missing P5：飞轮三闸门（G1/G2/G3）在 step-04 落地。"""
        f = (SKILL_ROOT / "steps" / "step-04-deliver.md").read_text(encoding="utf-8")
        assert "G1" in f and "G2" in f and "G3" in f

    def test_recovery_route_global(self):
        """fix_missing P6：中断恢复路由在 dispatch.md 落地。"""
        f = (SKILL_ROOT / "references" / "orchestrator" / "dispatch.md").read_text()
        assert "恢复路由" in f

    def test_geom_read_usage(self):
        """fix_missing P7：geom 字段→设计用途在 rooms.md 落地。"""
        f = (SKILL_ROOT / "references" / "design" / "rooms.md").read_text()
        assert "strip_area" in f and "exposure_m" in f and "deep_zone" in f

    def test_vocabulary_reference(self):
        """fix_missing P8：词表引用在 rooms.md 落地。"""
        f = (SKILL_ROOT / "references" / "design" / "rooms.md").read_text()
        assert "predicate_vocabulary" in f


class TestLinearExecutionContract:
    """2026-08-18 决议：v3 改主 agent 线性逐 zone 执行，废除二级 subagent 派发。

    契约：steps + 设计/编排规范 + SKILL.md + machine_contract 不得出现并行/subagent 派发指令；
    编排文档必须声明「线性」「逐 zone」。
    """

    def _scan_texts(self):
        texts = {"SKILL.md": (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")}
        for base in ("steps", *_SPEC_DIRS):
            for p in (SKILL_ROOT / base).rglob("*.md"):
                texts[str(p.relative_to(SKILL_ROOT))] = p.read_text(encoding="utf-8")
        texts["references/machine_contract.md"] = (
            SKILL_ROOT / "references" / "machine_contract.md").read_text(encoding="utf-8")
        return texts

    def test_no_subagent_dispatch_instructions(self):
        """零 subagent / 并行派发指令（二级派发已废除）。"""
        banned = ("subagent", "rooms-worker", "details-worker",
                  "task 派发", "并行派发", "并行派发 subagent")
        texts = self._scan_texts()
        for name, content in texts.items():
            for b in banned:
                assert b not in content, f"{name} 出现已废除的派发措辞: {b}"

    def test_linear_per_zone_declared(self):
        """编排文档声明线性逐 zone 模型。"""
        texts = self._scan_texts()
        dispatch = texts["references/orchestrator/dispatch.md"]
        assert "线性" in dispatch and "逐 zone" in dispatch
        assert "线性" in texts["SKILL.md"]
        assert "逐 zone" in texts["SKILL.md"]

    def test_prompt_loading_kept(self):
        """参考提示加载逻辑与逐 zone 任务包一致（include 链保留）。"""
        dispatch = self._scan_texts()["references/orchestrator/dispatch.md"]
        assert "include" in dispatch and "pack" in dispatch


class TestPatternsSeeds:
    """T50-8：patterns 种子可入库（reindex 扫描）。"""

    def test_room_patterns_five_files(self):
        rp = SKILL_ROOT / "references" / "room_patterns"
        for name in ("orientation.md", "wet_core.md", "circulation.md",
                     "capacity.md"):
            assert (rp / name).exists()

    def test_skeleton_patterns_three_types(self):
        bt = SKILL_ROOT / "references" / "building_types"
        for t in ("residence", "office", "retail"):
            assert (bt / t / "skeleton_patterns.md").exists()

    def test_patterns_reindexable(self, tmp_path):
        """patterns 种子能被 reindex 扫到（入库前置）。"""
        from goldlib.reindex import reindex
        db = tmp_path / "g.db"
        reindex(str(SKILL_ROOT / "references"), str(db))
        import sqlite3
        conn = sqlite3.connect(db)
        n = conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
        conn.close()
        assert n >= 5, f"应扫到 ≥5 条 pattern（实得 {n}）"


class TestSteps:
    """T51：steps 五份 + 零 docs/ 路径。"""

    def test_steps_five(self):
        steps = list((SKILL_ROOT / "steps").glob("step-*.md"))
        assert len(steps) == 5
        names = {s.name for s in steps}
        assert {"step-00-preprocess.md", "step-01-skeleton.md", "step-02-rooms.md",
                "step-03-details.md", "step-04-deliver.md"} <= names

    def test_steps_no_docs_path(self):
        for s in (SKILL_ROOT / "steps").glob("step-*.md"):
            content = s.read_text(encoding="utf-8")
            assert "docs/buildingplan" not in content, f"{s} 引用了 docs/"

    def test_steps_has_recovery_table(self):
        """step-04-deliver.md 有中断恢复路由表。"""
        f = (SKILL_ROOT / "steps" / "step-04-deliver.md").read_text()
        assert "恢复" in f or "中断" in f

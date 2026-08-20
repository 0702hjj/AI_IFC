"""translate_golden.py 测试（D36 金例 design_intent → plan.json 翻译）。"""

import json
from pathlib import Path

import pytest

from aiplan_tools.paths import REFS
from aiplan_tools.translate_golden import (
    translate_case,
    translate_intent,
    validate_translated,
)

GOLDEN = REFS / "golden"


def _load(case: str):
    d = GOLDEN / case
    intent = json.loads((d / "design_intent.json").read_text(encoding="utf-8"))
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    return intent, meta


class TestTranslateIntent:
    """design_intent + meta → plan.json（过 plan schema）。"""

    def test_res_2s4u_passes_schema(self):
        intent, meta = _load("residence/res_2s4u_std")
        plan, notes = translate_intent(intent, meta)
        errs = validate_translated(plan)
        assert errs == [], f"schema 错误: {errs[:3]}"

    def test_outline_mm_structure(self):
        """outline_mm 多块 ring 结构（outer/holes/arcs）。"""
        intent, meta = _load("residence/res_2s4u_std")
        plan, _ = translate_intent(intent, meta)
        outline = plan["zones"][0]["outline_mm"]
        assert len(outline) >= 1
        outer = outline[0]["outer"]
        assert "vertices" in outer and len(outer["vertices"]) >= 3

    def test_core_rings_and_anchor_array(self):
        """多核：core=ring 数组（无 id/anchor——契约对齐），core_anchor_mm=锚点数组。"""
        intent, meta = _load("residence/res_2s4u_std")
        plan, _ = translate_intent(intent, meta)
        z = plan["zones"][0]
        assert isinstance(z["core"], list) and len(z["core"]) == 2
        for ring in z["core"]:
            assert set(ring.keys()) <= {"vertices", "arcs"}  # 无 id/anchor 残留
        assert isinstance(z["core_anchor_mm"], list)
        assert isinstance(z["core_anchor_mm"][0], list)  # 锚点数组

    def test_retail_arcs_preserved(self):
        """retail_mall_01：4 个幕墙圆角真弧保留（at/center/radius/a0/a1）。"""
        intent, meta = _load("retail/retail_mall_01")
        plan, _ = translate_intent(intent, meta)
        outer = plan["zones"][0]["outline_mm"][0]["outer"]
        arcs = outer.get("arcs", [])
        assert len(arcs) == 4
        for a in arcs:
            assert {"at", "center", "radius"} <= set(a.keys())
            assert a["radius"] > 1000  # mm 单位（radius_m×1000）

    def test_retail_holes_preserved(self):
        """retail_mall_01：中庭孔洞保留。"""
        intent, meta = _load("retail/retail_mall_01")
        plan, _ = translate_intent(intent, meta)
        holes = plan["zones"][0]["outline_mm"][0]["holes"]
        assert len(holes) == 1

    def test_required_fields_filled(self):
        """plan required 字段齐（version/project/site/zones）+ zone required 齐。"""
        intent, meta = _load("single_family/floorplan_structure")
        plan, _ = translate_intent(intent, meta)
        assert {"version", "project", "site", "zones"} <= set(plan.keys())
        z = plan["zones"][0]
        assert {"id", "function", "floors", "floor_height_mm",
                "outline_mm", "program"} <= set(z.keys())

    def test_notes_flag_placeholders(self):
        """占位字段在 notes 标注（site/floors/program 非金例数据）。"""
        intent, meta = _load("residence/res_2s4u_std")
        _, notes = translate_intent(intent, meta)
        assert any("占位" in n or "缺省" in n for n in notes)


class TestTranslateCase:
    """单金例翻译 + 坐标轴报告。"""

    def test_case_writes_plan_json(self, tmp_path):
        """翻译落盘 plan.json（schema 过时）——用临时目录复制金例避免污染。"""
        import shutil
        src = GOLDEN / "residence" / "res_2s4u_std"
        dst = tmp_path / "res_2s4u_std"
        shutil.copytree(src, dst)
        r = translate_case(dst)
        assert r["schema_errors"] == []
        assert (dst / "plan.json").exists()
        plan = json.loads((dst / "plan.json").read_text(encoding="utf-8"))
        assert plan["zones"][0]["outline_mm"]

    def test_coord_report_flags_transform(self):
        """坐标报告：intent 归一化 vs source.dxf 原生——平移量/跨差可比。"""
        r = translate_case(GOLDEN / "residence" / "res_2s4u_std", write=False)
        cr = r["coord_report"]
        assert cr["intent_bbox"] is not None
        if cr["source_bbox"] is not None:
            # 金例 intent 是归一化坐标（原点附近），source 是大地坐标——必须不同
            assert abs(cr["source_bbox"][0] - cr["intent_bbox"][0]) > 1000

    def test_all_golden_cases_translate(self):
        """全部金例可翻译且过 schema（批量回归）。"""
        cases = sorted(p.parent for p in GOLDEN.rglob("design_intent.json"))
        assert cases, "金例目录为空"
        for case_dir in cases:
            r = translate_case(case_dir, write=False)
            assert r["schema_errors"] == [], \
                f"{r['case_id']}: {r['schema_errors'][:2]}"


class TestSourceDxfMissing:
    """source.dxf 缺失时优雅降级（W-0050：aiplan 侧 source.dxf 已删，诊断可选）。"""

    def test_translate_without_source_dxf(self, tmp_path):
        import shutil
        src = GOLDEN / "residence" / "res_2s4u_std"
        case = tmp_path / "res_2s4u_std"
        case.mkdir()
        shutil.copy(src / "design_intent.json", case)
        shutil.copy(src / "meta.json", case)
        result = translate_case(case, write=False)
        assert result["schema_errors"] == []
        report = result["coord_report"]
        assert report["source_bbox"] is None
        assert "跳过坐标对比" in report["note"]
        assert report["intent_bbox"] is not None

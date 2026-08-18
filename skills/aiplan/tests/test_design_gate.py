"""design_gate 设计质量门禁测试（把"可选流程"升级为强制门禁，2026-08-11）。

验收：
- 无 design_rationale → FAIL（必填）
- design_rationale 不引 derive 事实字段 → FAIL
- design_rationale 引用真实 derive 字段 → PASS
- 默认矩形（长板 + 全矩形 outline）→ warning（不 FAIL）
- 方形地块矩形 outline → 无 warning（合理矩形不误伤）
"""

from aiplan_tools.design_gate import validate_design_quality, _is_simple_rect_fills_buildable
from aiplan_tools.derive import derive_facts


# 基础 plan 骨架（80×40m 长板地块，setbacks 各 4-6m）
def _base_plan(design_rationale=None, zones=None):
    plan = {
        "version": 3,
        "project": "测试",
        "site": {
            "lot_polygon_mm": [[0, 0], [80000, 0], [80000, 40000], [0, 40000]],
            "origin": "lot_southwest",
            "setbacks_mm": {"front": 6000, "rear": 4000, "left": 4000, "right": 4000},
        },
        "zones": zones or [],
    }
    if design_rationale is not None:
        plan["design_rationale"] = design_rationale
    return plan


RECT_ZONE = {
    "id": "z", "function": "residence", "floors": {"from": 1, "to": 5},
    "floor_height_mm": 3000,
    "outline_mm": [{"outer": [[4000, 4000], [76000, 4000], [76000, 36000], [4000, 36000]], "holes": [], "arcs": []}],
    "core": [[35000, 15000], [45000, 15000], [45000, 25000], [35000, 25000]],
    "core_anchor_mm": [40000, 20000],
    "program": [{"room": "unit", "count": 1, "area_sqm": [100, 120]}],
}


# ── 反例：无 design_rationale → FAIL ─────────────────────────

def test_no_design_rationale_fails():
    plan = _base_plan(zones=[RECT_ZONE])  # 无 design_rationale
    errors, _ = validate_design_quality(plan)
    assert any("design_rationale 必填" in e for e in errors)


def test_empty_design_rationale_fails():
    plan = _base_plan(design_rationale="   ", zones=[RECT_ZONE])  # 空白
    errors, _ = validate_design_quality(plan)
    assert any("design_rationale 必填" in e for e in errors)


# ── 反例：design_rationale 不引 derive 字段 → FAIL ─────────────

def test_rationale_no_derive_reference_fails():
    plan = _base_plan(
        design_rationale="我觉得板式比较好，朝向也好",
        zones=[RECT_ZONE],
    )
    errors, _ = validate_design_quality(plan)
    assert any("必须引用 ≥1 个 derive 事实字段" in e for e in errors)


# ── 正例：引用真实 derive 字段 → PASS ─────────────────────────

def test_rationale_with_derive_reference_passes():
    plan = _base_plan(
        design_rationale="aspect_ratio=2.0 且 exposure_m.S=72m → 板式贴南最大化南向采光",
        zones=[RECT_ZONE],
    )
    errors, _ = validate_design_quality(plan)
    assert errors == []


def test_rationale_references_multiple_fields():
    plan = _base_plan(
        design_rationale="aspect_ratio=2.0 + deep_zone_ratio=0.5 → 板式双面 + 核心筒居中吃暗区",
        zones=[RECT_ZONE],
    )
    errors, _ = validate_design_quality(plan)
    assert errors == []


# ── 默认矩形检测（warning，不 FAIL）─────────────────────────────

def test_simple_rect_on_long_slab_warns():
    """长板地块（aspect_ratio=2.0）+ 全矩形 outline → warning。"""
    plan = _base_plan(
        design_rationale="aspect_ratio=2.0 → 板式",
        zones=[RECT_ZONE],
    )
    errors, warnings = validate_design_quality(plan)
    assert errors == []  # 不 FAIL
    assert any("疑似默认矩形" in w for w in warnings)


def test_rect_with_hole_no_warning():
    """矩形带孔洞（庭院）→ 不是默认矩形，无 warning。"""
    zone_with_hole = dict(RECT_ZONE)
    zone_with_hole["outline_mm"] = [{
        "outer": [[4000, 4000], [76000, 4000], [76000, 36000], [4000, 36000]],
        "holes": [[[30000, 15000], [50000, 15000], [50000, 25000], [30000, 25000]]],
        "arcs": [],
    }]
    plan = _base_plan(design_rationale="aspect_ratio=2.0 → 板式", zones=[zone_with_hole])
    errors, warnings = validate_design_quality(plan)
    assert errors == []
    assert not any("疑似默认矩形" in w for w in warnings)


def test_square_lot_rect_no_warning():
    """方形地块（aspect_ratio≈1）+ 矩形 outline → 合理矩形，无 warning。"""
    plan = _base_plan(design_rationale="aspect_ratio=1.0 → 方形塔楼", zones=[RECT_ZONE])
    # 方形地块
    plan["site"]["lot_polygon_mm"] = [[0, 0], [40000, 0], [40000, 40000], [0, 40000]]
    facts = derive_facts(plan["site"]["lot_polygon_mm"], plan["site"]["setbacks_mm"])
    assert facts["aspect_ratio"] == 1.0  # 方形
    assert not _is_simple_rect_fills_buildable(plan, facts)  # 不标


# ── 辅助函数 ──────────────────────────────────────────────────

def test_derive_fact_fields_match_derive_output():
    """DERIVE_FACT_FIELDS 与 derive_facts 产出键对齐（防漂移）。"""
    from aiplan_tools.design_gate import DERIVE_FACT_FIELDS
    facts = derive_facts([[0, 0], [80000, 0], [80000, 40000], [0, 40000]])
    for f in DERIVE_FACT_FIELDS:
        base = f.rstrip("0123456789")  # exposure_m / bounding_box 等
        assert base in facts or f in facts, f"字段 {f} 不在 derive 产出里"

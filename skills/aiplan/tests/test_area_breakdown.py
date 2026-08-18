"""面积分块测试：area_breakdown（wrapping 核心计算）。

验收：
- polygon_area_m2: shoelace 面积正确（60×40m 矩形 = 2400㎡）
- block_area_sqm: program 大类条目按 block 分组汇总（区间取中值）
- breakdown: 各 block 面积 + 占比
- check_allocation: 超总面积 → 报；<80% → 报；合理 → 过
- area_standards 并入 cases.json：ratio_standards 词表正确
- load_standard: 读 building_types/<type>.cases.json 的 ratio_standards
"""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
from aiplan_tools import area_breakdown as ab  # noqa: E402


# ── polygon_area_m2 ───────────────────────────────────────────────────────


def test_polygon_area_rectangle():
    """60×40m 矩形（mm 输入）→ 2400㎡。"""
    poly = [[0, 0], [60000, 0], [60000, 40000], [0, 40000]]
    assert ab.polygon_area_m2(poly) == pytest.approx(2400.0)


def test_polygon_area_clockwise_same():
    """顺/逆时针面积相同（取绝对值）。"""
    poly_cw = [[0, 0], [0, 40000], [60000, 40000], [60000, 0]]
    assert ab.polygon_area_m2(poly_cw) == pytest.approx(2400.0)


def test_polygon_area_tower():
    """plan_demo tower 24×18m → 432㎡。"""
    poly = [[18000, 22000], [42000, 22000], [42000, 40000], [18000, 40000]]
    assert ab.polygon_area_m2(poly) == pytest.approx(432.0)


# ── block_area_sqm / breakdown ────────────────────────────────────────────


def test_block_area_sqm_range_midpoint():
    """area_sqm 区间取中值 × count。"""
    program = [{"room": "core", "count": 1, "area_sqm": [400, 600]}]
    assert ab.block_area_sqm(program, "core") == pytest.approx(500.0)


def test_block_area_sqm_prefix_aggregation():
    """前缀聚合：units 匹配 unit_3br/unit_2br（具体户型 → 聚合 block）。"""
    program = [
        {"room": "unit_3br", "count": 2, "area_sqm": [92, 98]},
        {"room": "unit_2br", "count": 2, "area_sqm": [70, 78]},
    ]
    assert ab.block_area_sqm(program, "units") == pytest.approx(95.0 * 2 + 74.0 * 2)


def test_block_area_sqm_count_list():
    """count 区间取上界。"""
    program = [{"room": "shop", "count": [10, 20], "area_sqm": [80, 120]}]
    assert ab.block_area_sqm(program, "shop") == pytest.approx(100.0 * 20)


def test_block_area_sqm_no_area_skipped():
    """无 area_sqm 的条目（corridor 只给 min_width）不算面积。"""
    program = [{"room": "corridor", "count": 1, "min_width_mm": 2400}]
    assert ab.block_area_sqm(program, "corridor") == 0.0


def test_breakdown_residence_blocks():
    """residence 分块：core+corridor+units（前缀聚合 unit_3br→units）。"""
    program = [
        {"room": "core", "count": 1, "area_sqm": [400, 500]},
        {"room": "corridor", "count": 1, "area_sqm": [600, 700]},
        {"room": "unit_3br", "count": 2, "area_sqm": [92, 98]},
    ]
    bd = ab.breakdown(program, "residence")
    blocks = {b["block"]: b for b in bd["blocks"]}
    assert "core" in blocks and "units" in blocks
    # core 450 + corridor 650 + units(unit_3br 2×95=190) = 1290
    assert bd["total_block_sqm"] == pytest.approx(450 + 650 + 190)
    assert blocks["units"]["area_sqm"] == pytest.approx(190.0)


def test_load_standard_blocks():
    """cases.json 的 ratio_standards 各 type 的 block 词表加载正确。"""
    res = ab.load_standard("residence")
    assert res and [b["block"] for b in res["blocks"]] == ["core", "corridor", "units", "balcony"]
    off = ab.load_standard("office")
    assert off and "open_office" in [b["block"] for b in off["blocks"]]
    ret = ab.load_standard("retail")
    assert ret and "atrium" in [b["block"] for b in ret["blocks"]]


def test_load_standard_missing_returns_none():
    """无标准文件 → None。"""
    assert ab.load_standard("hospital") is None


# ── check_allocation ──────────────────────────────────────────────────────


def test_check_allocation_ok():
    """block 合计 ≈ 总面积（1% 容差内）→ 通过。"""
    blocks = [{"block": "core", "area_sqm": 450}, {"block": "units", "area_sqm": 1900}]
    assert ab.check_allocation(2400, blocks) == []


def test_check_allocation_over_total():
    """block 合计超总面积 → 报。"""
    blocks = [{"block": "core", "area_sqm": 1000}, {"block": "units", "area_sqm": 2000}]
    errs = ab.check_allocation(2400, blocks)
    assert any("超" in e for e in errs)


def test_check_allocation_under_80pct():
    """block 合计 <80% 总面积 → 报（有大块未分块）。"""
    blocks = [{"block": "core", "area_sqm": 300}]
    errs = ab.check_allocation(2400, blocks)
    assert any("80%" in e for e in errs)


def test_check_allocation_zero_total():
    """总面积 ≤0 → 报。"""
    assert ab.check_allocation(0, [{"block": "core", "area_sqm": 100}]) != []


def test_summarize_cross_zone():
    """summarize：跨 zone 合并同 block（bim 汇总视图）。"""
    za1 = [{"block": "core", "ratio": [0.10, 0.14], "area_sqm": [400, 560]}]
    za2 = [{"block": "core", "ratio": [0.08, 0.12], "area_sqm": [440, 660]}]
    out = ab.summarize([za1, za2])
    assert out["total_area_sqm"] == pytest.approx((400 + 560 + 440 + 660) / 2)
    assert len(out["blocks"]) == 1
    core = out["blocks"][0]
    assert core["block"] == "core"
    assert core["area_sqm"] == pytest.approx([840.0, 1220.0])


def test_summarize_multi_block():
    """summarize：多 block 汇总。"""
    za1 = [{"block": "core", "ratio": [0.1, 0.14], "area_sqm": [400, 560]}]
    za2 = [{"block": "units", "ratio": [0.65, 0.78], "area_sqm": [2600, 3120]}]
    out = ab.summarize([za1, za2])
    blocks = {b["block"]: b for b in out["blocks"]}
    assert "core" in blocks and "units" in blocks
    assert out["total_area_sqm"] == pytest.approx((480 + 2860))


def test_summarize_empty():
    """summarize：空输入 → 空汇总。"""
    out = ab.summarize([])
    assert out["total_area_sqm"] == 0.0
    assert out["blocks"] == []

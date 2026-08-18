"""aiplan-geom 测试：轮廓生成 + 校验 + 对齐。

验收：
- check/align：轮廓合法性 + 跨层核对齐（generate/construct 已删 2026-08-17）
- tower_on_podium: 塔楼⊆裙房、落位按 align
- check_outline: 合法通过 / 超地块 / 退线 / 锚点出轮廓 / 自相交 各反例
- check_alignment: 塔楼⊆裙房通过 / 超出报错
- 确定性：同输入同输出
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from shapely.geometry import Point, Polygon

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from aiplan_tools import geom  # noqa: E402

GEN_CMD = [str(HERE.parent / ".venv" / "bin" / "aiplan-geom")]


# ── generate ──────────────────────────────────────────────────────────────
def test_check_valid():
    outline = [{"outer": [[4000, 4000], [56000, 4000], [56000, 34000], [4000, 34000]],
                "holes": [], "arcs": []}]
    lot = [[0, 0], [60000, 0], [60000, 40000], [0, 40000]]
    sb = {"front": 6000, "rear": 4000, "left": 4000, "right": 4000}
    assert geom.check_outline(outline, lot, sb, [28000, 18000]) == []


def test_check_anchor_outside():
    outline = [{"outer": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]],
                "holes": [], "arcs": []}]
    errs = geom.check_outline(outline, core_anchor_mm=[70000, 50000])
    assert any("锚点" in e for e in errs)


def test_check_exceeds_lot():
    outline = [{"outer": [[0, 0], [70000, 0], [70000, 40000], [0, 40000]],
                "holes": [], "arcs": []}]
    lot = [[0, 0], [60000, 0], [60000, 40000], [0, 40000]]
    errs = geom.check_outline(outline, lot_polygon_mm=lot)
    assert any("超出地块" in e for e in errs)


def test_check_setback_violation():
    outline = [{"outer": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]],
                "holes": [], "arcs": []}]
    lot = [[0, 0], [60000, 0], [60000, 40000], [0, 40000]]
    sb = {"front": 6000, "rear": 4000, "left": 4000, "right": 4000}
    errs = geom.check_outline(outline, lot, sb)
    assert any("退线" in e for e in errs)


def test_check_invalid_geometry():
    """自相交多边形 → 报无效几何。"""
    bowtie = [[0, 0], [60000, 40000], [60000, 0], [0, 40000]]
    outline = [{"outer": bowtie, "holes": [], "arcs": []}]
    errs = geom.check_outline(outline)
    assert errs  # 无效几何必报


# ── check_alignment ───────────────────────────────────────────────────────


def test_align_tower_in_podium():
    zones = [
        {"id": "podium", "outline_mm": [{"outer": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]],
                                          "holes": [], "arcs": []}]},
        {"id": "tower", "position": {"on": "podium"},
         "outline_mm": [{"outer": [[18000, 22000], [42000, 22000], [42000, 40000], [18000, 40000]],
                          "holes": [], "arcs": []}]},
    ]
    assert geom.check_alignment(zones) == []


def test_align_tower_exceeds_podium():
    zones = [
        {"id": "podium", "outline_mm": [{"outer": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]],
                                          "holes": [], "arcs": []}]},
        {"id": "tower", "position": {"on": "podium"},
         "outline_mm": [{"outer": [[0, 0], [70000, 0], [70000, 40000], [0, 40000]],
                          "holes": [], "arcs": []}]},
    ]
    errs = geom.check_alignment(zones)
    assert any("超出宿主" in e for e in errs)


def test_align_missing_host():
    zones = [
        {"id": "tower", "position": {"on": "ghost"},
         "outline_mm": [{"outer": [[0, 0], [10000, 0], [10000, 10000], [0, 10000]],
                          "holes": [], "arcs": []}]},
    ]
    errs = geom.check_alignment(zones)
    assert any("不存在" in e for e in errs)


# ── CLI ───────────────────────────────────────────────────────────────────
def test_cli_check_exit_codes():
    ok = subprocess.run(GEN_CMD + ["check",
        "--outline", '[{"outer":[[4000,4000],[56000,4000],[56000,34000],[4000,34000]],"holes":[],"arcs":[]}]',
        "--lot", '[[0,0],[60000,0],[60000,40000],[0,40000]]',
        "--setbacks", '{"front":6000,"rear":4000,"left":4000,"right":4000}',
        "--anchor", '[28000,18000]'], capture_output=True, text=True)
    assert ok.returncode == 0

    bad = subprocess.run(GEN_CMD + ["check",
        "--outline", '[{"outer":[[0,0],[60000,0],[60000,40000],[0,40000]],"holes":[],"arcs":[]}]',
        "--anchor", '[70000,50000]'], capture_output=True, text=True)
    assert bad.returncode == 1


def test_check_alignment_core_anchor_consistent():
    """S3: 核心筒锚点一致的 zone 通过对齐校验。"""
    from aiplan_tools.geom import check_alignment
    zones = [
        {"id": "residence", "core_anchor_mm": [15000, 11000],
         "outline_mm": [{"outer": [[6000, 6000], [24000, 6000], [24000, 19000], [6000, 19000]], "holes": [], "arcs": []}]},
        {"id": "t10", "core_anchor_mm": [15000, 11000],
         "outline_mm": [{"outer": [[8000, 6000], [22000, 6000], [22000, 17000], [8000, 17000]], "holes": [], "arcs": []}]},
    ]
    assert check_alignment(zones) == []


def test_check_alignment_core_anchor_mismatch():
    """S3: 核心筒锚点不一致 → 报错（分裂 zone 必须跨层对齐）。"""
    from aiplan_tools.geom import check_alignment
    zones = [
        {"id": "residence", "core_anchor_mm": [15000, 11000],
         "outline_mm": [{"outer": [[6000, 6000], [24000, 6000], [24000, 19000], [6000, 19000]], "holes": [], "arcs": []}]},
        {"id": "t10", "core_anchor_mm": [18000, 14000],
         "outline_mm": [{"outer": [[8000, 6000], [22000, 6000], [22000, 17000], [8000, 17000]], "holes": [], "arcs": []}]},
    ]
    errs = check_alignment(zones)
    assert any("核心筒锚点不一致" in e for e in errs)


# ── 几何构造引擎（图元 + 操作）───────
def test_polygon_area_m2_with_holes():
    """面积计算扣孔洞（中庭户型面积 = outer - hole）。"""
    from aiplan_tools.area_breakdown import polygon_area_m2
    block = {"outer": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]],
             "holes": [[[14000, 11000], [14000, 19000], [26000, 19000], [26000, 11000]]],
             "arcs": []}
    area = polygon_area_m2(block)
    assert abs(area - 1104) < 2  # 40×30 - 12×8 = 1200-96


# ── v3.1 ring / 真弧（holes 与 outer 同等表达力）──────────────────
def test_zone_union_plain_hole_compat():
    """v3 直边孔简写（纯顶点数组）兼容不破。"""
    from aiplan_tools.geom import zone_union
    block = {"outer": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]],
             "holes": [[[14000, 11000], [14000, 19000], [26000, 19000], [26000, 11000]]],
             "arcs": []}
    assert abs(zone_union([block]).area / 1e6 - 1104) < 1
def test_check_hole_outside_outer_rejected():
    """孔洞超出外环 → 报（v3.1 新增校验）。"""
    from aiplan_tools.geom import check_outline
    block = {"outer": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]],
             "holes": [[[30000, 10000], [50000, 10000], [50000, 20000], [30000, 20000]]]}
    errs = check_outline([block])
    assert any("超出外环" in e for e in errs)


def test_check_anchor_in_circle_hole_rejected():
    """锚点落在真圆孔洞内 → 锚点出轮廓（孔洞已按真弧挖空）。"""
    from aiplan_tools.geom import check_outline
    # 真圆 ring 对象（3 顶点 + 3×120° 弧，内联构造——circle_ring 工厂已删）
    ring = {"vertices": [[26000, 15000], [20000, 21000], [14000, 15000]],
            "arcs": [{"at": 0, "center": [20000, 15000], "radius": 6000},
                     {"at": 1, "center": [20000, 15000], "radius": 6000},
                     {"at": 2, "center": [20000, 15000], "radius": 6000}]}
    block = {"outer": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]],
             "holes": [ring], "arcs": []}
    errs = check_outline([block], core_anchor_mm=[20000, 15000])
    assert any("锚点" in e for e in errs)


def test_outer_arc_true_area():
    """outer 带弧（曲面轮廓）：并集面积按真弧算（正方形 + 东侧半圆鼓出）。"""
    import math
    from aiplan_tools.geom import zone_union
    # 正方形 20000×20000（CCW），东边（顶点1→2）替换为直径=边长的外凸半圆
    block = {"outer": [[0, 0], [20000, 0], [20000, 20000], [0, 20000]],
             "holes": [],
             "arcs": [{"at": 1, "center": [20000, 10000], "radius": 10000, "a0": -90, "a1": 90}]}
    area_m2 = zone_union([block]).area / 1e6
    expect = 400 + math.pi * 10**2 / 2  # r=10m：400 + 50π ≈ 557.08
    assert abs(area_m2 - expect) < 5




# ── v3.1+ core 校验（统一 ring：与 outer/holes 同类型）──


def test_check_core_polygon_in_outline_ok():
    from aiplan_tools.geom import check_alignment
    zones = [{"id":"z","outline_mm":[{"outer":[[0,0],[60000,0],[60000,40000],[0,40000]]}],
              "core":[[27000,16000],[33000,16000],[33000,24000],[27000,24000]]}]
    assert check_alignment(zones) == []


def test_check_core_circle_in_outline_ok():
    from aiplan_tools.geom import check_alignment
    ring = {"vertices": [[33000, 20000], [30000, 23000], [27000, 20000]],
            "arcs": [{"at": 0, "center": [30000, 20000], "radius": 3000},
                     {"at": 1, "center": [30000, 20000], "radius": 3000},
                     {"at": 2, "center": [30000, 20000], "radius": 3000}]}
    zones = [{"id":"z","outline_mm":[{"outer":[[0,0],[60000,0],[60000,40000],[0,40000]]}],
              "core":ring}]
    assert check_alignment(zones) == []


def test_check_core_outside_outline_rejected():
    from aiplan_tools.geom import check_alignment
    zones = [{"id":"z","outline_mm":[{"outer":[[0,0],[60000,0],[60000,40000],[0,40000]]}],
              "core":[[50000,16000],[65000,16000],[65000,24000],[50000,24000]]}]
    errs = check_alignment(zones)
    assert any("核心筒" in e and "超出" in e for e in errs)


def test_check_core_mismatch_across_zones():
    from aiplan_tools.geom import check_alignment
    outline=[{"outer":[[0,0],[60000,0],[60000,40000],[0,40000]]}]
    zones=[{"id":"a","outline_mm":outline,"core":[[27000,16000],[33000,16000],[33000,24000],[27000,24000]]},
           {"id":"b","outline_mm":outline,"core":[[27000,16000],[33000,16000],[33000,20000],[27000,20000]]}]
    errs = check_alignment(zones)
    assert any("不一致" in e for e in errs)


# ── 2026-08-17 修复：多核数组 / 独立楼栋栈语义 / 全量 --zones ────────


def test_check_alignment_multicore_arrays():
    """多核数组（design_intent 结构）跨层对齐：同栈核位置一致 → 通过。"""
    from aiplan_tools.geom import check_alignment
    def core(cx, cy):
        return {"id": "c0", "path": {"rings": [{"edges": {
            "west": [[cx-2600, cy-3500], [cx-2600, cy+3500]],
            "north": [[cx-2600, cy+3500], [cx+2600, cy+3500]],
            "east": [[cx+2600, cy+3500], [cx+2600, cy-3500]],
            "south": [[cx+2600, cy-3500], [cx-2600, cy-3500]]}}]}}
    outl = [{"outer": [[0,0],[60000,0],[60000,40000],[0,40000]], "holes": [], "arcs": []}]
    zones = [
        {"id": "std",  "outline_mm": outl, "core": [core(15000,20000)]},
        {"id": "t10",  "outline_mm": outl, "core": [core(15000,20000)]},
    ]
    assert check_alignment(zones) == []


def test_check_alignment_multicore_mismatch():
    """多核数组同栈核错位 → 报错（点名 core id）。"""
    from aiplan_tools.geom import check_alignment
    def core(cx, cy):
        return {"id": "c0", "path": {"rings": [{"edges": {
            "west": [[cx-2600, cy-3500], [cx-2600, cy+3500]],
            "north": [[cx-2600, cy+3500], [cx+2600, cy+3500]],
            "east": [[cx+2600, cy+3500], [cx+2600, cy-3500]],
            "south": [[cx+2600, cy-3500], [cx-2600, cy-3500]]}}]}}
    outl = [{"outer": [[0,0],[60000,0],[60000,40000],[0,40000]], "holes": [], "arcs": []}]
    zones = [
        {"id": "std",  "outline_mm": outl, "core": [core(15000,20000)]},
        {"id": "t10",  "outline_mm": outl, "core": [core(20000,20000)]},
    ]
    errs = check_alignment(zones)
    assert any("c0" in e and "不一致" in e for e in errs)


def test_check_alignment_independent_buildings_not_compared():
    """独立楼栋（轮廓不重叠、无 position.on）核不互比——两排住宅语义。"""
    from aiplan_tools.geom import check_alignment
    south = {"id": "south", "outline_mm": [{"outer": [[0,0],[56000,0],[56000,15000],[0,15000]]}],
             "core": [[20000,5000],[23000,5000],[23000,9000],[20000,9000]]}
    north = {"id": "north", "outline_mm": [{"outer": [[10000,80000],[66000,80000],[66000,95000],[10000,95000]]}],
             "core": [[30000,85000],[33000,85000],[33000,89000],[30000,89000]]}
    assert check_alignment([south, north]) == []


def test_check_alignment_multi_core_normalized_output():
    """normalize 产物（core=[{vertices,arcs}] 无 id）→ 同栈按 core<i> 对齐。"""
    from aiplan_tools.geom import check_alignment
    outl = [{"outer": [[0,0],[60000,0],[60000,40000],[0,40000]]}]
    def ring(x0,y0,x1,y1):
        return {"vertices": [[x0,y0],[x1,y0],[x1,y1],[x0,y1]], "arcs": []}
    zones = [
        {"id": "std", "outline_mm": outl,
         "core": [ring(12000,15000,15000,19000), ring(40000,15000,43000,19000)]},
        {"id": "ph",  "outline_mm": outl,
         "core": [ring(12000,15000,15000,19000), ring(40000,15000,43000,19000)]},
    ]
    assert check_alignment(zones) == []


def test_check_alignment_ph_core_moved_rejected():
    """退台 zone 核移动（同栈）→ 报错。"""
    from aiplan_tools.geom import check_alignment
    outl = [{"outer": [[0,0],[60000,0],[60000,40000],[0,40000]]}]
    def ring(x0,y0,x1,y1):
        return {"vertices": [[x0,y0],[x1,y0],[x1,y1],[x0,y1]], "arcs": []}
    zones = [
        {"id": "std", "outline_mm": outl,
         "core": [ring(12000,15000,15000,19000)]},
        {"id": "ph", "outline_mm": outl,
         "core": [ring(16000,15000,19000,19000)]},
    ]
    errs = check_alignment(zones)
    assert any("不一致" in e for e in errs)

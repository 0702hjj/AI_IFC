"""normalize 统一 path 测试（2026-08-11 统一 path 重构）。

design_intent v2：form 统一为 path（outer: base+segments / holes），取消 5 种 form 分类 + axis_grid。
验收：
- 基础 path（base 顶点）→ outline_mm ring
- 方向归一化（CW 输入 → 外环自动转 CCW）
- segment recess（凹进）/ projection（凸出）展开
- segment arc（圆角）→ ring with arcs
- holes（孔洞）→ CW 内环
- core placement（语义定位）→ core polygon + anchor
- core path（直接顶点）
- spatial_relations on → position
- 错误：孔洞在外环外 / arc 顶点越界 / segment 边未找到
"""

import pytest
from aiplan_tools.normalize import normalize, NormalizeError


# ── 基础 path ──────────────────────────────────────────────────

def test_basic_rect_path():
    """基础矩形 path → outline_mm ring（outer 是 ring object）。"""
    intent = {
        "version": 2, "project": "t",
        "zones": [{"id": "z", "form": {"path": {
            "outer": {"base": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]]}
        }}}],
    }
    result = normalize(intent)
    outer = result["zones"][0]["outline_mm"][0]["outer"]
    assert isinstance(outer, dict)
    assert "vertices" in outer and "arcs" in outer
    assert len(outer["vertices"]) == 4


def test_direction_normalization_cw_to_ccw():
    """CW 输入的外环 → 自动转 CCW（方向归一化）。"""
    from aiplan_tools.normalize import _signed_area
    # CW 顶点（顺时针）
    cw_verts = [[0, 0], [0, 30000], [40000, 30000], [40000, 0]]
    intent = {
        "version": 2, "project": "t",
        "zones": [{"id": "z", "form": {"path": {"outer": {"base": cw_verts}}}}],
    }
    result = normalize(intent)
    outer = result["zones"][0]["outline_mm"][0]["outer"]
    assert _signed_area(outer["vertices"]) > 0  # 外环应 CCW（有向面积>0）


def test_hole_direction_cw():
    """孔洞自动转 CW（内环方向与外环相反）。"""
    from aiplan_tools.normalize import _signed_area
    intent = {
        "version": 2, "project": "t",
        "zones": [{"id": "z", "form": {"path": {
            "outer": {"base": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]]},
            "holes": [{"base": [[15000, 10000], [15000, 20000], [25000, 20000], [25000, 10000]]}],
        }}}],
    }
    result = normalize(intent)
    hole = result["zones"][0]["outline_mm"][0]["holes"][0]
    assert _signed_area(hole["vertices"]) < 0  # 孔洞应 CW（有向面积<0）


# ── segment recess/projection ──────────────────────────────────

def test_recess_expands_notch():
    """recess 在南边 offset 处凹进 → 顶点数增加 + 凹口。"""
    intent = {
        "version": 2, "project": "t",
        "zones": [{"id": "z", "form": {"path": {"outer": {
            "base": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]],
            "segments": [{"type": "recess", "at_edge": "S", "offset_m": 15, "width_m": 5, "depth_m": 2.5}],
        }}}}],
    }
    result = normalize(intent)
    verts = result["zones"][0]["outline_mm"][0]["outer"]["vertices"]
    assert len(verts) == 4 + 4  # 矩形 4 + recess 插入 4 顶点 = 8
    # 凹进顶点 y>0（向内凹）
    notch_pts = [v for v in verts if 0 < v[1] < 30000 and 14000 < v[0] < 21000]
    assert any(v[1] == 2500 for v in notch_pts)  # 凹进深度 2.5m


def test_projection_expands_bump():
    """projection 在北边凸出 → 顶点凸出到 y>30000。"""
    intent = {
        "version": 2, "project": "t",
        "zones": [{"id": "z", "form": {"path": {"outer": {
            "base": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]],
            "segments": [{"type": "projection", "at_edge": "N", "offset_m": 10, "width_m": 4, "depth_m": 1.5}],
        }}}}],
    }
    result = normalize(intent)
    verts = result["zones"][0]["outline_mm"][0]["outer"]["vertices"]
    assert any(v[1] > 30000 for v in verts)  # 凸出到北边外


def test_multi_recess_same_edge():
    """同边多处 recess（多段 path 兼容性）——同一条边放多个凹进，normalize 一次性正确展开。"""
    intent = {
        "version": 2, "project": "t",
        "zones": [{"id": "z", "form": {"path": {"outer": {
            "base": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]],
            "segments": [
                {"type": "recess", "at_edge": "S", "offset_m": 5, "width_m": 3, "depth_m": 2},
                {"type": "recess", "at_edge": "S", "offset_m": 20, "width_m": 3, "depth_m": 2},
            ],
        }}}}],
    }
    result = normalize(intent)
    verts = result["zones"][0]["outline_mm"][0]["outer"]["vertices"]
    # 矩形 4 + 两个 recess 各插入 4 顶点 = 12
    assert len(verts) == 12
    # 两个凹进都在南边（y 从 0 凹到 2000）
    notch_pts = [v for v in verts if v[1] == 2000]
    assert len(notch_pts) == 4  # 两个凹进各 2 个底点


def test_mixed_segments_same_edge():
    """同边 recess + projection 混合（多段 path 兼容性）。"""
    intent = {
        "version": 2, "project": "t",
        "zones": [{"id": "z", "form": {"path": {"outer": {
            "base": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]],
            "segments": [
                {"type": "recess", "at_edge": "S", "offset_m": 5, "width_m": 3, "depth_m": 2},
                {"type": "projection", "at_edge": "N", "offset_m": 10, "width_m": 4, "depth_m": 1.5},
                {"type": "recess", "at_edge": "S", "offset_m": 20, "width_m": 3, "depth_m": 2},
            ],
        }}}}],
    }
    result = normalize(intent)
    verts = result["zones"][0]["outline_mm"][0]["outer"]["vertices"]
    # 南边 2 个 recess（y=2000 凹点）+ 北边 1 个 projection（y>30000 凸点）
    assert len([v for v in verts if v[1] == 2000]) == 4   # 2 个 recess 各 2 底点
    assert any(v[1] > 30000 for v in verts)               # projection 凸出


# ── segment arc ────────────────────────────────────────────────

def test_arc_produces_ring_arcs():
    """arc segment → outer ring 带 arcs（顶点倒圆角）。"""
    intent = {
        "version": 2, "project": "t",
        "zones": [{"id": "z", "form": {"path": {"outer": {
            "base": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]],
            "segments": [{"type": "arc", "at_vertex": 1, "radius_m": 6}],
        }}}}],
    }
    result = normalize(intent)
    outer = result["zones"][0]["outline_mm"][0]["outer"]
    assert len(outer["arcs"]) == 1
    assert outer["arcs"][0]["radius"] == 6000
    assert len(outer["vertices"]) == 5  # 4 顶点倒 1 角 → 5


def test_multi_arc_at_indices_shift():
    """多角倒圆：后做的 fillet 插入点后，先记录的 arc.at 必须后移，否则 densify 自交。"""
    from shapely.geometry import Polygon
    intent = {
        "version": 2, "project": "t",
        "zones": [{"id": "z", "form": {"path": {"outer": {
            "base": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]],
            "segments": [
                {"type": "arc", "at_vertex": 0, "radius_m": 4},
                {"type": "arc", "at_vertex": 1, "radius_m": 4},
                {"type": "arc", "at_vertex": 2, "radius_m": 4},
                {"type": "arc", "at_vertex": 3, "radius_m": 4},
            ],
        }}}}],
    }
    result = normalize(intent)
    outer = result["zones"][0]["outline_mm"][0]["outer"]
    assert len(outer["arcs"]) == 4
    assert [a["at"] for a in outer["arcs"]] == [0, 2, 4, 6]
    assert Polygon(outer["vertices"]).is_valid


def test_arc_then_recess_order():
    """arc（at_vertex）+ recess（at_edge）混合——arc 先做（下标不错位）。"""
    intent = {
        "version": 2, "project": "t",
        "zones": [{"id": "z", "form": {"path": {"outer": {
            "base": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]],
            "segments": [
                {"type": "recess", "at_edge": "S", "offset_m": 15, "width_m": 5, "depth_m": 2.5},
                {"type": "arc", "at_vertex": 2, "radius_m": 6},  # 东北角
            ],
        }}}}],
    }
    result = normalize(intent)
    outer = result["zones"][0]["outline_mm"][0]["outer"]
    assert len(outer["arcs"]) == 1  # arc 生效
    assert len(outer["vertices"]) > 4  # recess 也生效


# ── core ───────────────────────────────────────────────────────

def test_core_placement():
    """core placement（region+extent）→ core polygon + anchor。"""
    intent = {
        "version": 2, "project": "t",
        "zones": [{"id": "z",
                   "form": {"path": {"outer": {"base": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]]}}},
                   "core": {"placement": {"region": "center", "extent_w_m": 10, "extent_d_m": 6}}}],
    }
    result = normalize(intent)
    z = result["zones"][0]
    assert "core" in z and "core_anchor_mm" in z
    assert z["core_anchor_mm"] == [20000, 15000]  # 居中


def test_core_path_direct():
    """core 直接 path（顶点）→ core polygon + anchor（质心）。"""
    intent = {
        "version": 2, "project": "t",
        "zones": [{"id": "z",
                   "form": {"path": {"outer": {"base": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]]}}},
                   "core": {"path": {"outer": {"base": [[18000, 12000], [22000, 12000], [22000, 18000], [18000, 18000]]}}}}],
    }
    result = normalize(intent)
    z = result["zones"][0]
    assert z["core_anchor_mm"] == [20000, 15000]  # 质心


# ── spatial_relations ──────────────────────────────────────────

def test_spatial_relations_on():
    """spatial_relations rel=on → position{on,align}。"""
    intent = {
        "version": 2, "project": "t",
        "zones": [
            {"id": "podium", "form": {"path": {"outer": {"base": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]]}}}},
            {"id": "tower", "form": {"path": {"outer": {"base": [[18000, 22000], [42000, 22000], [42000, 40000], [18000, 40000]]}}}},
        ],
        "spatial_relations": [{"from": "tower", "rel": "on", "to": "podium", "align": "north_center"}],
    }
    result = normalize(intent)
    tower = next(z for z in result["zones"] if z["id"] == "tower")
    assert tower["position"] == {"on": "podium", "align": "north_center"}


def test_zone_on_host_auto_aligned_into_host():
    """rel=on 塔楼坐标在宿主外 → normalize 按 align 平移落进宿主（双塔场景回归）。

    塔楼 outline 手写绝对坐标与裙房脱节（如 cad S0 check_alignment FAIL），
    normalize 应把塔楼平移进宿主，产出的 plan 满足塔楼⊆裙房约束。
    """
    from shapely.geometry import Polygon
    intent = {
        "version": 2, "project": "t",
        "zones": [
            # 裙房矩形（60×40m，足够容纳塔楼）
            {"id": "podium", "form": {"path": {"outer": {"base": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]]}}}},
            # 塔楼 A 手写在裙房西外（bbox x≥90000）
            {"id": "tower_a", "form": {"path": {"outer": {"base": [
                [90000, 10000], [135000, 10000], [135000, 50000], [90000, 50000]]}}}},
            # 塔楼 B 手写在裙房北外（bbox y≥70000）
            {"id": "tower_b", "form": {"path": {"outer": {"base": [
                [20000, 70000], [42000, 70000], [42000, 90000], [20000, 90000]]}}}},
        ],
        "spatial_relations": [
            {"from": "tower_a", "rel": "on", "to": "podium", "align": "west_center"},
            {"from": "tower_b", "rel": "on", "to": "podium", "align": "north_center"},
        ],
    }
    result = normalize(intent)
    host = Polygon([[0, 0], [60000, 0], [60000, 40000], [0, 40000]])
    for zid in ("tower_a", "tower_b"):
        zone = next(z for z in result["zones"] if z["id"] == zid)
        assert zone["position"]["on"] == "podium"
        outer = zone["outline_mm"][0]["outer"]["vertices"]
        assert host.covers(Polygon(outer)), f"{zid} 未落进宿主：{outer}"
    # 已落位的塔楼不应超出宿主 bbox
    ta = next(z for z in result["zones"] if z["id"] == "tower_a")
    va = ta["outline_mm"][0]["outer"]["vertices"]
    xs = [v[0] for v in va]
    assert min(xs) >= 0 and max(xs) <= 60000, f"tower_a x 越界：{xs}"


def test_zone_on_host_fit_checked_against_polygon():
    """rel=on 落位以宿主**多边形**为准（L 形凹部不算覆盖）。

    塔楼尺寸超过宿主实际可容纳区域 → 不强行平移，返回原坐标（由下游 check 报超出）。
    """
    from shapely.geometry import Polygon
    intent = {
        "version": 2, "project": "t",
        "zones": [
            # L 形裙房：西臂高 20m，南臂宽 20m——塔楼 40m 高放不进任何臂
            {"id": "podium", "form": {"path": {"outer": {"base": [
                [0, 0], [60000, 0], [60000, 20000], [20000, 20000], [20000, 60000], [0, 60000]]}}}},
            {"id": "tower", "form": {"path": {"outer": {"base": [
                [90000, 10000], [135000, 10000], [135000, 50000], [90000, 50000]]}}}},
        ],
        "spatial_relations": [{"from": "tower", "rel": "on", "to": "podium", "align": "west_center"}],
    }
    result = normalize(intent)
    tower = next(z for z in result["zones"] if z["id"] == "tower")
    host = Polygon([[0, 0], [60000, 0], [60000, 20000], [20000, 20000], [20000, 60000], [0, 60000]])
    outer = tower["outline_mm"][0]["outer"]["vertices"]
    assert not host.covers(Polygon(outer))  # 放不下 → 不伪造落位
    assert tower["position"] == {"on": "podium", "align": "west_center"}


# ── 错误处理 ──────────────────────────────────────────────────

def test_hole_outside_outer_fails():
    """孔洞在外环外 → NormalizeError。"""
    intent = {
        "version": 2, "project": "t",
        "zones": [{"id": "z", "form": {"path": {
            "outer": {"base": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]]},
            "holes": [{"base": [[50000, 10000], [60000, 10000], [60000, 20000], [50000, 20000]]}],  # 外环外
        }}}],
    }
    with pytest.raises(NormalizeError) as exc:
        normalize(intent)
    assert exc.value.error["error"] == "hole_outside_outer"


def test_arc_vertex_out_of_range():
    """arc at_vertex 越界 → NormalizeError。"""
    intent = {
        "version": 2, "project": "t",
        "zones": [{"id": "z", "form": {"path": {"outer": {
            "base": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]],
            "segments": [{"type": "arc", "at_vertex": 99, "radius_m": 5}],
        }}}}],
    }
    with pytest.raises(NormalizeError) as exc:
        normalize(intent)
    assert exc.value.error["error"] == "arc_vertex_out_of_range"


def test_recess_edge_not_found():
    """recess 的 at_edge 方位找不到边 → NormalizeError。"""
    intent = {
        "version": 2, "project": "t",
        "zones": [{"id": "z", "form": {"path": {"outer": {
            "base": [[0, 0], [40000, 0], [40000, 30000], [0, 30000]],
            "segments": [{"type": "recess", "at_edge": "SE", "offset_m": 5, "width_m": 3, "depth_m": 2}],  # 矩形无 SE 边
        }}}}],
    }
    with pytest.raises(NormalizeError) as exc:
        normalize(intent)
    assert exc.value.error["error"] == "segment_edge_not_found"

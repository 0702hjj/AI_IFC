"""floorgeom/derive.py —— 轮廓 → 派生几何事实（geo_cognition §1 全字段）。

设计纪律：
- 纯函数、shapely 唯一依赖、零设计判断（只给事实，不给建议）；
- 输入 = 整 plan 的 zones 数组（per-floor 事实 + 跨 zone 邻接 + 跨层差异一次产全）；
- 方位词汇统一（N/S/E/W/NE/NW/SE/SW + region 九宫格）；
- 字节级确定（排序键 + 定点舍入，由调用方 canon 写出保证）。
"""

from __future__ import annotations

import math

from shapely.geometry import Polygon, box

# 进深暗区阈值（geo_cognition §9-4：8m）
DEEP_ZONE_DEPTH_M = 8.0
# 方位归并半角（±22.5°）
DIR_HALF_ANGLE_DEG = 22.5

_DIRS_8 = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _dir_of_segment(p0, p1) -> str:
    """线段方位：北在上，±22.5° 归并到 8 方位。"""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return "N"  # 零长度兜底
    ang = math.degrees(math.atan2(dx, dy))  # 北为 0，顺时针为正
    if ang < 0:
        ang += 360.0
    idx = int(round(ang / 45.0)) % 8
    return _DIRS_8[idx]


def _region_of_point(x: float, y: float, x0: float, y0: float, x1: float, y1: float) -> str:
    """九宫格 region 判定。"""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    xs = "center" if abs(x - cx) < (x1 - x0) / 6 else ("E" if x > cx else "W")
    ys = "center" if abs(y - cy) < (y1 - y0) / 6 else ("N" if y > cy else "S")
    if xs == "center" and ys == "center":
        return "center"
    if xs == "center":
        return ys
    if ys == "center":
        return xs
    return ys + xs  # 如 "NE"、"SW"


def _densify_ring(vertices, arcs=None, chord_deg=12.0):
    """顶点 + 弧标注 → 致密化顶点（从 aiplan geom 移植，T12 使用）。"""
    verts = [[float(p[0]), float(p[1])] for p in vertices]
    if not arcs:
        return verts
    s = 0.0
    n = len(verts)
    for i in range(n):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    ccw = s / 2.0 > 0
    arc_by_at = {int(a["at"]): a for a in arcs}
    out: list[list[float]] = []
    for i in range(n):
        p0, p1 = verts[i], verts[(i + 1) % n]
        out.append(p0)
        a = arc_by_at.get(i)
        if a is None:
            continue
        cx, cy = float(a["center"][0]), float(a["center"][1])
        r = float(a["radius"])
        a0 = a.get("a0")
        a1 = a.get("a1")
        if a0 is None:
            a0 = math.degrees(math.atan2(p0[1] - cy, p0[0] - cx))
        if a1 is None:
            a1 = math.degrees(math.atan2(p1[1] - cy, p1[0] - cx))
        a0, a1 = float(a0), float(a1)
        if ccw:
            while a1 <= a0:
                a1 += 360.0
        else:
            while a1 >= a0:
                a1 -= 360.0
        steps = max(1, int(abs(a1 - a0) / chord_deg + 0.999))
        for k in range(1, steps):
            ang = math.radians(a0 + (a1 - a0) * k / steps)
            out.append([cx + r * math.cos(ang), cy + r * math.sin(ang)])
    return out


def _ring_to_polygon(ring) -> Polygon:
    """统一 ring → shapely Polygon（outer/holes/core 全走这里，T12 弧支持）。"""
    if isinstance(ring, dict):
        verts = _densify_ring(ring.get("vertices") or [], ring.get("arcs") or [])
    else:
        verts = [[float(p[0]), float(p[1])] for p in ring]
    poly = Polygon(verts)
    if not poly.is_valid:
        poly = poly.buffer(0)  # 防御：修复退化自交
    return poly


def _block_polygons(block: dict) -> tuple[Polygon, list[Polygon]]:
    """outline 块 → (outer, holes)。弧标注兼容 bare polygon + block-level arcs。"""
    outer_raw = block["outer"]
    block_arcs = block.get("arcs") or []
    if isinstance(outer_raw, dict):
        outer_poly = _ring_to_polygon(outer_raw)
    elif block_arcs:
        outer_poly = _ring_to_polygon({"vertices": outer_raw, "arcs": block_arcs})
    else:
        outer_poly = _ring_to_polygon(outer_raw)
    hole_polys = [_ring_to_polygon(h) for h in block.get("holes") or []]
    return outer_poly, hole_polys


def _polygon_area_sqm(poly: Polygon) -> float:
    """shapely 面积（mm²）→ ㎡。"""
    return abs(poly.area) / 1e6


def _polygon_perimeter_m(poly: Polygon) -> float:
    return poly.length / 1000.0

"""goldlib/reverse.py —— readback 房间图 → rooms DSL 声明。

2026-08-13（D41）：反推目标改新结构（walls + labels）——
- 房间多边形 → 边界段提取（共边去重 = 一道墙）→ walls（axis 轴线，key 自动）
- 房间名/类型/面积 → labels（质心 at 点落区绑定）
- 门（readback doors）→ openings 挂墙 key + along（沿墙定位）
- 轴网不再反推（新结构 walls 用绝对坐标；outline 原样传回供围区域边界）

知识诚实性：推不出定位的房间 label 仍产出（质心总在区域内）——
围区域是机器从墙推的，不存在"定位推不出"的旧 loc=null 问题。
"""

from __future__ import annotations

from collections import Counter

from shapely.geometry import Polygon

MIN_ROOM_SQM = 4.0


def _walls_from_room_boundaries(rooms: list[dict]) -> list[dict]:
    """房间多边形边界段 → 墙轴线（共边去重：一道墙只产一次）。"""
    edge_count: Counter = Counter()
    edge_pts: dict = {}
    for n in rooms:
        verts = n.get("polygon_mm") or []
        if len(verts) < 3:
            continue
        for i in range(len(verts)):
            import math
            if (math.isnan(float(verts[i][0])) or math.isnan(float(verts[i][1]))
                    or math.isnan(float(verts[(i + 1) % len(verts)][0]))
                    or math.isnan(float(verts[(i + 1) % len(verts)][1]))):
                continue  # 无效多边形 NaN 坐标跳过（readback 栅格降级产物）
            p0 = (round(verts[i][0], 3), round(verts[i][1], 3))
            p1 = (round(verts[(i + 1) % len(verts)][0], 3),
                  round(verts[(i + 1) % len(verts)][1], 3))
            if p0 == p1:
                continue
            key = tuple(sorted((p0, p1)))
            edge_count[key] += 1
            edge_pts[key] = (list(p0), list(p1))

    walls = []
    for i, key in enumerate(sorted(edge_pts)):
        p0, p1 = edge_pts[key]
        walls.append({
            "key": f"1F:int:{i}",
            "kind": "int",
            "t_mm": 120,
            "axis": [p0, p1],
        })
    return walls


def _label_at(verts: list[list[float]]) -> list[float]:
    """房间多边形 → 内部代表点（label at 点，落区绑定）。

    representative_point 保证点在多边形内部（质心可能在凹形外）。
    """
    if len(verts) < 3:
        return [0.0, 0.0]
    poly = Polygon(verts)
    if not poly.is_valid or poly.is_empty:
        return [0.0, 0.0]
    c = poly.representative_point()
    return [round(float(c.x), 3), round(float(c.y), 3)]


def _openings_from_doors(doors: list[dict], walls: list[dict]) -> list[dict]:
    """readback 门（hinge/strike）→ openings 挂墙 key + along。

    门中点落在墙轴线上 → 挂该墙，along = 沿墙起点距离。
    """
    openings = []
    wall_lines = [(w["key"], w["axis"][0], w["axis"][1]) for w in walls]
    for di, d in enumerate(doors or []):
        hinge = d.get("hinge") or []
        strike = d.get("strike") or []
        if len(hinge) < 2 or len(strike) < 2:
            continue
        mid = [(hinge[0] + strike[0]) / 2, (hinge[1] + strike[1]) / 2]
        for key, p0, p1 in wall_lines:
            # 门中点是否在墙轴线上（共线 + 范围内）
            if _point_on_segment(mid, p0, p1, tol=300.0):
                w_mm = round(_dist(hinge, strike), 1)
                wall_len = _dist(p0, p1)
                if w_mm > wall_len + 1.0:
                    continue  # 碎墙段装不下门（readback 边界未合并共线段）→ 找下一段
                # along 语义 = 门起点沿墙距离（中点距离 − 门宽/2，clamp 墙内）
                along_mm = _dist(p0, mid) - w_mm / 2.0
                along_mm = max(0.0, min(along_mm, wall_len - w_mm))
                openings.append({
                    "wall": key,
                    "along_m": round(along_mm / 1000.0, 3),
                    "w_mm": w_mm,
                    "h_mm": 2100,
                    "sill_mm": 0,
                    "type": "door",
                })
                break
    return openings


def _point_on_segment(p: list[float], a: list[float], b: list[float],
                      tol: float) -> bool:
    """p 是否在 ab 线段上（容差 tol mm）。"""
    import math
    d_ab = _dist(a, b)
    if d_ab < 1e-6:
        return _dist(p, a) < tol
    # 点到线距离
    cross = abs((b[0] - a[0]) * (a[1] - p[1]) - (a[0] - p[0]) * (b[1] - a[1]))
    if cross / d_ab > tol:
        return False
    # 投影范围
    dot = ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / d_ab
    return -tol <= dot <= d_ab + tol


def _dist(a, b) -> float:
    import math
    return math.hypot(a[0] - b[0], a[1] - b[1])


def reverse(readback_graph: dict, min_room_sqm: float = MIN_ROOM_SQM) -> dict:
    """readback 房间图 → rooms DSL 声明（D41 新结构：walls + labels + openings）。

    :param readback_graph: dxfkit.readback 产出
    :param min_room_sqm: 房间最小面积（R-01 校准 4㎡）
    :return: {"floor": ..., "walls": [...], "labels": [...], "openings": [...]}
    """
    nodes = readback_graph.get("nodes", [])
    doors = readback_graph.get("doors", []) or []
    floor = readback_graph.get("source_dxf", "?")

    # 面积过滤（R-01 校准）
    real_rooms = [n for n in nodes
                  if (n.get("area_geo_sqm") or 0) >= min_room_sqm]

    walls = _walls_from_room_boundaries(real_rooms)
    labels = [
        {
            "room": n.get("id"),
            "type": n.get("type", "unlabeled"),
            "area_sqm": n.get("area_sqm") or round(n.get("area_geo_sqm", 0), 1),
            "at": _label_at(n.get("polygon_mm") or []),
        }
        for n in real_rooms
        if n.get("id") and n.get("polygon_mm")
    ]
    openings = _openings_from_doors(doors, walls)

    return {
        "floor": floor,
        "walls": walls,
        "labels": labels,
        "openings": openings,
    }

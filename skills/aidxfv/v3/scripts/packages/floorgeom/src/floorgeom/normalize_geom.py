"""floorgeom/normalize.py —— DSL 声明 → 几何坐标 JSON（唯一坐标计算点）。

纪律（geo_cognition §8 / architecture D24）：
- 轴网 snap（frame.modulus，默认 100mm），锚定 dominant_axes；
- 锚点豁免（T4）：core anchor 原值锁死，snap 不得移动；
- 解析链一体（§6A 机制5）：细节索引 → 骨架轴值 → 绝对坐标；
- SchemaError（exit 2 语义）：声明非法回喂重发，结构化 {"error","at"}。
- 产出是几何坐标 JSON（非 DXF），DXF 由 draw 逐构件。
"""

from __future__ import annotations

import math

from shapely.geometry import Point, Polygon


class SchemaError(Exception):
    """声明非法（exit 2 语义）。结构化 error 可回喂 LLM。"""

    def __init__(self, error: str, at: str, **extra):
        self.error = {"error": error, "at": at, **extra}
        super().__init__(f"{error} @ {at}")


# ---------------------------------------------------------------------------
# 轴网解析
# ---------------------------------------------------------------------------

def _snap(v: float, modulus: float) -> float:
    return round(v / modulus) * modulus


def _resolve_axis(axis_grid: dict, axis: str, idx: int, at: str) -> float:
    vals = axis_grid.get(axis, [])
    if idx < 0 or idx >= len(vals):
        raise SchemaError("axis_index_out_of_range", at,
                          axis=axis, index=idx, size=len(vals))
    return float(vals[idx])


def _resolve_point(pt: dict, axis_grid: dict, at: str) -> list[float]:
    """路径/多边形顶点 → 绝对坐标。两种形态（2026-08-11 拍板，取消 pt 自由顶点）：
    - {x, y}                     轴网索引点
    - {x, y, dx_mm, dy_mm}       轴网索引 + 相对偏移（局部小曲折）
    相邻点不强制共 x/共 y——网格点间任意连线即非 90 度角（斜切/楔形）。
    """
    x = _resolve_axis(axis_grid, "x", pt["x"], f"{at}.x")
    y = _resolve_axis(axis_grid, "y", pt["y"], f"{at}.y")
    dx = float(pt.get("dx_mm", 0.0))
    dy = float(pt.get("dy_mm", 0.0))
    return [x + dx, y + dy]

# ---------------------------------------------------------------------------
# 统一多段 path 解析 + segments 展开（2026-08-11：多段兼容性是核心）
# ---------------------------------------------------------------------------

def _arc_discretize(center: list[float], radius: float, a0: float, a1: float,
                    seg_deg: float = 5.0) -> list[list[float]]:
    """弧离散为折线点列（含起终点）。D32：skeleton path 弧能力。"""
    if a1 < a0:
        a1 += 360.0
    n = max(2, int((a1 - a0) / seg_deg) + 1)
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append([center[0] + radius * math.cos(a),
                    center[1] + radius * math.sin(a)])
    return pts


def _ring_to_vertices(ring, at: str) -> list[list[float]]:
    """ring（polygon 简写 | {vertices, arcs?}）→ 顶点列表（D33 holes 用）。

    arcs 是 plan_arcAnn（center 绝对坐标——继承 plan 事实，非 LLM 新说）。
    弧边离散进顶点序列。
    """
    if isinstance(ring, list):  # polygon 简写
        return [[float(p[0]), float(p[1])] for p in ring]
    if isinstance(ring, dict):
        verts = ring.get("vertices")
        if verts is None:
            raise SchemaError("ring_missing_vertices", at)
        pts = [[float(p[0]), float(p[1])] for p in verts]
        arcs = ring.get("arcs")
        if arcs:
            arc_map = {int(a["at"]): a for a in arcs}
            out: list[list[float]] = []
            for i in range(len(pts)):
                out.append(pts[i])
                if i in arc_map and i + 1 < len(pts):
                    a = arc_map[i]
                    arc_pts = _arc_discretize(
                        [float(a["center"][0]), float(a["center"][1])],
                        float(a["radius"]),
                        float(a.get("a0", 0.0)), float(a.get("a1", 90.0)))
                    out.extend(arc_pts[1:-1])
            pts = out
        return pts
    raise SchemaError("bad_ring", at)


def _resolve_path_pts(path: list, grid: dict, at: str,
                      closed: bool = False, arcs: list | None = None) -> list[list[float]]:
    """多段 path 顶点 → 绝对坐标（逐点解析，任意段数/任意方向）。

    顶点两种形式（schema oneOf）：
    - 轴网索引 {x,y,dx_mm?,dy_mm?}（模型声明）
    - 绝对坐标 [x,y]（金例迁移/继承分区几何）
    closed=True 时首尾自动闭合（房间边界/区域）。
    arcs（D32）：[{"at":边索引, "center":{x,y轴网索引+dx/dy}, "radius","a0","a1"}]——
    at=i 的边（顶点i→i+1）替换为弧离散点列。
    """
    pts = []
    for i, p in enumerate(path):
        if isinstance(p, dict):
            pts.append(_resolve_point(p, grid, f"{at}[{i}]"))
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            pts.append([float(p[0]), float(p[1])])
        else:
            raise SchemaError("bad_path_point", f"{at}[{i}]")
    if arcs:
        arc_map = {int(a["at"]): a for a in arcs}
        out: list[list[float]] = []
        for i in range(len(pts)):
            out.append(pts[i])
            if i in arc_map and i + 1 < len(pts):
                a = arc_map[i]
                center = _resolve_point(a["center"], grid, f"{at}.arcs[{i}].center")
                arc_pts = _arc_discretize(center, float(a["radius"]),
                                          float(a.get("a0", 0.0)), float(a.get("a1", 90.0)))
                out.extend(arc_pts[1:-1])  # 起终点即相邻顶点，只插中间点
        pts = out
    if closed and len(pts) > 2 and not (pts[0][0] == pts[-1][0] and pts[0][1] == pts[-1][1]):
        pts = pts + [pts[0]]
    return pts


def _edge_outward_normal(p0: list[float], p1: list[float]) -> tuple[float, float]:
    """CCW 外环边 (p0→p1) 的外法向（右侧，指向外部），归一化。

    （D39 修正：对齐 aiplan——CCW 外环外法向 = 边方向右转 90° = (dy, -dx)）
    """
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return (0.0, 0.0)
    return (dy / length, -dx / length)


def _find_edge(pts: list[list[float]], direction: str) -> int | None:
    """找方位 direction 对应的边下标（N/S/E/W，取该方向最外侧边）。"""
    n = len(pts)
    best, best_key = None, None
    for i in range(n):
        p0, p1 = pts[i], pts[(i + 1) % n]
        if direction == "N":
            key = (p0[1] + p1[1]) / 2  # 北 = y 最大
        elif direction == "S":
            key = -(p0[1] + p1[1]) / 2
        elif direction == "E":
            key = (p0[0] + p1[0]) / 2
        elif direction == "W":
            key = -(p0[0] + p1[0]) / 2
        else:
            continue
        if best_key is None or key > best_key:
            best_key, best = key, i
    return best


def _expand_recess_projection(pts: list[list[float]], seg: dict) -> list[list[float]]:
    """在 at_edge 边 offset_m 处插入凹进/凸出顶点（从 aiplan 移植）。

    seg: {type: recess|projection, at_edge, offset_m, width_m, depth_m}
    """
    direction = seg["at_edge"]
    offset = seg["offset_m"] * 1000
    width = seg["width_m"] * 1000
    depth = seg["depth_m"] * 1000
    is_recess = seg["type"] == "recess"

    edge_idx = _find_edge(pts, direction)
    if edge_idx is None:
        raise SchemaError("segment_edge_not_found", "segments.at_edge", direction=direction)

    n = len(pts)
    p0 = pts[edge_idx]
    p1 = pts[(edge_idx + 1) % n]
    edge_len = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    if offset + width > edge_len + 1e-6:
        raise SchemaError("segment_exceeds_edge", "segments",
                          direction=direction, offset_m=seg["offset_m"],
                          width_m=seg["width_m"], edge_len_m=round(edge_len / 1000, 2))

    ux = (p1[0] - p0[0]) / edge_len
    uy = (p1[1] - p0[1]) / edge_len
    nx, ny = _edge_outward_normal(p0, p1)
    sign = -1.0 if is_recess else 1.0

    a = [p0[0] + ux * offset, p0[1] + uy * offset]
    b = [p0[0] + ux * (offset + width), p0[1] + uy * (offset + width)]
    a2 = [a[0] + sign * nx * depth, a[1] + sign * ny * depth]
    b2 = [b[0] + sign * nx * depth, b[1] + sign * ny * depth]

    if edge_idx == n - 1:
        return pts[:edge_idx + 1] + [a, a2, b2, b]
    return pts[:edge_idx + 1] + [a, a2, b2, b] + pts[(edge_idx + 1) % n:]


def _expand_path_with_segments(pts: list[list[float]], segments: list, grid: dict,
                               at: str) -> list[list[float]]:
    """多段 path + segments（recess/projection 细节封装）→ 展开后顶点。

    segments 是 schema 的 segment def（recess/projection/arc）；arc 圆角用
    _fillet 展开（简化为在顶点处插入弧中点，完整弧标注留 draw 阶段）。
    """
    out = [list(p) for p in pts]
    for si, seg in enumerate(segments or []):
        sat = f"{at}.segments[{si}]"
        typ = seg.get("type")
        if typ in ("recess", "projection"):
            out = _expand_recess_projection(out, seg)
        elif typ == "arc":
            # 圆角：简化为保留顶点（弧标注由 draw 处理）；后续可移植 aiplan _fillet_at_vertex
            continue
        else:
            raise SchemaError("bad_segment_type", sat, type=typ)
    return out


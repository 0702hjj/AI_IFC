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


# ---------------------------------------------------------------------------
# 波次 1（D39）：path 分段协议（ring_edges + segments）——从 aiplan 移植对齐
# ---------------------------------------------------------------------------

def _signed_area(verts: list[list[float]]) -> float:
    """鞋带公式有向面积（>0 逆时针）。"""
    n = len(verts)
    s = 0.0
    for i in range(n):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return s / 2.0


def _normal_to_direction(nx: float, ny: float) -> str:
    """外法向 → 方位（N/S/E/W 主方位）。"""
    if abs(nx) > abs(ny):
        return "E" if nx > 0 else "W"
    return "N" if ny > 0 else "S"


def _normalize_ring_direction(verts: list[list[float]], ccw: bool) -> list[list[float]]:
    """环方向归一化：ccw=True 强制逆时针（外环），ccw=False 强制顺时针（孔洞）。

    模型不用记方向——normalize 自动反转到正确旋向。
    """
    is_ccw = _signed_area(verts) > 0
    if is_ccw != ccw:
        return [verts[0]] + list(reversed(verts[1:]))  # 反转（保持起点）
    return verts


def _fillet_at_vertex(pts: list[list[float]], k: int, radius_mm: float) -> tuple[list, dict] | None:
    """顶点 pts[k] 倒圆角 radius_mm。返回 (new_pts, arc_ann) 或 None。

    从 aiplan 移植：直线角/半径过大/几何无效 → None（调用方报 SchemaError）。
    """
    n = len(pts)
    prev, curr, nxt = pts[(k - 1) % n], pts[k], pts[(k + 1) % n]
    d1 = (curr[0] - prev[0], curr[1] - prev[1])
    d2 = (nxt[0] - curr[0], nxt[1] - curr[1])
    len1, len2 = math.hypot(*d1), math.hypot(*d2)
    if len1 < 1e-9 or len2 < 1e-9:
        return None
    u1 = (d1[0] / len1, d1[1] / len1)
    u2 = (d2[0] / len2, d2[1] / len2)
    dot = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
    theta = math.acos(dot)
    half = (math.pi - theta) / 2
    if half <= 1e-6 or math.sin(half) < 1e-6:
        return None
    d = radius_mm / math.tan(half)
    if d >= len1 or d >= len2:
        return None
    t1 = [curr[0] - d * u1[0], curr[1] - d * u1[1]]
    t2 = [curr[0] + d * u2[0], curr[1] + d * u2[1]]
    bis = (u2[0] - u1[0], u2[1] - u1[1])
    blen = math.hypot(*bis)
    if blen < 1e-9:
        return None
    ubis = (bis[0] / blen, bis[1] / blen)
    poly = Polygon(pts)
    dist = radius_mm / math.sin(half)
    center = None
    for sign in (1, -1):
        cx = curr[0] + sign * dist * ubis[0]
        cy = curr[1] + sign * dist * ubis[1]
        if poly.covers(Point(cx, cy)):
            center = [cx, cy]
            break
    if center is None:
        center = [curr[0] + dist * ubis[0], curr[1] + dist * ubis[1]]
    a0 = math.degrees(math.atan2(t1[1] - center[1], t1[0] - center[0]))
    a1 = math.degrees(math.atan2(t2[1] - center[1], t2[0] - center[0]))
    new_pts = pts[:k] + [t1, t2] + pts[k + 1:]
    arc = {"at": k, "center": center, "radius": float(radius_mm), "a0": a0, "a1": a1}
    return new_pts, arc


def _expand_segments_grouped(pts: list[list[float]], edge_segs: list[dict]) -> list[list[float]]:
    """按边分组一次性展开所有 recess/projection segment（支持同边多处凹凸）。

    从 aiplan 移植（用户拍板：多段 path 兼容性——同一边多个 segment 必须正确展开）：
    1. 识别原始 pts 每条边的方位（外法向）
    2. segment 按目标边分组（同方位多边时用"能容纳 offset+width"区间匹配）
    3. 每条边内按 offset 排序，一次性展开该边所有凹凸顶点
    4. 从后往前处理边（避免下标偏移）
    """
    if not edge_segs:
        return pts
    pts = [list(p) for p in pts]
    n = len(pts)

    edges = []
    for i in range(n):
        p0, p1 = pts[i], pts[(i + 1) % n]
        nx, ny = _edge_outward_normal(p0, p1)
        direction = _normal_to_direction(nx, ny)
        elen = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if elen < 1e-9:
            continue
        ux, uy = (p1[0] - p0[0]) / elen, (p1[1] - p0[1]) / elen
        edges.append({"idx": i, "dir": direction, "p0": p0, "p1": p1,
                      "len": elen, "ux": ux, "uy": uy, "nx": nx, "ny": ny})

    edge_groups: dict[int, list[dict]] = {}
    for seg in edge_segs:
        direction = seg["at_edge"]
        offset = seg["offset_m"] * 1000
        width = seg["width_m"] * 1000
        target = None
        for e in edges:
            if e["dir"] == direction and offset + width <= e["len"] + 1e-6:
                target = e
                break
        if target is None:
            cands = [e for e in edges if e["dir"] == direction]
            if not cands:
                raise SchemaError("segment_edge_not_found", "segments.at_edge",
                                  direction=direction)
            raise SchemaError("segment_exceeds_edge", "segments",
                              direction=direction, offset_m=seg["offset_m"],
                              width_m=seg["width_m"],
                              edge_len_m=round(max(e["len"] for e in cands) / 1000, 2))
        edge_groups.setdefault(target["idx"], []).append(seg)

    for edge_idx in sorted(edge_groups.keys(), reverse=True):
        e = next(x for x in edges if x["idx"] == edge_idx)
        segs = sorted(edge_groups[edge_idx], key=lambda s: s["offset_m"])
        inserts: list[list[float]] = []
        for seg in segs:
            offset = seg["offset_m"] * 1000
            width = seg["width_m"] * 1000
            depth = seg["depth_m"] * 1000
            sign = -1.0 if seg["type"] == "recess" else 1.0
            ux, uy, nx, ny = e["ux"], e["uy"], e["nx"], e["ny"]
            p0 = e["p0"]
            a = [p0[0] + ux * offset, p0[1] + uy * offset]
            b = [p0[0] + ux * (offset + width), p0[1] + uy * (offset + width)]
            a2 = [a[0] + sign * nx * depth, a[1] + sign * ny * depth]
            b2 = [b[0] + sign * nx * depth, b[1] + sign * ny * depth]
            inserts += [a, a2, b2, b]
        next_idx = (edge_idx + 1) % n
        if edge_idx < n - 1:
            pts = pts[:edge_idx + 1] + inserts + pts[next_idx:]
        else:
            pts = pts[:edge_idx + 1] + inserts
        n = len(pts)

    return pts


def _edges_to_base(edges: dict) -> list[list[float]]:
    """四条边折线 → 闭合环顶点序列。

    从 aiplan 移植。拼合（逆时针 west→north→east→south），去掉重复角点：
    base = west + north[1:] + east[1:] + south[1:]
    """
    west = [list(p) for p in edges["west"]]
    north = [list(p) for p in edges["north"]]
    east = [list(p) for p in edges["east"]]
    south = [list(p) for p in edges["south"]]
    base = west + north[1:] + east[1:] + south[1:]
    if len(base) >= 2 and base[0] == base[-1]:
        base = base[:-1]
    return [[float(p[0]), float(p[1])] for p in base]


def _expand_ring_edges(ring_spec: dict, is_outer: bool) -> dict:
    """ring_edges（edges + segments）→ {vertices, arcs}（完整顶点 + 弧标注）。

    从 aiplan 移植：
    1. 四条边拼合成闭合环 base（方向归一化：外环 CCW / 孔洞 CW）
    2. 展开 segments：先 arc（at_vertex 圆角，从大到小防下标偏移），
       后 recess/projection（按边分组一次性展开——同边多处）
    """
    edges = ring_spec["edges"]
    base = _edges_to_base(edges)
    pts = _normalize_ring_direction(base, ccw=is_outer)

    arcs: list[dict] = []
    segments = ring_spec.get("segments") or []

    # ① arc（顶点倒圆角，at_vertex 在 base 原始顶点上做，从大到小防下标偏移）
    arc_segs = [s for s in segments if s["type"] == "arc"]
    for seg in sorted(arc_segs, key=lambda s: -s["at_vertex"]):
        k = seg["at_vertex"]
        radius_mm = seg["radius_m"] * 1000
        if k < 0 or k >= len(pts):
            raise SchemaError("arc_vertex_out_of_range", "segments.at_vertex",
                              index=k, length=len(pts))
        res = _fillet_at_vertex(pts, k, radius_mm)
        if res is None:
            raise SchemaError("arc_fillet_failed", "segments", index=k,
                              reason="直线角/半径过大/几何无效")
        pts, arc = res
        for prev in arcs:
            if prev["at"] >= k:
                prev["at"] += 1
        arcs.append(arc)

    # ② recess/projection（按边分组一次性展开）
    edge_segs = [s for s in segments if s["type"] in ("recess", "projection")]
    pts = _expand_segments_grouped(pts, edge_segs)

    return {"vertices": pts, "arcs": sorted(arcs, key=lambda a: a["at"])}


def _resolve_axes_rect(rect: dict, axis_grid: dict, at: str) -> dict:
    """轴网区间 {x:[i1,i2], y:[i1,i2]} → 绝对坐标矩形（x0,y0,x1,y1）。"""
    xs = [_resolve_axis(axis_grid, "x", i, f"{at}.x[{i}]") for i in rect["x"]]
    ys = [_resolve_axis(axis_grid, "y", i, f"{at}.y[{i}]") for i in rect["y"]]
    return {"x": sorted(xs), "y": sorted(ys)}


def _resolve_polygon_vertices(vertices: list, axis_grid: dict, at: str) -> list[list[float]]:
    """轴网索引顶点 [[xi,yi],...] → 绝对坐标。"""
    out = []
    for i, v in enumerate(vertices):
        if len(v) != 2:
            raise SchemaError("bad_vertex", f"{at}.vertices[{i}]")
        out.append([
            _resolve_axis(axis_grid, "x", v[0], f"{at}.vertices[{i}].x"),
            _resolve_axis(axis_grid, "y", v[1], f"{at}.vertices[{i}].y"),
        ])
    return out


# ---------------------------------------------------------------------------
# skeleton 半
# ---------------------------------------------------------------------------

def normalize_skeleton(skeleton: dict) -> dict:
    """skeleton.json → 几何模型（几何坐标 JSON，唯一坐标计算点）。

    :raises SchemaError: 声明非法（exit 2 语义）
    """
    frame = skeleton.get("frame") or {}
    modulus = float(frame.get("modulus", 100))

    zones_out = []
    for zi, zone in enumerate(skeleton.get("zones") or []):
        at = f"zones[{zi}]"

        # core（D31：单对象|数组|null；输出 cores 数组 + core 兼容键）
        #      （D39：path 分段 ring_edges 或 vertices 绝对坐标 ring——extent 已删）
        core = zone.get("core")
        core_list = []
        if core is not None:
            core_list = core if isinstance(core, list) else [core]
        cores_out = []
        for ci, c in enumerate(core_list):
            cat = f"{at}.core" + (f"[{ci}]" if isinstance(core, list) else "")
            anchor = c.get("anchor")
            if anchor is None:
                raise SchemaError("missing_anchor", cat)
            if "vertices" in c:  # D36 绝对坐标 ring：继承 plan core（非轴网对齐核心筒）
                pts = _ring_to_vertices(c["vertices"], f"{cat}.vertices")
                poly = {"vertices": pts}
            elif "path" in c:  # D39 path 分段 ring_edges（edges 四边拼合 + segments）
                ring = _expand_ring_edges(c["path"], is_outer=True)
                poly = {"vertices": ring["vertices"]}
                if ring["arcs"]:
                    poly["arcs"] = ring["arcs"]
            else:
                raise SchemaError("missing_core_geometry", cat)
            out = {
                "anchor": [float(anchor[0]), float(anchor[1])],  # T4 锁死，不 snap
                "polygon_mm": poly,
            }
            if c.get("id") is not None:
                out["id"] = c["id"]
            cores_out.append(out)
        core_out = cores_out[0] if cores_out else None  # 兼容键：单=对象/多=首个/null=None

        # corridor
        corridor = zone.get("corridor")
        corr_out = None
        corridor_outer_pts = None  # D40：外缘环顶点（push_layers 差集输入）
        if corridor is not None:
            form = corridor.get("form")
            width = float(corridor.get("width_mm", 0))
            if form != "path":
                raise SchemaError("bad_corridor_form", f"{at}.corridor", form=form)
            path = corridor.get("path")
            if not path or not isinstance(path, dict) or "edges" not in path:
                raise SchemaError("missing_ring_edges", f"{at}.corridor.path")
            ring = _expand_ring_edges(path, is_outer=True)
            corridor_outer_pts = ring["vertices"]
            corr_out = {"form": "path", "width_mm": width,
                        "path_mm": ring["vertices"]}
            if ring["arcs"]:
                corr_out["arcs"] = ring["arcs"]

        # main_partitions（D40：切割线锚定——唯一形式，旧 path 已删）
        partitions = []
        cuts_spec = []  # D40：切割线锚定形式（push_layers 消费）
        for pi, part in enumerate(zone.get("main_partitions") or []):
            if "from" in part and "to" in part:
                cuts_spec.append(part)
            else:
                raise SchemaError("partition_requires_anchors",
                                  f"{at}.main_partitions[{pi}]")

        # outline（D34：线性继承 plan outline_mm——多块分区轮廓，真弧/孔洞，
        #      骨架分区以此为界；绝对坐标，非轴网索引）
        outline_out = []
        for oi, oblk in enumerate(zone.get("outline") or []):
            oat = f"{at}.outline[{oi}]"
            try:
                outer_pts = _ring_to_vertices(oblk.get("outer"), f"{oat}.outer")
                holes_pts = []
                for hi, hole in enumerate(oblk.get("holes") or []):
                    holes_pts.append(_ring_to_vertices(hole, f"{oat}.holes[{hi}]"))
                outline_out.append({
                    "outer": {"vertices": outer_pts},
                    "holes": [{"vertices": h} for h in holes_pts],
                })
            except SchemaError:
                raise
            except Exception as ex:
                raise SchemaError("bad_outline_block", oat, detail=str(ex))

        # holes（D33：通用语义块——ring 数组，对齐 plan outline holes，绝对坐标继承）
        holes_out = []
        for hi, hole in enumerate(zone.get("holes") or []):
            try:
                ring_poly = _ring_to_vertices(hole, f"{at}.holes[{hi}]")
                holes_out.append({"polygon_mm": {"vertices": ring_poly}})
            except SchemaError:
                raise
            except Exception as ex:
                raise SchemaError("bad_hole_ring", f"{at}.holes[{hi}]", detail=str(ex))

        # blocks（D40：between 认领——唯一形式，旧 path 已删；认领结果由 push_layers 产）
        blocks_out = []
        blocks_between_spec = []
        for bi, blk in enumerate(zone.get("blocks") or []):
            bat = f"{at}.blocks[{bi}]"
            if "between" not in blk:
                raise SchemaError("block_requires_between", bat)
            blocks_between_spec.append(blk)

        # ── D40 分层外推（push_layers：差集/切割/切段/认领/轴网派生/标签）──
        layered = {}
        if outline_out or corridor_outer_pts or cuts_spec or blocks_between_spec:
            from .normalize_skeleton import push_layers
            outline_polys = []
            outline_edges_flat = []
            for oblk in outline_out:
                verts = oblk["outer"]["vertices"]
                if len(verts) >= 3:
                    outline_polys.append(Polygon(verts).buffer(0))
                    for i in range(len(verts)):
                        outline_edges_flat.append([verts[i],
                                                   verts[(i + 1) % len(verts)]])
            holes_rings = [h["polygon_mm"]["vertices"] for h in holes_out]
            cores_rings = {}
            for i, c in enumerate(cores_out):
                poly = c["polygon_mm"]
                if "vertices" in poly:
                    verts = poly["vertices"]
                else:  # extent 轴网区间 → 矩形 {x:[x0,x1], y:[y0,y1]}
                    xs, ys = poly["x"], poly["y"]
                    verts = [[xs[0], ys[0]], [xs[1], ys[0]],
                             [xs[1], ys[1]], [xs[0], ys[1]]]
                cores_rings[c.get("id") or f"core{i}"] = verts
            layered = push_layers(
                outline_polys=outline_polys,
                outline_edges=outline_edges_flat,
                holes_rings=holes_rings,
                cores=cores_rings,
                corridor_outer=corridor_outer_pts,
                cuts_spec=cuts_spec,
                blocks_spec=blocks_between_spec,
            )
            blocks_out.extend(layered["blocks_claimed"])

        zones_out.append({
            "zone": zone.get("zone"),
            "axis_grid": {"x": [], "y": []},  # 旧轴网键保留空（轴网派生见 axis_grid_derived）
            "outline": outline_out,  # D34：轮廓块（线性继承 plan outline_mm）
            "core": core_out,
            "cores": cores_out,   # D31：总是数组（0/1/N）
            "corridor": corr_out,
            "main_partitions": partitions,
            "holes": holes_out,     # D33：通用语义块（对齐 plan outline holes）
            "blocks": blocks_out,   # D33：宽松分区 + D40 between 认领
            "corridor_zone": layered.get("corridor_zone"),      # D40：外缘−核差集
            "big_zones": layered.get("big_zones"),              # D40：outline−corridor 差集
            "cuts": layered.get("cuts"),                        # D40：切割线绝对坐标
            "segments": layered.get("segments"),                # D46：大区切段（rooms 分块承接边界）
            "axis_grid_derived": layered.get("axis_grid_derived"),  # D40：分区边界提取
            "partition_labels": layered.get("partition_labels"),    # D40：段质心标签
        })

    return {
        "frame": {
            "units": frame.get("units", "mm"),
            "origin": frame.get("origin", "lot_southwest"),
            "north_deg": float(frame.get("north_deg", 0)),
            "modulus": modulus,
        },
        "zones": zones_out,
    }


# 2026-08-11：path 禁对角约束已取消——相邻点任意方向即非 90 度角（用户拍板）。
# 保留函数签名兼容，但不再抛错（斜切/楔形户型合法）。


# ---------------------------------------------------------------------------
# rooms 半（D41 重写，2026-08-13）


def normalize_rooms(rooms: dict, skeleton_model: dict) -> dict:
    """rooms.json → 几何模型（几何坐标 JSON）。

    D41 新结构（walls + labels + partitions，无 rooms[] 数组）：
    walls 解析 → 墙围区域 → labels 落区绑定 → openings 挂墙。
    实现全在 floorgeom/normalize_rooms.py（G 节拆分：rooms 半独立模块）。

    :raises SchemaError: 声明非法（exit 2 语义）
    """
    if rooms.get("status") == "infeasible":
        return {k: v for k, v in rooms.items()}  # 直通

    if not rooms.get("walls") and not rooms.get("labels"):
        raise SchemaError("missing_rooms_content", "rooms",
                          hint="rooms 需声明 walls（分墙）或 labels（房间标签）")

    from .normalize_rooms import normalize_rooms_new
    return normalize_rooms_new(rooms, skeleton_model)

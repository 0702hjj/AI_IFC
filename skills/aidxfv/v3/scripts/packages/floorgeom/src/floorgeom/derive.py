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


def _derive_floor(zone: dict, floor: str, floor_height_mm: float) -> dict:
    """单 zone 单层的派生量。T11：直边版；T12：弧/孔/语境。"""
    blocks = zone.get("outline_mm") or []
    polys = []
    for b in blocks:
        outer_p, holes_p = _block_polygons(b)
        # 净多边形 = outer − holes（面积用净）
        net = outer_p
        for h in holes_p:
            if outer_p.contains(h):
                net = net.difference(h)
        polys.append({"outer": outer_p, "holes": holes_p, "net": net})

    if not polys:
        return {"floor": floor, "error": "no_outline"}

    # 净面积 = 各块净面积之和（T11 单块为主，多块求和）
    area_sqm = sum(_polygon_area_sqm(p["net"]) for p in polys)

    # 全部外环合并（多块 union 用于 bbox/depth）
    union_outer = Polygon()
    for p in polys:
        union_outer = union_outer.union(p["outer"])
    bbox = union_outer.bounds  # (minx, miny, maxx, maxy)
    w_m = (bbox[2] - bbox[0]) / 1000.0
    d_m = (bbox[3] - bbox[1]) / 1000.0
    aspect = w_m / d_m if d_m > 0 else 0.0

    # 边清单 + 暴露面（主块外环边，基于原始顶点 + 弧标注——致密化会破坏 at 下标）
    edges: list[dict] = []
    exposure: dict[str, float] = {}
    eid = 0
    main_outer = polys[0]["outer"]
    outer_vertices, outer_arcs = _outer_raw(blocks[0])
    for p0, p1, arc in _raw_edge_iter(outer_vertices, outer_arcs):
        length_m = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 1000.0
        d = _dir_of_segment(p0, p1)
        if arc is None:
            edges.append({"id": eid, "kind": "line", "dir": d, "len_m": round(length_m, 3)})
            exposure[d] = exposure.get(d, 0.0) + length_m
        else:
            # 弧段：弧长（a0/a1 显式）或致密化累加
            arc_len_m = _arc_length_deg(arc)
            edges.append({
                "id": eid, "kind": "arc", "dir": d, "len_m": round(arc_len_m, 3),
                "arc": {k: arc[k] for k in ("center", "radius") if k in arc},
            })
            if "a0" in arc:
                edges[-1]["arc"]["a0"] = arc["a0"]
            if "a1" in arc:
                edges[-1]["arc"]["a1"] = arc["a1"]
            exposure[d] = exposure.get(d, 0.0) + arc_len_m
        eid += 1

    # 凹角（内角 > 180°）
    concave = _concave_corners(main_outer, bbox)

    # holes 派生（各块孔洞面积/region/尺寸）
    holes_out = []
    for p in polys:
        for h in p["holes"]:
            if h.is_empty:
                continue
            h_area = _polygon_area_sqm(h)
            hb = h.bounds
            hw_m = (hb[2] - hb[0]) / 1000.0
            hd_m = (hb[3] - hb[1]) / 1000.0
            hregion = _region_of_point((hb[0] + hb[2]) / 2, (hb[1] + hb[3]) / 2,
                                       bbox[0], bbox[1], bbox[2], bbox[3])
            holes_out.append({
                "area_sqm": round(h_area, 2), "region": hregion,
                "w_m": round(hw_m, 2), "d_m": round(hd_m, 2),
            })

    # dominant_axes：主边坐标集（x 向主边 y 坐标 / y 向主边 x 坐标）
    dom = _dominant_axes(main_outer)

    # 深度/暗区
    depth = _depth(union_outer, area_sqm, bbox)

    # 换算尺
    per_m_x = area_sqm / w_m if w_m > 0 else 0.0
    per_m_y = area_sqm / d_m if d_m > 0 else 0.0

    # core_anchor 语境（D31：多核心筒支持——core_anchors 数组 + core_anchor 兼容键）
    core_ctxs = _core_contexts(zone, union_outer, bbox)

    return {
        "floor": floor,
        "area_sqm": round(area_sqm, 2),
        "bbox_m": {"w": round(w_m, 2), "d": round(d_m, 2)},
        "aspect_ratio": round(aspect, 3),
        "perimeter_m": round(sum(e["len_m"] for e in edges), 2),
        "edges": edges,
        "exposure_m": {k: round(v, 3) for k, v in sorted(exposure.items())},
        "concave_corners": concave,
        "holes": holes_out,
        "depth": depth,
        "core_anchor": core_ctxs[0] if core_ctxs else None,  # 兼容键：单=对象/多=首个
        "core_anchors": core_ctxs,                            # D31：总是数组
        "dominant_axes": dom,
        "strip_area": {"per_m_x_sqm": round(per_m_x, 2), "per_m_y_sqm": round(per_m_y, 2)},
        "neighbors": [],  # T12 末尾统一填
        "diff_from_prev": None,  # T12 末尾统一填
    }


def _outer_rings_to_lines(poly: Polygon) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """外环坐标 → 线段列表。"""
    lines = []
    coords = list(poly.exterior.coords)
    for i in range(len(coords) - 1):
        lines.append(((coords[i][0], coords[i][1]), (coords[i + 1][0], coords[i + 1][1])))
    return lines


def _outer_arcs(block: dict, poly: Polygon) -> dict:
    """块级弧标注 → {顶点下标: arc}（外环顶点下标 → 弧）。

    兼容两种形态：block.arcs（bare polygon + block-level arcs）与
    block.outer.arcs（ring object 自带 arcs）。
    """
    arcs = block.get("arcs") or []
    if isinstance(block.get("outer"), dict):
        arcs = (block["outer"].get("arcs") or []) or arcs
    return {int(a["at"]): a for a in arcs}


def _outer_raw(block: dict) -> tuple[list, dict]:
    """原始外环顶点 + 弧标注（未致密化）。"""
    outer = block["outer"]
    if isinstance(outer, dict):
        return outer["vertices"], {int(a["at"]): a for a in outer.get("arcs") or []}
    return outer, {int(a["at"]): a for a in block.get("arcs") or []}


def _raw_edge_iter(vertices: list, arc_by_at: dict):
    """原始外环边遍历（顶点 i → i+1），带弧标注。"""
    n = len(vertices)
    for i in range(n):
        p0 = (float(vertices[i][0]), float(vertices[i][1]))
        p1 = (float(vertices[(i + 1) % n][0]), float(vertices[(i + 1) % n][1]))
        yield p0, p1, arc_by_at.get(i)


def _arc_length_deg(arc: dict) -> float:
    """弧长（mm → m）：a0/a1 显式时用圆心角；缺省退化为弦长。"""
    r = float(arc.get("radius", 0))
    if r <= 0:
        return 0.0
    if "a0" in arc and "a1" in arc:
        span = abs(float(arc["a1"]) - float(arc["a0"]))
        if span > 360:
            span = 360 - (span - 360)
        if span > 180:
            span = 360 - span
        return math.radians(span) * r / 1000.0
    return 0.0


def _arc_length(arc: dict, poly: Polygon) -> float:
    """旧版弧长（兼容保留）。"""
    return _arc_length_deg(arc)


def _core_contexts(zone: dict, union_outer: Polygon, bbox) -> list[dict]:
    """plan 预锁锚点的空间语境（D31：多核心筒——返回数组）。

    锚点来源：core_anchor_mm（单 [x,y] 或嵌套 [[x,y],...]）
    或 core（单 ring 或 ring 数组）质心。每个锚点产一个语境 dict。
    """
    anchors: list = []
    anchor = zone.get("core_anchor_mm")
    if anchor is not None:
        # 嵌套数组 [[x,y],...] vs 单点 [x,y]
        if anchor and isinstance(anchor[0], (list, tuple)):
            anchors = [list(a) for a in anchor]
        else:
            anchors = [list(anchor)]
    if not anchors:
        core = zone.get("core")
        if core is not None:
            rings = core if isinstance(core, list) else [core]
            for ring in rings:
                try:
                    cp = _ring_to_polygon(ring)
                    anchors.append([cp.centroid.x, cp.centroid.y])
                except Exception:
                    pass
    return [ctx for a in anchors
            if (ctx := _single_core_context(a, bbox)) is not None]


def _single_core_context(anchor, bbox) -> dict | None:
    """单锚点 → 空间语境（relative + dist_to_edges）。"""
    ax, ay = float(anchor[0]), float(anchor[1])
    bbox0 = (bbox[0], bbox[1], bbox[2], bbox[3])
    rel = _region_of_point(ax, ay, *bbox0)
    # 相对方位（中心/偏X）
    if rel == "center":
        relative = "center"
    elif rel in ("N", "S", "E", "W"):
        relative = f"{rel}缘"
    else:
        # NE → "中心偏NE"（简称）
        relative = f"偏{rel}"
    dist = {
        "W": (ax - bbox[0]) / 1000.0,
        "S": (ay - bbox[1]) / 1000.0,
        "N": (bbox[3] - ay) / 1000.0,
        "E": (bbox[2] - ax) / 1000.0,
    }
    return {
        "abs": [round(ax), round(ay)],
        "relative": relative,
        "dist_to_edges_m": {k: round(v, 2) for k, v in dist.items()},
    }


def _concave_corners(poly: Polygon, bbox) -> list[dict]:
    """凹角检测：内角 >180°（叉积符号）。"""
    coords = list(poly.exterior.coords)[:-1]
    if len(coords) < 4:
        return []
    # 外环默认 CCW（shapely），内角 = 360° - 外角；用叉积判断凹（右转）
    out = []
    n = len(coords)
    for i in range(n):
        p0 = coords[i - 1]
        p1 = coords[i]
        p2 = coords[(i + 1) % n]
        v1 = (p1[0] - p0[0], p1[1] - p0[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        cross = v1[0] * v2[1] - v1[1] * v2[0]
        # 外环 CCW：cross < 0 为凹
        if cross < -1e-6:
            region = _region_of_point(p1[0], p1[1], bbox[0], bbox[1], bbox[2], bbox[3])
            out.append({"at_vertex": i, "region": region})
    return out


def _dominant_axes(poly: Polygon) -> dict:
    """主边坐标集：x 向主边（近水平）的 y 值 + y 向主边（近垂直）的 x 值。"""
    xs, ys = [], []
    for p0, p1 in _outer_rings_to_lines(poly):
        dx = abs(p1[0] - p0[0])
        dy = abs(p1[1] - p0[1])
        if dx > dy * 5:  # 近水平
            ys.append(round((p0[1] + p1[1]) / 2))
        elif dy > dx * 5:  # 近垂直
            xs.append(round((p0[0] + p1[0]) / 2))
    return {
        "x": sorted(set(xs)) if xs else [0],
        "y": sorted(set(ys)) if ys else [0],
    }


def _depth(union_outer: Polygon, area_sqm: float, bbox) -> dict:
    """进深/暗区：max_m + deep_zone_ratio（距外边界 >8m 面积占比）。"""
    # 最大进深 ≈ 外接框短边（进深 = 垂直于主临街面方向的深度，矩形取短边）
    w_m = (bbox[2] - bbox[0]) / 1000.0
    d_m = (bbox[3] - bbox[1]) / 1000.0
    max_m = min(w_m, d_m)

    # 暗区：outer 向内部 buffer -8000mm
    try:
        deep = union_outer.buffer(-DEEP_ZONE_DEPTH_M * 1000.0)
        deep_area = _polygon_area_sqm(deep) if not deep.is_empty else 0.0
    except Exception:
        deep_area = 0.0
    ratio = deep_area / area_sqm if area_sqm > 0 else 0.0
    region = "center"
    if ratio > 1e-9:
        region = _region_of_point(
            (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2, bbox[0], bbox[1], bbox[2], bbox[3]
        )
    return {"max_m": round(max_m, 2), "deep_zone_ratio": round(ratio, 4), "deep_zone_region": region}


def derive(plan: dict | list[dict]) -> dict:
    """plan → 派生量（geo_cognition §1）。

    :param plan: plan.json 整个 dict（取 zones），或直接传 zones 数组（兼容）
    :return: {"floors": {floor: {…}}, "zones": [...]}——floors 键 = 楼层 id
    """
    plan_zones = plan["zones"] if isinstance(plan, dict) else plan
    floors: dict[str, dict] = {}
    zone_out = []
    # 每 zone 每层的净多边形（用于邻接/差量二次 pass）
    floor_polys: dict[str, Polygon] = {}
    for zi, zone in enumerate(plan_zones):
        floors_spec = zone.get("floors")
        floor_list = _floor_list(floors_spec)
        for floor in floor_list:
            f = _derive_floor(zone, floor, zone.get("floor_height_mm", 3000))
            # 净多边形缓存（_derive_floor 内算了，这里重算一次供邻接用）
            net = _zone_net_polygon(zone)
            floor_polys[floor] = net
            floors[floor] = f
        zone_out.append({"id": zone.get("id"), "floors": floor_list})

    # 二次 pass：neighbors（跨 zone 共享边）+ diff_from_prev（同 zone 渐退链）
    for floor, f in floors.items():
        f["neighbors"] = _find_neighbors(floor, floor_polys)
        f["diff_from_prev"] = _diff_from_prev(floor, floor_polys, plan_zones)
    return {"floors": floors, "zones": zone_out}


def _zone_net_polygon(zone: dict) -> Polygon:
    """zone 全部 outline 块净面积 union。"""
    u = Polygon()
    for b in zone.get("outline_mm") or []:
        outer_p, holes_p = _block_polygons(b)
        net = outer_p
        for h in holes_p:
            if outer_p.contains(h):
                net = net.difference(h)
        u = u.union(net)
    return u


def _find_neighbors(floor: str, floor_polys: dict) -> list[dict]:
    """跨 zone 共享边：floor 多边形与同层其他 zone 共享边。"""
    # 简化：同层号的其他 floor 多边形与之相交即记录共享边长度
    mine = floor_polys.get(floor)
    if mine is None or mine.is_empty:
        return []
    out = []
    for other, poly in floor_polys.items():
        if other == floor:
            continue
        if not poly.is_empty and mine.intersects(poly):
            shared = mine.intersection(poly)
            shared_len = shared.length / 1000.0 if shared.geom_type != "GeometryCollection" else 0.0
            if shared_len > 0.5:  # >0.5m 才算真共享边
                out.append({"zone": other, "shared_edge": "shared", "len_m": round(shared_len, 2)})
    return out


def _diff_from_prev(floor: str, floor_polys: dict, plan_zones: list) -> dict | None:
    """同 zone 渐退链差量：上一层（数字-1）与当前层的 outline 差。

    inset_mm 语义：正值 = 该方向内缩（当前层比上一层收进），负值 = 外扩。
    """
    # 解析楼层号
    num = _floor_num(floor)
    if num is None:
        return None
    prev = f"f{num - 1}"
    if prev not in floor_polys:
        return None
    cur, pv = floor_polys[floor], floor_polys[prev]
    if cur.is_empty or pv.is_empty:
        return None
    # 差量：cur 在 pv 基础上内缩/外扩的方向与量（bbox 级近似）
    cb, pb = cur.bounds, pv.bounds
    inset = {}
    # S/W：cur_min - prev_min；正值 = 内缩（cur 边界向内）
    sw = {"S": (cb[1] - pb[1]), "W": (cb[0] - pb[0])}
    # N/E：prev_max - cur_max；正值 = 内缩
    ne = {"N": (pb[3] - cb[3]), "E": (pb[2] - cb[2])}
    for side, diff in {**sw, **ne}.items():
        diff_mm = diff  # mm
        if abs(diff_mm) > 10:  # >10mm 才算差异
            inset[side] = round(diff_mm)
    if not inset:
        return None
    return {"floor": prev, "inset_mm": inset}


def _floor_num(floor: str) -> int | None:
    """f10 → 10；f1 → 1。"""
    if floor.startswith("f") and floor[1:].isdigit():
        return int(floor[1:])
    return None


def _floor_list(floors_spec) -> list[str]:
    """plan zone.floors（{from,to} 或 [n,...]）→ 楼层 id 列表。"""
    if floors_spec is None:
        return ["f1"]
    if isinstance(floors_spec, dict):
        lo, hi = floors_spec.get("from", 1), floors_spec.get("to", 1)
        return [f"f{i}" for i in range(lo, hi + 1)]
    if isinstance(floors_spec, list):
        return [f"f{i}" for i in floors_spec]
    return ["f1"]

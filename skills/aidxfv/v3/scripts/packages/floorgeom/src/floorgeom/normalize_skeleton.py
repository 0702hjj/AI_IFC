"""floorgeom/normalize_skeleton.py —— 骨架分层外推（波次 2，D40）。

机器差集产分区多边形（零坐标手算）：
  1. corridor zone = 外缘 − union(cores)（环带/带形走廊区域）
  2. 大区 = outline − corridor zone（差集自动，多块）
  3. 切割线 = from/to 锚定（ref+edge+at）→ 绝对坐标线段
  4. 切段 = 大区 shapely split by 切割线
  5. blocks between 认领（候选段唯一 → 认领；多个 → side 方位消歧）
  6. 轴网派生 = 分区边界坐标集合（模型不手填）
  7. 分区标签 = 段质心 BLOCK_<id>

纯函数 + 字节级确定；只依赖 shapely。SchemaError 结构化回喂。
"""

from __future__ import annotations

import math

from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import split as shapely_split
from shapely.ops import unary_union

from .normalize import SchemaError, _edge_outward_normal, _normal_to_direction

# 方位 → 质心相对方位（side 消歧用）
_SIDE_DIR = {
    "N": (0.0, 1.0), "S": (0.0, -1.0), "E": (1.0, 0.0), "W": (-1.0, 0.0),
    "NE": (1.0, 1.0), "NW": (-1.0, 1.0), "SE": (1.0, -1.0), "SW": (-1.0, -1.0),
}


def _ring_edges_polygon(ring_vertices: list[list[float]]) -> Polygon:
    """顶点环 → shapely Polygon（自动闭合/去退化）。"""
    poly = Polygon(ring_vertices)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly


def _point_along_edge(edge_pts: list[list[float]], at: float) -> list[float]:
    """沿折线边按比例取点（弦近似弧边）。"""
    segs = []
    total = 0.0
    for i in range(len(edge_pts) - 1):
        d = math.hypot(edge_pts[i + 1][0] - edge_pts[i][0],
                       edge_pts[i + 1][1] - edge_pts[i][1])
        segs.append((edge_pts[i], edge_pts[i + 1], d))
        total += d
    target = at * total
    acc = 0.0
    for p0, p1, d in segs:
        if acc + d >= target - 1e-9:
            t = (target - acc) / d if d > 1e-9 else 0.0
            return [p0[0] + t * (p1[0] - p0[0]), p0[1] + t * (p1[1] - p0[1])]
        acc += d
    return list(segs[-1][1])


def _find_direction_edge(ring_vertices: list[list[float]], direction: str) -> list[list[float]]:
    """在闭合环上找外法向方位 = direction 的边（返回该边两端点）。"""
    n = len(ring_vertices)
    for i in range(n):
        p0, p1 = ring_vertices[i], ring_vertices[(i + 1) % n]
        nx, ny = _edge_outward_normal(p0, p1)
        if _normal_to_direction(nx, ny) == direction:
            return [list(p0), list(p1)]
    return []


def _resolve_anchor(anchor: dict, ctx: dict, at: str) -> list[float]:
    """锚定 ref+edge+at → 绝对坐标点。

    ctx: {corridor_outer: [环顶点], outline_edges: [[边...]...], cores: {id: [环顶点]},
          holes: [[环顶点]...]}
    """
    ref = anchor["ref"]
    at_frac = float(anchor.get("at", 0.5))
    edge_dir = anchor.get("edge")

    if ref == "corridor:outer":
        ring = ctx.get("corridor_outer")
        if not ring:
            raise SchemaError("anchor_ref_unavailable", at, ref=ref)
        if edge_dir:
            edge = _find_direction_edge(ring, edge_dir)
            if not edge:
                raise SchemaError("anchor_edge_not_found", at, ref=ref, edge=edge_dir)
            return _point_along_edge(edge, at_frac)
        return _point_along_edge(ring + [ring[0]], at_frac)

    if ref.startswith("outline:edge:"):
        try:
            idx = int(ref.split(":")[2])
        except (IndexError, ValueError):
            raise SchemaError("bad_anchor_ref", at, ref=ref)
        edges = ctx.get("outline_edges") or []
        if idx < 0 or idx >= len(edges):
            raise SchemaError("anchor_edge_out_of_range", at, ref=ref, count=len(edges))
        return _point_along_edge(edges[idx], at_frac)

    if ref.startswith("core:"):
        cid = ref.split(":", 1)[1]
        ring = (ctx.get("cores") or {}).get(cid)
        if not ring:
            raise SchemaError("anchor_ref_unavailable", at, ref=ref)
        if edge_dir:
            edge = _find_direction_edge(ring, edge_dir)
            if not edge:
                raise SchemaError("anchor_edge_not_found", at, ref=ref, edge=edge_dir)
            return _point_along_edge(edge, at_frac)
        return _point_along_edge(ring + [ring[0]], at_frac)

    if ref.startswith("hole:"):
        try:
            idx = int(ref.split(":")[1])
        except (IndexError, ValueError):
            raise SchemaError("bad_anchor_ref", at, ref=ref)
        holes = ctx.get("holes") or []
        if idx < 0 or idx >= len(holes):
            raise SchemaError("anchor_ref_unavailable", at, ref=ref)
        return _point_along_edge(holes[idx] + [holes[idx][0]], at_frac)

    raise SchemaError("bad_anchor_ref", at, ref=ref)


def push_layers(outline_polys: list[Polygon],
                outline_edges: list[list[list[float]]],
                holes_rings: list[list[list[float]]],
                cores: dict[str, list[list[float]]],
                corridor_outer: list[list[float]] | None,
                cuts_spec: list[dict],
                blocks_spec: list[dict]) -> dict:
    """分层外推主函数（D40）。

    :param outline_polys: outline 各块 Polygon（外环）
    :param outline_edges: 各块边列表（锚定用，与 outline_polys 对应摊平）
    :param holes_rings: 孔洞环顶点
    :param cores: {core_id: 环顶点}
    :param corridor_outer: corridor 外缘环顶点（None = 无走廊，形态族 C/D）
    :param cuts_spec: main_partitions 切割线声明（{id, from, to}）
    :param blocks_spec: blocks 声明（between 形式）
    :return: {corridor_zone, big_zones, cuts, blocks_claimed, axis_grid_derived,
              partition_labels}
    """
    out = {
        "corridor_zone": None,
        "big_zones": [],
        "cuts": [],
        "blocks_claimed": [],
        "axis_grid_derived": {"x": [], "y": []},
        "partition_labels": [],
    }

    union_outline = unary_union(outline_polys)
    union_cores = unary_union([Polygon(v).buffer(0) for v in cores.values()]) \
        if cores else None

    # ① corridor zone = 外缘 − union(cores)
    corridor_zone = None
    corridor_outer_poly = None
    if corridor_outer and len(corridor_outer) >= 3:
        outer_poly = _ring_edges_polygon(corridor_outer)
        corridor_outer_poly = outer_poly
        zone = outer_poly.difference(union_cores) if union_cores is not None else outer_poly
        corridor_zone = zone if not zone.is_empty else None
        out["corridor_zone"] = {
            "polygon_mm": _poly_meta(zone),
        } if zone is not None and not zone.is_empty else None
    # 开线（<3 点）不产差集——旧 path 线语义兼容

    # ② 大区 = outline − corridor 外缘（差集自动，多块）
    #    注意：减的是外缘整体（含 core 区域），core 由 cores 键独立承载——
    #    总账 outline = 大区 + corridor 外缘 = 大区 + (走廊带 + core)
    if corridor_outer_poly is not None:
        big = union_outline.difference(corridor_outer_poly)
    else:
        big = union_outline
    big_polys = _as_polygon_list(big)
    out["big_zones"] = [{"polygon_mm": _poly_meta(p)} for p in big_polys]

    # ③ 切割线解析（锚定 ctx）
    ctx = {
        "corridor_outer": corridor_outer,
        "outline_edges": outline_edges,
        "cores": cores,
        "holes": holes_rings,
    }
    cuts = []
    for ci, cs in enumerate(cuts_spec):
        cat = f"main_partitions[{ci}]"
        p0 = _resolve_anchor(cs["from"], ctx, f"{cat}.from")
        p1 = _resolve_anchor(cs["to"], ctx, f"{cat}.to")
        cuts.append({"id": cs.get("id"), "line_mm": [p0, p1],
                     "line": LineString([p0, p1])})
    out["cuts"] = [{"id": c["id"], "line_mm": c["line_mm"]} for c in cuts]

    # ④ 切段：大区 split by 切割线
    segments: list[Polygon] = []
    if cuts and big_polys:
        mls = MultiLineString([c["line"] for c in cuts])
        for poly in big_polys:
            try:
                parts = shapely_split(poly, mls)
                segments.extend(_as_polygon_list(parts))
            except Exception:
                # 切割线未完全穿透 → 保持整块
                segments.append(poly)
    else:
        segments = list(big_polys)

    # ⑤ blocks between 认领
    claimed: list[dict] = []
    remaining = list(segments)
    for bi, bs in enumerate(blocks_spec):
        bat = f"blocks[{bi}]"
        between = bs.get("between") or []
        if not between:
            continue
        cut_ids = set(between)
        cut_lines = [c["line"] for c in cuts if c.get("id") in cut_ids]
        if len(cut_lines) != len(cut_ids):
            missing = cut_ids - {c.get("id") for c in cuts if c.get("id")}
            raise SchemaError("block_between_unknown_cut", bat, missing=sorted(missing))
        cands = []
        for seg in remaining:
            touches_all = all(seg.touches(cl) or seg.intersects(cl) for cl in cut_lines)
            if touches_all:
                cands.append(seg)
        if not cands:
            raise SchemaError("block_between_no_segment", bat, between=sorted(cut_ids))
        picked = cands[0]
        if len(cands) > 1:
            side = bs.get("side")
            if not side:
                raise SchemaError("block_between_ambiguous", bat,
                                  candidates=len(cands),
                                  hint="加 side 方位消歧（质心相对走廊质心）")
            picked = _pick_by_side(cands, side, corridor_zone, bat)
        remaining.remove(picked)
        meta = _poly_meta(picked)
        claimed.append({"id": bs.get("id"), "role": bs.get("role"),
                        "polygon_mm": meta, "poly": picked})
        out["partition_labels"].append({
            "block": bs.get("id"),
            "tag": f"BLOCK_{bs.get('id')}" if bs.get("id") else None,
            "at_mm": meta["centroid_mm"],
        })
    out["blocks_claimed"] = [
        {"id": b["id"], "role": b["role"], "polygon_mm": b["polygon_mm"]}
        for b in claimed
    ]
    # D46：切段产出（大区被切割线切出的段——rooms 分块承接的边界，
    # 不依赖 blocks 认领；已认领段带 block_id）
    claimed_ids = {b["id"]: True for b in claimed}
    out["segments"] = [
        {"id": f"seg:{si}", "polygon_mm": _poly_meta(seg)}
        for si, seg in enumerate(segments)
    ]

    # ⑥ 轴网派生：分区边界坐标集合
    xs, ys = set(), set()
    for poly in [union_outline, corridor_zone if corridor_zone is not None else None]:
        if poly is None:
            continue
        for p in _as_polygon_list(poly):
            for x, y in p.exterior.coords:
                xs.add(round(x, 3)); ys.add(round(y, 3))
            for hole in p.interiors:
                for x, y in hole.coords:
                    xs.add(round(x, 3)); ys.add(round(y, 3))
    for v in cores.values():
        for x, y in v:
            xs.add(round(x, 3)); ys.add(round(y, 3))
    for c in cuts:
        for x, y in c["line_mm"]:
            xs.add(round(x, 3)); ys.add(round(y, 3))
    out["axis_grid_derived"] = {"x": sorted(xs), "y": sorted(ys)}

    return out


def _as_polygon_list(geom) -> list[Polygon]:
    """Geometry/MultiPolygon/GeometryCollection → Polygon 列表。"""
    from shapely.geometry import GeometryCollection, MultiPolygon
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    if isinstance(geom, GeometryCollection):
        return [g for g in geom.geoms if isinstance(g, Polygon)]
    return [geom] if isinstance(geom, Polygon) else []


def _pick_by_side(cands: list[Polygon], side: str, corridor_zone, at: str) -> Polygon:
    """候选段方位消歧：质心相对走廊质心（无走廊 → 整体质心）的 8 方位。"""
    base = corridor_zone.centroid if corridor_zone is not None else None
    dirv = _SIDE_DIR[side]
    best, best_score = None, None
    for cand in cands:
        cx, cy = cand.centroid.x, cand.centroid.y
        bx, by = (base.x, base.y) if base is not None else (0.0, 0.0)
        score = (cx - bx) * dirv[0] + (cy - by) * dirv[1]
        if best_score is None or score > best_score:
            best_score, best = score, cand
    return best


def _poly_meta(poly) -> dict:
    """Polygon/MultiPolygon → {vertices, holes, area_sqm, centroid_mm}。

    环带（corridor 外缘 − core 差集）的内环进 holes——不丢孔洞几何。
    MultiPolygon：vertices/holes 取主块（最大面积），area 总面积，centroid 整体质心。
    """
    polys = _as_polygon_list(poly)
    main = max(polys, key=lambda p: p.area) if polys else None
    verts = ([[round(float(x), 3), round(float(y), 3)]
              for x, y in main.exterior.coords[:-1]] if main is not None else [])
    holes = []
    if main is not None:
        for ring in main.interiors:
            holes.append([[round(float(x), 3), round(float(y), 3)]
                          for x, y in ring.coords[:-1]])
    return {
        "vertices": verts,
        **({"holes": holes} if holes else {}),
        "area_sqm": round(poly.area / 1e6, 3),
        "centroid_mm": [round(float(poly.centroid.x), 3),
                        round(float(poly.centroid.y), 3)],
    }

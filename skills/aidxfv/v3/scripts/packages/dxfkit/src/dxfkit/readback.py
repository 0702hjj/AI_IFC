"""readback: DXf → 房间图（V3，从 V2 layout/from_dxf.py 迁移，改包名 import）。

V2 解析器（墙体 HATCH 掩码 + 栅格洪水填充分区 + 门配对 + 标注配对）逻辑不动；
V3 适配：
- 输出增加 `to_room_graph()`：V2 词表（nodes/edges）→ V3 房间图（rooms/adjacencies/
  doors），对齐 floorgeom.reconcile 消费格式（T24+ 契约测试 P1）；
- 代理实体前置检查（I-01）：ACAD_PROXY_ENTITY 无 proxy_graphic 占比 > 阈值 → 拒收；
- layer_map 图层映射（I-04）：源图层 → 标准语义层。
"""

from __future__ import annotations

import math
import re
from collections import deque
from pathlib import Path

import ezdxf
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
from shapely.prepared import prep

from dxfkit import readback_state as _st
from dxfkit.readback_state import (  # noqa: F401 再导出保持原契约
    GRID_MM, BASE_GRID_MM, MAX_CELLS_PER_SIDE, MIN_WALL_SEG_MM,
    WALL_PAIR_GAP_MM, WALL_GAP_CLOSE_MM, PROBE_MAX_MM,
    WALL_LAYERS, DOOR_LAYER, GLAZ_LAYER, ANNO_LAYER, IGNORE_LAYERS,
    ANNO_WHITELIST, AREA_RE, CELL_COLS, PROXY_REJECT_RATIO,
    _adaptive_grid_mm, _merge_runs,
)
from dxfkit.readback_checks import (  # noqa: F401
    check_proxy_entities, LAYER_MAP_DEFAULT, _map_layer,
)
from dxfkit.readback_parse import (  # noqa: F401
    _text_pos, _arc_points, _polyline_with_bulge, _unparsed, _parse,
    _close_wall_gaps, _pair_double_line_walls,
)
from dxfkit.readback_doors import (  # noqa: F401
    _pair_doors, _seg_intersect, _arc_polyline, _polyline_hits_seg,
    doorwin_collisions,
)
from dxfkit.readback_grid import (  # noqa: F401
    _Grid, _region_at, _cells_to_polygon_mm,
)
from dxfkit.readback_graph import to_room_graph  # noqa: F401


# ---------------------------------------------------------------- 主入口

def readback(path, grid_mm: float | None = None, layer_map: dict | None = None,
             units: str | None = None, min_wall_seg_mm: float | None = None,
             close_wall_gaps: bool = False,
             bbox: tuple | list | None = None) -> dict:
    """解析 archdxf 产 DXF → 气泡图/几何 JSON（V3 入口，V2 from_dxf 逻辑）。

    输出:version / source_dxf / grid_mm / outline_mm / nodes[] / edges[] /
    windows[] / doors[] / unparsed[]。nodes/edges 词表同 cad_draft.json。
    layer_map: 源图层 → 标准语义层（I-04），缺省用 LAYER_MAP_DEFAULT。
    units: None=自动检测（doc.units）/ "mm" / "inch"（×25.4 换算，R-01 适配）。
    grid_mm: None=自适应（图幅每边 ≤MAX_CELLS 算，2 的倍数增长）/ 显式值。
    bbox: (minx, miny, maxx, maxy) 可选——只处理范围内实体（多坐标系图过滤离群段，
        如 mall 幕墙负坐标镜像段）。

    升级（2026-08-15 T33b 校准驱动）：
    - 自适应栅格：大图不爆格数；- 输出坐标归一化（平移原点，min=0）；
    - 双线墙腔填实（平行线对 buffer）；- 碎线过滤（<300mm 孤立短线）。
    """
    # 代理实体前置检查（I-01）
    proxy_errs = check_proxy_entities(path)
    if proxy_errs:
        return {"error": "G1_rejected", "reasons": proxy_errs}

    if min_wall_seg_mm is not None:
        _st.MIN_WALL_SEG_MM = float(min_wall_seg_mm)
    doc = ezdxf.readfile(Path(path))
    msp = doc.modelspace()

    # 单位换算（R-01 等：doc.units 声明 mm 但实际 inch）
    if units == "inch":
        from ezdxf.math import Matrix44
        scale = Matrix44.scale(25.4, 25.4, 1.0)
        for e in list(msp):
            try:
                e.transform(scale)
            except Exception:
                pass  # 不可缩放实体跳过

    (solids, barriers, fat_barriers, jambs, windows, texts, leafs, arcs,
     unparsed, wall_arcs) = _parse(msp, layer_map)

    # bbox 过滤：多坐标系图（mall 幕墙负坐标镜像段）只留主范围实体
    if bbox is not None:
        bx0, by0, bx1, by1 = (float(v) for v in bbox)
        solids = [s for s in solids
                  if s.bounds[0] >= bx0 and s.bounds[2] <= bx1
                  and s.bounds[1] >= by0 and s.bounds[3] <= by1]
        barriers = [s for s in barriers
                    if bx0 <= s[0][0] <= bx1 and bx0 <= s[1][0] <= bx1
                    and by0 <= s[0][1] <= by1 and by0 <= s[1][1] <= by1]
        fat_barriers = [s for s in fat_barriers
                        if bx0 <= s[0][0] <= bx1 and bx0 <= s[1][0] <= bx1
                        and by0 <= s[0][1] <= by1 and by0 <= s[1][1] <= by1]

    doors = _pair_doors(leafs, arcs, unparsed)
    # 门窗碰撞检测（details 后对账兜底）：用原始 leaf/arc 几何，只报真相交
    doorwin_issues = doorwin_collisions(leafs, arcs, windows)

    xs, ys = [], []

    def _finite(v):
        return v is not None and not math.isnan(v) and not math.isinf(v)

    for poly in solids:
        b = poly.bounds
        if all(_finite(v) for v in b):
            xs += [b[0], b[2]]; ys += [b[1], b[3]]
    for seg in barriers:
        if all(_finite(v) for v in (seg[0][0], seg[0][1], seg[1][0], seg[1][1])):
            xs += [seg[0][0], seg[1][0]]; ys += [seg[0][1], seg[1][1]]
    # 统一 NaN 防线（源头实体坐标异常兜底）
    xs = [v for v in xs if _finite(v)]
    ys = [v for v in ys if _finite(v)]
    if not xs:
        raise ValueError(f"{path}: 无任何墙体实体,无法反编译")
    # 自适应栅格（T33b）：显式 grid_mm 优先，否则按图幅算（每边 ≤MAX_CELLS）
    if grid_mm is not None:
        _st.GRID_MM = float(grid_mm)
    else:
        _st.GRID_MM = _adaptive_grid_mm(max(xs) - min(xs), max(ys) - min(ys))
    pad = 2.0 * _st.GRID_MM
    grid = _Grid(min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)

    for poly in solids:
        b = poly.bounds
        if not all(math.isfinite(v) for v in b):
            continue  # 无效多边形（NaN 顶点）跳过
        prepped = prep(poly)
        r0, c0 = grid.cell_of(b[0], b[1])
        r1, c1 = grid.cell_of(b[2], b[3])
        for r in range(max(0, r0), min(grid.ny, r1 + 2)):
            for c in range(max(0, c0), min(grid.nx, c1 + 2)):
                if not grid.solid[r][c] and prepped.covers(Point(*grid.center(r, c))):
                    grid.solid[r][c] = True
    for seg in barriers:
        grid.mark_segment(*seg)
    for seg in fat_barriers:
        grid.mark_segment(*seg, fat=True)
    for d in doors:  # 门洞封口:分区在门处断开
        grid.mark_segment(d["hinge"], d["strike"])
    # 间隙闭合（升级）：主体墙段间开口（门/窗）补线——洪水不贯通
    # 默认关闭（archdxf 产墙闭合 + door 配对已封口）；真实图（墙段开口无门配对）显式开启
    if close_wall_gaps:
        # 只取墙轴向长边（墙厚短边不进间隙匹配——否则墙厚方向端点被误连）
        wall_axes = []
        for poly in solids:
            b = poly.bounds
            if not all(math.isfinite(v) for v in b):
                continue
            w, h = b[2] - b[0], b[3] - b[1]
            if w >= h:  # 水平墙段：上下两条轴向长边
                wall_axes += [((b[0], b[1]), (b[2], b[1])),
                              ((b[0], b[3]), (b[2], b[3]))]
            else:       # 垂直墙段：左右两条轴向长边
                wall_axes += [((b[0], b[1]), (b[0], b[3])),
                              ((b[2], b[1]), (b[2], b[3]))]
        wall_axes += barriers
        for p, q in _close_wall_gaps(wall_axes):
            grid.mark_segment(p, q)

    region_map, regions = grid.flood()
    exterior_ids = {i for i, rg in enumerate(regions) if rg["exterior"]}

    # 墙段输出(B 层对账 B3 用):自由格↔实体格的边界面,合并共线长段
    wall_unit_edges = []
    for r0 in range(grid.ny):
        for c0 in range(grid.nx):
            if grid.solid[r0][c0]:
                continue
            x0 = grid.minx + c0 * _st.GRID_MM
            y0 = grid.miny + r0 * _st.GRID_MM
            x1, y1 = x0 + _st.GRID_MM, y0 + _st.GRID_MM
            # 越界按非实体(否则外边界一圈被误判为墙)
            if grid.in_range(r0, c0 + 1) and grid.solid[r0][c0 + 1]:
                wall_unit_edges.append((x1, y0, x1, y1))
            if grid.in_range(r0, c0 - 1) and grid.solid[r0][c0 - 1]:
                wall_unit_edges.append((x0, y0, x0, y1))
            if grid.in_range(r0 + 1, c0) and grid.solid[r0 + 1][c0]:
                wall_unit_edges.append((x0, y1, x1, y1))
            if grid.in_range(r0 - 1, c0) and grid.solid[r0 - 1][c0]:
                wall_unit_edges.append((x0, y0, x1, y0))
    wall_segments = _merge_runs(wall_unit_edges)

    # 房间标注配对:面积文本向上找房名
    area_texts = [t for t in texts if AREA_RE.match(t["content"])]
    name_texts = [t for t in texts if not AREA_RE.match(t["content"])]
    labels, used_names = [], set()
    for at in sorted(area_texts, key=lambda t: (t["at"][1], t["at"][0])):
        ax, ay = at["at"]
        best, best_key = None, None
        for i, nt in enumerate(name_texts):
            if i in used_names:
                continue
            nx, ny = nt["at"]
            dy = ny - ay  # 房名在面积文本上方
            if abs(nx - ax) < 1500 and 0.8 * nt["height"] < dy < 2.2 * nt["height"]:
                key = (abs(nx - ax), dy)
                if best_key is None or key < best_key:
                    best, best_key = i, key
        if best is None:
            continue
        used_names.add(best)
        labels.append({"name": name_texts[best]["content"].lower(),
                       "at": name_texts[best]["at"],
                       "area_sqm": float(AREA_RE.match(at["content"]).group(1))})

    # 分区 → 节点
    region_node = {}
    nodes = []
    named = sorted(labels, key=lambda l: l["name"])
    for label in named:
        rid = _region_at(grid, region_map, *label["at"])
        if rid is None or rid in exterior_ids:
            continue
        region_node.setdefault(rid, []).append(label)
    seen_ids = {}
    for rid in sorted(region_node, key=lambda i: min(region_node[i], key=lambda l: l["name"])["name"]):
        rg = regions[rid]
        label_group = sorted(region_node[rid], key=lambda l: l["name"])
        cx = sum(grid.center(r, c)[0] for r, c in rg["cells"]) / len(rg["cells"])
        cy = sum(grid.center(r, c)[1] for r, c in rg["cells"]) / len(rg["cells"])
        area_geo = len(rg["cells"]) * _st.GRID_MM * _st.GRID_MM / 1e6
        main = label_group[0]
        base_id = re.sub(r"\s+", "_", main["name"])
        seen_ids[base_id] = seen_ids.get(base_id, 0) + 1
        node_id = base_id if seen_ids[base_id] == 1 else f"{base_id}_{seen_ids[base_id]}"
        nodes.append({
            "id": node_id,
            "type": base_id,
            "area_sqm": main["area_sqm"],
            "area_geo_sqm": round(area_geo, 2),
            "centroid_mm": [round(cx, 3), round(cy, 3)],
            "polygon_mm": _cells_to_polygon_mm(rg["cells"], grid),
            "region_id": rid,
            "_labels": label_group if len(label_group) > 1 else None,
            "_min_cell": min(rg["cells"]),
        })
    # 未标注的室内分区:诚实记录;剔除墙带夹层等栅格残渣(<0.25㎡)
    MIN_SPACE_CELLS = 100  # 0.25㎡ @50mm
    labeled_rids = set(region_node)
    interior_unlabeled = [i for i, rg in enumerate(regions)
                          if not rg["exterior"] and i not in labeled_rids
                          and len(rg["cells"]) >= MIN_SPACE_CELLS]
    interior_unlabeled.sort(key=lambda i: min(regions[i]["cells"]))
    for k, rid in enumerate(interior_unlabeled, 1):
        rg = regions[rid]
        cx = sum(grid.center(r, c)[0] for r, c in rg["cells"]) / len(rg["cells"])
        cy = sum(grid.center(r, c)[1] for r, c in rg["cells"]) / len(rg["cells"])
        nodes.append({
            "id": f"space_{k}", "type": "unlabeled", "area_sqm": None,
            "area_geo_sqm": round(len(rg["cells"]) * _st.GRID_MM * _st.GRID_MM / 1e6, 2),
            "centroid_mm": [round(cx, 3), round(cy, 3)],
            "polygon_mm": _cells_to_polygon_mm(rg["cells"], grid),
            "region_id": rid, "_labels": None, "_min_cell": min(rg["cells"]),
        })

    # 外轮廓:墙体实体 ∪ 室内分区格
    # 外轮廓:墙体实体 ∪ 室内分区格 ∪ 开洞补缺(jamb 对恢复被切除的墙带)
    def _plug(p1, p2):
        # jamb 横跨墙厚,与开洞走向垂直;按方向过滤,防止误配墙端短面线
        sx, sy = p2[0] - p1[0], p2[1] - p1[1]
        sl = math.hypot(sx, sy) or 1.0
        su, sv = sx / sl, sy / sl
        cands = []
        for j in jambs:
            jx, jy = j[1][0] - j[0][0], j[1][1] - j[0][1]
            jl = math.hypot(jx, jy) or 1.0
            if abs(jx * su + jy * sv) / jl <= 0.3:
                cands.append(j)
        ends = []
        for p in (p1, p2):
            best, best_d = None, 150.0
            for j in cands:
                d = min(math.hypot(j[0][0] - p[0], j[0][1] - p[1]),
                        math.hypot(j[1][0] - p[0], j[1][1] - p[1]))
                if d < best_d:
                    best, best_d = j, d
            if best is None:
                return None
            ends.append(best)
        return Polygon([ends[0][0], ends[0][1], ends[1][1], ends[1][0]])

    plugs = []
    for d in doors:
        plug = _plug(d["hinge"], d["strike"])
        if plug is not None:
            plugs.append(plug)
    for seg in windows:
        plug = _plug(seg[0], seg[1])
        if plug is not None:
            plugs.append(plug)

    interior_boxes = []
    for i, rg in enumerate(regions):
        if rg["exterior"]:
            continue
        for r, c in rg["cells"]:
            x0 = grid.minx + c * _st.GRID_MM
            y0 = grid.miny + r * _st.GRID_MM
            interior_boxes.append(box(x0, y0, x0 + _st.GRID_MM, y0 + _st.GRID_MM))
    # 防御性拓扑修复：大量 box union 可能触发 GEOS TopologyException
    # （side location conflict），逐级降级处理
    import logging
    _logger = logging.getLogger("dxfkit.readback")
    all_parts = sorted(solids, key=lambda p: p.bounds) + plugs + interior_boxes
    
    # 级别 1：直接 union
    try:
        footprint = unary_union(all_parts)
        if not footprint.is_valid:
            footprint = footprint.buffer(0)
    except Exception:
        _logger.warning("unary_union 失败，降级：interior_boxes buffer(0) 后合并")
        # 级别 2：先 buffer(0) 每个 box 再合并
        try:
            valid_boxes = [b.buffer(0) for b in interior_boxes if b.is_valid]
            valid_plugs = [p.buffer(0) for p in plugs if p.is_valid]
            footprint = unary_union(valid_boxes + valid_plugs + 
                                   [s for s in solids if s.is_valid])
            if not footprint.is_valid:
                footprint = footprint.buffer(0)
        except Exception:
            _logger.warning("分步合并也失败，降级：convex_hull")
            # 级别 3：用 interior_boxes 的 convex_hull（粗略但稳健）
            from shapely.geometry import MultiPoint
            all_coords = []
            for b in interior_boxes:
                all_coords.extend(list(b.exterior.coords))
            if all_coords:
                footprint = MultiPoint(all_coords).convex_hull
            else:
                # 级别 4：用 barriers bbox
                bxs = [s[0][0] for s in barriers] + [s[1][0] for s in barriers]
                bys = [s[0][1] for s in barriers] + [s[1][1] for s in barriers]
                from shapely.geometry import box as _box
                footprint = _box(min(bxs), min(bys), max(bxs), max(bys))
    if footprint.geom_type == "MultiPolygon":
        footprint = max(footprint.geoms, key=lambda p: p.area)
    elif footprint.geom_type == "GeometryCollection":
        # 斜墙/复杂分隔可能产生 GeometryCollection——取面积最大 polygon 成员
        candidates = []
        for g in footprint.geoms:
            if g.geom_type == "Polygon":
                candidates.append(g)
            elif g.geom_type == "MultiPolygon":
                candidates.extend(g.geoms)
        if not candidates:
            raise ValueError(f"{path}: 无法从解析结果构造外轮廓")
        footprint = max(candidates, key=lambda p: p.area)
    footprint = footprint.simplify(_st.GRID_MM / 2, preserve_topology=True)
    from shapely import normalize
    outline = [
        [round(x, 3), round(y, 3)]
        for x, y in list(normalize(footprint).exterior.coords)[:-1]
    ]
    minx, miny, maxx, maxy = footprint.bounds

    def _cell_of_point(cx, cy):
        col = min(4, max(0, int((cx - minx) / (maxx - minx) * 5)))
        row = min(4, max(0, int((cy - miny) / (maxy - miny) * 5)))
        return f"{CELL_COLS[col]}{row + 1}"

    total_geo = sum(n["area_geo_sqm"] for n in nodes)
    for n in nodes:
        n["cell"] = _cell_of_point(*n["centroid_mm"])
        n["area_ratio"] = round(n["area_geo_sqm"] / total_geo, 4) if total_geo else None

    # 门边:开洞中点向两侧探测分区
    def _probe(mid, direction, sign):
        dx, dy = direction
        k = _st.GRID_MM
        while k <= PROBE_MAX_MM:
            x = mid[0] + sign * dx * k
            y = mid[1] + sign * dy * k
            rid = _region_at(grid, region_map, x, y)
            if rid is not None:
                return rid
            k += _st.GRID_MM
        return None

    rid_to_node = {n["region_id"]: n["id"] for n in nodes}
    edges, open_pairs = set(), set()
    for d in sorted(doors, key=lambda d: (d["hinge"], d["strike"])):
        hx, hy = d["hinge"]
        sx, sy = d["strike"]
        length = math.hypot(sx - hx, sy - hy) or 1.0
        along = ((sx - hx) / length, (sy - hy) / length)
        normal = (-along[1], along[0])
        mid = ((hx + sx) / 2, (hy + sy) / 2)
        ra = _probe(mid, normal, +1)
        rb = _probe(mid, normal, -1)
        if ra is None or rb is None or ra == rb:
            continue
        if ra in exterior_ids or rb in exterior_ids:
            inner = ra if rb in exterior_ids else rb
            name = rid_to_node.get(inner, f"region_{inner}")
            edges.add((name, "outside", "front_door"))
        else:
            a = rid_to_node.get(ra, f"region_{ra}")
            b = rid_to_node.get(rb, f"region_{rb}")
            edges.add(tuple(sorted((a, b))) + ("door",))
    # 开敞连通:同一分区多个房名
    for n in nodes:
        if n["_labels"]:
            ids = [n["id"]] if len(n["_labels"]) == 1 else None
    for rid, label_group in region_node.items():
        if len(label_group) > 1:
            names = sorted(re.sub(r"\s+", "_", l["name"]) for l in label_group)
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    open_pairs.add((names[i], names[j], "open"))
    edges |= open_pairs

    nodes_out = []
    for n in sorted(nodes, key=lambda n: n["id"]):
        nodes_out.append({
            "id": n["id"], "type": n["type"], "area_sqm": n["area_sqm"],
            "area_geo_sqm": n["area_geo_sqm"], "area_ratio": n["area_ratio"],
            "cell": n["cell"], "centroid_mm": n["centroid_mm"],
            "polygon_mm": n.get("polygon_mm"),
        })
    edges_out = [{"a": a, "b": b, "via": v}
                 for a, b, v in sorted(edges)]
    windows_out = [
        {"at": [round((s[0] + t[0]) / 2, 3), round((s[1] + t[1]) / 2, 3)],
         "width_mm": round(math.hypot(t[0] - s[0], t[1] - s[1]), 3)}
        for s, t in sorted(windows)
    ]
    doors_out = sorted(doors, key=lambda d: (d["hinge"], d["strike"]))
    unparsed.sort(key=lambda u: (u["layer"], u["entity"], u["at"]))

    # 坐标归一化（升级）：全部坐标平移原点（ox,oy）→ min = 0，防大坐标下游浮点问题
    ox, oy = grid.minx, grid.miny

    def _shift2(v):
        return [round(v[0] - ox, 3), round(v[1] - oy, 3)]

    def _shift_poly(verts):
        return [[round(v[0] - ox, 3), round(v[1] - oy, 3)] for v in verts]

    outline = _shift_poly(outline)
    for n in nodes_out:
        if "polygon_mm" in n:
            n["polygon_mm"] = _shift_poly(n["polygon_mm"])
        if "centroid_mm" in n:
            n["centroid_mm"] = _shift2(n["centroid_mm"])
    wall_segments = [[_shift2(s), _shift2(t)] for s, t in wall_segments]
    windows_out = [
        {"at": [round((s[0] + t[0]) / 2 - ox, 3), round((s[1] + t[1]) / 2 - oy, 3)],
         "width_mm": round(math.hypot(t[0] - s[0], t[1] - s[1]), 3)}
        for s, t in sorted(windows)
    ]
    doors_out = [
        {"hinge": _shift2(d["hinge"]), "strike": _shift2(d["strike"]),
         "at": _shift2(d.get("at", [d["hinge"][0] + ox, d["hinge"][1] + oy])),
         "width_mm": d["width_mm"]}
        for d in doors_out
    ]

    return {
        "version": 1,
        "source_dxf": Path(path).name,
        "grid_mm": _st.GRID_MM,
        "outline_mm": outline,
        "nodes": nodes_out,
        "edges": edges_out,
        "windows": windows_out,
        "doors": [
            {"hinge": [round(v, 3) for v in d["hinge"]],
             "strike": [round(v, 3) for v in d["strike"]],
             "at": [round((d["hinge"][0] + d["strike"][0]) / 2, 3),
                    round((d["hinge"][1] + d["strike"][1]) / 2, 3)],
             "width_mm": d["width_mm"]}
            for d in doors_out
        ],
        "wall_segments": wall_segments,
        "wall_arcs": sorted(wall_arcs, key=lambda a: (a["center"], a["radius"])),
        "doorwin_issues": doorwin_issues,
        "unparsed": unparsed,
    }


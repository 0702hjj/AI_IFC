"""floorgeom/normalize_rooms.py —— rooms 直接声明墙（波次 3，D41）。

新流程（替代 loc 区域表达）：
  1. partition 承接：从 skeleton 几何拿分区边界（outline/block/corridor）
  2. walls 解析：aiifc 4 形式 → 绝对坐标墙轴线折线（straight/polyline/axis-grid/arc）
  3. 墙围区域：墙线段 + 分区边界 → polygonize 闭合区域
  4. labels at 落区绑定 → 房间多边形（机器推验证产物）
  5. openings 挂墙 key + along → 沿墙绝对位置（WallFrame 定位）——
     能力保留供 details 复用；rooms 声明已剥离 openings（D44：门窗统一规律归 details）

纯函数 + 字节级确定；只依赖 shapely。SchemaError 结构化回喂。
"""

from __future__ import annotations

import math

from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import polygonize, unary_union

from .normalize import SchemaError


def _wall_to_polyline(wall: dict, axis_grid: dict, at: str) -> list[list[float]]:
    """一道墙（4 形式）→ 轴线折线（绝对坐标顶点序列）。

    straight/polyline：axis 点数组（绝对坐标）
    axis-grid：path {x,y} 索引粗轴网（dx_mm/dy_mm 偏移）
    arc：{center, r_mm, a0_deg, a1_deg} → 弦近似折线（~12° 一段）
    """
    if "axis" in wall:
        return [[float(p[0]), float(p[1])] for p in wall["axis"]]
    if "path" in wall:
        pts = []
        for i, p in enumerate(wall["path"]):
            x = axis_grid.get("x", [])
            y = axis_grid.get("y", [])
            if p["x"] >= len(x) or p["y"] >= len(y):
                raise SchemaError("axis_index_out_of_range", f"{at}.path[{i}]",
                                  x=p["x"], y=p["y"])
            px = float(x[p["x"]]) + float(p.get("dx_mm", 0))
            py = float(y[p["y"]]) + float(p.get("dy_mm", 0))
            pts.append([px, py])
        return pts
    if "arc" in wall:
        arc = wall["arc"]
        cx, cy = float(arc["center"][0]), float(arc["center"][1])
        r = float(arc["r_mm"])
        a0 = float(arc.get("a0_deg", 0))
        a1 = float(arc.get("a1_deg", 180))
        # 弦近似 ~12° 一段（aiifc 同款）
        sweep = a1 - a0
        n = max(int(abs(sweep) / 12.0) + 1, 1)
        return [[cx + r * math.cos(math.radians(a0 + sweep * i / n)),
                 cy + r * math.sin(math.radians(a0 + sweep * i / n))]
                for i in range(n + 1)]
    raise SchemaError("wall_missing_geometry", at)


def _region_bounds(partitions: dict, skeleton_zones: list[dict], at: str) -> list[list[list[float]]]:
    """partitions 承接 → 分区边界折线列表（画布边界，围区域用）。"""
    bounds: list[list[list[float]]] = []
    zone = skeleton_zones[0] if skeleton_zones else {}
    for name, ref in (partitions or {}).items():
        pat = f"{at}.partitions[{name}]"
        if ref == "outline":
            outline_blocks = zone.get("outline") or []
            if outline_blocks:
                for oblk in outline_blocks:
                    verts = (oblk.get("outer") or {}).get("vertices") or []
                    if len(verts) >= 3:
                        bounds.append(verts + [verts[0]])
            else:
                # 旧骨架无 outline（D34 前）→ 轴网 bbox 兜底（手填优先，派生兜底）
                hand = zone.get("axis_grid") or {}
                derived = zone.get("axis_grid_derived") or {}
                ag = hand if (hand.get("x") or hand.get("y")) else derived
                xs, ys = ag.get("x") or [], ag.get("y") or []
                if len(xs) >= 2 and len(ys) >= 2:
                    x0, x1, y0, y1 = xs[0], xs[-1], ys[0], ys[-1]
                    rect = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
                    bounds.append(rect + [rect[0]])
        elif ref.startswith("block:"):
            bid = ref.split(":", 1)[1]
            found = None
            for b in zone.get("blocks") or []:
                if b.get("id") == bid:
                    found = (b.get("polygon_mm") or {}).get("vertices")
                    break
            if not found:
                raise SchemaError("partition_block_not_found", pat, block=bid)
            bounds.append(found + [found[0]])
        elif ref.startswith("seg:"):
            sid = ref.split(":", 1)[1]
            found = None
            for sg in zone.get("segments") or []:
                if sg.get("id") == ref:
                    found = (sg.get("polygon_mm") or {}).get("vertices")
                    break
            if not found:
                raise SchemaError("partition_seg_not_found", pat, seg=ref)
            bounds.append(found + [found[0]])
        elif ref == "corridor":
            cz = zone.get("corridor_zone") or {}
            pm = cz.get("polygon_mm") or {}
            verts = pm.get("vertices") or []
            if verts:
                bounds.append(verts + [verts[0]])
                # 环带内环（core 边界）也是画布边界——墙贴 core 缘围区域用
                for h in pm.get("holes") or []:
                    bounds.append(h + [h[0]])
        else:
            raise SchemaError("bad_partition_ref", pat, ref=ref)
    return bounds


def _poly_meta(poly: Polygon) -> dict:
    verts = [[round(float(x), 3), round(float(y), 3)]
             for x, y in poly.exterior.coords[:-1]]
    return {
        "vertices": verts,
        "area_sqm": round(poly.area / 1e6, 3),
        "centroid_mm": [round(float(poly.centroid.x), 3),
                        round(float(poly.centroid.y), 3)],
    }


def _room_boundary_walls(face: Polygon, walls_out: list[dict],
                         bounds: list[list[list[float]]] | None = None) -> list[dict]:
    """房间多边形 → 围合墙段映射（details 开洞"墙在哪"的机器依据）。

    每段：key / length_m / 方位（N/S/E/W 主方向）/ is_exterior（贴分区边界 = 外墙）。
    匹配 = 墙段与房间边界共线重合（容差 10mm）。
    外墙 = 分区边界段（bounds，非声明墙）也进列表——key 为 boundary:<n>，
    附 p0/p1 绝对坐标（开窗直接可用），is_exterior=True。
    """
    ring = list(face.exterior.coords)
    out = []
    for w in walls_out:
        line = w["line_mm"]
        for i in range(len(line) - 1):
            a, b = line[i], line[i + 1]
            seg_len = math.hypot(b[0]-a[0], b[1]-a[1])
            if seg_len < 1.0:
                continue
            for j in range(len(ring) - 1):
                r0, r1 = ring[j], ring[j + 1]
                r_len = math.hypot(r1[0]-r0[0], r1[1]-r0[1])
                if r_len < 1.0:
                    continue
                overlap = _seg_overlap_len(a, b, r0, r1)
                if overlap > seg_len * 0.5:
                    out.append({
                        "key": w["key"],
                        "seg_i": i,
                        "length_m": round(seg_len / 1000.0, 3),
                        # 方位 = 墙在房间哪侧（房间质心相对墙段方向的反方向）——
                        # 南外墙 = 墙在房间南边（开窗规律的方位语义）
                        "azimuth": _azimuth_of_side(a, b, face),
                        "is_exterior": w.get("kind") == "ext",
                    })
                    break
    # 分区边界段（外墙）——开窗的墙在哪：p0/p1 绝对坐标给模型
    if bounds:
        for bi, bound in enumerate(bounds):
            for j in range(len(bound) - 1):
                c, d = bound[j], bound[j + 1]
                seg_len = math.hypot(d[0]-c[0], d[1]-c[1])
                if seg_len < 1.0:
                    continue
                # 该边界段是否在房间环上（重合 > 50%）
                for k in range(len(ring) - 1):
                    r0, r1 = ring[k], ring[k + 1]
                    overlap = _seg_overlap_len(c, d, r0, r1)
                    if overlap > seg_len * 0.5:
                        out.append({
                            "key": f"boundary:{bi}:{j}",
                            "seg_i": None,
                            "length_m": round(seg_len / 1000.0, 3),
                            "azimuth": _azimuth_of_side(c, d, face),
                            "is_exterior": True,
                            "p0_mm": [round(c[0], 1), round(c[1], 1)],
                            "p1_mm": [round(d[0], 1), round(d[1], 1)],
                        })
                        break
    return out


def _azimuth_of_side(a, b, face: Polygon) -> str:
    """墙段在房间哪侧 → N/S/E/W（墙段中点 → 房间质心向量反方向的主方向）。"""
    cx, cy = face.centroid.x, face.centroid.y
    mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
    vx, vy = cx - mx, cy - my  # 质心相对墙段中点
    if abs(vx) > abs(vy):
        return "E" if vx < 0 else "W"  # 质心在墙东 → 墙在房间西
    return "S" if vy > 0 else "N"      # 质心在墙北 → 墙在房间南


def _seg_overlap_len(a, b, c, d) -> float:
    """两线段共线重合长度（不共线 → 0）。"""
    dx, dy = b[0]-a[0], b[1]-a[1]
    d_len = math.hypot(dx, dy)
    if d_len < 1e-6:
        return 0.0
    ux, uy = dx / d_len, dy / d_len
    # c、d 到 a 的投影
    tc0 = (c[0]-a[0]) * ux + (c[1]-a[1]) * uy
    tc1 = (d[0]-a[0]) * ux + (d[1]-a[1]) * uy
    # 垂距（不共线判定，10mm 容差）
    for p in (c, d):
        proj = (p[0]-a[0]) * ux + (p[1]-a[1]) * uy
        px, py = a[0] + ux * proj, a[1] + uy * proj
        if math.hypot(p[0]-px, p[1]-py) > 10.0:
            return 0.0
    lo, hi = max(0.0, min(tc0, tc1)), min(d_len, max(tc0, tc1))
    return max(0.0, hi - lo)


def _point_along_polyline(pts: list[list[float]], dist: float) -> list[float]:
    """沿折线累计距离 dist 取点。"""
    acc = 0.0
    for i in range(len(pts) - 1):
        seg = math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        if acc + seg >= dist - 1e-9:
            t = (dist - acc) / seg if seg > 1e-9 else 0.0
            return [pts[i][0] + t * (pts[i + 1][0] - pts[i][0]),
                    pts[i][1] + t * (pts[i + 1][1] - pts[i][1])]
        acc += seg
    return list(pts[-1])


def _host_poly(verts: list[list[float]]) -> Polygon:
    """房间多边形顶点 → shapely Polygon。"""
    return Polygon(verts)


def _shared_edge_len(p1: Polygon, p2: Polygon) -> float:
    """两多边形共享边界长度（>100mm 视为邻接）。"""
    inter = p1.boundary.intersection(p2.boundary)
    return float(inter.length)


def normalize_rooms_new(rooms: dict, skeleton_model: dict) -> dict:
    """rooms DSL（D41 新结构）→ 几何模型（唯一坐标计算点）。"""
    if rooms.get("status") == "infeasible":
        return {"status": "infeasible", "region": rooms.get("region"),
                "reason": rooms.get("reason"), "evidence": rooms.get("evidence")}

    zone = (skeleton_model.get("zones") or [{}])[0]
    # 轴网：手填优先（walls path 索引锚定旧契约），派生兜底（新骨架轴网派生后手填空）
    hand = zone.get("axis_grid") or {}
    derived = zone.get("axis_grid_derived") or {}
    axis_grid = hand if (hand.get("x") or hand.get("y")) else derived

    # ① walls 解析 → 轴线折线
    walls_out = []
    for wi, w in enumerate(rooms.get("walls") or []):
        wat = f"walls[{wi}]"
        pts = _wall_to_polyline(w, axis_grid, wat)
        if len(pts) < 2:
            raise SchemaError("wall_too_few_points", wat, count=len(pts))
        key = w.get("key") or f"{rooms.get('floor')}:wall:{wi}"
        line_mm = [[round(float(p[0]), 3), round(float(p[1]), 3)] for p in pts]
        walls_out.append({
            "key": key,
            "kind": w.get("kind", "int"),
            "t_mm": float(w.get("t_mm", 120)),
            "line_mm": line_mm,
            "length_m": round(sum(math.hypot(line_mm[i+1][0]-line_mm[i][0],
                                             line_mm[i+1][1]-line_mm[i][1])
                                   for i in range(len(line_mm)-1)) / 1000.0, 3),
        })
    key_to_wall = {w["key"]: w for w in walls_out}

    # ② 分区边界（画布）
    bounds = _region_bounds(rooms.get("partitions"), skeleton_model.get("zones") or [],
                            "partitions")

    # ③ 墙围区域：线段节点化 → polygonize
    segments = []
    for w in walls_out:
        pts = w["line_mm"]
        for i in range(len(pts) - 1):
            segments.append(LineString([pts[i], pts[i + 1]]))
    for b in bounds:
        for i in range(len(b) - 1):
            segments.append(LineString([b[i], b[i + 1]]))
    faces: list[Polygon] = []
    if segments:
        unioned = unary_union(segments)
        faces = [f for f in polygonize(unioned) if f.area > 1.0]  # >1mm² 去碎面

    # ④ labels at 落区绑定
    rooms_out = []
    unbound = []
    for li, lab in enumerate(rooms.get("labels") or []):
        lat = f"labels[{li}]"
        at_pt = [float(lab["at"][0]), float(lab["at"][1])]
        host = None
        for face in faces:
            if face.covers(__import__("shapely.geometry", fromlist=["Point"]).Point(at_pt)):
                host = face
                break
        if host is None:
            unbound.append({"label": lab, "at": at_pt})
            continue
        meta = _poly_meta(host)
        room_wall_keys = _room_boundary_walls(host, walls_out, bounds)
        rooms_out.append({
            "id": lab["room"],
            "room": lab["room"],
            "type": lab.get("type", "room"),
            "area_sqm": meta["area_sqm"],
            "area_sqm_measured": meta["area_sqm"],  # check R-03 兼容键
            "target_area_sqm": lab.get("area_sqm"),
            "polygon_mm": meta,
            # D44：房间 → 围合墙段直接对应（details 开洞"墙在哪"的依据）——
            # 每段含 key/长度/方位/是否外墙（贴分区边界）
            "boundary_walls": room_wall_keys,
            **({"frontage": lab["frontage"]} if lab.get("frontage") else {}),
            **({"placemark": lab["placemark"]} if lab.get("placemark") else {}),
        })
    if unbound:
        first = unbound[0]
        raise SchemaError("label_not_in_region", "labels",
                          room=first["label"]["room"], label_at=first["at"])

    # neighbors 几何推导（共享边 = 邻接；check R-07 / reconcile 用）
    room_polys = {r["id"]: _host_poly(r["polygon_mm"]["vertices"]) for r in rooms_out}
    for r in rooms_out:
        r["neighbors"] = [
            other for other, opoly in room_polys.items()
            if other != r["id"]
            and _shared_edge_len(_host_poly(r["polygon_mm"]["vertices"]), opoly) > 100.0
        ]

    # ⑤ openings 挂墙 key + along → 沿墙位置
    openings_out = []
    for oi, o in enumerate(rooms.get("openings") or []):
        oat = f"openings[{oi}]"
        wall_ref = o["wall"]
        if isinstance(wall_ref, int):  # 旧索引兼容
            if wall_ref >= len(walls_out):
                raise SchemaError("opening_wall_index_out_of_range", oat, index=wall_ref)
            key = walls_out[wall_ref]["key"]
        else:
            key = wall_ref
        wall = key_to_wall.get(key)
        if wall is None:
            raise SchemaError("opening_wall_key_not_found", oat, wall=key)
        along_mm = float(o.get("along_m", 0.0)) * 1000
        w_mm = float(o.get("w_mm", 900))
        wall_len = wall.get("length_m", 0.0) * 1000
        # 门起点在墙内，终点可达墙端（贴端门合法）；1mm 浮点容差
        if along_mm < 0 or along_mm + w_mm > wall_len + 1.0:
            raise SchemaError("opening_out_of_wall", oat,
                              wall=key, along_m=o.get("along_m"),
                              wall_len_m=round(wall_len / 1000.0, 3))
        at_mm = _point_along_polyline(wall["line_mm"], along_mm)
        openings_out.append({
            "wall_key": key,
            "along_m": float(o.get("along_m", 0.0)),
            "w_mm": float(o.get("w_mm", 900)),
            "h_mm": float(o.get("h_mm", 2100)),
            "sill_mm": float(o.get("sill_mm", 0)),
            "type": o.get("type", "door"),
            "at_mm": [round(float(v), 3) for v in at_mm],
        })

    return {
        "floor": rooms.get("floor"),
        "walls": walls_out,
        "rooms": rooms_out,
        "openings": openings_out,
        "requirements_trace": rooms.get("requirements_trace") or [],
        "deviations": rooms.get("deviations") or [],
        "defaults_used": rooms.get("defaults_used") or [],
    }

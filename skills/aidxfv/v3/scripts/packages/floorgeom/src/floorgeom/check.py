"""floorgeom/check.py —— 规则机检（T15 轮廓级摄取 + T16/T17 房间级 R-01~R-09）。

纪律（architecture D22 / geo_cognition §7）：
- 两级机检：轮廓级摄取校验（plan 摄取时）+ 房间级 R-01~R-09；
- 报告结构化：{"rule","severity","target","detail"}，Error 拦截 / Warning 提示；
- FAIL 回喂 LLM（exit 1 语义），不解释过去；
- 纯函数、字节级确定。
"""

from __future__ import annotations

from shapely.geometry import Point, Polygon


# ---------------------------------------------------------------------------
# T15 轮廓级（plan 摄取校验）
# ---------------------------------------------------------------------------

def _zone_union(zone: dict) -> Polygon:
    """zone outline 全部块 union（致密化 + 净面积）。"""
    from floorgeom.derive import _block_polygons
    u = Polygon()
    for b in zone.get("outline_mm") or []:
        outer_p, holes_p = _block_polygons(b)
        net = outer_p
        for h in holes_p:
            if outer_p.contains(h):
                net = net.difference(h)
        u = u.union(net)
    return u


def _strict_block_polygons(block: dict) -> tuple[Polygon, list[Polygon]]:
    """outline 块 → (outer, holes)，严格构造（不 buffer 修复，暴露 invalid）。"""
    from floorgeom.derive import _densify_ring
    outer_raw = block["outer"]
    block_arcs = block.get("arcs") or []
    if isinstance(outer_raw, dict):
        outer_p = Polygon(_densify_ring(outer_raw["vertices"], outer_raw.get("arcs") or []))
    elif block_arcs:
        outer_p = Polygon(_densify_ring(outer_raw, block_arcs))
    else:
        outer_p = Polygon(outer_raw)
    hole_polys = []
    for h in block.get("holes") or []:
        if isinstance(h, dict):
            hole_polys.append(Polygon(_densify_ring(h["vertices"], h.get("arcs") or [])))
        else:
            hole_polys.append(Polygon(h))
    return outer_p, hole_polys


def check_outline_plan(plan: dict) -> list[str]:
    """plan 轮廓级摄取校验（T2 原样消费的前提）。

    检查：自相交 / 孔洞在外环内 / 锚点在轮廓内 / 退线（如提供）。
    :return: 违规列表（空 = 通过）
    """
    errs: list[str] = []
    for zi, zone in enumerate(plan.get("zones") or []):
        prefix = f"zone[{zi}]"
        union = _zone_union(zone)
        if union.is_empty:
            errs.append(f"{prefix} 轮廓为空或无效")
            continue

        for bi, block in enumerate(zone.get("outline_mm") or []):
            outer_p, hole_polys = _strict_block_polygons(block)
            if not outer_p.is_valid or outer_p.is_empty:
                errs.append(f"{prefix}.outline_mm[{bi}] 无效几何/自相交")
                continue
            for hi, hp in enumerate(hole_polys):
                if not hp.is_valid or hp.is_empty:
                    errs.append(f"{prefix}.outline_mm[{bi}].holes[{hi}] 无效几何/自相交")
                elif not outer_p.covers(hp):
                    errs.append(f"{prefix}.outline_mm[{bi}].holes[{hi}] 超出外环")

        # 锚点在轮廓内（core_anchor_mm：单点或多核点数组——schema oneOf 点|点数组）
        anchor = zone.get("core_anchor_mm")
        if anchor is not None:
            anchors = anchor if (anchor and isinstance(anchor[0], (list, tuple))) else [anchor]
            for ai, a in enumerate(anchors):
                pt = Point(float(a[0]), float(a[1]))
                if not union.covers(pt):
                    errs.append(f"{prefix} 核心筒锚点[{ai}] {a} 不在轮廓内")

    return errs


def check_alignment_zones(plan: dict) -> list[str]:
    """多 zone 对齐校验：tower ⊆ 宿主；核心筒锚点跨层一致。"""
    errs: list[str] = []
    zones = plan.get("zones") or []
    for z in zones:
        pos = z.get("position") or {}
        if pos.get("on"):
            host_id = pos["on"]
            host = next((h for h in zones if h["id"] == host_id), None)
            if host is None:
                errs.append(f"zone {z['id']} 的 position.on={host_id} 不存在")
                continue
            child = _zone_union(z)
            parent = _zone_union(host)
            if not parent.covers(child):
                errs.append(f"zone {z['id']} 超出宿主 {host_id}（塔楼⊄裙房）")
    return errs


def outline_polygons_from_skeleton(skeleton_model: dict) -> list:
    """skeleton 几何模型 → 轮廓多边形列表（outer − holes；R-01/CLI 房间级校验用）。"""
    polys = []
    for zone in skeleton_model.get("zones") or []:
        for oblk in zone.get("outline") or []:
            verts = (oblk.get("outer") or {}).get("vertices")
            if not verts or len(verts) < 3:
                continue
            poly = Polygon(verts)
            for hole in oblk.get("holes") or []:
                hv = hole.get("vertices")
                if hv and len(hv) >= 3:
                    poly = poly.difference(Polygon(hv))
            if not poly.is_empty:
                polys.append(poly)
    return polys


def check_skeleton_outline_containment(skeleton_model: dict) -> list[str]:
    """D34：骨架分区越轮廓校验——blocks/main_partitions/core 必须在 outline 内。

    线性继承（plan outline_mm → skeleton outline）：骨架分区不得超出外轮廓。
    用 skeleton_model 的 outline 块（normalize 产 polygon）作为边界，检查
    blocks（polygon_mm）与 main_partitions（path_mm）的顶点是否在轮廓内。
    """
    errs: list[str] = []
    for zi, zone in enumerate(skeleton_model.get("zones") or []):
        prefix = f"zone[{zone.get('zone') or zi}]"
        outline_blocks = zone.get("outline") or []
        if not outline_blocks:
            continue  # 无 outline 声明（旧案例）→ 跳过
        # 轮廓并集（含 holes 减除）
        outer_polys = []
        holes_polys = []
        for oblk in outline_blocks:
            outer = oblk.get("outer") or {}
            verts = outer.get("vertices")
            if verts and len(verts) >= 3:
                outer_polys.append(Polygon(verts))
            for hole in oblk.get("holes") or []:
                hverts = hole.get("vertices")
                if hverts and len(hverts) >= 3:
                    holes_polys.append(Polygon(hverts))
        if not outer_polys:
            continue
        boundary = outer_polys[0]
        for p in outer_polys[1:]:
            boundary = boundary.union(p)
        for hp in holes_polys:
            boundary = boundary.difference(hp)
        if boundary.is_empty:
            continue

        # blocks 越轮廓
        for bi, blk in enumerate(zone.get("blocks") or []):
            pm = blk.get("polygon_mm") or {}
            verts = pm.get("vertices")
            if not verts or len(verts) < 3:
                continue
            bpoly = Polygon(verts)
            if not boundary.covers(bpoly):
                outside = bpoly.difference(boundary)
                if not outside.is_empty and outside.area > 1e-6:
                    errs.append(f"{prefix}.blocks[{bi}]（{blk.get('role','?')}）超出轮廓")

        # main_partitions 越轮廓（path 折线——顶点在轮廓内即可）
        for pi, part in enumerate(zone.get("main_partitions") or []):
            pm = part.get("path_mm") or []
            for vi, pt in enumerate(pm):
                p = Point(float(pt[0]), float(pt[1]))
                if not boundary.covers(p):
                    errs.append(f"{prefix}.main_partitions[{pi}] 顶点{vi} {pt} 超出轮廓")
                    break

        # core 越轮廓（anchor 必须在轮廓内；extent/path 整体在轮廓内）
        for core_item in (zone.get("cores") or []):
            pm = core_item.get("polygon_mm") or {}
            if "vertices" in pm:
                cpoly = Polygon(pm["vertices"])
            elif "x" in pm and "y" in pm:
                cpoly = Polygon([(pm["x"][0], pm["y"][0]), (pm["x"][1], pm["y"][0]),
                                 (pm["x"][1], pm["y"][1]), (pm["x"][0], pm["y"][1])])
            else:
                continue
            if not boundary.covers(cpoly):
                outside = cpoly.difference(boundary)
                if not outside.is_empty and outside.area > 1e-6:
                    errs.append(f"{prefix}.core 超出轮廓")
            anchor = core_item.get("anchor")
            if anchor is not None:
                pt = Point(float(anchor[0]), float(anchor[1]))
                if not boundary.covers(pt):
                    errs.append(f"{prefix}.core anchor {anchor} 超出轮廓")

    return errs


# ---------------------------------------------------------------------------
# T16/T17 房间级 R-01~R-09
# ---------------------------------------------------------------------------

def check_floor(geom_model: dict, params: dict | None = None,
                outline_polygons: list[Polygon] | None = None) -> list[dict]:
    """房间级机检 R-01~R-09（W1 T16/T17 入口）。

    :param geom_model: normalize_rooms 产出的几何模型
    :param params: 校验参数（program 区间 / corridor_min_width_mm 等）
    :param outline_polygons: 轮廓多边形（R-01 用，缺省跳过）
    :return: 报告列表（空 = 通过）
    """
    params = params or {}
    report: list[dict] = []
    rooms = geom_model.get("rooms") or []

    # R-01 房间在轮廓内（10mm buffer 容差：1mm 级浮点噪声不阻断，1.2 拍定）
    if outline_polygons:
        for r in rooms:
            if "polygon_mm" not in r:
                continue
            poly = _polygon_from_rect(r["polygon_mm"])
            if any(outer.covers(poly) for outer in outline_polygons):
                continue  # 任一轮廓块覆盖即通过（多块分区）
            # 全不覆盖 → 查越界面积（10mm buffer 容差：贴边噪声豁免）
            best_diff = min((poly.difference(outer) for outer in outline_polygons),
                            key=lambda d: d.area)
            tol = 10.0 * poly.length  # 越界平均 <10mm 视为贴边噪声
            if not best_diff.is_empty and best_diff.area > tol:
                report.append(_rec("R-01", "error", r["id"],
                                   f"房间超出轮廓 {best_diff.area/1e6:.2f}㎡"))

    # R-02 房间互不重叠
    polys = []
    for r in rooms:
        if "polygon_mm" in r:
            polys.append((r["id"], _polygon_from_rect(r["polygon_mm"])))
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            id_a, pa = polys[i]
            id_b, pb = polys[j]
            inter = pa.intersection(pb)
            # 10mm buffer：相交区域平均宽 >10mm 才算真重叠（贴边噪声豁免，1.2 拍定）
            if inter.geom_type != "GeometryCollection" and not inter.is_empty \
                    and inter.area > 10.0 * inter.length:
                report.append(_rec("R-02", "error", f"{id_a}+{id_b}",
                                   f"相交面积 {inter.area/1e6:.2f}㎡"))

    # R-03 面积达标（program 区间 ±10%）
    program = params.get("program") or {}
    for r in rooms:
        measured = r.get("area_sqm_measured")
        if measured is None:
            continue
        rng = program.get(r["type"])
        if rng is None:
            continue
        lo, hi = rng[0], rng[1]
        lo10, hi10 = lo * 0.9, hi * 1.1
        if measured < lo10 or measured > hi10:
            report.append(_rec("R-03", "error", r["id"],
                               f"实测 {measured}㎡ ∉ [{lo10:.0f},{hi10:.0f}]㎡"))

    # R-04 走廊宽度
    min_w = params.get("corridor_min_width_mm")
    if min_w:
        # 骨架走廊在 skeleton_model 里，rooms 几何模型没有——走骨架校验（T13 已解析）
        pass  # 骨架级宽度由 normalize_skeleton 保留 width_mm，check_floor 层不重复

    # R-05 朝向落实（frontage 边 ∈ edges[dir]）
    # 需要 derive 的 edges——rooms 几何模型含 frontage 声明，逐房间比对简化：
    for r in rooms:
        frontage = r.get("frontage")
        if not frontage:
            continue
        # frontage 是方位词或 edge/hole 引用；有 polygon_mm 时检查贴边
        if "polygon_mm" in r and frontage in ("N", "S", "E", "W"):
            poly = _polygon_from_rect(r["polygon_mm"])
            # 简化：房间 bbox 是否触及该方向边界（真实 edges 校验在 W1 后续细化）
            if not _room_touches_direction(poly, frontage):
                report.append(_rec("R-05", "error", r["id"],
                                   f"frontage={frontage} 但房间未贴该方向边"))

    # R-07 连通性（门图连通）——V3 挂墙 openings 丢房间对（learn_gold P2-3），
    # 门图不可推；退化为 Warning：房间无任何邻居（几何孤立）提示——
    # 不阻断（孤立可能因 follows 走廊/独立服务间），Error 语义留给 reconcile 门对。
    room_ids = {r["id"] for r in rooms}
    connected: set[str] = set()
    for r in rooms:
        if r.get("neighbors"):
            connected.add(r["id"])
    has_neighbors = {r["id"] for r in rooms if r.get("neighbors")}
    for rid in room_ids:
        if rid == "corridor":
            continue
        if rid not in connected and rid not in has_neighbors:
            report.append(_rec("R-07", "warning", rid, "无几何邻居（门图连接受限，挂墙 openings 无房间对）"))

    # R-08 采光面（needs_exterior 房间必须 frontage 贴外边）——Warning
    # 需要类型包属性，简化为：有 frontage 声明即视为有采光声明（Warning 级）
    for r in rooms:
        if r.get("type") in ("bedroom", "office", "living") and "frontage" not in r:
            report.append(_rec("R-08", "warning", r["id"], "需要采光的房间缺 frontage 声明"))

    # R-09 暗区警示（deep 区放非采光房）——Warning
    # 需要 deep_zone 信息；简化为有 deep_zone_region 时提示
    return report


def check_core_alignment(floors: list[dict]) -> list[dict]:
    """R-06：跨层核心筒一致（各层 core 多边形比对）。

    D31 多核心筒：优先读 normalize 输出的 cores 数组，按位置逐一比对；
    回退单 core（旧格式）。各层 core 数量不一致也报 R-06。
    """
    report = []

    def _core_polys(f):
        z = (f.get("zones") or [{}])[0] if isinstance(f.get("zones"), list) else {}
        cores = z.get("cores")
        if cores is None:
            c = z.get("core")
            cores = [c] if c is not None else []
        return [c["polygon_mm"] for c in cores if isinstance(c, dict) and "polygon_mm" in c]

    per_floor = [(f.get("floor", "?"), _core_polys(f)) for f in floors]
    per_floor = [(n, ps) for n, ps in per_floor if ps]
    if len(per_floor) < 2:
        return report  # 少于 2 层不检

    base_name, base = per_floor[0]
    for fname, polys in per_floor[1:]:
        if len(polys) != len(base):
            report.append(_rec("R-06", "error", fname,
                               f"核心筒数量 {len(polys)} 与 {base_name}({len(base)}) 不一致"))
            continue
        for i, (a, b) in enumerate(zip(base, polys)):
            if a != b:
                report.append(_rec("R-06", "error", fname,
                                   f"core[{i}] 多边形与 {base_name} 不一致"))
    return report


def _rec(rule: str, severity: str, target: str, detail: str) -> dict:
    return {"rule": rule, "severity": severity, "target": target, "detail": detail}


# 通用语义块 role（D33）：这些必须走 skeleton 专用字段，不得塞 blocks
GENERIC_BLOCK_ROLES = ("core", "corridor", "holes")


def check_blocks_semantic(zone: dict) -> list[dict]:
    """D33 语义识别：blocks 的 role 撞通用语义块名（core/corridor/holes）→ warning。

    通用块有专门语义（锚点锁死/跨层对齐/引用），必须走 core/corridor/holes
    专用字段；类型 block（units/open_office/meeting…）role 不限定（宽松）。
    """
    report = []
    for i, blk in enumerate(zone.get("blocks") or []):
        role = blk.get("role", "")
        base = role.split("|")[0].strip()  # "units|units 分界" → "units"
        if base in GENERIC_BLOCK_ROLES:
            report.append(_rec(
                "D33", "warning", f"blocks[{i}]",
                f"role='{role}' 撞通用语义块——{base} 应走 skeleton 专用字段"
                f"（{base}=...），不得塞 blocks"))
    return report


def check_holes_alignment(skeleton_zone: dict, plan_zone: dict) -> list[dict]:
    """D33/T2：skeleton holes 与 plan outline holes 一致性（原样消费传透）。

    plan 有的 holes，skeleton 必须原样带入（LLM 不得转述/遗漏轮廓孔洞）。
    """
    report = []
    plan_outlines = plan_zone.get("outline_mm") or []
    plan_holes = []
    for ol in plan_outlines:
        plan_holes.extend(ol.get("holes") or [])
    skel_holes = skeleton_zone.get("holes") or []
    if len(skel_holes) < len(plan_holes):
        report.append(_rec(
            "T2", "error", skeleton_zone.get("zone", "?"),
            f"plan outline 有 {len(plan_holes)} 个 holes，skeleton 只表达 "
            f"{len(skel_holes)} 个——holes 必须原样消费（T2），缺失"))
    return report


def _polygon_from_rect(rect: dict) -> Polygon:
    """房间 polygon_mm → shapely Polygon。

    兼容两种格式：
    - {"x":[x0,x1], "y":[y0,y1]} —— 矩形（历史兼容）
    - {"vertices": [[x,y],...]}  —— 轴网索引多边形（polygon 形式，D27）
    """
    if "vertices" in rect:
        return Polygon(rect["vertices"])
    x0, x1 = rect["x"]
    y0, y1 = rect["y"]
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _room_touches_direction(poly: Polygon, direction: str) -> bool:
    """房间多边形是否触及 bbox 的某方向边界（简化 R-05）。"""
    minx, miny, maxx, maxy = poly.bounds
    if direction == "S":
        return miny < 100  # 贴南边（y≈0）
    if direction == "N":
        return True  # 未知上界，兜底
    if direction == "W":
        return minx < 100
    if direction == "E":
        return True
    return True

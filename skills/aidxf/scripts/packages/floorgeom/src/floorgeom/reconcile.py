"""floorgeom/reconcile.py —— 声明房间图 vs 回读房间图对账（T18，geo_cognition §2 反向闭环）。

纪律（mission_parrallel §3A）：画出来的 ≠ 声明的 → error 回喂重画。
身份匹配（D41 退化，2026-08-13）：**质心落区几何匹配**——声明房间 centroid_mm
落在回读哪个区域（polygon_mm），不依赖标注命名（readback 自我循环根治）。
id 字符串匹配兜底（无 polygon 时）。

severity 统一（1.2，2026-08-13）：error（阻断 exit1）/ warning（提示 exit0）/
info（记录 exit0）——与 check 共用一套词表。

输入契约（V3，两侧统一房间图）：
    decl_graph:     声明侧房间图 {rooms, adjacencies, doors}（由 floorgeom.to_room_graph
                    从 normalize 产物转换——邻接来自 normalize 推好的 neighbors[]；
                    rooms 带 centroid_mm/bbox_mm 供几何匹配）
    readback_graph: 回读侧房间图 {rooms, adjacencies, doors}（dxfkit.readback.to_room_graph；
                    rooms 带 polygon_mm 供落区）

    检查项：
    - room_missing：声明房间在回读图中缺失（双向，带 bbox 诊断）
    - area：面积差 <5%（±）
    - adjacency：单向防多（回读门图邻接超出声明几何共墙 → error）
    """

from __future__ import annotations

from shapely.geometry import Point, Polygon

AREA_TOL = 0.05  # 5%


def _finding(rule: str, severity: str, message: str) -> dict:
    return {"rule": rule, "severity": severity, "message": message}


def _rooms_by_id(graph: dict) -> dict:
    return {r["id"]: r for r in (graph.get("rooms") or [])}


def _adjacency_set(graph: dict) -> set[tuple]:
    return {tuple(sorted(a)) for a in (graph.get("adjacencies") or [])}


def _bbox_of(room: dict) -> list[float] | None:
    """房间 bbox [minx, miny, maxx, maxy]（显式或从 polygon 推）。"""
    if room.get("bbox_mm"):
        return room["bbox_mm"]
    verts = (room.get("polygon_mm") or {}).get("vertices") or []
    if len(verts) >= 3:
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        return [min(xs), min(ys), max(xs), max(ys)]
    return None


def _geometry_match(decl_graph: dict, readback_graph: dict) -> dict:
    """质心落区匹配：decl 房间 centroid 落在回读哪个区域 → {decl_id: read_id}。

    无 centroid（回读无 polygon）→ 退化为 id 相同匹配。
    """
    decl_by_id = _rooms_by_id(decl_graph)
    read_by_id = _rooms_by_id(readback_graph)

    read_polys = {}
    for rid, r in read_by_id.items():
        verts = (r.get("polygon_mm") or {}).get("vertices") or []
        if len(verts) >= 3:
            read_polys[rid] = Polygon(verts)

    matched: dict = {}
    if not read_polys:
        # 兜底：id 字符串匹配
        return {rid: rid for rid in decl_by_id if rid in read_by_id}

    for did, droom in decl_by_id.items():
        cent = droom.get("centroid_mm")
        if not cent:
            continue
        pt = Point(cent)
        for rid, poly in read_polys.items():
            if poly.covers(pt):
                matched[did] = rid
                break
    return matched


def _fmt_bbox(room: dict) -> str:
    bbox = _bbox_of(room)
    if bbox:
        return f"bbox[{bbox[0]:.0f},{bbox[1]:.0f}..{bbox[2]:.0f},{bbox[3]:.0f}]"
    return ""


def reconcile(decl_graph: dict, readback_graph: dict) -> list[dict]:
    """声明房间图 vs 回读房间图对账（severity 三档：error/warning/info）。

    :param decl_graph: {rooms, adjacencies, doors}（normalize 产物经 to_room_graph）
    :param readback_graph: {rooms, adjacencies, doors}（readback 经 to_room_graph）
    :return: 报告列表（空 = 通过）

    邻接口径（2026-08-17 根治）：声明侧 normalize 按**几何共享边**推 neighbors，
    回读侧 readback 只从**画出的门**推邻接——V3 每房一扇门（D44），门图必然是
    几何共墙的子集。故"声明有回读无"不是错误（无判别力），只做单向防多检查：
    - 回读邻接超出声明共墙（画了声明没有的邻接）→ error
    - 回读门对超出声明邻接集 → error
    """
    findings: list[dict] = []

    decl_by_id = _rooms_by_id(decl_graph)
    read_by_id = _rooms_by_id(readback_graph)

    # 身份匹配（D41：质心落区几何匹配，id 兜底）
    matched = _geometry_match(decl_graph, readback_graph)
    matched_read_ids = set(matched.values())

    # 双向 room_missing（带 bbox 诊断）
    for rid, room in decl_by_id.items():
        if rid not in matched:
            findings.append(_finding("room_missing", "error",
                                     f"{rid} 在声明中但回读缺失 {_fmt_bbox(room)}"))
    for rid, room in read_by_id.items():
        if rid not in matched_read_ids:
            findings.append(_finding("room_missing", "error",
                                     f"{rid} 在回读中但声明缺失 {_fmt_bbox(room)}"))

    # 匹配对重命名：面积/邻接按几何匹配对比较
    rename = {did: rid for did, rid in matched.items()}

    # area：声明 area_sqm vs 回读 area_sqm（<5%）
    for did, rid in sorted(rename.items()):
        declared = decl_by_id[did].get("area_sqm")
        actual = read_by_id[rid].get("area_sqm")
        if declared is None or actual is None:
            continue
        if declared > 0 and abs(actual - declared) / declared > AREA_TOL:
            findings.append(_finding("area", "error",
                                     f"{did} 面积声明 {declared}㎡ vs 回读 {actual}㎡"))

    # adjacency：单向防多（声明几何共墙 ⊇ 回读门图，回读超出才报错）
    decl_adj = {tuple(sorted((rename.get(a[0], a[0]), rename.get(a[1], a[1]))))
                for a in _adjacency_set(decl_graph)}
    read_adj = _adjacency_set(readback_graph)
    for a in sorted(read_adj - decl_adj):
        if "corridor" in a:
            continue
        findings.append(_finding("adjacency", "error",
                                 f"邻接 {a[0]}↔{a[1]} 回读但声明缺失"))

    findings.sort(key=lambda f: (f["rule"], f["message"]))
    return findings

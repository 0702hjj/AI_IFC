"""floorgeom/room_graph.py —— normalize 产物 → 统一房间图（V3 对账契约，T18 支撑）。

V3 对账契约两侧对称（无 polygon 依赖）：
    {rooms: [{id, type?, area_sqm}], adjacencies: [(a,b)], doors: [{between}]}

声明侧邻接来源 = normalize 产物 rooms 的 `neighbors[]`：
    normalize 从几何共享边推好邻居（D41：墙围区域后几何推导）
    （normalize 是唯一坐标计算点，见 normalize.py neighbors 推导）。
    room_graph 直接消费，不做二次几何推导。

回读侧：dxfkit.readback.to_room_graph 产出同格式（邻接来自 readback 几何边）。
reconcile 只消费本格式，两侧对称。
"""

from __future__ import annotations


def _bbox_of_polygon_mm(polygon_mm: dict | None) -> list[float] | None:
    """polygon_mm → bbox [minx, miny, maxx, maxy]（诊断用）。"""
    verts = (polygon_mm or {}).get("vertices") or []
    if len(verts) < 3:
        return None
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    return [min(xs), min(ys), max(xs), max(ys)]


def to_room_graph(normalized: dict) -> dict:
    """normalize 产物 → 统一房间图 {rooms, adjacencies, doors}。

    :param normalized: floorgeom.normalize.normalize_rooms 产出
        （rooms[] 带 neighbors[] / id / type / area_sqm；openings[] 挂墙）
    :return: V3 房间图（reconcile 消费格式）
    """
    rooms = normalized.get("rooms") or []
    adj: set[tuple] = set()
    for r in rooms:
        rid = r.get("id")
        if not rid:
            continue
        for nid in (r.get("neighbors") or []):
            adj.add(tuple(sorted((rid, nid))))
    room_graph = {
        "rooms": [
            {
                "id": r.get("id"),
                "type": r.get("type"),
                "area_sqm": r.get("area_sqm"),
                # D41 退化：质心落区几何匹配输入（reconcile 不依赖标注命名）
                "centroid_mm": (r.get("polygon_mm") or {}).get("centroid_mm"),
                "bbox_mm": _bbox_of_polygon_mm(r.get("polygon_mm")),
            }
            for r in rooms
        ],
        "adjacencies": sorted(adj),
        # 挂墙 openings 无房间对（learn_gold P2-3）——门对留空，数量以 openings 计数
        "doors": [],
    }
    return room_graph

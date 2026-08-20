"""readback_graph: V3 房间图适配（V2 词表 nodes/edges → V3 rooms/adjacencies/doors）。

拆分自 readback.py（W-0049 文件行数门控）；对外契约仍由 dxfkit.readback 再导出。
"""

from __future__ import annotations


# ---------------------------------------------------------------- V3 房间图适配

def to_room_graph(graph: dict) -> dict:
    """V2 词表（nodes/edges）→ V3 房间图（rooms/adjacencies/doors）。

    对齐 floorgeom.reconcile 消费格式（T24+ 契约测试 P1）：
    {rooms: [{id, area_sqm}], adjacencies: [(a,b)], doors: [{between}]}
    """
    rooms = [{"id": n["id"], "area_sqm": n.get("area_sqm")}
             for n in graph.get("nodes", [])]
    adjacencies = []
    doors = []
    for e in graph.get("edges", []):
        a, b, via = e["a"], e["b"], e["via"]
        if via in ("door", "front_door"):
            doors.append({"between": (a, b)})
            adjacencies.append((a, b))
        elif via == "open":
            adjacencies.append((a, b))
    adjacencies = sorted(set(adjacencies))
    return {
        "floor": graph.get("source_dxf", "?"),
        "rooms": rooms,
        "adjacencies": adjacencies,
        "doors": sorted(doors, key=lambda d: tuple(sorted(d["between"]))),
    }

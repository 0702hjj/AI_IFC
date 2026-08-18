"""goldlib/replay.py —— replay 前置（T34，G2 闸门产物）。

组合调用，无新逻辑：反推声明 → floorgeom.normalize → to_room_graph →
与回读房间图 reconcile → 产 replay_check.json。FAIL 直接进 _quarantine/，不进入库。
"""

from __future__ import annotations

import json
from pathlib import Path

from goldlib.reverse import reverse
from floorgeom.reconcile import reconcile
from floorgeom.room_graph import to_room_graph
from floorgeom.normalize import normalize_rooms, SchemaError


def replay_case(case_dir) -> dict:
    """对 golden 案例跑 replay，产 replay_check.json。

    :param case_dir: golden/<type>/<case_id>/ 目录
    :return: {"status": "PASS"|"FAIL", "replay_area_diff_pct": float, "findings": [...]}
    """
    from goldlib.reverse import MIN_ROOM_SQM
    case_dir = Path(case_dir)

    # 输入：readback 图（反推源）+ rooms 声明（若有）
    readback_path = case_dir / "readback.json"
    if not readback_path.exists():
        # 降级：如果已有 replay_check.json 且 PASS（如房间名驱动案例），
        # 直接用已有结果，不阻塞 ingest
        existing_replay = case_dir / "replay_check.json"
        if existing_replay.exists():
            existing = json.loads(existing_replay.read_text(encoding="utf-8"))
            if existing.get("status") == "PASS":
                return existing
        return {"status": "FAIL", "reason": "缺 readback.json"}

    readback_data = json.loads(readback_path.read_text(encoding="utf-8"))
    graph = readback_data.get("readback_graph", readback_data)

    # 1. 过滤小分区（与 reverse 同阈值 MIN_ROOM_SQM）——两边对齐
    graph_nodes = [n for n in graph.get("nodes", [])
                   if (n.get("area_geo_sqm") or 0) >= MIN_ROOM_SQM]
    graph = dict(graph)
    graph["nodes"] = graph_nodes

    # 2. 反推声明（D41 新结构：walls + labels + openings）
    decl = reverse(graph)

    # 3. 反推声明过 normalize（G2 前提：声明可重放）→ 统一房间图
    #    walls 用绝对坐标（边界提取）；outline 原样传回作围区域边界
    rooms_decl = {
        "floor": decl.get("floor") or graph.get("source_dxf", "?"),
        "walls": decl.get("walls", []),
        "labels": decl.get("labels", []),
        "openings": decl.get("openings", []),
    }
    outline_verts = graph.get("outline_mm") or []
    skeleton_model = {
        "zones": [{
            "zone": "replay",
            "outline": ([{"outer": {"vertices": outline_verts}}]
                        if len(outline_verts) >= 3 else []),
        }]
    }
    try:
        normalized = normalize_rooms(rooms_decl, skeleton_model)
        decl_graph = to_room_graph(normalized)
    except SchemaError as ex:
        return {"status": "FAIL", "reason": f"反推声明过 normalize 失败: {ex.error}",
                "findings": [], "declared_rooms": 0, "readback_rooms": 0}

    # 4. 转回读房间图（reconcile 消费格式，同样过滤后）
    room_ids = {n.get("id") for n in graph_nodes}
    room_graph = {
        "rooms": [{"id": n.get("id"), "area_sqm": n.get("area_sqm")
                   or n.get("area_geo_sqm")}
                  for n in graph_nodes if n.get("id") in room_ids],
        # 邻接/门只保留两端都在过滤后房间内的（碎块噪声不进对账）
        "adjacencies": [a for a in _edges_to_adjacencies(graph.get("edges", []))
                        if a[0] in room_ids and a[1] in room_ids],
        "doors": [{"between": tuple(sorted((e["a"], e["b"])))}
                  for e in graph.get("edges", [])
                  if e.get("via") in ("door", "front_door")
                  and e["a"] in room_ids and e["b"] in room_ids],
    }

    # 5. reconcile 对账（声明房间图 ↔ 回读房间图）
    #    单向防多（回读门图 ⊆ 声明共墙），无"声明有回读无"误报
    findings = reconcile(decl_graph, room_graph)
    fails = [f for f in findings if f["severity"] == "FAIL"]

    # 6. 面积差（反推声明面积 vs 回读面积）
    diff_pct = 0.0
    decl_by_id = {r["id"]: r for r in decl_graph.get("rooms", [])}
    for rg in room_graph["rooms"]:
        rid = rg["id"]
        if rid in decl_by_id and rg.get("area_sqm"):
            declared = decl_by_id[rid].get("area_sqm") or 0
            if declared > 0:
                diff_pct = max(diff_pct, abs(rg["area_sqm"] - declared) / declared * 100)

    result = {
        "status": "FAIL" if fails or diff_pct > 5 else "PASS",
        "replay_area_diff_pct": round(diff_pct, 2),
        "findings": findings,
        "declared_rooms": len(decl_graph.get("rooms", [])),
        "readback_rooms": len(room_graph["rooms"]),
        "decl_loc_null_skipped": 0,  # D41: no loc-null concept
    }
    # 落盘
    (case_dir / "replay_check.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return result


def _edges_to_adjacencies(edges: list) -> list:
    out = set()
    for e in edges:
        a, b = e.get("a"), e.get("b")
        if a and b:
            out.add(tuple(sorted((a, b))))
    return sorted(out)

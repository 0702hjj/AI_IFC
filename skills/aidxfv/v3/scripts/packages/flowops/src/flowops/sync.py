"""flowops/sync.py —— 同步桥（T43，V2 sync.py 迁移 + readback 替换）。

流程：DXF 哈希比对 → 未变快速路径；已变 → readback 再生 →
新旧 diff 审计（门移动/墙段/房间改名/新增弧线）→ 语义事件 JSON。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from dxfkit.readback import readback

MOVE_TOL_MM = 100.0
MATCH_TOL_MM = 500.0


def _sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(old_layout: dict, graph: dict) -> dict:
    """新旧比对：门移动/增删、墙段变化、房间增删、新增弧线、不可解析实体。"""
    diff = {"doors_moved": [], "doors_added": [], "doors_removed": [],
            "rooms_added": [], "rooms_removed": [],
            "wall_segments_delta": 0, "arcs_added": [], "unparsed": []}

    new_doors = graph.get("doors", [])
    used = set()
    for od in old_layout.get("doors", []):
        best, best_d = None, MATCH_TOL_MM
        for k, nd in enumerate(new_doors):
            if k in used:
                continue
            od_at, nd_at = od.get("at", [0, 0]), nd.get("at", [0, 0])
            dist = ((od_at[0] - nd_at[0]) ** 2 + (od_at[1] - nd_at[1]) ** 2) ** 0.5
            if dist <= best_d:
                best, best_d = k, dist
        if best is None:
            diff["doors_removed"].append(f"{od.get('between')} at {od.get('at')}")
        else:
            used.add(best)
            if best_d > MOVE_TOL_MM:
                diff["doors_moved"].append(
                    f"{od.get('between')}: {od.get('at')} → {new_doors[best].get('at')}")
    for k, nd in enumerate(new_doors):
        if k not in used:
            diff["doors_added"].append(f"at {nd.get('at')}")

    old_rooms = {r["id"] for r in old_layout.get("rooms", [])}
    new_rooms = {n["id"] for n in graph.get("nodes", [])}
    diff["rooms_added"] = sorted(new_rooms - old_rooms)
    diff["rooms_removed"] = sorted(old_rooms - new_rooms)

    old_segs = sum(len(w.get("segments", [])) for w in old_layout.get("walls", []))
    new_segs = len(graph.get("wall_segments", []))
    diff["wall_segments_delta"] = new_segs - old_segs

    diff["arcs_added"] = graph.get("wall_arcs", [])
    diff["unparsed"] = graph.get("unparsed", [])
    return diff


def sync_floor(dxf_path, recorded_dxf_sha256: str, old_layout: dict,
               layer_map: dict | None = None, units: str | None = None) -> dict:
    """同步桥主入口。

    :param dxf_path: DXF 路径
    :param recorded_dxf_sha256: 上次记录的 DXF 哈希
    :param old_layout: 旧布局（消费或对比）
    :return: {"path": "fast"|"regenerate", "diff":..., "verdict": "pass"|"adjudicate"}
    """
    current = _sha256(dxf_path)
    if current == recorded_dxf_sha256:
        return {"path": "fast", "verdict": "pass", "reason": "DXF 未变"}

    graph = readback(dxf_path, layer_map=layer_map, units=units)
    if graph.get("error"):
        return {"path": "regenerate", "verdict": "adjudicate",
                "reason": graph["error"]}
    diff = audit(old_layout, graph)
    verdict = "pass" if not diff["unparsed"] else "adjudicate"
    return {
        "path": "regenerate",
        "diff": diff,
        "verdict": verdict,
        "semantic_events": diff,  # 语义事件 JSON（audit 即事件集）
        "wall_arcs": graph.get("wall_arcs", []),
    }

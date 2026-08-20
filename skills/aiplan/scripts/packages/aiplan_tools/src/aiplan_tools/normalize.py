"""normalize —— 统一 path → plan.json outline_mm（P1 迁移核心，2026-08-11 统一 path 重构）。

把 design_intent.json（统一 path：多段 path 围成的闭合图形）展开为 plan.json 的
outline_mm / core / core_anchor_mm / position（绝对坐标）。

统一抽象（用户拍板）：outline / hole / core 都是"多段 path 围成的闭合图形"（顶点 + 分段，mm 坐标）。
- 方向归一化：normalize 自动处理（外环强制 CCW、孔洞强制 CW）——模型不用记方向
- segment 封装细节：recess（凹进）/ projection（凸出）/ arc（圆角），机器展开成顶点
- 语义定位：at_edge+offset_m / at_vertex / core_placement(region+extent)——机器解算位置

对应 migration_to_v3_dsl.md §五 ②翻译器层。

纯函数，确定性（shapely 2.x）。
"""

from __future__ import annotations

import json
import math
import sys
from shapely.geometry import Polygon, Point

from .normalize_segments import (  # noqa: F401 再导出保持原契约
    NormalizeError,
    _signed_area, _normalize_ring_direction, _fillet_at_vertex,
    _edge_outward_normal, _normal_to_direction, _find_edge,
    _expand_recess_projection, _expand_segments_grouped,
    _expand_ring_path, _edges_to_base, _expand_ring_edges, resolve_path,
)


# ═══════════════════════ core（placement 语义定位 / path 直接顶点）═══════════════

def resolve_core_placement(placement: dict, zone_outer_vertices: list[list[float]]) -> tuple[list[list[float]], list[float]]:
    """core_placement（region + extent）→ (core_vertices, core_anchor_mm)。

    zone_outer_vertices: 所属 zone 的外环顶点（展开后）。
    """
    region = placement["region"]
    ew = placement.get("extent_w_m", 8) * 1000
    ed = placement.get("extent_d_m", 5) * 1000
    zone_poly = Polygon(zone_outer_vertices)
    zx_min, zy_min, zx_max, zy_max = zone_poly.bounds
    zw = zx_max - zx_min
    zd = zy_max - zy_min
    zcx = (zx_min + zx_max) / 2
    zcy = (zy_min + zy_max) / 2
    region_offset = {
        "center": (0, 0),
        "N": (0, zd / 4), "S": (0, -zd / 4),
        "E": (zw / 4, 0), "W": (-zw / 4, 0),
        "NE": (zw / 4, zd / 4), "NW": (-zw / 4, zd / 4),
        "SE": (zw / 4, -zd / 4), "SW": (-zw / 4, -zd / 4),
    }
    dx, dy = region_offset.get(region, (0, 0))
    cx, cy = zcx + dx, zcy + dy
    core_verts = [
        [cx - ew / 2, cy - ed / 2], [cx + ew / 2, cy - ed / 2],
        [cx + ew / 2, cy + ed / 2], [cx - ew / 2, cy + ed / 2],
    ]
    return core_verts, [round(cx), round(cy)]


def _bbox_shift_into_host(child_verts: list[list[float]], host_verts: list[list[float]],
                          align: str | None) -> tuple[float, float]:
    """塔楼平移量 → 落进宿主（按 align 方位贴边/居中）。

    以**宿主多边形 covers 塔楼多边形**为准（L 形等凹形宿主只在真实覆盖区判定）。
    先试 align 方位落位；不满足时在宿主 bbox 内按网格扫位找第一个覆盖点。
    塔楼比宿主 bbox 还大 → 返回 (0,0)（放不下，调用方报错）。

    align 语义（2026-08-17）：`<主方位>` 或 `<主方位>_center`，
    如 north_center（北贴边居中）、west_center（西贴边居中）、east_center（东贴边居中）。
    """
    child_poly = Polygon(child_verts)
    host_poly = Polygon(host_verts)
    if not child_poly.is_valid or not host_poly.is_valid:
        return 0.0, 0.0
    cminx, cminy, cmaxx, cmaxy = child_poly.bounds
    hminx, hminy, hmaxx, hmaxy = host_poly.bounds
    cw, ch = cmaxx - cminx, cmaxy - cminy
    hw, hh = hmaxx - hminx, hmaxy - hminy
    if cw > hw or ch > hh:
        return 0.0, 0.0
    if host_poly.covers(child_poly):
        return 0.0, 0.0

    def covers_at(dx: float, dy: float) -> bool:
        moved = Polygon([(v[0] + dx, v[1] + dy) for v in child_verts])
        return host_poly.covers(moved) if moved.is_valid else False

    align = (align or "").lower()
    primary = None
    for d in ("north", "south", "east", "west"):
        if align.startswith(d):
            primary = d
            break
    center = "_center" in align
    # ① align 候选（主方位贴边 + 次方向居中/贴边）
    candidates = []
    if primary == "west":
        xs = [hminx - cminx]
    elif primary == "east":
        xs = [hmaxx - cmaxx]
    elif center:
        xs = [(hw - cw) / 2 - cminx + hminx]
    else:
        xs = [0.0, hminx - cminx, hmaxx - cmaxx]
    if primary == "north":
        ys = [hmaxy - cmaxy]
    elif primary == "south":
        ys = [hminy - cminy]
    elif center:
        ys = [(hh - ch) / 2 - cminy + hminy]
    else:
        ys = [0.0, hminy - cminy, hmaxy - cmaxy]
    for dx in xs:
        for dy in ys:
            if covers_at(dx, dy):
                return round(dx), round(dy)
    # ② 网格扫位兜底：宿主 bbox 内逐步平移找覆盖点（步长 = min(塔楼宽/高, 1000mm)）
    step = max(100.0, min(cw, ch) / 4)
    x_cands = [hminx - cminx + i * step for i in range(int(hw / step) + 2)]
    y_cands = [hminy - cminy + i * step for i in range(int(hh / step) + 2)]
    for dx in x_cands:
        for dy in y_cands:
            if covers_at(dx, dy):
                return round(dx), round(dy)
    return 0.0, 0.0


def _shift_outline(zone_out: dict, dx: float, dy: float) -> dict:
    """zone outline_mm 全部顶点 + core/core_anchor 平移 (dx,dy)。"""
    moved = dict(zone_out)
    moved["outline_mm"] = []
    for blk in zone_out.get("outline_mm", []):
        new_block = {"outer": {}, "holes": [], "arcs": blk.get("arcs", [])}
        for key, ring in (("outer", blk["outer"]),):
            verts = ring["vertices"]
            new_block["outer"] = {"vertices": [[v[0] + dx, v[1] + dy] for v in verts],
                                  "arcs": ring.get("arcs", [])}
        new_block["holes"] = [
            {"vertices": [[v[0] + dx, v[1] + dy] for v in h["vertices"]],
             "arcs": h.get("arcs", [])}
            for h in blk.get("holes", [])
        ]
        moved["outline_mm"].append(new_block)
    if "core" in moved:
        c = moved["core"]
        moved["core"] = [[v[0] + dx, v[1] + dy] for v in c["vertices"]]
    if "core_anchor_mm" in moved:
        a = moved["core_anchor_mm"]
        if a and isinstance(a[0], (int, float)):
            moved["core_anchor_mm"] = [a[0] + dx, a[1] + dy]
        else:
            moved["core_anchor_mm"] = [[p[0] + dx, p[1] + dy] for p in a]
    return moved


# ═══════════════════════ 主翻译函数 ═══════════════════════

def normalize(intent: dict, lot_polygon_mm: list[list[float]] | None = None) -> dict:
    """design_intent（统一 path）→ plan.json zones（outline_mm + core + core_anchor_mm + position）。

    参数:
        intent: design_intent.json（统一 path 语义层）
        lot_polygon_mm: 地块顶点（可选，用于校验；path 已是绝对坐标时可省）

    返回: {zones: [...], design_rationale: str}

    多 zone 落位（2026-08-17）：spatial_relations rel=on 时，塔楼 outline 若不在
    宿主轮廓内（LLM 手写绝对坐标与宿主脱节），按 align 方位平移落进宿主——
    `align: <主方位>[+_center]`（如 north_center 北贴边居中 / west_center 西贴边居中）。
    产出满足"塔楼⊆裙房"约束，cad S0 对齐校验不再 FAIL。
    """
    # 第 1 遍：全部 zone 展开（先落盘 outline/core，供落位参考宿主）
    plan_zones: list[dict] = []
    for z in intent["zones"]:
        outline_rings = resolve_path(z["form"]["path"])
        zone_out: dict = {"id": z["id"], "outline_mm": outline_rings}
        core_spec = z.get("core")
        if core_spec:
            first_outer_verts = outline_rings[0]["outer"]["vertices"]
            if isinstance(core_spec, list):
                cores_out = []
                anchors = []
                for ci in core_spec:
                    if "path" in ci:
                        core_rings = resolve_path(ci["path"])
                        ring = core_rings[0]["outer"]
                        cp = Polygon(ring["vertices"])
                        anchors.append([round(cp.centroid.x), round(cp.centroid.y)])
                        cores_out.append(ring)
                zone_out["core"] = cores_out
                if anchors:
                    zone_out["core_anchor_mm"] = anchors
            elif "placement" in core_spec:
                core_verts, anchor = resolve_core_placement(core_spec["placement"], first_outer_verts)
                zone_out["core"] = {"vertices": core_verts}
                zone_out["core_anchor_mm"] = anchor
            elif "path" in core_spec:
                core_rings = resolve_path(core_spec["path"])
                ring = core_rings[0]["outer"]
                zone_out["core"] = ring
                cp = Polygon(ring["vertices"])
                zone_out["core_anchor_mm"] = [round(cp.centroid.x), round(cp.centroid.y)]
        if "typology" in z:
            zone_out["typology_candidates"] = [z["typology"]]
        plan_zones.append(zone_out)

    # spatial_relations → position + rel=on 落位
    for rel in intent.get("spatial_relations", []):
        if rel["rel"] != "on":
            continue
        child = next((pz for pz in plan_zones if pz["id"] == rel["from"]), None)
        host = next((pz for pz in plan_zones if pz["id"] == rel["to"]), None)
        if child is None or host is None:
            continue
        child["position"] = {"on": rel["to"]}
        if "align" in rel:
            child["position"]["align"] = rel["align"]
        # 落位：塔楼 outline 不在宿主内 → 平移进宿主
        child_verts = child["outline_mm"][0]["outer"]["vertices"]
        host_verts = host["outline_mm"][0]["outer"]["vertices"]
        dx, dy = _bbox_shift_into_host(child_verts, host_verts, rel.get("align"))
        if dx or dy:
            plan_zones[plan_zones.index(child)] = _shift_outline(child, dx, dy)

    return {
        "zones": plan_zones,
        "design_rationale": intent.get("design_rationale", ""),
    }


def _main(argv: list[str]) -> int:
    import argparse
    from pathlib import Path
    p = argparse.ArgumentParser(description="aiplan normalize: 统一 path → plan.json zones 绝对坐标")
    p.add_argument("--intent", required=True, help="design_intent.json 路径")
    p.add_argument("--lot", help="lot_polygon_mm JSON（可选，用于校验）")
    args = p.parse_args(argv)

    intent = json.loads(Path(args.intent).read_text(encoding="utf-8"))
    lot = json.loads(args.lot) if args.lot else None
    try:
        result = normalize(intent, lot)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except NormalizeError as e:
        print(json.dumps(e.error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2  # 结构化错误 exit 2（回喂模型重发）


def main() -> int:
    return _main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))

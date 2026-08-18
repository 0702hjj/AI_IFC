"""geom —— 轮廓几何校验（aiplan geom check / align）。

plan 的"空间理解"靠本模块校验 LLM 声明的几何，LLM 只给设计意图：
- **check**：地块内 / 退线 / 自相交 / 锚点在轮廓内 / 多 zone 不重叠 / 孔洞在 outer 内
- **align**：跨层核心筒对齐 / zone 落宿主
- 生成/构造（旧 generate/operate）已删（2026-08-17）：流程是 LLM 声明 rings → normalize
  展开 → 本模块校验，机器不再生成轮廓

数据结构对齐自持 plan.schema.json：outline_mm = [{outer, holes, arcs}]，
site = {lot_polygon_mm, setbacks_mm}。纯函数，确定性（shapely 2.x）。

v3.1（2026-08-09）：holes 升级 ring——纯顶点数组（直边孔简写）或
{"vertices", "arcs?"}（真弧孔洞，与 outer 同等表达力）；整圆规范形
真弧 ring（vertices+arcs）由 normalize 产出，本模块致密化 ~12° 弦段后判定
），面积/包含判定按真弧算。

v3.1+（2026-08-10）：core 升级 object——anchor_mm（位置）+ extent_mm?
（外包尺寸）+ shape?（轮廓 polygon|ring，与 holes 同等）；核心筒不再只是
一个点，plan 可给形状，CAD 跨层基线在 plan。
"""

from __future__ import annotations

import math

from shapely.geometry import Point, Polygon

from aiplan_tools.json_arg import load_json_arg


# ═══════════════════ ring / 真弧支持（v3.1）═══════════════════

def _signed_area(verts: list[list[float]]) -> float:
    """顶点环有向面积（>0 = 逆时针）。弧致密化方向判定用。"""
    s = 0.0
    n = len(verts)
    for i in range(n):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return s / 2.0


def _densify_ring(vertices: list, arcs: list | None = None, chord_deg: float = 12.0) -> list[list[float]]:
    """顶点 + 弧标注 → 致密化顶点（弧段替换为 ~12° 弦段逼近）。

    arcs 中 at = 弧起点顶点下标；弧从 vertices[at] 沿环向到 vertices[(at+1)%n]。
    a0/a1 缺省时从两端点相对圆心的方位角推算；方向随环的旋向（CCW 正/CW 负）。
    """
    verts = [[float(p[0]), float(p[1])] for p in vertices]
    if not arcs:
        return verts
    ccw = _signed_area(verts) > 0
    n = len(verts)
    arc_by_at = {int(a["at"]): a for a in arcs}
    out: list[list[float]] = []
    for i in range(n):
        p0, p1 = verts[i], verts[(i + 1) % n]
        out.append(p0)
        a = arc_by_at.get(i)
        if a is None:
            continue
        cx, cy = float(a["center"][0]), float(a["center"][1])
        r = float(a["radius"])
        a0 = a.get("a0")
        a1 = a.get("a1")
        if a0 is None:
            a0 = math.degrees(math.atan2(p0[1] - cy, p0[0] - cx))
        if a1 is None:
            a1 = math.degrees(math.atan2(p1[1] - cy, p1[0] - cx))
        a0, a1 = float(a0), float(a1)
        if ccw:
            while a1 <= a0:
                a1 += 360.0
        else:
            while a1 >= a0:
                a1 -= 360.0
        steps = max(1, int(abs(a1 - a0) / chord_deg + 0.999))
        for k in range(1, steps):
            ang = math.radians(a0 + (a1 - a0) * k / steps)
            out.append([cx + r * math.cos(ang), cy + r * math.sin(ang)])
    return out


def _ring_to_polygon(ring) -> Polygon:
    """任意闭合形状 → shapely Polygon（统一入口，outer/holes/core 全走这里）。

    三种输入形态（v3.1 统一）：
    - 纯顶点数组 [[x,y],...] —— 直边简写（polygon shorthand）
    - {"vertices": [...], "arcs": [...]} —— ring object（真弧，致密化后构造）
    - 派生：ring 上的 arcs 按致密化展开，面积/包含判定按真弧算（误差 <0.5%）
    """
    if isinstance(ring, dict):
        return _polygon_from_outer(_densify_ring(ring["vertices"], ring.get("arcs") or []))
    return _polygon_from_outer(ring)


def _resolve_block_rings(block: dict) -> tuple[Polygon, list[Polygon]]:
    """outline 块 → (outer_polygon, [hole_polygon, ...])。

    统一处理三种 outer 形态：bare polygon / ring object / bare polygon + block-level arcs（兼容）。
    holes 统一走 _ring_to_polygon。
    """
    outer_raw = block["outer"]
    block_arcs = block.get("arcs") or []

    if isinstance(outer_raw, dict):
        # ring object（arcs 自带）
        outer_poly = _ring_to_polygon(outer_raw)
    elif block_arcs:
        # bare polygon + block-level arcs（v3 兼容：arcs 吸收进 ring）
        outer_poly = _ring_to_polygon({"vertices": outer_raw, "arcs": block_arcs})
    else:
        # bare polygon，无弧
        outer_poly = _ring_to_polygon(outer_raw)

    hole_polys = [_ring_to_polygon(h) for h in block.get("holes", [])]
    return outer_poly, hole_polys


# ═══════════════════════════════ 校验 ═══════════════════════════════

def _polygon_from_outer(outer: list[list[float]]) -> Polygon:
    """顶点数组 → shapely Polygon（自动闭合）。

    不做 make_valid——保持原始有效性，供自相交检测；生成场景保证输入合法。
    """
    if outer and outer[0] != outer[-1]:
        outer = outer + [outer[0]]
    return Polygon(outer)


def zone_union(outline_mm: list[dict]) -> Polygon:
    """zone 的多边形集合 → 并集（多块离散 + 孔洞挖空）。

    v3.1 统一：所有 ring 走 _resolve_block_rings → _ring_to_polygon。
    """
    parts = []
    for block in outline_mm:
        outer_poly, hole_polys = _resolve_block_rings(block)
        for hp in hole_polys:
            outer_poly = outer_poly.difference(hp)
        parts.append(outer_poly)
    if not parts:
        return Polygon()
    union = parts[0]
    for p in parts[1:]:
        union = union.union(p)
    return union


def check_outline(
    outline_mm: list[dict],
    lot_polygon_mm: list[list[float]] | None = None,
    setbacks_mm: dict | None = None,
    core_anchor_mm: list[float] | list[list[float]] | None = None,
) -> list[str]:
    """轮廓合法性校验，返回违规列表（空=通过）。

    - 自相交 / 无效几何 → 报（附 shapely explain_validity 定位）
    - 地块内：lot 存在时 union ⊆ lot → 否则报"超地块"
    - 退线：setbacks 存在时 union 各边距 lot 边 ≥ 对应退线 → 否则报
    - 锚点在轮廓内：core_anchor 单点或锚点数组（多核）都支持，逐点校验
    """
    errs: list[str] = []
    union = zone_union(outline_mm)
    if union.is_empty:
        return ["轮廓为空或无效"]

    # 自相交 + 孔洞须在外环内（v3.1 统一：_resolve_block_rings 处理所有 ring 形态）
    for i, block in enumerate(outline_mm):
        outer_poly, hole_polys = _resolve_block_rings(block)
        if not outer_poly.is_valid or outer_poly.is_empty:
            from shapely.validation import explain_validity
            reason = explain_validity(outer_poly) if not outer_poly.is_empty else "empty"
            errs.append(f"outline_mm[{i}] 无效几何/自相交: {reason}")
            continue
        for j, hp in enumerate(hole_polys):
            if not hp.is_valid or hp.is_empty:
                from shapely.validation import explain_validity
                reason = explain_validity(hp) if not hp.is_empty else "empty"
                errs.append(f"outline_mm[{i}].holes[{j}] 无效几何/自相交: {reason}")
            elif not outer_poly.covers(hp):
                errs.append(f"outline_mm[{i}].holes[{j}] 超出外环")

    # 地块内（covers：轮廓可与地块重合，但不能超出）
    if lot_polygon_mm is not None:
        lot = _polygon_from_outer(lot_polygon_mm)
        if not lot.covers(union):
            errs.append("轮廓超出地块边界")

    # 退线
    if setbacks_mm is not None and lot_polygon_mm is not None:
        lot = _polygon_from_outer(lot_polygon_mm)
        # 用 union 外边界点到 lot 边界的距离近似（简化：检查外包络 vs lot buffer 退线）
        from shapely.geometry import box

        minx, miny, maxx, maxy = union.bounds
        # 四个方向距 lot 边界距离
        lminx, lminy, lmaxx, lmaxy = lot.bounds
        front = maxx - lmaxx  # front=北（align 语义沿用 v2: front=建筑正面，此处按北简化）
        # 实际按四面距：左/右/北/南 对应 left/right/front/rear（近似，正面=北）
        dist_right = lmaxx - maxx
        dist_left = minx - lminx
        dist_north = lmaxy - maxy
        dist_south = miny - lminy
        for side, dist, req in [
            ("front(北)", dist_north, setbacks_mm.get("front", 0)),
            ("rear(南)", dist_south, setbacks_mm.get("rear", 0)),
            ("left", dist_left, setbacks_mm.get("left", 0)),
            ("right", dist_right, setbacks_mm.get("right", 0)),
        ]:
            if dist < req - 1e-6:
                errs.append(f"退线不满足: {side} 距地块边 {dist:.0f}mm < 要求 {req}mm")

    # 锚点在轮廓内（单点或多核数组都支持）
    if core_anchor_mm is not None:
        anchors = core_anchor_mm
        if anchors and isinstance(anchors[0], (int, float)):
            anchors = [anchors]
        for k, a in enumerate(anchors):
            pt = Point(a)
            if not union.covers(pt):
                errs.append(f"核心筒锚点[{k}] {a} 不在轮廓内")

    return errs


def check_alignment(zones: list[dict]) -> list[str]:
    """多 zone 对齐校验（楼层对齐）：
    - 相邻 zone（如 tower 落 podium）outline ⊆ 对方 → 否则报
    - **核心筒跨层对齐（S3）**：zone_split 链上的 zone 核心筒锚点必须一致
      （align_vertical core——分裂 zone 与父 zone 几何位置相同）
      v3.1+：若 zone 带 core.shape，shape 也须跨层一致（不仅锚点）
    - **核心筒在轮廓内**：core shape/extent ⊆ zone outline
    - 返回违规列表（空=通过）。
    """
    errs: list[str] = []
    for z in zones:
        pos = z.get("position") or {}
        if pos.get("on"):
            host_id = pos["on"]
            host = next((h for h in zones if h["id"] == host_id), None)
            if host is None:
                errs.append(f"zone {z['id']} 的 position.on={host_id} 不存在")
                continue
            child = zone_union(z["outline_mm"])
            parent = zone_union(host["outline_mm"])
            if not parent.covers(child):
                errs.append(f"zone {z['id']} 超出宿主 {host_id}（塔楼⊄裙房）")

    # 核心筒解析（v3.1 统一）：core = polygon|ring|core 数组（多核），
    # 或 core_anchor_mm 简写（单点/多点数组）；anchor 从 ring 质心派生
    def core_info(z):
        """返回 {core_id: (anchor, poly)}；无核 → {}。

        支持四种形态：
        - design_intent 多核数组 [{"id","path":{rings:[{edges}]}}]
        - normalize 产物环对象数组 [{"vertices","arcs"}]（无 id → 按 core<i> 命名）
        - 单核对象（path 或 vertices）
        - core_anchor_mm（单点 / 多点数组）
        """
        c = z.get("core")
        if isinstance(c, list):
            # 空数组 → 无核
            if not c:
                return {}
            # 元素是 dict：
            #   a) 带 path（design_intent 数组）
            #   b) 带 vertices（normalize 环对象）
            #   c) 纯点（裸顶点多边形）
            if isinstance(c[0], dict) and ("path" in c[0] or "vertices" in c[0]):
                out = {}
                for i, item in enumerate(c):
                    cid = item.get("id", f"core{i}")
                    if "path" in item:
                        r0 = (item["path"] or {}).get("rings", [{}])[0]
                        if "edges" in r0:
                            # ring_edges（四边拼合）→ 顶点环
                            es = r0["edges"]
                            verts = list(es["west"])
                            for side in ("north", "east", "south"):
                                verts.extend(es[side][1:])
                            poly = _ring_to_polygon(verts)
                        else:
                            poly = _ring_to_polygon(r0)
                    else:
                        poly = _ring_to_polygon(item)
                    cx, cy = poly.centroid.x, poly.centroid.y
                    out[cid] = ((cx, cy), poly)
                return out
            # 裸顶点多边形（单核，顶点数组）
            poly = _ring_to_polygon(c)
            cx, cy = poly.centroid.x, poly.centroid.y
            return {"core": ((cx, cy), poly)}
        if c is not None:
            poly = _ring_to_polygon(c)
            cx, cy = poly.centroid.x, poly.centroid.y
            return {"core": ((cx, cy), poly)}
        a = z.get("core_anchor_mm")
        if a:
            if a and isinstance(a[0], (int, float)):
                return {"core": (tuple(a), None)}
            return {f"core{i}": (tuple(p), None) for i, p in enumerate(a)}
        return {}

    # S3 核心筒跨层对齐：仅在同一竖向栈的 zone 间比较。
    # 竖向栈 = position.on 链 或 轮廓重叠（塔楼落裙房隐式）→ 并查集连通分组；
    # 独立楼栋（南排 vs 北排，轮廓不重叠也无 position.on）的核不互比
    parent = {z["id"]: z["id"] for z in zones}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for z in zones:
        pos = z.get("position") or {}
        if pos.get("on") and pos["on"] in parent:
            union(z["id"], pos["on"])
    for z in zones:
        u = zone_union(z.get("outline_mm") or [])
        for o in zones:
            if o is z:
                continue
            ov = zone_union(o.get("outline_mm") or [])
            # 栈判定只认「面积重叠」（塔落裙房隐式）；贴边相邻（intersects 但交集面积=0）
            # 视为独立楼栋不互比——双塔+裙房贴边围合广场场景（2026-08-17）
            if not u.is_empty and not ov.is_empty and u.intersection(ov).area > 0:
                union(z["id"], o["id"])

    by_stack: dict[str, dict[str, list]] = {}
    for z in zones:
        st = find(z["id"])
        for cid, (a, s) in core_info(z).items():
            by_stack.setdefault(st, {}).setdefault(cid, []).append(z["id"])
            if s is not None:
                key = (round(s.area), round(s.bounds[2] - s.bounds[0]),
                       round(s.bounds[3] - s.bounds[1]))
                by_stack.setdefault(st, {}).setdefault(f"{cid}:shape", []).append(key)
    for st, groups in by_stack.items():
        for cid, ids in groups.items():
            if cid.endswith(":shape"):
                continue
            anchors_uniq: dict = {}
            for z in zones:
                if find(z["id"]) != st:
                    continue
                for cid2, (a, s) in core_info(z).items():
                    if cid2 == cid:
                        anchors_uniq.setdefault(a, []).append(z["id"])
            if len(anchors_uniq) > 1:
                desc = "; ".join(f"{','.join(ids)}@{list(k)}" for k, ids in anchors_uniq.items())
                if cid == "core" and len(groups) <= 2:
                    errs.append(f"核心筒锚点不一致（跨层须对齐，S3）: {desc}")
                else:
                    errs.append(f"核心筒[{cid}] 锚点不一致（跨层须对齐，S3）: {desc}")
        for cid, keys in groups.items():
            if cid.endswith(":shape") and len(set(keys)) > 1:
                desc = "; ".join(f"area={k[0]:.0f}" for k in sorted(set(keys)))
                errs.append(f"核心筒[{cid[:-6]}] shape 不一致（跨层须对齐，S3）: {desc}")

    # 核心筒在轮廓内（v3.1+ 新增）
    for z in zones:
        for cid, (a, s) in core_info(z).items():
            union = zone_union(z["outline_mm"])
            if s is not None:
                if not union.covers(s):
                    errs.append(f"zone {z['id']} 核心筒[{cid}] shape 超出轮廓")
            else:
                pt = Point(a)
                if not union.covers(pt):
                    errs.append(f"zone {z['id']} 核心筒[{cid}] 锚点 {list(a)} 不在轮廓内")
    return errs


# ═══════════════════════════════ CLI ═══════════════════════════════


def _main(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(description="aiplan 轮廓几何校验：check（地块/退线/锚点/自交）+ align（跨层对齐）")
    sub = p.add_subparsers(dest="cmd")

    c = sub.add_parser("check", help="轮廓校验（地块/退线/锚点/自相交）；--zones 全量多 zone 一次校验")
    c.add_argument("--outline", help="outline_mm JSON 或文件路径")
    c.add_argument("--lot", help="lot_polygon_mm JSON 或文件路径（裸数组 [[x,y],...]）")
    c.add_argument("--setbacks", help="setbacks_mm JSON 或文件路径")
    c.add_argument("--anchor", help="core_anchor_mm JSON（单点或多点数组）")
    c.add_argument("--zones", help="zones JSON 或文件路径（normalize 产物）→ 全 zone 轮廓+对齐一次校验")

    a = sub.add_parser("align", help="多 zone 对齐校验（塔楼⊆裙房等；兼容保留，推荐用 check --zones）")
    a.add_argument("--zones", required=True, help="zones JSON（含 outline_mm + position）")

    args = p.parse_args(argv)

    if args.cmd == "check":
        # --zones 全量入口：normalize 产物 zones → 逐 zone 轮廓 + 全量对齐一次校验
        if args.zones:
            zones_data = load_json_arg(args.zones)
            # 兼容 normalize 产物（顶层 {"zones": [...]}）和裸 zones 数组
            zones = zones_data.get("zones") if isinstance(zones_data, dict) else zones_data
            lot = load_json_arg(args.lot) if args.lot else None
            sb = load_json_arg(args.setbacks) if args.setbacks else None
            errs = []
            for z in zones:
                e = check_outline(z.get("outline_mm") or [], lot, sb,
                                  z.get("core_anchor_mm"))
                for msg in e:
                    errs.append(f"zone[{z.get('id','?')}] {msg}")
            errs += check_alignment(zones)
            if errs:
                print("[FAIL]")
                for e in errs:
                    print(f"  - {e}")
                return 1
            print("[OK] 全 zone 轮廓 + 对齐校验通过")
            return 0
        if not args.outline:
            print("check 需要 --outline 或 --zones")
            return 2
        outline = load_json_arg(args.outline)
        lot = load_json_arg(args.lot) if args.lot else None
        sb = load_json_arg(args.setbacks) if args.setbacks else None
        anchor = load_json_arg(args.anchor) if args.anchor else None
        errs = check_outline(outline, lot, sb, anchor)
        if errs:
            print("[FAIL]")
            for e in errs:
                print(f"  - {e}")
            return 1
        print("[OK] 轮廓合法")
        return 0

    if args.cmd == "align":
        zones_data = load_json_arg(args.zones)
        zones = zones_data.get("zones") if isinstance(zones_data, dict) else zones_data
        errs = check_alignment(zones)
        if errs:
            print("[FAIL]")
            for e in errs:
                print(f"  - {e}")
            return 1
        print("[OK] 多 zone 对齐正确")
        return 0

    p.print_help()
    return 2


def main() -> int:
    import sys
    return _main(sys.argv[1:])

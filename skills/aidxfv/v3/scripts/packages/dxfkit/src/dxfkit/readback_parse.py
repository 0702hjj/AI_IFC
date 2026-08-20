"""readback_parse: DXF 实体解析（墙/门窗/标注 → 几何图元）与墙段整理。

拆分自 readback.py（W-0049 文件行数门控）；对外契约仍由 dxfkit.readback 再导出。
"""

from __future__ import annotations

import math

from shapely.geometry import Polygon

from dxfkit import readback_state as _st
from dxfkit.readback_state import (
    WALL_PAIR_GAP_MM, WALL_GAP_CLOSE_MM,
    WALL_LAYERS, DOOR_LAYER, GLAZ_LAYER, ANNO_LAYER, IGNORE_LAYERS,
    ANNO_WHITELIST, AREA_RE,
)
from dxfkit.readback_checks import _map_layer


def _text_pos(e):
    if e.dxf.get("halign", 0) or e.dxf.get("valign", 0):
        p = e.dxf.get("align_point")
        if p is not None:
            return (round(p.x, 3), round(p.y, 3))
    p = e.dxf.insert
    return (round(p.x, 3), round(p.y, 3))


def _arc_points(center, radius, start_deg, end_deg, chord=_st.GRID_MM / 2):
    sweep = math.radians((end_deg - start_deg) % 360.0) or math.tau
    n = max(4, int(math.ceil(radius * sweep / chord)))
    a0 = math.radians(start_deg)
    return [
        (center[0] + radius * math.cos(a0 + sweep * i / n),
         center[1] + radius * math.sin(a0 + sweep * i / n))
        for i in range(n + 1)
    ]


def _polyline_with_bulge(pts_xyb: list) -> list:
    """LWPOLYLINE 顶点（含 bulge）→ 折线顶点（弧段弦近似 ~12° 一段）。

    曲线墙/不规则轮廓（mall 幕墙）：bulge ≠ 0 的段是弧，按弧长拆弦。
    """
    out = []
    for i in range(len(pts_xyb)):
        x0, y0, b = pts_xyb[i]
        x1, y1, _ = pts_xyb[(i + 1) % len(pts_xyb)]
        out.append((x0, y0))
        if abs(b) < 1e-6:
            continue
        # bulge 段弧：弦长/方向 + 半径
        chord = math.hypot(x1 - x0, y1 - y0)
        if chord < 1e-6:
            continue
        radius = chord * (1 + b * b) / (4 * abs(b))
        if not math.isfinite(radius) or radius > 1e7:
            continue
        # 圆心：弦中点 + 法向偏移
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        ux, uy = (x1 - x0) / chord, (y1 - y0) / chord
        h = math.sqrt(max(0.0, radius * radius - (chord / 2) ** 2))
        side = 1.0 if b > 0 else -1.0
        cx, cy = mx - side * h * uy, my + side * h * ux
        a0 = math.degrees(math.atan2(y0 - cy, x0 - cx))
        a1 = math.degrees(math.atan2(y1 - cy, x1 - cx))
        # 弧段方向修正（bulge 符号决定扫掠方向）
        sweep = (a1 - a0) % 360.0
        if b > 0 and sweep > 180.0:
            sweep -= 360.0
        elif b < 0 and sweep < 180.0:
            sweep -= 360.0
        n = max(1, int(abs(sweep) / 12.0) + 1)
        for k in range(1, n + 1):
            ang = math.radians(a0 + sweep * k / n)
            out.append((cx + radius * math.cos(ang), cy + radius * math.sin(ang)))
    return out


def _unparsed(unparsed, e, at, reason):
    unparsed.append({
        "layer": e.dxf.layer,
        "entity": e.dxftype(),
        "at": [round(at[0], 3), round(at[1], 3)],
        "reason": reason,
    })


def _parse(msp, layer_map=None):
    solids, barriers, windows, texts, unparsed = [], [], [], [], []
    wall_arcs = []     # 墙层 ARC 实体记录(曲线回收,同步桥用)
    fat_barriers = []  # 窗线:须覆盖整墙厚(开洞带上下都可能绕行)
    jambs = []         # 短墙线(≤600mm 跨墙厚):开洞封口,轮廓补缺用
    door_leafs, door_arcs = [], []
    for e in msp:
        layer = _map_layer(e.dxf.layer, layer_map)
        kind = e.dxftype()
        if layer in IGNORE_LAYERS:
            continue
        if layer in WALL_LAYERS:
            if kind == "HATCH":
                try:
                    for path in e.paths:
                        pts = []
                        if hasattr(path, "vertices"):
                            # PolylinePath（type 1）：直接顶点
                            pts = [(round(v[0], 3), round(v[1], 3))
                                   for v in path.vertices
                                   if v[0] is not None and v[1] is not None
                                   and not math.isnan(v[0]) and not math.isnan(v[1])]
                        else:
                            # EdgePath（type 2）：line/arc 边转顶点（hotel 主体墙形态）
                            for edge in getattr(path, "edges", []):
                                et = getattr(edge, "type", 0)
                                if et == 1:  # line edge
                                    for v in (edge.start, edge.end):
                                        pts.append((round(v.x, 3), round(v.y, 3)))
                                elif et == 2:  # arc edge → 弦近似
                                    arc_pts = _arc_points(
                                        edge.center, edge.radius,
                                        edge.start_angle, edge.end_angle)
                                    pts.extend([(round(v[0], 3), round(v[1], 3))
                                                for v in arc_pts])
                        if len(pts) >= 3:
                            solids.append(Polygon(pts))
                except Exception:
                    _unparsed(unparsed, e, (0, 0), "hatch boundary unsupported")
            elif kind == "LINE":
                seg = ((e.dxf.start.x, e.dxf.start.y),
                       (e.dxf.end.x, e.dxf.end.y))
                fat_barriers.append(seg)  # fat(±50mm)填满双线墙腔(~152mm)
                barriers.append(seg)  # ★真实结构图常为 LINE 墙（无 HATCH）——LINE 也是屏障（R-01 适配）
                if math.hypot(seg[1][0] - seg[0][0],
                              seg[1][1] - seg[0][1]) <= 600.0:
                    jambs.append(seg)
            elif kind == "ARC":
                if (e.dxf.radius or 0) <= 0:
                    _unparsed(unparsed, e, (0, 0), "arc radius zero")
                    continue
                pts = _arc_points(e.dxf.center, e.dxf.radius,
                                  e.dxf.start_angle, e.dxf.end_angle)
                barriers.extend(zip(pts, pts[1:]))
                wall_arcs.append({
                    "center": [round(e.dxf.center.x, 3),
                               round(e.dxf.center.y, 3)],
                    "radius": round(e.dxf.radius, 3),
                    "start_angle": round(e.dxf.start_angle, 3),
                    "end_angle": round(e.dxf.end_angle, 3),
                })
            elif kind == "LWPOLYLINE":
                try:
                    pts = _polyline_with_bulge(list(e.get_points("xyb")))
                except Exception:
                    pts = [(p[0], p[1]) for p in e.get_points()]
                barriers.extend(zip(pts, pts[1:]))
            else:
                _unparsed(unparsed, e, (0, 0), "unexpected on wall layer")
        elif layer == DOOR_LAYER:
            if kind == "LINE":
                door_leafs.append(((e.dxf.start.x, e.dxf.start.y),
                                   (e.dxf.end.x, e.dxf.end.y)))
            elif kind == "ARC":
                door_arcs.append((e.dxf.center.x, e.dxf.center.y, e.dxf.radius,
                                  e.dxf.start_angle, e.dxf.end_angle))
            else:
                _unparsed(unparsed, e, (0, 0), "unexpected on door layer")
        elif layer == GLAZ_LAYER:
            if kind == "LINE":
                seg = ((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y))
                windows.append(seg)
                fat_barriers.append(seg)  # 窗洞不可通行:封住整段开洞带
            else:
                _unparsed(unparsed, e, (0, 0), "unexpected on glazing layer")
        elif layer == ANNO_LAYER:
            if kind in ("TEXT", "MTEXT"):
                content = e.dxf.text if kind == "TEXT" else e.plain_text()
                pos = _text_pos(e) if kind == "TEXT" else (
                    round(e.dxf.insert.x, 3), round(e.dxf.insert.y, 3))
                h = e.dxf.height if kind == "TEXT" else e.dxf.char_height
                texts.append({"content": content.strip(), "at": pos,
                              "height": round(float(h), 3)})
            elif kind in ANNO_WHITELIST:
                continue  # 下划线/圆标/指北针等,非语义
            else:
                _unparsed(unparsed, e, (0, 0), "unexpected on annotation layer")
        else:
            at = (0.0, 0.0)
            if kind == "LINE":
                at = (e.dxf.start.x, e.dxf.start.y)
            elif kind in ("CIRCLE", "ARC"):
                at = (e.dxf.center.x, e.dxf.center.y)
            elif kind in ("TEXT", "MTEXT"):
                at = (e.dxf.insert.x, e.dxf.insert.y)
            _unparsed(unparsed, e, at, "unknown layer")
    # 双线墙识别：平行线对（间距 < WALL_PAIR_GAP_MM + 投影重叠）→ 墙腔填实
    # （中线段 buffer(gap/2) 成 polygon 进 solids——HATCH 同路径，覆盖任意墙腔宽）
    # 配对成功的线从 barriers 剔除（主体墙已由墙腔 solids 表达，单线重复 mark 会切碎空间）
    from shapely.geometry import LineString as _LS
    paired_idx = set()
    for mid_seg, gap, (ia, ib) in _pair_double_line_walls(barriers):
        if not all(math.isfinite(v) for v in
                   (mid_seg[0][0], mid_seg[0][1], mid_seg[1][0], mid_seg[1][1])):
            continue
        mid_poly = _LS([mid_seg[0], mid_seg[1]]).buffer(gap / 2 + 5.0,
                                                         cap_style="flat")
        solids.append(mid_poly)
        paired_idx.add(ia)
        paired_idx.add(ib)
    barriers = [s for i, s in enumerate(barriers) if i not in paired_idx]
    # 碎线过滤：孤立短线（<MIN_WALL_SEG_MM 且非 jamb）从屏障剔除（家具/标注残留）
    barriers = [s for s in barriers
                if math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1]) >= _st.MIN_WALL_SEG_MM
                or s in {j for j in jambs}]

    return (solids, barriers, fat_barriers, jambs, windows, texts,
            door_leafs, door_arcs, unparsed, wall_arcs)


def _close_wall_gaps(segments: list) -> list:
    """墙段间隙闭合：同向共线墙段端点距离 < WALL_GAP_CLOSE_MM → 补线段（门/窗开口封口）。

    主体墙由 HATCH 墙段/双线腔表达，段间开口（门 ~900/窗 ~2000）不封闭则
    洪水从开口涌入把全部房间连通成 exterior——间隙闭合是房间识别的关键。
    """
    closes = []
    for i in range(len(segments)):
        a0, a1 = segments[i]
        la = math.hypot(a1[0] - a0[0], a1[1] - a0[1])
        if la < 1e-6:
            continue
        ua = ((a1[0] - a0[0]) / la, (a1[1] - a0[1]) / la)
        for j in range(i + 1, len(segments)):
            b0, b1 = segments[j]
            lb = math.hypot(b1[0] - b0[0], b1[1] - b0[1])
            if lb < 1e-6:
                continue
            ub = ((b1[0] - b0[0]) / lb, (b1[1] - b0[1]) / lb)
            # 共线（同向或反向）
            dot = abs(ua[0] * ub[0] + ua[1] * ub[1])
            if dot < 0.95:
                continue
            # 端点间隙：四对端点最近距
            gap = min(
                math.hypot(a0[0] - b0[0], a0[1] - b0[1]),
                math.hypot(a0[0] - b1[0], a0[1] - b1[1]),
                math.hypot(a1[0] - b0[0], a1[1] - b0[1]),
                math.hypot(a1[0] - b1[0], a1[1] - b1[1]),
            )
            if 1e-3 < gap <= WALL_GAP_CLOSE_MM:
                # 找最近端点对补线
                pairs = [((a0, b0), math.hypot(a0[0] - b0[0], a0[1] - b0[1])),
                         ((a0, b1), math.hypot(a0[0] - b1[0], a0[1] - b1[1])),
                         ((a1, b0), math.hypot(a1[0] - b0[0], a1[1] - b0[1])),
                         ((a1, b1), math.hypot(a1[0] - b1[0], a1[1] - b1[1]))]
                (p, q), _ = min(pairs, key=lambda x: x[1])
                closes.append((p, q))
    return closes


def _pair_double_line_walls(segments: list) -> list:
    """平行线对识别 → [(中线段, 间距)]（双线墙墙腔填实）。

    两条线：方向平行（夹角 <10°）、间距 < WALL_PAIR_GAP_MM、投影重叠 > 30%。
    """
    pairs = []
    used = set()
    for i in range(len(segments)):
        if i in used:
            continue
        a0, a1 = segments[i]
        la = math.hypot(a1[0] - a0[0], a1[1] - a0[1])
        if la < _st.MIN_WALL_SEG_MM:
            continue
        for j in range(i + 1, len(segments)):
            if j in used:
                continue
            b0, b1 = segments[j]
            lb = math.hypot(b1[0] - b0[0], b1[1] - b0[1])
            if lb < _st.MIN_WALL_SEG_MM:
                continue
            # 平行：叉积 < 10% 长度积
            cross = abs((a1[0] - a0[0]) * (b1[1] - b0[1])
                        - (a1[1] - a0[1]) * (b1[0] - b0[0]))
            if cross > 0.17 * la * lb:
                continue
            # 间距（a 起点到 b 线的距离）
            dist = abs((b1[0] - b0[0]) * (a0[1] - b0[1])
                       - (b1[1] - b0[1]) * (a0[0] - b0[0])) / lb
            if dist < 1e-6 or dist > WALL_PAIR_GAP_MM:
                continue
            # 投影重叠 > 30%
            ua = ((a1[0] - a0[0]) / la, (a1[1] - a0[1]) / la)
            proj_b0 = (b0[0] - a0[0]) * ua[0] + (b0[1] - a0[1]) * ua[1]
            proj_b1 = (b1[0] - a0[0]) * ua[0] + (b1[1] - a0[1]) * ua[1]
            lo, hi = sorted((proj_b0, proj_b1))
            overlap = max(0.0, min(hi, la) - max(lo, 0.0))
            if overlap < 0.3 * min(la, lb):
                continue
            # 中线段
            mid0 = ((a0[0] + b0[0]) / 2, (a0[1] + b0[1]) / 2)
            mid1 = ((a1[0] + b1[0]) / 2, (a1[1] + b1[1]) / 2)
            pairs.append(((mid0, mid1), dist, (i, j)))
            used.add(i)
            used.add(j)
            break
    return pairs


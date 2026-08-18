"""readback: DXf → 房间图（V3，从 V2 layout/from_dxf.py 迁移，改包名 import）。

V2 解析器（墙体 HATCH 掩码 + 栅格洪水填充分区 + 门配对 + 标注配对）逻辑不动；
V3 适配：
- 输出增加 `to_room_graph()`：V2 词表（nodes/edges）→ V3 房间图（rooms/adjacencies/
  doors），对齐 floorgeom.reconcile 消费格式（T24+ 契约测试 P1）；
- 代理实体前置检查（I-01）：ACAD_PROXY_ENTITY 无 proxy_graphic 占比 > 阈值 → 拒收；
- layer_map 图层映射（I-04）：源图层 → 标准语义层。
"""

from __future__ import annotations

import math
import re
from collections import deque
from pathlib import Path

import ezdxf
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
from shapely.prepared import prep

GRID_MM = 50.0
BASE_GRID_MM = 50.0
MAX_CELLS_PER_SIDE = 800     # 自适应栅格：每边最多 800 格（大图不爆）
MIN_WALL_SEG_MM = 300.0      # 碎线过滤阈值（<300mm 孤立短线视为噪声）
WALL_PAIR_GAP_MM = 320.0     # 双线墙识别：平行线间距 < 此值 → 墙腔填实
WALL_GAP_CLOSE_MM = 2400.0   # 墙段间隙闭合：同线墙段端点距离 < 此值补线（门/窗开口也是房间边界）
PROBE_MAX_MM = 800.0


def _adaptive_grid_mm(width_mm: float, height_mm: float) -> float:
    """图幅 → 自适应栅格（每边 ≤ MAX_CELLS_PER_SIDE，2 的倍数增长）。"""
    side = max(width_mm, height_mm)
    grid = BASE_GRID_MM
    while side / grid > MAX_CELLS_PER_SIDE:
        grid *= 2
    return grid
WALL_LAYERS = ("WALL", "WALL")
DOOR_LAYER = "DOOR"
GLAZ_LAYER = "WINDOW"
ANNO_LAYER = "TEXT"
IGNORE_LAYERS = {
    "0", "Defpoints", "DIM", "FIRE", "FIXTURE", "STAIR",
    "COLUMN", "SECTION", "TABLE",
    "IGNORE",  # layer_map 映射值（LAYER_MAP_DEFAULT 的 S-FOOTER/S-SLAB 等）——跳过不进 unparsed
}
ANNO_WHITELIST = {"TEXT", "MTEXT", "LINE", "CIRCLE", "SOLID", "POINT"}
AREA_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*(M2|SF|㎡)$", re.IGNORECASE)

CELL_COLS = "abcde"

# I-01 代理实体拒收阈值（占比 > 此值拒收）
PROXY_REJECT_RATIO = 0.1


def _merge_runs(edges):
    """单位格边合并为共线长段（V2 vectorize._merge_runs 自持）。edges: [(x1,y1,x2,y2)]。"""
    groups = {}
    for x1, y1, x2, y2 in edges:
        if x1 == x2:
            key = ("v", x1)
            lo, hi = sorted((y1, y2))
        else:
            key = ("h", y1)
            lo, hi = sorted((x1, x2))
        groups.setdefault(key, []).append((lo, hi))
    segments = []
    for (orient, fixed), spans in sorted(groups.items()):
        spans.sort()
        cur_lo, cur_hi = spans[0]
        for lo, hi in spans[1:]:
            if lo <= cur_hi + 1e-6:
                cur_hi = max(cur_hi, hi)
            else:
                segments.append((orient, fixed, cur_lo, cur_hi))
                cur_lo, cur_hi = lo, hi
        segments.append((orient, fixed, cur_lo, cur_hi))
    out = []
    for orient, fixed, lo, hi in segments:
        if orient == "v":
            out.append([[int(round(fixed)), int(round(lo))],
                        [int(round(fixed)), int(round(hi))]])
        else:
            out.append([[int(round(lo)), int(round(fixed))],
                        [int(round(hi)), int(round(fixed))]])
    return out


# ---------------------------------------------------------------- 实体解析

def _text_pos(e):
    if e.dxf.get("halign", 0) or e.dxf.get("valign", 0):
        p = e.dxf.get("align_point")
        if p is not None:
            return (round(p.x, 3), round(p.y, 3))
    p = e.dxf.insert
    return (round(p.x, 3), round(p.y, 3))


def _arc_points(center, radius, start_deg, end_deg, chord=GRID_MM / 2):
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
                if math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1]) >= MIN_WALL_SEG_MM
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
        if la < MIN_WALL_SEG_MM:
            continue
        for j in range(i + 1, len(segments)):
            if j in used:
                continue
            b0, b1 = segments[j]
            lb = math.hypot(b1[0] - b0[0], b1[1] - b0[1])
            if lb < MIN_WALL_SEG_MM:
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


# ---------------------------------------------------------------- 门配对

def _pair_doors(leafs, arcs, unparsed):
    """leaf LINE + swing ARC 配对:弧心=铰链,弧起点=门闩侧 → 开洞区间。"""
    doors, used = [], set()
    for cx, cy, r, a0, a1 in sorted(arcs):
        best, best_d = None, GRID_MM
        for i, (p1, p2) in enumerate(leafs):
            if i in used:
                continue
            for p in (p1, p2):
                d = math.hypot(p[0] - cx, p[1] - cy)
                if d < best_d:
                    best, best_d = i, d
        if best is None:
            unparsed.append({"layer": DOOR_LAYER, "entity": "ARC",
                             "at": [round(cx, 3), round(cy, 3)],
                             "reason": "swing arc without leaf"})
            continue
        used.add(best)
        strike = (cx + r * math.cos(math.radians(a0)),
                  cy + r * math.sin(math.radians(a0)))
        doors.append({"hinge": (round(cx, 3), round(cy, 3)),
                      "strike": (round(strike[0], 3), round(strike[1], 3)),
                      "width_mm": round(r, 3),
                      "arc": (round(cx, 3), round(cy, 3), round(r, 3),
                              round(a0, 3), round(a1, 3))})
    for i, (p1, _p2) in enumerate(leafs):
        if i not in used:
            unparsed.append({"layer": DOOR_LAYER, "entity": "LINE",
                             "at": [round(p1[0], 3), round(p1[1], 3)],
                             "reason": "door leaf without swing arc"})
    return doors


# ---------------------------------------------------------------- 门窗碰撞检测

def _seg_intersect(p1, p2, p3, p4, tol: float = 0.0) -> bool:
    """线段 (p1,p2) 与 (p3,p4) 是否真相交（非仅端点接触，含共线区间重叠）。

    用 ccw 叉积判交：两段互相跨立才判相交。tol 为距离容差（mm）。
    """
    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])

    d1 = ccw(p3, p4, p1)
    d2 = ccw(p3, p4, p2)
    d3 = ccw(p1, p2, p3)
    d4 = ccw(p1, p2, p4)

    def _near_zero(v):
        return abs(v) <= tol * 0.01 if tol else abs(v) < 1e-9

    if _near_zero(d1) and _near_zero(d2):
        # 共线：检查投影区间是否重叠（错开相邻不算碰撞）
        axis = "x" if abs(p2[0] - p1[0]) > abs(p2[1] - p1[1]) else "y"
        a1, a2 = sorted((p1[0 if axis == "x" else 1], p2[0 if axis == "x" else 1]))
        a3, a4 = sorted((p3[0 if axis == "x" else 1], p4[0 if axis == "x" else 1]))
        gap = max(a1, a3) - min(a2, a4)
        return gap < 0  # 区间真重叠
    if _near_zero(d1) or _near_zero(d2) or _near_zero(d3) or _near_zero(d4):
        return False  # 端点触碰不算（邻墙共用角）
    return (d1 * d2 < 0) and (d3 * d4 < 0)


def _arc_polyline(cx, cy, r, a0, a1, step: float = 15.0) -> list:
    """swing 弧 → 折线（弦近似，步长角度）。"""
    if a1 < a0:
        a1 += 360.0
    n = max(2, int(math.ceil((a1 - a0) / step)))
    return [
        (cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
         cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
        for i in range(n + 1)
    ]


def _polyline_hits_seg(pline: list, p3, p4, tol: float = 0.0) -> bool:
    for i in range(len(pline) - 1):
        if _seg_intersect(pline[i], pline[i + 1], p3, p4, tol):
            return True
    return False


def doorwin_collisions(leafs: list, arcs: list, windows: list,
                       tol: float = 50.0) -> list:
    """门窗碰撞检测（details 后对账兜底，精确判定防误报）。

    输入 readback 原始解析结果：
    - leafs：门 leaf 线段对列表 [(p1, p2), ...]
    - arcs：门 swing 弧 [(cx, cy, r, a0, a1), ...]
    - windows：窗线段对列表 [(p1, p2), ...]

    只报真相交：共线错开、端点接触、跨房间平行线都不算。
    tol：几何容差（mm），默认 50——相交线小于该间距考虑为碰撞噪声。
    """
    issues = []
    # leaf × window
    for j, (w0, w1) in enumerate(windows):
        for i, (p1, p2) in enumerate(leafs):
            if _seg_intersect(p1, p2, w0, w1, tol):
                issues.append({"type": "door_leaf_window",
                               "door": i, "window": j,
                               "at": [round((p1[0] + p2[0]) / 2, 1),
                                      round((p1[1] + p2[1]) / 2, 1)]})
    # leaf × leaf
    for a in range(len(leafs)):
        for b in range(a + 1, len(leafs)):
            p1, p2 = leafs[a]
            p3, p4 = leafs[b]
            if _seg_intersect(p1, p2, p3, p4, tol):
                issues.append({"type": "door_door_leaf",
                               "door_a": a, "door_b": b,
                               "at": [round((p1[0] + p2[0]) / 2, 1),
                                      round((p1[1] + p2[1]) / 2, 1)]})
    # swing 弧折线
    arc_lines = [_arc_polyline(cx, cy, r, a0, a1) for cx, cy, r, a0, a1 in arcs]
    # swing × window
    for j, (w0, w1) in enumerate(windows):
        for i, pline in enumerate(arc_lines):
            if _polyline_hits_seg(pline, w0, w1, tol):
                issues.append({"type": "door_swing_window",
                               "door": i, "window": j,
                               "at": [round((w0[0] + w1[0]) / 2, 1),
                                      round((w0[1] + w1[1]) / 2, 1)]})
    # swing × swing（逐段对逐段）
    for a in range(len(arc_lines)):
        for b in range(a + 1, len(arc_lines)):
            hit = False
            for k in range(len(arc_lines[b]) - 1):
                if _polyline_hits_seg(arc_lines[a],
                                      arc_lines[b][k], arc_lines[b][k + 1], tol):
                    hit = True
                    break
            if hit:
                issues.append({"type": "door_door_swing",
                               "door_a": a, "door_b": b,
                               "at": [round((arc_lines[a][0][0] + arc_lines[a][-1][0]) / 2, 1),
                                      round((arc_lines[a][0][1] + arc_lines[a][-1][1]) / 2, 1)]})
    return issues


# ---------------------------------------------------------------- 栅格分区

class _Grid:
    def __init__(self, minx, miny, maxx, maxy):
        self.minx, self.miny = minx, miny
        self.nx = int(math.ceil((maxx - minx) / GRID_MM))
        self.ny = int(math.ceil((maxy - miny) / GRID_MM))
        self.solid = [[False] * self.nx for _ in range(self.ny)]

    def cell_of(self, x, y):
        return int((y - self.miny) // GRID_MM), int((x - self.minx) // GRID_MM)

    def in_range(self, r, c):
        return 0 <= r < self.ny and 0 <= c < self.nx

    def is_solid(self, r, c):
        return not self.in_range(r, c) or self.solid[r][c]

    def mark_point(self, x, y, fat=False):
        r, c = self.cell_of(x, y)
        for dr in (-1, 0, 1) if fat else (0,):
            for dc in (-1, 0, 1) if fat else (0,):
                if self.in_range(r + dr, c + dc):
                    self.solid[r + dr][c + dc] = True

    def mark_segment(self, p1, p2, fat=False):
        steps = max(1, int(math.hypot(p2[0] - p1[0], p2[1] - p1[1]) / (GRID_MM / 4)))
        for i in range(steps + 1):
            t = i / steps
            self.mark_point(p1[0] + (p2[0] - p1[0]) * t,
                            p1[1] + (p2[1] - p1[1]) * t, fat=fat)

    def center(self, r, c):
        return (self.minx + (c + 0.5) * GRID_MM, self.miny + (r + 0.5) * GRID_MM)

    def flood(self):
        """四邻洪水填充;返回 (region_map, regions)。region 0 = 触边界的室外。"""
        region_map = [[-1] * self.nx for _ in range(self.ny)]
        regions = []
        for r0 in range(self.ny):
            for c0 in range(self.nx):
                if self.solid[r0][c0] or region_map[r0][c0] != -1:
                    continue
                rid = len(regions)
                cells, touches_border = [], False
                q = deque([(r0, c0)])
                region_map[r0][c0] = rid
                while q:
                    r, c = q.popleft()
                    cells.append((r, c))
                    if r in (0, self.ny - 1) or c in (0, self.nx - 1):
                        touches_border = True
                    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nr, nc = r + dr, c + dc
                        if (self.in_range(nr, nc) and not self.solid[nr][nc]
                                and region_map[nr][nc] == -1):
                            region_map[nr][nc] = rid
                            q.append((nr, nc))
                regions.append({"cells": cells, "exterior": touches_border})
        return region_map, regions


def _region_at(grid, region_map, x, y):
    r, c = grid.cell_of(x, y)
    if grid.in_range(r, c) and not grid.solid[r][c]:
        return region_map[r][c]
    # 标注落在墙里等偏差:就近找自由格
    for radius in range(1, 8):
        for dr in range(-radius, radius + 1):
            for dc in (-radius, radius):
                nr, nc = r + dr, c + dc
                if grid.in_range(nr, nc) and not grid.solid[nr][nc]:
                    return region_map[nr][nc]
        for dc in range(-radius + 1, radius):
            for dr in (-radius, radius):
                nr, nc = r + dr, c + dc
                if grid.in_range(nr, nc) and not grid.solid[nr][nc]:
                    return region_map[nr][nc]
    return None


def _cells_to_polygon_mm(cells: list[tuple[int, int]], grid) -> list[list[float]]:
    """region 格集合 → 多边形轮廓坐标（mm）。格 union → 外环简化。"""
    from shapely.ops import unary_union
    boxes = []
    for r, c in cells:
        x0 = grid.minx + c * GRID_MM
        y0 = grid.miny + r * GRID_MM
        boxes.append(box(x0, y0, x0 + GRID_MM, y0 + GRID_MM))
    if not boxes:
        return []
    union = unary_union(boxes)
    if union.geom_type == "GeometryCollection":
        polys = [g for g in union.geoms if g.geom_type == "Polygon"]
        if not polys:
            return []
        union = max(polys, key=lambda p: p.area)
    elif union.geom_type == "MultiPolygon":
        union = max(union.geoms, key=lambda p: p.area)
    if union.is_empty:
        return []
    union = union.simplify(GRID_MM / 2, preserve_topology=True)
    coords = list(union.exterior.coords)
    if len(coords) < 4:
        return []
    return [[round(x, 2), round(y, 2)] for x, y in coords[:-1]]


# ---------------------------------------------------------------- 代理实体检查（I-01）

def check_proxy_entities(path, ratio: float = PROXY_REJECT_RATIO) -> list[str]:
    """前置扫描 ACAD_PROXY_ENTITY：无 proxy_graphic 占比 > 阈值 → 拒收原因列表。

    :return: 空 = 可读；非空 = 拒收原因（G1 闸门）
    """
    doc = ezdxf.readfile(Path(path))
    try:
        msp = doc.modelspace()
        total = 0
        proxy_no_gfx = 0
        for e in msp:
            if e.dxftype() == "ACAD_PROXY_ENTITY":
                total += 1
                if not getattr(e, "proxy_graphic", None):
                    proxy_no_gfx += 1
    except Exception:
        return ["DXF 读取失败"]
    if total == 0:
        return []
    ratio_actual = proxy_no_gfx / total if total else 0.0
    if ratio_actual > ratio:
        return [f"天正代理实体 {proxy_no_gfx}/{total} 无图形占比 {ratio_actual:.0%} "
                f"> 阈值 {ratio:.0%}——几何不可恢复，需 T3 导出"]
    return []


# ---------------------------------------------------------------- 图层映射（I-04）

LAYER_MAP_DEFAULT = {
    # AIA 标准 → 标准语义
    "WALL": "WALL",
    "WALL": "WALL",
    "DOOR": "DOOR",
    "WINDOW": "WINDOW",
    "TEXT": "TEXT",
    # 中文施工图 → 标准语义
    "墙体": "WALL",
    "过梁": "WALL",
    "门窗": "DOOR",
    "HEADER": "WALL",
    "S-FOOTER": "IGNORE",
    "S-SLAB": "IGNORE",
    "S-STEM-WALL": "WALL",
    "FOOTPRINT": "IGNORE",
    "R-BEAM": "IGNORE",
}


def _map_layer(layer: str, layer_map: dict | None) -> str:
    """源图层 → 标准语义层（映射不存在时原样返回）。"""
    if not layer_map:
        layer_map = LAYER_MAP_DEFAULT
    return layer_map.get(layer, layer)


# ---------------------------------------------------------------- 主入口

def readback(path, grid_mm: float | None = None, layer_map: dict | None = None,
             units: str | None = None, min_wall_seg_mm: float | None = None,
             close_wall_gaps: bool = False,
             bbox: tuple | list | None = None) -> dict:
    """解析 archdxf 产 DXF → 气泡图/几何 JSON（V3 入口，V2 from_dxf 逻辑）。

    输出:version / source_dxf / grid_mm / outline_mm / nodes[] / edges[] /
    windows[] / doors[] / unparsed[]。nodes/edges 词表同 cad_draft.json。
    layer_map: 源图层 → 标准语义层（I-04），缺省用 LAYER_MAP_DEFAULT。
    units: None=自动检测（doc.units）/ "mm" / "inch"（×25.4 换算，R-01 适配）。
    grid_mm: None=自适应（图幅每边 ≤MAX_CELLS 算，2 的倍数增长）/ 显式值。
    bbox: (minx, miny, maxx, maxy) 可选——只处理范围内实体（多坐标系图过滤离群段，
        如 mall 幕墙负坐标镜像段）。

    升级（2026-08-15 T33b 校准驱动）：
    - 自适应栅格：大图不爆格数；- 输出坐标归一化（平移原点，min=0）；
    - 双线墙腔填实（平行线对 buffer）；- 碎线过滤（<300mm 孤立短线）。
    """
    # 代理实体前置检查（I-01）
    proxy_errs = check_proxy_entities(path)
    if proxy_errs:
        return {"error": "G1_rejected", "reasons": proxy_errs}

    global GRID_MM, MIN_WALL_SEG_MM
    if min_wall_seg_mm is not None:
        MIN_WALL_SEG_MM = float(min_wall_seg_mm)
    doc = ezdxf.readfile(Path(path))
    msp = doc.modelspace()

    # 单位换算（R-01 等：doc.units 声明 mm 但实际 inch）
    if units == "inch":
        from ezdxf.math import Matrix44
        scale = Matrix44.scale(25.4, 25.4, 1.0)
        for e in list(msp):
            try:
                e.transform(scale)
            except Exception:
                pass  # 不可缩放实体跳过

    (solids, barriers, fat_barriers, jambs, windows, texts, leafs, arcs,
     unparsed, wall_arcs) = _parse(msp, layer_map)

    # bbox 过滤：多坐标系图（mall 幕墙负坐标镜像段）只留主范围实体
    if bbox is not None:
        bx0, by0, bx1, by1 = (float(v) for v in bbox)
        solids = [s for s in solids
                  if s.bounds[0] >= bx0 and s.bounds[2] <= bx1
                  and s.bounds[1] >= by0 and s.bounds[3] <= by1]
        barriers = [s for s in barriers
                    if bx0 <= s[0][0] <= bx1 and bx0 <= s[1][0] <= bx1
                    and by0 <= s[0][1] <= by1 and by0 <= s[1][1] <= by1]
        fat_barriers = [s for s in fat_barriers
                        if bx0 <= s[0][0] <= bx1 and bx0 <= s[1][0] <= bx1
                        and by0 <= s[0][1] <= by1 and by0 <= s[1][1] <= by1]

    doors = _pair_doors(leafs, arcs, unparsed)
    # 门窗碰撞检测（details 后对账兜底）：用原始 leaf/arc 几何，只报真相交
    doorwin_issues = doorwin_collisions(leafs, arcs, windows)

    xs, ys = [], []

    def _finite(v):
        return v is not None and not math.isnan(v) and not math.isinf(v)

    for poly in solids:
        b = poly.bounds
        if all(_finite(v) for v in b):
            xs += [b[0], b[2]]; ys += [b[1], b[3]]
    for seg in barriers:
        if all(_finite(v) for v in (seg[0][0], seg[0][1], seg[1][0], seg[1][1])):
            xs += [seg[0][0], seg[1][0]]; ys += [seg[0][1], seg[1][1]]
    # 统一 NaN 防线（源头实体坐标异常兜底）
    xs = [v for v in xs if _finite(v)]
    ys = [v for v in ys if _finite(v)]
    if not xs:
        raise ValueError(f"{path}: 无任何墙体实体,无法反编译")
    # 自适应栅格（T33b）：显式 grid_mm 优先，否则按图幅算（每边 ≤MAX_CELLS）
    if grid_mm is not None:
        GRID_MM = float(grid_mm)
    else:
        GRID_MM = _adaptive_grid_mm(max(xs) - min(xs), max(ys) - min(ys))
    pad = 2.0 * GRID_MM
    grid = _Grid(min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)

    for poly in solids:
        b = poly.bounds
        if not all(math.isfinite(v) for v in b):
            continue  # 无效多边形（NaN 顶点）跳过
        prepped = prep(poly)
        r0, c0 = grid.cell_of(b[0], b[1])
        r1, c1 = grid.cell_of(b[2], b[3])
        for r in range(max(0, r0), min(grid.ny, r1 + 2)):
            for c in range(max(0, c0), min(grid.nx, c1 + 2)):
                if not grid.solid[r][c] and prepped.covers(Point(*grid.center(r, c))):
                    grid.solid[r][c] = True
    for seg in barriers:
        grid.mark_segment(*seg)
    for seg in fat_barriers:
        grid.mark_segment(*seg, fat=True)
    for d in doors:  # 门洞封口:分区在门处断开
        grid.mark_segment(d["hinge"], d["strike"])
    # 间隙闭合（升级）：主体墙段间开口（门/窗）补线——洪水不贯通
    # 默认关闭（archdxf 产墙闭合 + door 配对已封口）；真实图（墙段开口无门配对）显式开启
    if close_wall_gaps:
        # 只取墙轴向长边（墙厚短边不进间隙匹配——否则墙厚方向端点被误连）
        wall_axes = []
        for poly in solids:
            b = poly.bounds
            if not all(math.isfinite(v) for v in b):
                continue
            w, h = b[2] - b[0], b[3] - b[1]
            if w >= h:  # 水平墙段：上下两条轴向长边
                wall_axes += [((b[0], b[1]), (b[2], b[1])),
                              ((b[0], b[3]), (b[2], b[3]))]
            else:       # 垂直墙段：左右两条轴向长边
                wall_axes += [((b[0], b[1]), (b[0], b[3])),
                              ((b[2], b[1]), (b[2], b[3]))]
        wall_axes += barriers
        for p, q in _close_wall_gaps(wall_axes):
            grid.mark_segment(p, q)

    region_map, regions = grid.flood()
    exterior_ids = {i for i, rg in enumerate(regions) if rg["exterior"]}

    # 墙段输出(B 层对账 B3 用):自由格↔实体格的边界面,合并共线长段
    wall_unit_edges = []
    for r0 in range(grid.ny):
        for c0 in range(grid.nx):
            if grid.solid[r0][c0]:
                continue
            x0 = grid.minx + c0 * GRID_MM
            y0 = grid.miny + r0 * GRID_MM
            x1, y1 = x0 + GRID_MM, y0 + GRID_MM
            # 越界按非实体(否则外边界一圈被误判为墙)
            if grid.in_range(r0, c0 + 1) and grid.solid[r0][c0 + 1]:
                wall_unit_edges.append((x1, y0, x1, y1))
            if grid.in_range(r0, c0 - 1) and grid.solid[r0][c0 - 1]:
                wall_unit_edges.append((x0, y0, x0, y1))
            if grid.in_range(r0 + 1, c0) and grid.solid[r0 + 1][c0]:
                wall_unit_edges.append((x0, y1, x1, y1))
            if grid.in_range(r0 - 1, c0) and grid.solid[r0 - 1][c0]:
                wall_unit_edges.append((x0, y0, x1, y0))
    wall_segments = _merge_runs(wall_unit_edges)

    # 房间标注配对:面积文本向上找房名
    area_texts = [t for t in texts if AREA_RE.match(t["content"])]
    name_texts = [t for t in texts if not AREA_RE.match(t["content"])]
    labels, used_names = [], set()
    for at in sorted(area_texts, key=lambda t: (t["at"][1], t["at"][0])):
        ax, ay = at["at"]
        best, best_key = None, None
        for i, nt in enumerate(name_texts):
            if i in used_names:
                continue
            nx, ny = nt["at"]
            dy = ny - ay  # 房名在面积文本上方
            if abs(nx - ax) < 1500 and 0.8 * nt["height"] < dy < 2.2 * nt["height"]:
                key = (abs(nx - ax), dy)
                if best_key is None or key < best_key:
                    best, best_key = i, key
        if best is None:
            continue
        used_names.add(best)
        labels.append({"name": name_texts[best]["content"].lower(),
                       "at": name_texts[best]["at"],
                       "area_sqm": float(AREA_RE.match(at["content"]).group(1))})

    # 分区 → 节点
    region_node = {}
    nodes = []
    named = sorted(labels, key=lambda l: l["name"])
    for label in named:
        rid = _region_at(grid, region_map, *label["at"])
        if rid is None or rid in exterior_ids:
            continue
        region_node.setdefault(rid, []).append(label)
    seen_ids = {}
    for rid in sorted(region_node, key=lambda i: min(region_node[i], key=lambda l: l["name"])["name"]):
        rg = regions[rid]
        label_group = sorted(region_node[rid], key=lambda l: l["name"])
        cx = sum(grid.center(r, c)[0] for r, c in rg["cells"]) / len(rg["cells"])
        cy = sum(grid.center(r, c)[1] for r, c in rg["cells"]) / len(rg["cells"])
        area_geo = len(rg["cells"]) * GRID_MM * GRID_MM / 1e6
        main = label_group[0]
        base_id = re.sub(r"\s+", "_", main["name"])
        seen_ids[base_id] = seen_ids.get(base_id, 0) + 1
        node_id = base_id if seen_ids[base_id] == 1 else f"{base_id}_{seen_ids[base_id]}"
        nodes.append({
            "id": node_id,
            "type": base_id,
            "area_sqm": main["area_sqm"],
            "area_geo_sqm": round(area_geo, 2),
            "centroid_mm": [round(cx, 3), round(cy, 3)],
            "polygon_mm": _cells_to_polygon_mm(rg["cells"], grid),
            "region_id": rid,
            "_labels": label_group if len(label_group) > 1 else None,
            "_min_cell": min(rg["cells"]),
        })
    # 未标注的室内分区:诚实记录;剔除墙带夹层等栅格残渣(<0.25㎡)
    MIN_SPACE_CELLS = 100  # 0.25㎡ @50mm
    labeled_rids = set(region_node)
    interior_unlabeled = [i for i, rg in enumerate(regions)
                          if not rg["exterior"] and i not in labeled_rids
                          and len(rg["cells"]) >= MIN_SPACE_CELLS]
    interior_unlabeled.sort(key=lambda i: min(regions[i]["cells"]))
    for k, rid in enumerate(interior_unlabeled, 1):
        rg = regions[rid]
        cx = sum(grid.center(r, c)[0] for r, c in rg["cells"]) / len(rg["cells"])
        cy = sum(grid.center(r, c)[1] for r, c in rg["cells"]) / len(rg["cells"])
        nodes.append({
            "id": f"space_{k}", "type": "unlabeled", "area_sqm": None,
            "area_geo_sqm": round(len(rg["cells"]) * GRID_MM * GRID_MM / 1e6, 2),
            "centroid_mm": [round(cx, 3), round(cy, 3)],
            "polygon_mm": _cells_to_polygon_mm(rg["cells"], grid),
            "region_id": rid, "_labels": None, "_min_cell": min(rg["cells"]),
        })

    # 外轮廓:墙体实体 ∪ 室内分区格
    # 外轮廓:墙体实体 ∪ 室内分区格 ∪ 开洞补缺(jamb 对恢复被切除的墙带)
    def _plug(p1, p2):
        # jamb 横跨墙厚,与开洞走向垂直;按方向过滤,防止误配墙端短面线
        sx, sy = p2[0] - p1[0], p2[1] - p1[1]
        sl = math.hypot(sx, sy) or 1.0
        su, sv = sx / sl, sy / sl
        cands = []
        for j in jambs:
            jx, jy = j[1][0] - j[0][0], j[1][1] - j[0][1]
            jl = math.hypot(jx, jy) or 1.0
            if abs(jx * su + jy * sv) / jl <= 0.3:
                cands.append(j)
        ends = []
        for p in (p1, p2):
            best, best_d = None, 150.0
            for j in cands:
                d = min(math.hypot(j[0][0] - p[0], j[0][1] - p[1]),
                        math.hypot(j[1][0] - p[0], j[1][1] - p[1]))
                if d < best_d:
                    best, best_d = j, d
            if best is None:
                return None
            ends.append(best)
        return Polygon([ends[0][0], ends[0][1], ends[1][1], ends[1][0]])

    plugs = []
    for d in doors:
        plug = _plug(d["hinge"], d["strike"])
        if plug is not None:
            plugs.append(plug)
    for seg in windows:
        plug = _plug(seg[0], seg[1])
        if plug is not None:
            plugs.append(plug)

    interior_boxes = []
    for i, rg in enumerate(regions):
        if rg["exterior"]:
            continue
        for r, c in rg["cells"]:
            x0 = grid.minx + c * GRID_MM
            y0 = grid.miny + r * GRID_MM
            interior_boxes.append(box(x0, y0, x0 + GRID_MM, y0 + GRID_MM))
    # 防御性拓扑修复：大量 box union 可能触发 GEOS TopologyException
    # （side location conflict），逐级降级处理
    import logging
    _logger = logging.getLogger("dxfkit.readback")
    all_parts = sorted(solids, key=lambda p: p.bounds) + plugs + interior_boxes
    
    # 级别 1：直接 union
    try:
        footprint = unary_union(all_parts)
        if not footprint.is_valid:
            footprint = footprint.buffer(0)
    except Exception:
        _logger.warning("unary_union 失败，降级：interior_boxes buffer(0) 后合并")
        # 级别 2：先 buffer(0) 每个 box 再合并
        try:
            valid_boxes = [b.buffer(0) for b in interior_boxes if b.is_valid]
            valid_plugs = [p.buffer(0) for p in plugs if p.is_valid]
            footprint = unary_union(valid_boxes + valid_plugs + 
                                   [s for s in solids if s.is_valid])
            if not footprint.is_valid:
                footprint = footprint.buffer(0)
        except Exception:
            _logger.warning("分步合并也失败，降级：convex_hull")
            # 级别 3：用 interior_boxes 的 convex_hull（粗略但稳健）
            from shapely.geometry import MultiPoint
            all_coords = []
            for b in interior_boxes:
                all_coords.extend(list(b.exterior.coords))
            if all_coords:
                footprint = MultiPoint(all_coords).convex_hull
            else:
                # 级别 4：用 barriers bbox
                bxs = [s[0][0] for s in barriers] + [s[1][0] for s in barriers]
                bys = [s[0][1] for s in barriers] + [s[1][1] for s in barriers]
                from shapely.geometry import box as _box
                footprint = _box(min(bxs), min(bys), max(bxs), max(bys))
    if footprint.geom_type == "MultiPolygon":
        footprint = max(footprint.geoms, key=lambda p: p.area)
    elif footprint.geom_type == "GeometryCollection":
        # 斜墙/复杂分隔可能产生 GeometryCollection——取面积最大 polygon 成员
        candidates = []
        for g in footprint.geoms:
            if g.geom_type == "Polygon":
                candidates.append(g)
            elif g.geom_type == "MultiPolygon":
                candidates.extend(g.geoms)
        if not candidates:
            raise ValueError(f"{path}: 无法从解析结果构造外轮廓")
        footprint = max(candidates, key=lambda p: p.area)
    footprint = footprint.simplify(GRID_MM / 2, preserve_topology=True)
    from shapely import normalize
    outline = [
        [round(x, 3), round(y, 3)]
        for x, y in list(normalize(footprint).exterior.coords)[:-1]
    ]
    minx, miny, maxx, maxy = footprint.bounds

    def _cell_of_point(cx, cy):
        col = min(4, max(0, int((cx - minx) / (maxx - minx) * 5)))
        row = min(4, max(0, int((cy - miny) / (maxy - miny) * 5)))
        return f"{CELL_COLS[col]}{row + 1}"

    total_geo = sum(n["area_geo_sqm"] for n in nodes)
    for n in nodes:
        n["cell"] = _cell_of_point(*n["centroid_mm"])
        n["area_ratio"] = round(n["area_geo_sqm"] / total_geo, 4) if total_geo else None

    # 门边:开洞中点向两侧探测分区
    def _probe(mid, direction, sign):
        dx, dy = direction
        k = GRID_MM
        while k <= PROBE_MAX_MM:
            x = mid[0] + sign * dx * k
            y = mid[1] + sign * dy * k
            rid = _region_at(grid, region_map, x, y)
            if rid is not None:
                return rid
            k += GRID_MM
        return None

    rid_to_node = {n["region_id"]: n["id"] for n in nodes}
    edges, open_pairs = set(), set()
    for d in sorted(doors, key=lambda d: (d["hinge"], d["strike"])):
        hx, hy = d["hinge"]
        sx, sy = d["strike"]
        length = math.hypot(sx - hx, sy - hy) or 1.0
        along = ((sx - hx) / length, (sy - hy) / length)
        normal = (-along[1], along[0])
        mid = ((hx + sx) / 2, (hy + sy) / 2)
        ra = _probe(mid, normal, +1)
        rb = _probe(mid, normal, -1)
        if ra is None or rb is None or ra == rb:
            continue
        if ra in exterior_ids or rb in exterior_ids:
            inner = ra if rb in exterior_ids else rb
            name = rid_to_node.get(inner, f"region_{inner}")
            edges.add((name, "outside", "front_door"))
        else:
            a = rid_to_node.get(ra, f"region_{ra}")
            b = rid_to_node.get(rb, f"region_{rb}")
            edges.add(tuple(sorted((a, b))) + ("door",))
    # 开敞连通:同一分区多个房名
    for n in nodes:
        if n["_labels"]:
            ids = [n["id"]] if len(n["_labels"]) == 1 else None
    for rid, label_group in region_node.items():
        if len(label_group) > 1:
            names = sorted(re.sub(r"\s+", "_", l["name"]) for l in label_group)
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    open_pairs.add((names[i], names[j], "open"))
    edges |= open_pairs

    nodes_out = []
    for n in sorted(nodes, key=lambda n: n["id"]):
        nodes_out.append({
            "id": n["id"], "type": n["type"], "area_sqm": n["area_sqm"],
            "area_geo_sqm": n["area_geo_sqm"], "area_ratio": n["area_ratio"],
            "cell": n["cell"], "centroid_mm": n["centroid_mm"],
            "polygon_mm": n.get("polygon_mm"),
        })
    edges_out = [{"a": a, "b": b, "via": v}
                 for a, b, v in sorted(edges)]
    windows_out = [
        {"at": [round((s[0] + t[0]) / 2, 3), round((s[1] + t[1]) / 2, 3)],
         "width_mm": round(math.hypot(t[0] - s[0], t[1] - s[1]), 3)}
        for s, t in sorted(windows)
    ]
    doors_out = sorted(doors, key=lambda d: (d["hinge"], d["strike"]))
    unparsed.sort(key=lambda u: (u["layer"], u["entity"], u["at"]))

    # 坐标归一化（升级）：全部坐标平移原点（ox,oy）→ min = 0，防大坐标下游浮点问题
    ox, oy = grid.minx, grid.miny

    def _shift2(v):
        return [round(v[0] - ox, 3), round(v[1] - oy, 3)]

    def _shift_poly(verts):
        return [[round(v[0] - ox, 3), round(v[1] - oy, 3)] for v in verts]

    outline = _shift_poly(outline)
    for n in nodes_out:
        if "polygon_mm" in n:
            n["polygon_mm"] = _shift_poly(n["polygon_mm"])
        if "centroid_mm" in n:
            n["centroid_mm"] = _shift2(n["centroid_mm"])
    wall_segments = [[_shift2(s), _shift2(t)] for s, t in wall_segments]
    windows_out = [
        {"at": [round((s[0] + t[0]) / 2 - ox, 3), round((s[1] + t[1]) / 2 - oy, 3)],
         "width_mm": round(math.hypot(t[0] - s[0], t[1] - s[1]), 3)}
        for s, t in sorted(windows)
    ]
    doors_out = [
        {"hinge": _shift2(d["hinge"]), "strike": _shift2(d["strike"]),
         "at": _shift2(d.get("at", [d["hinge"][0] + ox, d["hinge"][1] + oy])),
         "width_mm": d["width_mm"]}
        for d in doors_out
    ]

    return {
        "version": 1,
        "source_dxf": Path(path).name,
        "grid_mm": GRID_MM,
        "outline_mm": outline,
        "nodes": nodes_out,
        "edges": edges_out,
        "windows": windows_out,
        "doors": [
            {"hinge": [round(v, 3) for v in d["hinge"]],
             "strike": [round(v, 3) for v in d["strike"]],
             "at": [round((d["hinge"][0] + d["strike"][0]) / 2, 3),
                    round((d["hinge"][1] + d["strike"][1]) / 2, 3)],
             "width_mm": d["width_mm"]}
            for d in doors_out
        ],
        "wall_segments": wall_segments,
        "wall_arcs": sorted(wall_arcs, key=lambda a: (a["center"], a["radius"])),
        "doorwin_issues": doorwin_issues,
        "unparsed": unparsed,
    }


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

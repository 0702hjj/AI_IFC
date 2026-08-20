"""readback_doors: 门扇/摆弧配对与门窗碰撞检测。

拆分自 readback.py（W-0049 文件行数门控）；对外契约仍由 dxfkit.readback 再导出。
"""

from __future__ import annotations

import math

from dxfkit import readback_state as _st


def _pair_doors(leafs, arcs, unparsed):
    """leaf LINE + swing ARC 配对:弧心=铰链,弧起点=门闩侧 → 开洞区间。"""
    doors, used = [], set()
    for cx, cy, r, a0, a1 in sorted(arcs):
        best, best_d = None, _st.GRID_MM
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


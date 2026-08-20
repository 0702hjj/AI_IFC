"""normalize_segments —— path/segment 展开 helpers（方向归一化/fillet/recess/projection/ring_edges）。

拆分自 normalize.py（W-0049 文件行数门控）；对外契约仍由 aiplan_tools.normalize 再导出。
"""

from __future__ import annotations

import math

from shapely.geometry import Polygon, Point


class NormalizeError(Exception):
    """翻译/展开错误（顶点非法/几何无效/依赖缺失）。结构化回喂模型。"""

    def __init__(self, error: str, at: str, **extra):
        self.error = {"error": error, "at": at, **extra}
        super().__init__(self.error["error"])


# ═══════════════════════ 方向归一化 ═══════════════════════

def _signed_area(verts: list[list[float]]) -> float:
    """顶点环有向面积（>0 = 逆时针 CCW，<0 = 顺时针 CW）。"""
    s = 0.0
    n = len(verts)
    for i in range(n):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return s / 2.0


def _normalize_ring_direction(verts: list[list[float]], ccw: bool) -> list[list[float]]:
    """环方向归一化：ccw=True 强制逆时针（外环），ccw=False 强制顺时针（孔洞）。

    模型不用记方向——normalize 自动反转到正确旋向。
    """
    is_ccw = _signed_area(verts) > 0
    if is_ccw != ccw:
        return [verts[0]] + list(reversed(verts[1:]))  # 反转（保持起点）
    return verts


# ═══════════════════════ fillet（顶点倒圆角，arc segment）═══════════════

def _fillet_at_vertex(pts: list[list[float]], k: int, radius_mm: float) -> tuple[list, dict] | None:
    """顶点 pts[k] 倒圆角 radius_mm（凸角向内倒圆）。返回 (new_pts, arc_ann) 或 None。"""
    n = len(pts)
    prev, curr, nxt = pts[(k - 1) % n], pts[k], pts[(k + 1) % n]
    d1 = (curr[0] - prev[0], curr[1] - prev[1])
    d2 = (nxt[0] - curr[0], nxt[1] - curr[1])
    len1, len2 = math.hypot(*d1), math.hypot(*d2)
    if len1 < 1e-9 or len2 < 1e-9:
        return None
    u1 = (d1[0] / len1, d1[1] / len1)
    u2 = (d2[0] / len2, d2[1] / len2)
    dot = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
    theta = math.acos(dot)
    half = (math.pi - theta) / 2
    if half <= 1e-6 or math.sin(half) < 1e-6:
        return None
    d = radius_mm / math.tan(half)
    if d >= len1 or d >= len2:
        return None
    t1 = [curr[0] - d * u1[0], curr[1] - d * u1[1]]
    t2 = [curr[0] + d * u2[0], curr[1] + d * u2[1]]
    bis = (u2[0] - u1[0], u2[1] - u1[1])
    blen = math.hypot(*bis)
    if blen < 1e-9:
        return None
    ubis = (bis[0] / blen, bis[1] / blen)
    poly = Polygon(pts)
    dist = radius_mm / math.sin(half)
    center = None
    for sign in (1, -1):
        cx = curr[0] + sign * dist * ubis[0]
        cy = curr[1] + sign * dist * ubis[1]
        if poly.covers(Point(cx, cy)):
            center = [cx, cy]
            break
    if center is None:
        cx = curr[0] + dist * ubis[0]
        cy = curr[1] + dist * ubis[1]
        center = [cx, cy]
    a0 = math.degrees(math.atan2(t1[1] - center[1], t1[0] - center[0]))
    a1 = math.degrees(math.atan2(t2[1] - center[1], t2[0] - center[0]))
    new_pts = pts[:k] + [t1, t2] + pts[k + 1:]
    arc = {"at": k, "center": center, "radius": float(radius_mm), "a0": a0, "a1": a1}
    return new_pts, arc


# ═══════════════════════ segment 展开（recess / projection）═══════════════

def _edge_outward_normal(p0: list[float], p1: list[float]) -> tuple[float, float]:
    """CCW 外环边 p0→p1 的外法向（右侧，指向外部），归一化。"""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return (0.0, 0.0)
    # CCW 外环：外法向 = 边方向右转 90° = (dy, -dx)
    return (dy / length, -dx / length)


def _normal_to_direction(nx: float, ny: float) -> str:
    """外法向 → 方位（N/S/E/W 主方位）。"""
    if abs(nx) > abs(ny):
        return "E" if nx > 0 else "W"
    return "N" if ny > 0 else "S"


def _find_edge(pts: list[list[float]], direction: str) -> int | None:
    """找外法向方位为 direction 的边的下标（边 i = pts[i]→pts[i+1]）。返回第一个匹配的。"""
    n = len(pts)
    for i in range(n):
        p0, p1 = pts[i], pts[(i + 1) % n]
        nx, ny = _edge_outward_normal(p0, p1)
        if _normal_to_direction(nx, ny) == direction:
            return i
    return None


def _expand_recess_projection(pts: list[list[float]], seg: dict) -> list[list[float]]:
    """单个 recess/projection 在 at_edge 边 offset_m 处展开（供内部分组调用）。"""
    return _expand_segments_grouped(pts, [seg])


def _expand_segments_grouped(pts: list[list[float]], edge_segs: list[dict]) -> list[list[float]]:
    """按边分组，一次性展开所有 recess/projection segment（支持同边多处凹凸）。

    算法（用户拍板：多段 path 兼容性——同一边多个 segment 必须正确展开）：
    1. 在原始 pts 上识别每条边的方位（at_edge）
    2. 把 segment 按目标边分组
    3. 每条边内按 offset 排序，一次性展开该边的所有凹凸顶点
    4. 从后往前处理边（避免下标偏移）
    """
    if not edge_segs:
        return pts
    pts = [list(p) for p in pts]
    n = len(pts)

    # ① 识别原始 base 每条边的方位 + 几何
    #    edges[i] = {dir, p0, p1, len, ux, uy, nx, ny}
    edges = []
    for i in range(n):
        p0, p1 = pts[i], pts[(i + 1) % n]
        nx, ny = _edge_outward_normal(p0, p1)
        direction = _normal_to_direction(nx, ny)
        elen = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if elen < 1e-9:
            continue
        ux, uy = (p1[0] - p0[0]) / elen, (p1[1] - p0[1]) / elen
        edges.append({"idx": i, "dir": direction, "p0": p0, "p1": p1,
                      "len": elen, "ux": ux, "uy": uy, "nx": nx, "ny": ny})

    # ② 按目标边分组 segment（同方位多边时，按 offset 落到正确的边——用区间匹配）
    #    简化：每个 segment 找"该方位且能容纳 offset+width 的边"；同方位多条边时选可容纳的
    #    同边 segment 间重叠自检：offset+width 区间必须互不重叠（重叠 → 展开后自交）
    edge_groups: dict[int, list[dict]] = {}
    for seg in edge_segs:
        direction = seg["at_edge"]
        offset = seg["offset_m"] * 1000
        width = seg["width_m"] * 1000
        # 找该方位且能容纳 offset+width 的边
        target = None
        for e in edges:
            if e["dir"] == direction and offset + width <= e["len"] + 1e-6:
                target = e
                break
        if target is None:
            # 报更精确的错误：该方位没有足够长的边
            cands = [e for e in edges if e["dir"] == direction]
            if not cands:
                raise NormalizeError("segment_edge_not_found", "segments.at_edge", direction=direction)
            raise NormalizeError("segment_exceeds_edge", "segments",
                                 direction=direction, offset_m=seg["offset_m"], width_m=seg["width_m"],
                                 edge_len_m=round(max(e["len"] for e in cands) / 1000, 2))
        # 同边已挂 segment 区间重叠检查（先验——offset 未排序也能查）
        for exist in edge_groups.get(target["idx"], []):
            eo = exist["offset_m"] * 1000
            ew = exist["width_m"] * 1000
            if not (offset + width <= eo + 1e-6 or eo + ew <= offset + 1e-6):
                raise NormalizeError(
                    "segment_overlap", "segments",
                    direction=direction,
                    a={"offset_m": exist["offset_m"], "width_m": exist["width_m"]},
                    b={"offset_m": seg["offset_m"], "width_m": seg["width_m"]},
                    hint="同边 segments 区间重叠 → 展开后轮廓自交；请错开 offset 或收窄 width")
        edge_groups.setdefault(target["idx"], []).append(seg)

    # ③ 从后往前处理边（避免下标偏移），每边一次性展开该边所有凹凸
    for edge_idx in sorted(edge_groups.keys(), reverse=True):
        e = next(x for x in edges if x["idx"] == edge_idx)
        segs = sorted(edge_groups[edge_idx], key=lambda s: s["offset_m"])
        # 在该边上按 offset 依次展开多个凹凸
        inserts: list[list[float]] = []  # 该边要插入的凹凸顶点序列
        for seg in segs:
            offset = seg["offset_m"] * 1000
            width = seg["width_m"] * 1000
            depth = seg["depth_m"] * 1000
            sign = -1.0 if seg["type"] == "recess" else 1.0  # recess 向内 / projection 向外
            ux, uy, nx, ny = e["ux"], e["uy"], e["nx"], e["ny"]
            p0 = e["p0"]
            a = [p0[0] + ux * offset, p0[1] + uy * offset]
            b = [p0[0] + ux * (offset + width), p0[1] + uy * (offset + width)]
            a2 = [a[0] + sign * nx * depth, a[1] + sign * ny * depth]
            b2 = [b[0] + sign * nx * depth, b[1] + sign * ny * depth]
            inserts += [a, a2, b2, b]
        # 在该边位置插入凹凸顶点序列（替换原直边段 p0→p1 为 p0 + inserts + p1）
        # pts[edge_idx] = p0, pts[edge_idx+1] = p1 → 中间插入 inserts
        next_idx = (edge_idx + 1) % n
        if edge_idx < n - 1:
            pts = pts[:edge_idx + 1] + inserts + pts[next_idx:]
        else:
            # 最后一条边（绕回起点）：p0 是末顶点，p1 是首顶点
            pts = pts[:edge_idx + 1] + inserts
        n = len(pts)  # 更新顶点数（后续边在更前位置，下标不受影响——从后往前处理）

    return pts


# ═══════════════════════ path 展开（核心）═══════════════

def _expand_ring_path(ring_path: dict, is_outer: bool) -> dict:
    """ring_path（base + segments）→ {vertices, arcs}（完整顶点 + 弧标注）。

    1. base 顶点方向归一化（外环 CCW / 孔洞 CW）
    2. 展开 segments：recess/projection（凹凸顶点）+ arc（圆角）
    """
    base = [list(map(float, p)) for p in ring_path["base"]]
    if len(base) < 3:
        raise NormalizeError("base_too_few_vertices", "base", count=len(base))
    # 方向归一化：外环 CCW，孔洞 CW
    pts = _normalize_ring_direction(base, ccw=is_outer)

    arcs: list[dict] = []
    segments = ring_path.get("segments") or []
    # 展开顺序：先 arc（at_vertex 指 base 原始顶点下标），后 recess/projection（at_edge 找边方位，
    # 与顶点下标无关）——避免 recess 改顶点数导致 arc 下标错位。
    # ① arc（顶点倒圆角，at_vertex 在 base 原始顶点上做，从大到小防同类型下标偏移）
    arc_segs = [s for s in segments if s["type"] == "arc"]
    for seg in sorted(arc_segs, key=lambda s: -s["at_vertex"]):
        k = seg["at_vertex"]
        radius_mm = seg["radius_m"] * 1000
        if k < 0 or k >= len(pts):
            raise NormalizeError("arc_vertex_out_of_range", "segments.at_vertex", index=k, length=len(pts))
        res = _fillet_at_vertex(pts, k, radius_mm)
        if res is None:
            raise NormalizeError("arc_fillet_failed", "segments", index=k,
                                 reason="直线角/半径过大/几何无效")
        pts, arc = res
        # 本角 1 点变 2 点：已记录的 arc.at >= k 全部 +1，否则 densify 画错边自交
        for prev in arcs:
            if prev["at"] >= k:
                prev["at"] += 1
        arcs.append(arc)
    # ② recess/projection（凹凸，按边分组一次性展开——支持同边多处，多段 path 兼容性）
    edge_segs = [s for s in segments if s["type"] in ("recess", "projection")]
    pts = _expand_segments_grouped(pts, edge_segs)

    return {"vertices": pts, "arcs": sorted(arcs, key=lambda a: a["at"])}


def _edges_to_base(edges: dict) -> list[list[float]]:
    """四条边折线 → 闭合环顶点序列。

    拼合（逆时针 west→north→east→south），去掉重复角点：
    base = west + north[1:] + east[1:] + south[1:]
    """
    west = [list(p) for p in edges["west"]]
    north = [list(p) for p in edges["north"]]
    east = [list(p) for p in edges["east"]]
    south = [list(p) for p in edges["south"]]
    # 拼合：每条边去掉首顶点（=前一条边的末顶点=共享角点）
    base = west + north[1:] + east[1:] + south[1:]
    # south[-1] 与 west[0] 同为西南角——去掉闭合重复点，否则 at_vertex 下标错位
    if len(base) >= 2 and base[0] == base[-1]:
        base = base[:-1]
    return [[float(p[0]), float(p[1])] for p in base]


def _expand_ring_edges(ring_spec: dict, is_outer: bool) -> dict:
    """ring_edges（edges + segments）→ {vertices, arcs}（完整顶点 + 弧标注）。

    1. 四条边拼合成闭合环 base
    2. 复用 _expand_ring_path 展开 segments（recess/projection/arc）
    """
    edges = ring_spec["edges"]
    base = _edges_to_base(edges)
    # 构造 ring_path 格式，复用现有展开逻辑
    fake_ring_path = {"base": base, "segments": ring_spec.get("segments", [])}
    return _expand_ring_path(fake_ring_path, is_outer=is_outer)


def resolve_path(path: dict) -> list[dict]:
    """path → outline_mm ring 列表（与 plan.json outline_mm 格式对齐）。

    支持两种格式：
    - rings（分段折线，推荐）：四边拼合 + segments + holes，支持多分区
    - outer（完整环，兼容）：base + segments + holes

    返回: [{outer: {vertices, arcs}, holes: [...], arcs: []}, ...]
    """
    if "rings" in path:
        rings_out = []
        for ring_spec in path["rings"]:
            outer = _expand_ring_edges(ring_spec, is_outer=True)
            holes = [_expand_ring_edges(h, is_outer=False)
                     for h in (ring_spec.get("holes") or [])]
            # 校验：孔洞在外环内
            outer_poly = Polygon(outer["vertices"])
            for i, h in enumerate(holes):
                hp = Polygon(h["vertices"])
                if not outer_poly.covers(hp):
                    raise NormalizeError("hole_outside_outer", f"rings.holes[{i}]")
            rings_out.append({"outer": outer, "holes": holes, "arcs": []})
        return rings_out
    else:
        # 旧格式：outer + holes
        outer = _expand_ring_path(path["outer"], is_outer=True)
        holes = [_expand_ring_path(h, is_outer=False) for h in (path.get("holes") or [])]
        outer_poly = Polygon(outer["vertices"])
        for i, h in enumerate(holes):
            hp = Polygon(h["vertices"])
            if not outer_poly.covers(hp):
                raise NormalizeError("hole_outside_outer", f"path.holes[{i}]")
        return [{"outer": outer, "holes": holes, "arcs": []}]



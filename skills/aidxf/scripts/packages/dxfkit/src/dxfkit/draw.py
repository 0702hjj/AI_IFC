"""dxfkit/draw.py —— archdxf 画法工具箱封装（主 agent 逐构件调用）。

设计纪律（mission_parrallel §3A）：
- **不是 JSON→DXF 渲染器**——每函数 = 一个构件，主 agent 逐构件调用；
- 每函数返回实体 key（key 身份映射落盘，geo_cognition §2）；
- 墙体用墙线（非 HATCH）——由主 agent 传入墙轴线 + 厚，封装 wall_run/jamb/door。

沿墙定位（2026-08-12 修复：不规则墙的门窗定位）：
- wall_run 注册 `wall_key → WallFrame`（archdxf frames，s 沿墙/d 法向）；
- opening/door/window 用 wall_key + 沿墙距离（s）在 frame 内定位——
  支持水平/竖直/斜墙/多段 path 墙上的门窗（archdxf jamb_pair/door_leaf/window_line）。
  旧接口（传绝对坐标 at_center）保留兼容：wall_key 不在 registry 时按坐标画。
"""

from __future__ import annotations

import math

import ezdxf

from archdxf import annotate, fixtures, frames, layers, openings, stairs

# key 计数（每构件唯一）
_key_counter = [0]
# wall_key → WallFrame（沿墙定位用；draw_rooms_model 单次调用内有效）
_WALL_FRAMES: dict[str, frames.WallFrame] = {}


class _AsciiDrawing(ezdxf.document.Drawing):
    """AutoCAD 兼容文档。

    - 恒以 ASCII 编码存盘：非 ASCII 文本自动转 \\U+XXXX（AutoCAD 标准 unicode 转义）。
    - saveas 后自动 canonicalize（字节级确定性）。

    用法：new_doc() 返回的即此子类，主 agent 照旧 doc.saveas("floor.dxf")。
    """

    @property
    def output_encoding(self) -> str:
        return "ascii"

    def saveas(self, filename, encoding=None, fmt="asc") -> None:
        super().saveas(filename, encoding="ascii", fmt=fmt)
        from archdxf.canon import canonicalize_dxf
        canonicalize_dxf(str(filename))


def reset_keys() -> None:
    """重置 key 计数与墙 frame registry（新图纸/新调用前）。"""
    _key_counter[0] = 0
    _WALL_FRAMES.clear()


def new_doc(units: str = "mm") -> ezdxf.document.Drawing:
    """文档初始化封装（T25，AutoCAD 兼容）。

    V1 配方（archdxf 标准）：R2010 + setup + units + 图层表 + 标注样式。
    AutoCAD 兼容存盘：非 ASCII 文本自动转 \\U+XXXX；saveas 后自动 canonicalize。

    :param units: "mm" → ezdxf.units.MM（金例源图 units=4）；"ft" → FT
    :return: ezdxf.Drawing（已建图层表 + ARCHDXF 标注样式，恒 ASCII 存盘）
    """
    ezdxf.options.write_fixed_meta_data_for_testing = True  # 钉元数据（确定性）
    doc = ezdxf.new("R2010", setup=True)
    doc.__class__ = _AsciiDrawing  # 恒 ASCII 存盘（中文 → \U+XXXX）
    doc.units = ezdxf.units.MM if units == "mm" else ezdxf.units.FT
    layers.ensure_layers(doc, "floor")
    annotate.ensure_dimstyle(doc, text_height=450)
    return doc


def canonicalize(path) -> None:
    """确定性配方封装（T25）：CLASSES 段排序，字节级重现（金样验收项）。"""
    from archdxf.canon import canonicalize_dxf
    canonicalize_dxf(str(path))


def _next_key(prefix: str) -> str:
    _key_counter[0] += 1
    return f"{prefix}_{_key_counter[0]:04d}"


def _axis_wall(p0, p1, thickness: float) -> frames.WallFrame:
    """轴线 (p0,p1) + 厚 → WallFrame（s 沿轴线，d 向内部）。"""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy) or 1.0
    s_dir = (dx / length, dy / length)
    d_dir = (-s_dir[1], s_dir[0])  # 垂直于轴线
    half = thickness / 2
    # 轴线居中 → 墙 frame 的 d=0 在负侧
    ox = p0[0] - d_dir[0] * half
    oy = p0[1] - d_dir[1] * half
    return frames.WallFrame((ox, oy), s_dir, d_dir, length)


def wall_run(msp, p0, p1, thickness: float, cuts: list, hatch_span=None) -> str:
    """墙段（墙线 + 开洞切分）。p0/p1 = 墙轴线端点（mm）。

    :param cuts: [(s, w)] 开洞位置（沿轴线偏移 mm, 宽 mm）
    :return: wall key（已注册到沿墙定位 registry）
    """
    frame = _axis_wall(p0, p1, thickness)
    length = frame.length
    layer = "WALL"
    openings.wall_run(msp, frame, (0.0, length), thickness, cuts, layer,
                      hatch_span=hatch_span or (0.0, length))
    key = _next_key("wall")
    _WALL_FRAMES[key] = frame
    return key


def _resolve_wall_frame(wall_key: str) -> frames.WallFrame | None:
    """按 wall_key 查沿墙 frame（无则 None）。"""
    return _WALL_FRAMES.get(wall_key)


def opening(msp, wall_key: str, at_or_along, width_mm: float) -> str:
    """开洞（jamb 对）。

    :param wall_key: wall_run 返回的 key（registry 有且 at_or_along 为数字 →
        按沿墙距离 mm 定位；否则 at_or_along 为绝对坐标 [x,y]，旧接口兼容）
    :param at_or_along: 开洞沿墙距离（数字）或中心坐标（tuple/list）
    :return: opening key
    """
    frame = _resolve_wall_frame(wall_key)
    if frame is not None and not isinstance(at_or_along, (tuple, list)):
        s = float(at_or_along)
        openings.jamb_pair(msp, frame, s, width_mm, 0.0, "WALL")
    else:
        at_center = at_or_along
        msp.add_line(
            (at_center[0] - width_mm / 2, at_center[1] - 100),
            (at_center[0] - width_mm / 2, at_center[1] + 100),
            dxfattribs={"layer": "WALL"},
        )
        msp.add_line(
            (at_center[0] + width_mm / 2, at_center[1] - 100),
            (at_center[0] + width_mm / 2, at_center[1] + 100),
            dxfattribs={"layer": "WALL"},
        )
    return _next_key("open")


def door(msp, wall_key: str, open_key: str, at_or_along, width_mm: float,
         swing: str = "in-left") -> str:
    """门（leaf + swing arc），沿墙 frame 定位（任意墙方向）。

    :param wall_key: wall_run 返回的 key（registry 有 → at_or_along 为沿墙距离 mm；
        registry 无 → at_or_along 为铰链绝对坐标，旧接口兼容）
    :param at_or_along: 门沿墙起点距离或铰链坐标
    """
    frame = _resolve_wall_frame(wall_key)
    if frame is not None and not isinstance(at_or_along, (tuple, list)):
        s = float(at_or_along)
        openings.door_leaf(msp, frame, s, width_mm, swing, 0.0)
    else:
        hinge_at = at_or_along
        if swing == "in-left":
            leaf_end = (hinge_at[0] + width_mm, hinge_at[1])
            arc_end = 90.0
        else:
            leaf_end = (hinge_at[0] - width_mm, hinge_at[1])
            arc_end = 270.0
        msp.add_line(hinge_at, leaf_end, dxfattribs={"layer": "DOOR"})
        msp.add_arc(
            center=hinge_at, radius=width_mm, start_angle=0, end_angle=arc_end,
            dxfattribs={"layer": "DOOR"},
        )
    return _next_key("door")


def window(msp, wall_key: str, at_or_along, width_mm: float) -> str:
    """窗（window_line），沿墙 frame 定位（任意墙方向）。

    :param wall_key: wall_run 返回的 key（registry 有 → at_or_along 为沿墙距离 mm；
        registry 无 → at_or_along 为窗中心绝对坐标，旧接口兼容）
    """
    frame = _resolve_wall_frame(wall_key)
    if frame is not None and not isinstance(at_or_along, (tuple, list)):
        s = float(at_or_along)
        openings.window_line(msp, frame, s, width_mm, 0.0)
    else:
        at_center = at_or_along
        msp.add_line(
            (at_center[0] - width_mm / 2, at_center[1] - 80),
            (at_center[0] + width_mm / 2, at_center[1] - 80),
            dxfattribs={"layer": "WINDOW"},
        )
        msp.add_line(
            (at_center[0] - width_mm / 2, at_center[1] + 80),
            (at_center[0] + width_mm / 2, at_center[1] + 80),
            dxfattribs={"layer": "WINDOW"},
        )
    return _next_key("win")


def draw_stair(msp, at, size, run_width) -> str:
    """楼梯构件（archdxf stair 封装）。

    :param at: 楼梯起点 [x,y]
    :param size: (width, length) 楼梯宽与总长
    :param run_width: 梯段宽（保留参数，绘制用 width）
    """
    width, length = size
    stairs.draw_stair_flight(
        msp,
        at=tuple(at),
        length=length,
        width=run_width,
        tread=280.0,
        going="up",
    )
    return _next_key("stair")


def draw_landing(msp, at, *, width: float, depth: float) -> str:
    """楼梯平台（T25：双跑楼梯的平台段）。"""
    stairs.draw_landing(msp, at=tuple(at), width=width, depth=depth)
    return _next_key("landing")


def draw_fixture(msp, kind: str, at, rotation: float = 0, size=None) -> str:
    """洁具符号（T25：toilet/lavatory/bathtub/shower/…）。

    :param kind: fixtures.FIXTURE_TYPES（toilet/lavatory/bathtub/shower/kitchen-sink/…）
    :param at: 符号中心
    :param size: (w, d) 仅 counter 必填
    """
    fixtures.draw_fixture(msp, kind, at=tuple(at), rotation=rotation, size=size)
    return _next_key("fixt")


def partition_cap(msp, wall_key: str, at_or_along) -> str:
    """隔墙自由端封口（T25：端头不到其他墙时必画）。"""
    frame = _resolve_wall_frame(wall_key)
    if frame is not None and not isinstance(at_or_along, (tuple, list)):
        openings.partition_end_cap(msp, frame, float(at_or_along), 0.0, "WALL")
    else:
        p = at_or_along
        msp.add_line((p[0] - 60, p[1] - 60), (p[0] + 60, p[1] + 60),
                     dxfattribs={"layer": "WALL"})
    return _next_key("cap")


def draw_dim_chain(msp, wall_key: str, stations: list, angle: float = 0.0,
                   base=(0.0, -1500.0)) -> str:
    """尺寸链标注（T25：沿墙开洞链）。

    :param base: 标注线起点 (bx, by)（缺省墙起点法向下方 1500）
    """
    frame = _resolve_wall_frame(wall_key)
    if frame is not None:
        to_point = lambda s: frame.point(s, 0)
        annotate.dim_chain(msp, stations, to_point, angle=angle, base=base)
    return _next_key("dim")


def draw_tag(msp, mark: str, at, *, radius: float = 400, text_height: float = 300) -> str:
    """门窗编号圆标（T25：D1/W1 类）。"""
    annotate.add_tag(msp, mark, at, radius=radius, text_height=text_height,
                     layer="TEXT")
    return _next_key("tag")


def draw_leader(msp, text: str, tail, target, *, height: float = 300) -> str:
    """引线标注（T25：拥挤构件避让标注）。"""
    annotate.add_leader(msp, text, tail, target, height=height, layer="TEXT")
    return _next_key("leader")


def draw_north_arrow(msp, at, *, size: float = 800) -> str:
    """指北针（T25：有朝向才画）。"""
    annotate.north_arrow(msp, at, size=size, layer="TEXT")
    return _next_key("north")


def draw_title(msp, title: str, at, *, scale_label: str | None = None) -> str:
    """图题（T25：下划线标题 + 可选 SCALE 行）。"""
    annotate.view_title(msp, title, at, height=500, scale_label=scale_label,
                        layer="TEXT")
    return _next_key("title")


def draw_section_bubble(msp, name: str, sheet: str, center, direction=(0.0, 1.0)) -> str:
    """剖切符号（T25：split bubble + 实心三角）。

    :param direction: 剖切方向单位向量 (ux, uy)，缺省朝 +y
    """
    annotate.section_bubble(msp, name, sheet, tuple(center), tuple(direction),
                            radius=450, text_height=300, layer="SECTION")
    return _next_key("sect")


def draw_detector(msp, kind: str, at, *, radius: float = 300) -> str:
    """探测器符号（T25：smoke/co/combo）。"""
    annotate.detector_symbol(msp, kind, at, radius=radius, text_height=250)
    return _next_key("det")


def draw_column(msp, at, *, size: float = 700) -> str:
    """柱（T25：轴交点方块）。"""
    x, y = at
    msp.add_lwpolyline(
        [(x - size / 2, y - size / 2), (x + size / 2, y - size / 2),
         (x + size / 2, y + size / 2), (x - size / 2, y + size / 2)],
        close=True, dxfattribs={"layer": "COLUMN"})
    return _next_key("col")


def room_label(msp, name: str, at, area_sqm: float | None = None) -> str:
    """房间名 + 面积标注（readback 能读回——与 T20 闭环）。"""
    area_text = f"{area_sqm:.1f} M2" if area_sqm is not None else None
    annotate.room_label(msp, name, at, height=450, area=area_sqm,
                        area_text=area_text)
    return _next_key("label")


def draw_windows_from_rooms(msp, rooms: list[dict], window_w_mm: float = 1500.0) -> int:
    """房间多边形 + frontage → 外墙窗（T24，V2 windows refine 迁入简化版）。

    :return: 画出的窗数
    """
    count = 0
    for r in rooms:
        pm = r.get("polygon_mm")
        frontage = r.get("frontage")
        if not pm or not frontage:
            continue
        if "vertices" in pm:
            continue  # 异形房间窗位留主 agent 判断
        x0, x1 = pm.get("x") or [0, 0]
        y0, y1 = pm.get("y") or [0, 0]
        if frontage == "S":
            at = ((x0 + x1) / 2, y0)
            window(msp, "", at, window_w_mm)
            count += 1
        elif frontage == "N":
            at = ((x0 + x1) / 2, y1)
            window(msp, "", at, window_w_mm)
            count += 1
        elif frontage == "W":
            at = (x0, (y0 + y1) / 2)
            window(msp, "", at, window_w_mm)
            count += 1
        elif frontage == "E":
            at = (x1, (y0 + y1) / 2)
            window(msp, "", at, window_w_mm)
            count += 1
    return count


def draw_rooms_model(msp, model: dict) -> dict:
    """rooms 几何模型 → DXF（2026-08-11 统一 path 后入口）。

    - walls[]（axis_mm/path_mm/arc_mm + t_mm/kind）→ wall_run 画墙（注册 frame）
    - openings[]（挂 wall 索引 + along_m）→ 沿墙 frame 定位开口/门/窗
      （2026-08-12：沿墙定位修复——任意方向墙/多段 path 墙/弧墙的门窗不再画错位）
    - rooms[].placemark（stair/elevator/shaft）→ draw_stair/占位标记

    返回 {wall_keys, opening_keys, placemark_keys} 供 reconcile/回读对账。
    """
    import math as _math

    reset_keys()
    keys = {"walls": [], "openings": [], "placemarks": []}
    wall_keys_by_idx: dict[int, str] = {}

    # ① 画墙（先画墙，门窗挂墙）
    for wi, w in enumerate(model.get("walls") or []):
        t_mm = float(w.get("t_mm") or (200 if w.get("kind") == "ext" else 120))
        key = None
        if "axis_mm" in w:
            p0, p1 = w["axis_mm"][0], w["axis_mm"][1]
            key = wall_run(msp, tuple(p0), tuple(p1), t_mm, [])
        elif "path_mm" in w:
            pts = w["path_mm"]
            for i in range(len(pts) - 1):
                key = wall_run(msp, tuple(pts[i]), tuple(pts[i + 1]), t_mm, [])
        elif "arc_mm" in w:
            arc = w["arc_mm"]
            cx, cy = arc["center"]
            r = arc["r_mm"]
            a0 = arc.get("a0", 0.0)
            a1 = arc.get("a1", 360.0)
            segs = max(1, int(abs(a1 - a0) / 12.0) + 1)
            prev = None
            for k in range(segs + 1):
                ang = _math.radians(a0 + (a1 - a0) * k / segs)
                pt = (cx + r * _math.cos(ang), cy + r * _math.sin(ang))
                if prev:
                    key = wall_run(msp, prev, pt, t_mm, [])
                prev = pt
        if key:
            wall_keys_by_idx[wi] = key
            keys["walls"].append(key)

    # ② 门窗（挂墙：along_m 沿墙起点距离 → frame 沿墙 s 定位）
    #    wall 是 path 多段墙时，wall_keys_by_idx 只记该墙最后一段的 key——
    #    沿墙定位用该段的 frame（沿墙距离从段起点计）。多段墙跨段门窗
    #    由主 agent 拆成单段墙声明（每段一个 wall 条目）。
    for op in model.get("openings") or []:
        wi = op.get("wall")
        if wi is None or wi not in wall_keys_by_idx:
            continue
        wall_key = wall_keys_by_idx[wi]
        w_mm = float(op.get("w_mm", 900))
        along_mm = float(op.get("along_m", 0.0)) * 1000.0  # along_m 是米 → mm
        typ = op.get("type", "door")
        if typ == "door":
            ok = opening(msp, wall_key, along_mm, w_mm)
            keys["openings"].append(door(msp, wall_key, ok, along_mm, w_mm))
        else:
            keys["openings"].append(window(msp, wall_key, along_mm, w_mm))

    # ③ placemark（stair/elevator/shaft 占位标记）
    for r in model.get("rooms") or []:
        pm = r.get("placemark")
        if not pm:
            continue
        poly = r.get("polygon_mm") or {}
        if "vertices" in poly and len(poly["vertices"]) >= 3:
            cx = sum(p[0] for p in poly["vertices"]) / len(poly["vertices"])
            cy = sum(p[1] for p in poly["vertices"]) / len(poly["vertices"])
        elif "x" in poly and "y" in poly:
            cx = (poly["x"][0] + poly["x"][1]) / 2
            cy = (poly["y"][0] + poly["y"][1]) / 2
        else:
            continue
        if pm.get("kind") == "stair":
            keys["placemarks"].append(draw_stair(msp, (cx, cy), (3000, 6000), 1000))
        else:
            k = _next_key("placemark")
            msp.add_lwpolyline(
                [(cx - 1200, cy - 1200), (cx + 1200, cy - 1200),
                 (cx + 1200, cy + 1200), (cx - 1200, cy + 1200), (cx - 1200, cy - 1200)],
                dxfattribs={"layer": "FIXTURE"})
            keys["placemarks"].append(k)
    return keys


# ---------------------------------------------------------------------------
# 波次 2（D37/D40）：DXF 分区轮廓底座
# ---------------------------------------------------------------------------

def draw_partition_base(msp, geom: dict) -> dict:
    """分区轮廓底座（D37/D40）：按 normalize 分区几何画底座 DXF。

    画法（WALL 层）：outline 外轮廓 + core 多边形 + corridor 外缘 + 切割线。
    底座 = 分区底图——房间/墙/门窗由主 agent 增量画。

    :param msp: modelspace
    :param geom: normalize 产出的 zones[0] 几何（outline/cores/corridor/cuts）
    :return: {"n_outline": int, "n_core": int, "n_corridor": int, "n_cut": int}
    """
    n_outline = 0
    for oblk in geom.get("outline") or []:
        verts = (oblk.get("outer") or {}).get("vertices") or []
        if len(verts) >= 3:
            msp.add_lwpolyline([tuple(p) for p in verts] + [tuple(verts[0])],
                               close=True, dxfattribs={"layer": "WALL"})
            n_outline += 1
        for hole in oblk.get("holes") or []:
            hverts = (hole.get("vertices")) or []
            if len(hverts) >= 3:
                msp.add_lwpolyline([tuple(p) for p in hverts] + [tuple(hverts[0])],
                                   close=True, dxfattribs={"layer": "WALL"})

    n_core = 0
    for c in geom.get("cores") or []:
        verts = (c.get("polygon_mm") or {}).get("vertices") or []
        if len(verts) >= 3:
            msp.add_lwpolyline([tuple(p) for p in verts] + [tuple(verts[0])],
                               close=True, dxfattribs={"layer": "WALL"})
            n_core += 1

    n_corridor = 0
    corridor = geom.get("corridor") or {}
    corr_pts = corridor.get("path_mm") or []
    if len(corr_pts) >= 3:
        msp.add_lwpolyline([tuple(p) for p in corr_pts] + [tuple(corr_pts[0])],
                           close=True, dxfattribs={"layer": "WALL"})
        n_corridor += 1

    n_cut = 0
    for cut in geom.get("cuts") or []:
        line = cut.get("line_mm") or []
        if len(line) >= 2:
            msp.add_line(tuple(line[0]), tuple(line[1]),
                         dxfattribs={"layer": "WALL"})
            n_cut += 1

    return {"n_outline": n_outline, "n_core": n_core,
            "n_corridor": n_corridor, "n_cut": n_cut}

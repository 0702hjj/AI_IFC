# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""render.json payload v2 builder (pure function, ezdxf).

前端只读预览的数据源（W-0039，spec 决策 3：entity-keyed JSON + Canvas 2D）：

- **schemaVersion 2**：``{"schemaVersion", "bounds", "layers", "entities",
  "unsupported"}``。实体带 XDATA 稳定 key（APPID ``AIDXF``，与 ScriptMap
  同源，经 ``dxf_diffing.entity_key`` 单点读取），前端选中即得 key。
- **坐标**：保留原始 DXF 坐标系，不做 screen 归一化（v1 的归一化是 CLI
  预览遗留，v2 交给前端变换）；数字一律 round 6。
- **LWPOLYLINE 炸开**：直线段 → LINE 条目，bulge 段 → ARC 条目（bulge→arc
  数学移植自 aidxfv v1 的 ``scripts/dxf/render_payload.py``——该文件已随
  v1 遗留版本退役删除），同 key
  多条目。ARC 角度制：``start_angle`` 归一化到 [0,360)，``end_angle`` =
  start + sweep（不归一化，sweep 可负/超 360）。
- **INSERT 展开一层**（范围裁决）：仅应用 translate + rotate + **等比正
  scale**；非等比或负 scale（镜像）不展开，记 ``unsupported`` 一条（INSERT
  本体仍入 entities，保住 key 契约）。块内嵌套 INSERT（第二层）不展开，
  同样进 unsupported。展开的子实体 ``key=None`` 且带 ``block`` 来源标记
  （块定义实体的 XDATA key 是块局部身份，不外泄以免冲破 key==map 契约）。
- **unsupported 明面化**：白名单外实体列入
  ``unsupported:[{type, handle, coords}]``，不静默丢。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import ezdxf

from . import dxf_diffing

SCHEMA_VERSION = 2

_PRECISION = 6
_EPS = 1e-9

# 可展开为几何条目的类型（INSERT 单独走块展开路径）。
_POINT_FIELDS = ("start", "end", "center", "insert")


def _num(value: float) -> float:
    rounded = round(float(value), _PRECISION)
    return 0.0 if abs(rounded) < _EPS else rounded


def _xy(point: Any) -> List[float]:
    return [_num(point[0]), _num(point[1])]


def _normalize_angle(angle_deg: float) -> float:
    value = math.fmod(angle_deg, 360.0)
    return value + 360.0 if value < 0.0 else value


def _arc_from_bulge(
    start: Tuple[float, float], end: Tuple[float, float], bulge: float
) -> Optional[Dict[str, Any]]:
    """bulge 段 → ARC 条目（数学移植自 v1 render_payload._arc_from_bulge_segment）。"""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    chord = math.hypot(dx, dy)
    if chord <= _EPS or abs(bulge) <= _EPS:
        return None
    included = 4.0 * math.atan(bulge)
    radius = (chord * (1.0 + bulge * bulge)) / (4.0 * abs(bulge))
    midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    left_normal = (-dy / chord, dx / chord)
    center_offset = (chord * (1.0 - bulge * bulge)) / (4.0 * bulge)
    center = (
        midpoint[0] + left_normal[0] * center_offset,
        midpoint[1] + left_normal[1] * center_offset,
    )
    start_angle = _normalize_angle(
        math.degrees(math.atan2(start[1] - center[1], start[0] - center[0]))
    )
    sweep = math.degrees(included)
    return {
        "type": "ARC",
        "center": _xy(center),
        "radius": _num(radius),
        "start_angle": _num(start_angle),
        "end_angle": _num(start_angle + sweep),
    }


def _lwpolyline_entries(entity: Any) -> Optional[List[Dict[str, Any]]]:
    """LWPOLYLINE 炸开为 LINE/ARC 段；不足 2 顶点 → None（调用方记 unsupported）。"""
    points = [
        (float(p[0]), float(p[1]), float(p[2]))
        for p in entity.get_points("xyb")
    ]
    if len(points) < 2:
        return None
    out: List[Dict[str, Any]] = []

    def add_segment(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> None:
        start, bulge = (a[0], a[1]), a[2]
        end = (b[0], b[1])
        if start == end:
            return
        if abs(bulge) > _EPS:
            arc = _arc_from_bulge(start, end, bulge)
            if arc is not None:
                out.append(arc)
            return
        out.append({"type": "LINE", "start": _xy(start), "end": _xy(end)})

    for a, b in zip(points, points[1:]):
        add_segment(a, b)
    if entity.closed:
        add_segment(points[-1], points[0])
    return out


def _geometry_entries(entity: Any) -> Optional[List[Dict[str, Any]]]:
    """已知类型 → 几何条目列表（LWPOLYLINE 多条）；未知类型 → None。

    INSERT 不在此列（走 _expand_insert 块展开路径）。
    """
    dxftype = entity.dxftype()
    dxf = entity.dxf
    if dxftype == "LINE":
        return [{"type": "LINE", "start": _xy(dxf.start), "end": _xy(dxf.end)}]
    if dxftype == "CIRCLE":
        return [{"type": "CIRCLE", "center": _xy(dxf.center),
                 "radius": _num(dxf.radius)}]
    if dxftype == "ARC":
        return [{"type": "ARC", "center": _xy(dxf.center),
                 "radius": _num(dxf.radius),
                 "start_angle": _num(dxf.start_angle),
                 "end_angle": _num(dxf.end_angle)}]
    if dxftype == "TEXT":
        return [{"type": "TEXT", "text": dxf.text, "insert": _xy(dxf.insert),
                 "height": _num(dxf.height)}]
    if dxftype == "MTEXT":
        return [{"type": "MTEXT", "text": entity.text,
                 "insert": _xy(dxf.insert)}]
    if dxftype == "LWPOLYLINE":
        return _lwpolyline_entries(entity)
    return None


def _common(entity: Any) -> Dict[str, Any]:
    dxf = entity.dxf
    return {
        "layer": str(dxf.layer),
        "color": int(dxf.color),
        "linetype": str(dxf.linetype),
    }


def _representative_coords(entity: Any) -> List[float]:
    """unsupported 条目的代表坐标：insert/start/center/location/首顶点，皆无 → []。"""
    dxf = entity.dxf
    for attr in ("insert", "start", "center", "location"):
        point = getattr(dxf, attr, None)
        if point is not None:
            return _xy(point)
    try:
        points = entity.get_points("xy")
        if points:
            return _xy(points[0])
    except Exception:
        pass
    return []


def _uniform_scale(entity: Any) -> Optional[float]:
    """等比正 scale → 该值；非等比/负 scale（镜像）→ None（不展开，记 unsupported）。"""
    xscale = float(entity.dxf.xscale)
    yscale = float(entity.dxf.yscale)
    if xscale <= 0.0 or yscale <= 0.0 or abs(xscale - yscale) > _EPS:
        return None
    return xscale


def _transform(
    entry: Dict[str, Any],
    cos_t: float,
    sin_t: float,
    scale: float,
    tx: float,
    ty: float,
    rotation: float,
) -> None:
    """块空间条目应用 INSERT 变换：scale → rotate → translate（原地改写）。"""
    for field in _POINT_FIELDS:
        point = entry.get(field)
        if point is None:
            continue
        x, y = point
        entry[field] = [
            _num(scale * (cos_t * x - sin_t * y) + tx),
            _num(scale * (sin_t * x + cos_t * y) + ty),
        ]
    if "radius" in entry:
        entry["radius"] = _num(entry["radius"] * scale)
    if "height" in entry:
        entry["height"] = _num(entry["height"] * scale)
    if "start_angle" in entry:
        entry["start_angle"] = _num(entry["start_angle"] + rotation)
    if "end_angle" in entry:
        entry["end_angle"] = _num(entry["end_angle"] + rotation)


def _expand_insert(
    doc: Any,
    entity: Any,
    scale: float,
    entities: List[Dict[str, Any]],
    unsupported: List[Dict[str, Any]],
) -> None:
    """INSERT 块内实体展开一层：子实体 key=None + block 来源标记，应用变换。

    嵌套 INSERT / 未知子类型 / 缺失块定义 → unsupported，不静默丢。
    """
    dxf = entity.dxf
    name = dxf.name
    try:
        block = doc.blocks.get(name)
    except KeyError:
        unsupported.append({"type": "INSERT", "handle": dxf.handle,
                            "coords": _xy(dxf.insert)})
        return
    rotation = float(dxf.rotation)
    radians = math.radians(rotation)
    cos_t, sin_t = math.cos(radians), math.sin(radians)
    tx, ty = float(dxf.insert.x), float(dxf.insert.y)
    for child in block:
        if child.dxftype() == "INSERT":
            unsupported.append({"type": "INSERT", "handle": child.dxf.handle,
                                "coords": _representative_coords(child)})
            continue
        geoms = _geometry_entries(child)
        if geoms is None:
            unsupported.append({"type": child.dxftype(),
                                "handle": child.dxf.handle,
                                "coords": _representative_coords(child)})
            continue
        for geom in geoms:
            entry = {"key": None, "block": name, **geom, **_common(child)}
            _transform(entry, cos_t, sin_t, scale, tx, ty, rotation)
            entities.append(entry)


def _angle_in_sweep(angle: float, start_angle: float, sweep: float) -> bool:
    abs_sweep = abs(sweep)
    if abs_sweep >= 360.0 - _EPS:
        return True
    if sweep >= 0.0:
        delta = (_normalize_angle(angle) - _normalize_angle(start_angle)) % 360.0
    else:
        delta = (_normalize_angle(start_angle) - _normalize_angle(angle)) % 360.0
    return delta <= abs_sweep + _EPS


def _entry_points(entry: Dict[str, Any]) -> List[Tuple[float, float]]:
    """条目 bounds 采样点：LINE 端点 / CIRCLE 盒角 / ARC 极值 / 其余 insert。"""
    entry_type = entry["type"]
    if entry_type == "LINE":
        return [tuple(entry["start"]), tuple(entry["end"])]
    if entry_type == "CIRCLE":
        cx, cy = entry["center"]
        r = entry["radius"]
        return [(cx - r, cy - r), (cx + r, cy + r)]
    if entry_type == "ARC":
        cx, cy = entry["center"]
        r = entry["radius"]
        start_angle = entry["start_angle"]
        sweep = entry["end_angle"] - start_angle
        angles = [start_angle, start_angle + sweep]
        angles.extend(
            candidate for candidate in (0.0, 90.0, 180.0, 270.0)
            if _angle_in_sweep(candidate, start_angle, sweep)
        )
        return [
            (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
            for a in angles
        ]
    point = entry.get("insert")
    return [tuple(point)] if point is not None else []


def _bounds(entities: List[Dict[str, Any]]) -> Optional[Dict[str, List[float]]]:
    xs: List[float] = []
    ys: List[float] = []
    for entry in entities:
        for x, y in _entry_points(entry):
            xs.append(x)
            ys.append(y)
    if not xs:
        return None
    return {"min": [_num(min(xs)), _num(min(ys))],
            "max": [_num(max(xs)), _num(max(ys))]}


def build_render_payload(dxf_path: str) -> Dict[str, Any]:
    """DXF 文件 → render payload v2（实体级 JSON，key 与 ScriptMap 同源）。"""
    doc = ezdxf.readfile(dxf_path)
    entities: List[Dict[str, Any]] = []
    unsupported: List[Dict[str, Any]] = []

    for entity in doc.modelspace():
        dxftype = entity.dxftype()
        if dxftype == "INSERT":
            dxf = entity.dxf
            scale = _uniform_scale(entity)
            entities.append({
                "key": dxf_diffing.entity_key(entity),
                "type": "INSERT",
                "name": dxf.name,
                "insert": _xy(dxf.insert),
                "rotation": _num(dxf.rotation),
                "scale": _num(scale if scale is not None else dxf.xscale),
                **_common(entity),
            })
            if scale is None:
                unsupported.append({"type": "INSERT", "handle": dxf.handle,
                                    "coords": _xy(dxf.insert)})
            else:
                _expand_insert(doc, entity, scale, entities, unsupported)
            continue
        geoms = _geometry_entries(entity)
        if geoms is None:
            unsupported.append({"type": dxftype, "handle": entity.dxf.handle,
                                "coords": _representative_coords(entity)})
            continue
        key = dxf_diffing.entity_key(entity)
        common = _common(entity)
        for geom in geoms:
            entities.append({"key": key, **geom, **common})

    layers = [
        {
            "name": str(layer.dxf.name),
            "color": int(layer.color),
            "linetype": str(layer.dxf.linetype),
        }
        for layer in doc.layers
    ]
    # 实体引用但未建表项的层（ezdxf 允许）：补默认定义（color 7 / CONTINUOUS），
    # 前端按名取层时不会落空。
    known = {layer["name"] for layer in layers}
    for entry in entities:
        if entry["layer"] not in known:
            known.add(entry["layer"])
            layers.append({"name": entry["layer"], "color": 7,
                           "linetype": "CONTINUOUS"})

    return {
        "schemaVersion": SCHEMA_VERSION,
        "bounds": _bounds(entities),
        "layers": layers,
        "entities": entities,
        "unsupported": unsupported,
    }

"""aiifc.consume_upstream —— 上游产物 → design.json 转换器（cad->ifc 消费上游路径）。

把 aidxf/aiplan 的上游产物归一成 aiifc 可消费的 design.json（DESIGN_JSON_SCHEMA 协议）：
  building.json（zones 记 modelId + site/standards）+ bim_supplement.json（屋顶/特殊结构/PSET）
  + 各 zone DXF（outline/core/墙/房间/门窗几何）
  → design.json（meta + frame{footprint,storeys,axis_grid,typical} + floors{walls,openings,slabs,stairs,roof}）

几何处理（用户定）：**精确几何直用**——DXF 是坐标级精确几何，直接映射成 design.json 的
墙 axis/洞口沿轴（不降级为近似语义；design.json 的 axis/footprint 接受精确坐标）。
"""

from __future__ import annotations

import json
from pathlib import Path


def consume_upstream(building_path: str, bim_path: str, dxf_dir: str) -> dict:
    """上游产物 → design.json。

    :param building_path: building.json 路径（aidxf deliver_building 产物，zones 记 modelId）
    :param bim_path: bim_supplement.json 路径（aiplan 产物，屋顶/特殊结构/PSET）
    :param dxf_dir: 各 zone DXF 目录（或工作区——经 zones[].modelId 对应的 DXF）
    :return: design.json dict（DESIGN_JSON_SCHEMA 协议）
    """
    building = json.loads(Path(building_path).read_text(encoding="utf-8"))
    bim = json.loads(Path(bim_path).read_text(encoding="utf-8"))

    design: dict = {
        "meta": _meta(building),
        "frame": _frame(building, Path(dxf_dir)),
        "floors": _floors(building, bim, Path(dxf_dir)),
    }
    return design


def _meta(building: dict) -> dict:
    """meta：units/modulus/name（project 名）。"""
    return {
        "units": "m",
        "modulus": 0.1,
        "name": building.get("project", "building"),
    }


def _frame(building: dict, dxf_dir: Path) -> dict:
    """frame：storeys（zones floors_from/to → 层高推导）+ typical（标准层）+ footprint（首层轮廓）。

    footprint 从首层 DXF outline 读（readback 的 outline_mm，精确几何直用，mm→m）——
    design_builder 要求 footprint ≥3 点闭合多边形。
    """
    storeys: dict[str, float] = {}
    zones = building.get("zones", [])
    default_height = 3.0
    for z in zones:
        f_from = int(z.get("floors_from", 1))
        f_to = int(z.get("floors_to", f_from))
        for f in range(f_from, f_to + 1):
            name = f"{f}F"
            if name not in storeys:
                storeys[name] = (f - 1) * default_height
    if not storeys:
        storeys = {"1F": 0.0}
    frame: dict = {"storeys": storeys}
    # footprint：首层 DXF outline（readback outline_mm，精确几何直用，mm→m）
    footprint = _footprint_from_dxf(zones, dxf_dir)
    if footprint:
        frame["footprint"] = footprint
    typical = _typical(zones)
    if typical:
        frame["typical"] = typical
    return frame


def _footprint_from_dxf(zones: list, dxf_dir: Path) -> list:
    """首层 DXF outline → footprint（精确几何直用，mm→m）。

    经 readback 读首层 zone 的 DXF outline_mm（多边形坐标 mm）→ m。DXF 缺/readback 失败 →
    空（调用方 design_builder 会报 footprint 缺失——P2 经 zones[].modelId 定位 DXF 后必达）。
    """
    if not zones:
        return []
    first = sorted(zones, key=lambda z: int(z.get("floors_from", 1)))[0]
    # DXF 定位：dxf_dir/<zone>.dxf（aidxf deliver 落 <floor>.dxf；P2 经 zones[].modelId 精确对）
    zone_name = first.get("zone", "")
    dxf_path = None
    for cand in (dxf_dir / f"{zone_name}.dxf", dxf_dir / "floor.dxf"):
        if cand.is_file():
            dxf_path = cand
            break
    if dxf_path is None:
        return []
    try:
        from dxfkit.readback import readback
        rb = readback(str(dxf_path))
        outline_mm = rb.get("outline_mm") or []
        return [[round(x / 1000.0, 3), round(y / 1000.0, 3)] for x, y in outline_mm]
    except Exception:  # noqa: BLE001 —— readback 失败 → 空（design_builder 报错提示）
        return []


def _typical(zones: list) -> dict:
    """标准层映射：typology 相同的连续楼层归一个 typical key。"""
    typical: dict[str, list] = {}
    for z in zones:
        typ = z.get("typology") or z.get("zone", "STD")
        f_from = int(z.get("floors_from", 1))
        f_to = int(z.get("floors_to", f_from))
        if f_to > f_from:  # 多层 → 标准层
            key = str(typ).upper()
            typical.setdefault(key, []).extend(f"{f}F" for f in range(f_from, f_to + 1))
    return typical


def _floors(building: dict, bim: dict, dxf_dir: Path) -> dict:
    """floors：每楼层 walls/openings/slabs/stairs/roof（DXF 精确几何直用 + bim 补充 roof/PSET）。

    【P2 细化】当前骨架：DXF 几何解析（outline/core/墙/房间/门窗 → walls/openings）留 P2
    完整实现（dxf_to_ifc_geometry 映射）；roof 从 bim_supplement 映射（屋顶/特殊结构）。
    """
    floors: dict = {}
    zones = building.get("zones", [])
    for z in zones:
        f_from = int(z.get("floors_from", 1))
        f_to = int(z.get("floors_to", f_from))
        for f in range(f_from, f_to + 1):
            name = f"{f}F"
            floors[name] = _floor_from_zone(z, f, bim, dxf_dir)
    return floors


def _floor_from_zone(zone: dict, floor_no: int, bim: dict, dxf_dir: Path) -> dict:
    """单楼层：walls/openings（DXF 精确几何）+ roof（bim 补充，仅顶层）。

    【P2 细化】DXF → walls/openings 的精确几何解析（outline/core/墙/房间/门窗 →
    axis/沿轴洞口）——当前骨架返回空墙/洞（P2 经 dxf_dir + zones[].modelId 读 DXF 解析填充）。
    """
    floor: dict = {"walls": [], "openings": [], "slabs": [], "stairs": []}
    # roof：bim_supplement 的屋顶/特殊结构 → 顶层 roof 字段（P2 经 bim 解析填充）
    roof = _roof_from_bim(bim, floor_no)
    if roof:
        floor["roof"] = roof
    return floor


def _roof_from_bim(bim: dict, floor_no: int) -> dict | None:
    """bim_supplement 的屋顶/特殊结构 → design.json roof（仅顶层；P2 细化映射）。"""
    roof = bim.get("roof") if isinstance(bim, dict) else None
    if roof:
        return roof
    return None

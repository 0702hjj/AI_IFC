"""readback_checks: 代理实体前置检查（I-01）与图层映射（I-04）。

拆分自 readback.py（W-0049 文件行数门控）；对外契约仍由 dxfkit.readback 再导出。
"""

from __future__ import annotations

from pathlib import Path

import ezdxf

from dxfkit.readback_state import PROXY_REJECT_RATIO


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




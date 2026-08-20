"""readback_state: readback 共享常量与可变栅格状态（GRID_MM/MIN_WALL_SEG_MM 由 readback() 按图校准）。

拆分自 readback.py（W-0049 文件行数门控）；对外契约仍由 dxfkit.readback 再导出。
"""

from __future__ import annotations

import re


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

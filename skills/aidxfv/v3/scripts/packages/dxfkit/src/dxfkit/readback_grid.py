"""readback_grid: 栅格洪水填充分区与单元格多边形化。

拆分自 readback.py（W-0049 文件行数门控）；对外契约仍由 dxfkit.readback 再导出。
"""

from __future__ import annotations

import math
from collections import deque

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from dxfkit import readback_state as _st


class _Grid:
    def __init__(self, minx, miny, maxx, maxy):
        self.minx, self.miny = minx, miny
        self.nx = int(math.ceil((maxx - minx) / _st.GRID_MM))
        self.ny = int(math.ceil((maxy - miny) / _st.GRID_MM))
        self.solid = [[False] * self.nx for _ in range(self.ny)]

    def cell_of(self, x, y):
        return int((y - self.miny) // _st.GRID_MM), int((x - self.minx) // _st.GRID_MM)

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
        steps = max(1, int(math.hypot(p2[0] - p1[0], p2[1] - p1[1]) / (_st.GRID_MM / 4)))
        for i in range(steps + 1):
            t = i / steps
            self.mark_point(p1[0] + (p2[0] - p1[0]) * t,
                            p1[1] + (p2[1] - p1[1]) * t, fat=fat)

    def center(self, r, c):
        return (self.minx + (c + 0.5) * _st.GRID_MM, self.miny + (r + 0.5) * _st.GRID_MM)

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
        x0 = grid.minx + c * _st.GRID_MM
        y0 = grid.miny + r * _st.GRID_MM
        boxes.append(box(x0, y0, x0 + _st.GRID_MM, y0 + _st.GRID_MM))
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
    union = union.simplify(_st.GRID_MM / 2, preserve_topology=True)
    coords = list(union.exterior.coords)
    if len(coords) < 4:
        return []
    return [[round(x, 2), round(y, 2)] for x, y in coords[:-1]]


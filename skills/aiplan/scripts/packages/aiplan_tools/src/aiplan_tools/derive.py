"""derive —— 派生事实层（P0 迁移：让设计有据可依）。

把地块 + 退线算成**设计事实清单**，喂给模型的第 2 轮（几何）设计——
让"南房面宽预算""暗区占比""地块长宽比"成为设计依据，而非凭印象猜测。

对应迁移文档 migration_to_v3_dsl.md §五 ④增强层 / §六 P0。
吸收 aidxfv3 floorgeom/derive.py 的设计（派生事实喂模型做设计依据）。

产出事实（纯计算，确定性）：
- aspect_ratio: 地块长宽比（外接框宽/深）—— 判定板式/塔式/方形的依据
- lot_area_sqm / buildable_area_sqm / buildable_ratio: 面积量级
- exposure_m{N,S,E,W}: 各方位可建边长度（采光面预算）—— 南房能排多长
- deep_zone_ratio: 暗区占比（离可建边界 >6m 的面积/可建面积）—— 暗区放非采光功能
- dominant_axes: 主边方向（'EW' 东西长边为主 / 'NS' 南北长边为主）—— 轴网锚定基准
- concave_corners: 凹角数（0=矩形凸形 / >0=L 形或异形）—— 异形地块判定
- bounding_box: 外接框 {w_mm, d_mm, minx, miny, maxx, maxy}
"""

from __future__ import annotations

import json
import math
import sys
from shapely.geometry import Polygon, LineString


# 典型采光进深（mm）——超过此距离离外墙的区域算"暗区"
DAYLIGHT_DEPTH_MM = 6000


def _polygon_from_points(points: list[list[float]]) -> Polygon:
    """顶点数组 → shapely Polygon（自动闭合）。"""
    if points and points[0] != points[-1]:
        points = points + [points[0]]
    return Polygon(points)


def _setback_polygon(lot: Polygon, setbacks: dict | None) -> Polygon:
    """地块按退线内缩 → 可建多边形。setbacks 键: front(N)/rear(S)/left(W)/right(E)。"""
    if setbacks is None:
        return lot
    minx, miny, maxx, maxy = lot.bounds
    # front=北(y大侧) / rear=南(y小侧) / left=西(x小侧) / right=东(x大侧)
    s_north = setbacks.get("front", 0)
    s_south = setbacks.get("rear", 0)
    s_west = setbacks.get("left", 0)
    s_east = setbacks.get("right", 0)
    inset = Polygon([
        (minx + s_west, miny + s_south),
        (maxx - s_east, miny + s_south),
        (maxx - s_east, maxy - s_north),
        (minx + s_west, maxy - s_north),
    ])
    result = lot.intersection(inset)
    return result if not result.is_empty else lot


def _exposure_by_direction(buildable: Polygon) -> dict[str, float]:
    """可建多边形各方位外边长度（mm）。方位: N/S/E/W（正方位 ±45° 扇区归并）。"""
    if buildable.is_empty:
        return {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0}
    coords = list(buildable.exterior.coords[:-1])  # 不含闭合点
    exposure = {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0}
    for i in range(len(coords)):
        x0, y0 = coords[i]
        x1, y1 = coords[(i + 1) % len(coords)]
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length == 0:
            continue
        # 边的法向量方向（向外）：判定边朝哪个方位
        # 用边的方向角分类（水平边→N/S，垂直边→E/W）
        angle = math.degrees(math.atan2(dy, dx))
        if -45 <= angle <= 45 or angle > 135 or angle < -135:
            # 近东西向边 → 朝 N 或 S（看 y 位置：y 大=N，y 小=S）
            mid_y = (y0 + y1) / 2
            cy = buildable.centroid.y
            exposure["N" if mid_y > cy else "S"] += length
        else:
            # 近南北向边 → 朝 E 或 W（看 x 位置）
            mid_x = (x0 + x1) / 2
            cx = buildable.centroid.x
            exposure["E" if mid_x > cx else "W"] += length
    return exposure


def _count_concave_corners(poly: Polygon) -> int:
    """多边形凹角数（内角 >180°）。0=凸形（矩形），>0=L 形或异形。"""
    if poly.is_empty or poly.geom_type != "Polygon":
        return 0
    coords = list(poly.exterior.coords[:-1])
    if len(coords) < 3:
        return 0
    concave = 0
    n = len(coords)
    signed_area = poly.area  # shapely 保证正向（CCW >0）
    for i in range(n):
        x0, y0 = coords[i]
        x1, y1 = coords[(i + 1) % n]
        x2, y2 = coords[(i + 2) % n]
        # 叉积判定凹凸（CCW 多边形：叉积 <0 = 凹角）
        cross = (x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1)
        if cross < 0:
            concave += 1
    return concave


def derive_facts(
    lot_polygon_mm: list[list[float]],
    setbacks_mm: dict | None = None,
) -> dict:
    """地块 + 退线 → 设计事实清单。

    参数:
        lot_polygon_mm: 地块顶点 [[x,y],...]（逆时针或顺时针）
        setbacks_mm: {front(北), rear(南), left(西), right(东)}，可选

    返回: 设计事实 dict（见模块 docstring）
    """
    lot = _polygon_from_points(lot_polygon_mm)
    if not lot.is_valid:
        lot = lot.buffer(0)  # 自修复

    # 退化输入防护（共线/空多边形 → area=0）→ 返回零值结构，不崩
    if lot.is_empty or lot.area <= 0:
        return {
            "aspect_ratio": 0.0,
            "bounding_box_mm": {"w": 0, "d": 0, "minx": 0, "miny": 0, "maxx": 0, "maxy": 0},
            "lot_area_sqm": 0.0,
            "buildable_area_sqm": 0.0,
            "buildable_ratio": 0.0,
            "exposure_m": {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0},
            "deep_zone_ratio": 0.0,
            "dominant_axes": "EW",
            "concave_corners": 0,
        }

    buildable = _setback_polygon(lot, setbacks_mm)

    minx, miny, maxx, maxy = lot.bounds
    w_mm = maxx - minx
    d_mm = maxy - miny
    aspect_ratio = round(w_mm / d_mm, 3) if d_mm > 0 else 0.0

    lot_area_sqm = round(lot.area / 1e6, 2)
    buildable_area_sqm = round(buildable.area / 1e6, 2)
    buildable_ratio = round(buildable.area / lot.area, 4) if lot.area > 0 else 0.0

    exposure = _exposure_by_direction(buildable)

    # 暗区：可建区域向内缩 DAYLIGHT_DEPTH_MM 后的面积占比
    if buildable.area > 0:
        inner = buildable.buffer(-DAYLIGHT_DEPTH_MM)
        deep_area = inner.area if not inner.is_empty else 0.0
        deep_zone_ratio = round(deep_area / buildable.area, 4)
    else:
        deep_zone_ratio = 0.0

    # 主边方向：宽 > 深 → 东西长边为主（EW）；深 > 宽 → 南北长边为主（NS）
    dominant_axes = "EW" if w_mm >= d_mm else "NS"

    concave = _count_concave_corners(lot)

    return {
        "aspect_ratio": aspect_ratio,
        "bounding_box_mm": {
            "w": round(w_mm), "d": round(d_mm),
            "minx": round(minx), "miny": round(miny),
            "maxx": round(maxx), "maxy": round(maxy),
        },
        "lot_area_sqm": lot_area_sqm,
        "buildable_area_sqm": buildable_area_sqm,
        "buildable_ratio": buildable_ratio,
        "exposure_m": {
            "N": round(exposure["N"] / 1000, 2),
            "S": round(exposure["S"] / 1000, 2),
            "E": round(exposure["E"] / 1000, 2),
            "W": round(exposure["W"] / 1000, 2),
        },
        "deep_zone_ratio": deep_zone_ratio,
        "dominant_axes": dominant_axes,
        "concave_corners": concave,
    }


def _main(argv: list[str]) -> int:
    import argparse
    p = argparse.ArgumentParser(description="aiplan derive: 地块+退线 → 设计事实清单")
    p.add_argument("--lot", required=True, help="lot_polygon_mm JSON [[x,y],...]")
    p.add_argument("--setbacks", help="setbacks_mm JSON {front,rear,left,right}")
    args = p.parse_args(argv)

    from aiplan_tools.json_arg import coerce_lot_points, load_json_arg

    lot = coerce_lot_points(load_json_arg(args.lot))
    sb = load_json_arg(args.setbacks) if args.setbacks else None
    facts = derive_facts(lot, sb)
    print(json.dumps(facts, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    return _main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))

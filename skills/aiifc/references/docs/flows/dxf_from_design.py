"""dxf_from_design.py — design JSON → 2D 平面图 DXF（plan 阶段可视化 / 交付物）。

定位: aiifc workflow 的第 ② 阶段。把 design JSON（或 design_builder 产出的
features.json）画成 2D 平面图 DXF：每层一个图层，画 footprint / 墙轴线 /
墙厚 / 门窗开口 / 楼梯占用。DXF 既用于前端 svg 预览，也是可交付的 2D 图纸。

用法:
  python dxf_from_design.py design.json -o plan.dxf
  python dxf_from_design.py design.json -o plan.dxf --storey "1F"
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import ezdxf

# 图层约定
LAYER_FOOTPRINT = "FOOTPRINT"
LAYER_WALL = "WALL"
LAYER_WALL_CENTER = "WALL_CENTER"
LAYER_OPENING = "OPENING"
LAYER_STAIR = "STAIR"
LAYER_LABEL = "LABEL"


def _load(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    # 接受 design JSON 或 features.json；识别方式：有 frame/floors → design；有 walls/storeys → features
    if "frame" in data and "floors" in data:
        from design_builder import normalize

        return normalize(data), "design"
    return data, "features"


def _segment_bbox(seg):
    return (min(seg[0][0], seg[1][0]), min(seg[0][1], seg[1][1]),
            max(seg[0][0], seg[1][0]), max(seg[0][1], seg[1][1]))


def _bbox_segments(segs):
    xs, ys = [], []
    for s in segs:
        for p in s:
            xs.append(p[0]); ys.append(p[1])
    return (min(xs), min(ys), max(xs), max(ys))


def _label_offset(doc, storey_name, bounds):
    """在楼层图右上角写楼层名标注。"""
    msp = doc.modelspace()
    x0, y0, x1, y1 = bounds
    msp.add_text(storey_name, dxfattribs={
        "layer": LAYER_LABEL, "height": (x1 - x0) * 0.02,
    }).set_placement((x1, y1 + (y1 - y0) * 0.03))


def generate(features: dict, storey_filter: str | None = None) -> ezdxf.document.Document:
    """由 features.json 生成 DXF 平面图。每层画一次，坐标单位 = 米（design JSON 单位）。"""
    doc = ezdxf.new(dxfversion="R2010", setup=True)
    msp = doc.modelspace()
    for layer in (LAYER_FOOTPRINT, LAYER_WALL, LAYER_WALL_CENTER,
                  LAYER_OPENING, LAYER_STAIR, LAYER_LABEL):
        doc.layers.add(layer)

    storeys = features.get("storeys", {})          # {"1F": 0.0, ...}
    footprint = features.get("footprint", [])      # [[x,y],...] 闭合
    walls = features.get("walls", [])              # [{storey, axis, t, kind}]
    openings = features.get("openings", [])        # [{storey, wall, along, w, h, type}]
    stairs = features.get("stairs", [])            # [{storey, at|shaft, type}]

    for storey_name in storeys:
        if storey_filter and storey_name != storey_filter:
            continue
        segs = []

        # footprint（闭合多边形）
        if footprint:
            msp.add_lwpolyline(footprint, close=True, dxfattribs={"layer": LAYER_FOOTPRINT})
            segs.append((footprint[0], footprint[-1]))
            segs.extend((footprint[i], footprint[i + 1]) for i in range(len(footprint) - 1))

        # 墙：中心线 + 双线（厚度）
        for w in walls:
            if w.get("storey") != storey_name:
                continue
            ax = w["axis"]; t = w.get("t", 0.2)
            for i in range(len(ax) - 1):
                (x1, y1), (x2, y2) = ax[i], ax[i + 1]
                msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": LAYER_WALL_CENTER})
                # 双线：垂直轴方向的 ±t/2 偏移
                dx, dy = x2 - x1, y2 - y1
                L = math.hypot(dx, dy) or 1.0
                nx, ny = -dy / L * t / 2, dx / L * t / 2
                msp.add_line((x1 + nx, y1 + ny), (x2 + nx, y2 + ny), dxfattribs={"layer": LAYER_WALL})
                msp.add_line((x1 - nx, y1 - ny), (x2 - nx, y2 - ny), dxfattribs={"layer": LAYER_WALL})
                segs.append(((x1 + nx, y1 + ny), (x2 + nx, y2 + ny)))
                segs.append(((x1 - nx, y1 - ny), (x2 - nx, y2 - ny)))

        # 门/窗开口：沿墙轴线用矩形打断（画 OPENING 层小矩形）
        # 需要知道每面墙的几何（start + phi）。features 里墙是展开后的 axis 段，
        # 这里简化：开口画在 host 墙轴上沿 start→start+w 的一段粗线。
        for op in openings:
            if op.get("storey") != storey_name:
                continue
            host = walls[op["wall"]]
            ax = host["axis"]
            (x1, y1), (x2, y2) = ax[0], ax[1]
            dx, dy = x2 - x1, y2 - y1
            L = math.hypot(dx, dy) or 1.0
            ux, uy = dx / L, dy / L
            nx, ny = -uy, ux  # 墙法向单位向量
            ht = host.get("t", 0.2) / 2
            start = op.get("along", 0.0)
            w = op.get("w", 1.0)
            ox1, oy1 = x1 + ux * start, y1 + uy * start
            ox2, oy2 = x1 + ux * (start + w), y1 + uy * (start + w)
            # jamb：跨墙厚的垂线（任意朝向墙均非零长）
            msp.add_line((ox1 - nx * ht, oy1 - ny * ht), (ox1 + nx * ht, oy1 + ny * ht),
                         dxfattribs={"layer": LAYER_OPENING})
            msp.add_line((ox2 - nx * ht, oy2 - ny * ht), (ox2 + nx * ht, oy2 + ny * ht),
                         dxfattribs={"layer": LAYER_OPENING})
            if op.get("type") == "door":
                # 门：弧线（1/4 圆），起始角随墙朝向
                a0 = math.degrees(math.atan2(uy, ux)) % 360
                msp.add_arc(center=(ox1, oy1), radius=w, start_angle=a0, end_angle=a0 + 90,
                            dxfattribs={"layer": LAYER_OPENING})
            segs.append(((ox1, oy1), (ox2, oy2)))
            segs.append(((ox1 - nx * ht, oy1 - ny * ht), (ox1 + nx * ht, oy1 + ny * ht)))

        # 楼梯：占用矩形（at 位置 或 shaft 矩形）
        for st in stairs:
            if st.get("storey") != storey_name:
                continue
            if "at" in st:
                at, size = st["at"], st.get("size", [2.0, 4.0])
                x, y = at[0] - size[0] / 2, at[1] - size[1] / 2
                msp.add_lwpolyline([(x, y), (x + size[0], y), (x + size[0], y + size[1]),
                                    (x, y + size[1])], close=True,
                                   dxfattribs={"layer": LAYER_STAIR})
            elif "shaft" in st:
                s = st["shaft"]  # {"x0","x1","y0","y1"} 坐标矩形（design_builder.normalize 输出）
                x0, x1 = s["x0"], s["x1"]
                y0, y1 = s["y0"], s["y1"]
                msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                                   dxfattribs={"layer": LAYER_STAIR})

        if segs:
            _label_offset(doc, storey_name, _bbox_segments(segs))

    return doc


def main():
    ap = argparse.ArgumentParser(description="design JSON → 2D 平面图 DXF")
    ap.add_argument("design", help="design.json 或 features.json 路径")
    ap.add_argument("-o", "--out", default="plan.dxf")
    ap.add_argument("--storey", default=None, help="只画某层（如 1F）")
    a = ap.parse_args()

    data, kind = _load(Path(a.design))
    doc = generate(data, storey_filter=a.storey)

    # 单位换算到 DXF（保留缩放因子便于 CAD 读图）
    # R2010 不原生支持单位缩放，这里直接缩放坐标更实用；但 DXF 无矩阵变换层，
    # 简化：输出米坐标，DXF 头标注 INSUNITS=6（m）。
    header = doc.header
    header["$INSUNITS"] = 6  # meters
    doc.saveas(a.out)
    print(f"DXF: {a.out} ({kind}, storeys={list(data.get('storeys', {}))})")


if __name__ == "__main__":
    main()

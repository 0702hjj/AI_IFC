"""area_breakdown —— 面积分块计算（area allocation，plan 的 wrapping 核心）。

plan 是 wrapping：整体轮廓 + 面积分块。本模块做确定性计算：
- zone 总面积：outline_mm 用 shoelace 公式（mm² → m²）
- 各 block 面积与占比：从 program 条目按 block 词分组汇总（area_sqm × count）
- 配比检查：block 总和 vs 总面积（interaction 确认 + 后台校验用）

block 词表：复用 building_type room_attrs（core/corridor/units…）+ type 特殊构件
（balcony/shop/atrium…），与 building_types/<type>.cases.json 的 ratio_standards 对齐。

纯函数，确定性。供 step-02 面积配比确认环节 + 后台校验调用。
"""

from __future__ import annotations

import json
from pathlib import Path

from aiplan_tools.json_arg import load_json_arg
from aiplan_tools.paths import BUILDING_TYPES


def _vertices_of(ring) -> list:
    """任意 ring 形态 → 顶点数组。

    接受：裸数组 / {vertices, arcs?} / {outer: ...} 里抽到的子对象。
    arcs 只影响真弧面积，本函数取折线顶点（与 v3 直边简写一致）。
    """
    if isinstance(ring, dict):
        return ring.get("vertices") or ring.get("outer") or []
    return ring or []


def _to_vertex_list(shape) -> list[list[float]]:
    """把轮廓表示归一为顶点数组（v3 多边形集合取 outer，v2 裸数组原样）。"""
    if isinstance(shape, dict):
        return _vertices_of(shape.get("outer") if "outer" in shape else shape)
    return shape


def polygon_area_m2(shape) -> float:
    """shoelace 公式算多边形面积（mm² → m²）。

    输入：
    - v2 裸顶点数组 [[x,y],...]
    - v3 多边形集合 {"outer": [[x,y],...] | {vertices,arcs?}, "holes": [...]}
    - normalize 产物列表 [{outer, holes, arcs}]（取第一块；多块相加）
    - normalize 顶层 {"zones":[{outline_mm:[...]}]}（取第一个 zone 的 outline）
    **v3 支持孔洞扣减**：shape 带 holes 时 outer 面积减各孔洞面积。
    """
    # normalize 顶层 / 单 zone 列表：递归拆到一块
    if isinstance(shape, dict) and "zones" in shape:
        zones = shape.get("zones") or []
        return sum(polygon_area_m2(z.get("outline_mm") or []) for z in zones)
    if isinstance(shape, list) and shape and isinstance(shape[0], dict) and "outer" in shape[0]:
        return sum(polygon_area_m2(block) for block in shape)

    if isinstance(shape, dict):
        outer = _vertices_of(shape.get("outer") if "outer" in shape else shape)
        s = abs(_shoelace(outer))
        for h in shape.get("holes", []) or []:
            s -= abs(_shoelace(_vertices_of(h)))
        return s / 2.0 / 1_000_000.0
    return abs(_shoelace(shape)) / 2.0 / 1_000_000.0


def _shoelace(vertices: list) -> float:
    """shoelace 双倍面积（mm²，未除 2）。"""
    n = len(vertices)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s


def load_standard(btype: str) -> dict | None:
    """加载 building_types/<type>.cases.json 的 ratio_standards（配比标准）。

    cases.json 结构：{type, ratio_standards, cases}（本 skill 自持事实源）。
    ratio_standards = [{block, ratio_range, 依据?, 必填?}]。
    无此文件返回 None。
    """
    p = BUILDING_TYPES / f"{btype}.cases.json"
    if not p.exists():
        return None
    doc = json.loads(p.read_text(encoding="utf-8"))
    return {"type": btype, "blocks": doc.get("ratio_standards", [])}


def block_area_sqm(program: list[dict], block: str) -> float:
    """program 里属于 block 的条目面积合计（area_sqm × count）。

    block 匹配：
    - 精确：room == block
    - 前缀聚合（含去复数）：units 匹配 unit_3br（units→unit_ 前缀）、
      shop 匹配 shop_*、open_office 匹配 open_office_*
    无 area_sqm 的条目（如 corridor 只给 min_width）不算面积。
    """
    # 前缀聚合词：block 去末尾 's' 得单数前缀（units→unit_）
    agg_prefixes = {block + "_", block + "."}
    if block.endswith("s") and len(block) > 1:
        agg_prefixes.add(block[:-1] + "_")
        agg_prefixes.add(block[:-1] + ".")
    total = 0.0
    for item in program or []:
        room = item.get("room", "")
        if room != block and not any(room.startswith(p) for p in agg_prefixes):
            continue
        area = item.get("area_sqm")
        count = item.get("count", 1)
        if isinstance(area, list) and len(area) == 2:
            # 区间取中值
            area_val = (area[0] + area[1]) / 2.0
        elif isinstance(area, (int, float)):
            area_val = area
        else:
            continue
        cnt = count[1] if isinstance(count, list) else count
        total += area_val * cnt
    return total


def breakdown(program: list[dict], btype: str) -> dict:
    """计算面积分块：{blocks: [{block, area_sqm, ratio}], total_block_sqm}。

    按 cases.json ratio_standards 的 block 词表分组；无标准文件时用 program 的
    大类词（core/corridor）自动提取。
    """
    std = load_standard(btype)
    block_words = [b["block"] for b in std["blocks"]] if std else ["core", "corridor"]
    blocks = []
    for bw in block_words:
        a = block_area_sqm(program or [], bw)
        blocks.append({"block": bw, "area_sqm": round(a, 1)})
    total = sum(b["area_sqm"] for b in blocks)
    # ratio 相对 block 合计（block 合计 vs zone 总面积的配比检查由调用方做）
    for b in blocks:
        b["ratio"] = round(b["area_sqm"] / total, 4) if total else 0.0
    return {"blocks": blocks, "total_block_sqm": round(total, 1)}


def check_allocation(zone_total_m2: float, blocks: list[dict]) -> list[str]:
    """配比检查：block 合计 vs zone 总面积。返回违规列表（空=通过）。

    - 合计超总面积 → 报（面积分块不可超 wrapping）
    - 合计远小于总面积（<80%）→ 报（有大块面积未分块）
    """
    errs = []
    block_total = sum(b["area_sqm"] for b in blocks)
    if zone_total_m2 <= 0:
        return ["zone 总面积 ≤ 0，无法配比"]
    if block_total > zone_total_m2 * 1.01:  # 1% 容差
        errs.append(f"block 合计 {block_total:.0f}㎡ 超 zone 总面积 {zone_total_m2:.0f}㎡")
    if block_total < zone_total_m2 * 0.8:
        errs.append(f"block 合计 {block_total:.0f}㎡ 仅占 zone 总面积 {zone_total_m2:.0f}㎡ 的 "
                    f"{block_total/zone_total_m2*100:.0f}%（<80%，有大块面积未分块）")
    return errs


def summarize(zone_allocations: list[dict]) -> dict:
    """跨 zone 汇总视图（bim_supplement.area_allocation 的生成源）。

    输入：多个 zone 的 area_allocation（plan.json zones[].area_allocation 格式，
    含 {block, ratio, area_sqm?, source}）。
    输出：{total_area_sqm, blocks: [{block, ratio, area_sqm}]}——bim 汇总视图。
    同 block 跨 zone 合并：area_sqm 区间相加，ratio 按面积加权。
    """
    total_sqm = 0.0
    acc: dict[str, dict] = {}
    for za in zone_allocations or []:
        for b in za:
            blk = b["block"]
            a = b.get("area_sqm")
            if isinstance(a, list) and len(a) == 2:
                lo, hi = a
            elif isinstance(a, (int, float)):
                lo = hi = float(a)
            else:
                # 无 area_sqm：用 ratio × zone 总面积（调用方应已填 area_sqm）
                continue
            if blk not in acc:
                acc[blk] = {"lo": 0.0, "hi": 0.0}
            acc[blk]["lo"] += lo
            acc[blk]["hi"] += hi
            total_sqm += (lo + hi) / 2.0

    blocks = []
    for blk in sorted(acc):
        lo, hi = acc[blk]["lo"], acc[blk]["hi"]
        mid = (lo + hi) / 2.0
        ratio = round(mid / total_sqm, 4) if total_sqm else 0.0
        blocks.append({"block": blk, "ratio": [round(lo / total_sqm, 4) if total_sqm else 0.0,
                                              round(hi / total_sqm, 4) if total_sqm else 0.0],
                       "area_sqm": [round(lo, 1), round(hi, 1)]})
    return {"total_area_sqm": round(total_sqm, 1), "blocks": blocks}


def _main(argv: list[str]) -> int:
    """CLI：aiplan area <outline> <program> [btype]

    outline / program 均可为文件路径或内联 JSON。
    outline 接受裸顶点、v3 块、normalize 产物 {zones:[...]} / [{outer:{vertices}}]。
    """
    if len(argv) < 3:
        print("用法: aiplan area <outline JSON|文件> <program JSON|文件> [btype]", flush=True)
        return 2
    outline = load_json_arg(argv[1])
    program = load_json_arg(argv[2])
    btype = argv[3] if len(argv) > 3 else ""
    total = polygon_area_m2(outline)
    bd = breakdown(program, btype)
    print(f"zone 总面积: {total:.0f} ㎡")
    for b in bd["blocks"]:
        print(f"  {b['block']:12s} {b['area_sqm']:8.1f} ㎡  {b['ratio']*100:5.1f}%")
    errs = check_allocation(total, bd["blocks"])
    print("配比:", "OK" if not errs else "FAIL: " + "; ".join(errs))
    return 1 if errs else 0



def main() -> int:
    """console_scripts 无参入口（setuptools 调用）。"""
    import sys
    return _main(sys.argv[1:])

if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))

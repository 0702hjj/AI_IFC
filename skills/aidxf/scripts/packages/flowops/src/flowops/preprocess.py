"""flowops/preprocess.py —— S0 总装（T40 + T41）。

纪律（architecture / W4）：
- 无几何/画图逻辑（调 floorgeom/dxfkit/goldlib 三包）；
- plan schema 校验 + 轮廓级摄取校验 → FAIL 即停（T2 原样消费前提）；
- 楼层归并代表层（同构 covers）+ DAG 派生（vertical_relations）；
- zone 打包：geom 段 + 代表层切片 + vocab 裁剪 + 金例卡片指针。
"""

from __future__ import annotations

import json
from pathlib import Path

from flowops.validate import ValidationError, validate_plan
from floorgeom.check import check_alignment_zones, check_outline_plan
from floorgeom.derive import derive


# ---------------------------------------------------------------------------
# T40：楼层归并 + DAG
# ---------------------------------------------------------------------------

def _floor_list(floors_spec) -> list[int]:
    if floors_spec is None:
        return [1]
    if isinstance(floors_spec, dict):
        return list(range(floors_spec.get("from", 1), floors_spec.get("to", 1) + 1))
    if isinstance(floors_spec, list):
        return floors_spec
    return [1]


def merge_representative_floors(plan: dict) -> dict:
    """zone.floors 归并代表层（同构 covers）。"""
    out = {}
    for z in plan.get("zones", []):
        floors = _floor_list(z.get("floors"))
        rep = f"f{floors[0]}"
        out[z["id"]] = {
            "zone": z["id"],
            "function": z.get("function"),
            "representative": rep,
            "covers": [f"f{i}" for i in floors],
            "floor_height_mm": z.get("floor_height_mm", 3000),
        }
    return out


def derive_dag(plan: dict) -> dict:
    """DAG 派生：节点 = 各 zone 代表层 mission；**边恒空**（异楼层 zone 无画图依赖）。

    2026-08-17 修正：position.on（塔楼落裙房）与 vertical_relations.core_continuous
    （核心筒贯穿裙房）是**几何/结构约束**（塔楼⊆裙房投影、核筒跨层对齐 R-06），
    由 normalize 落位 + check_alignment_zones / check_core_alignment 校验——
    **不是画图顺序依赖**。异楼层 zone（裙房 1~4F / 塔楼 5~20F）各自独立代表层、
    独立 mission，互不依赖，DAG 无边（线性逐 zone 推进的拓扑基础）。

    :return: {"nodes": [...], "edges": []}（node = <zone>.<stage>）
    """
    zones = plan.get("zones", [])
    nodes = [{"node": f"{z['id']}.rooms", "zone": z["id"], "stage": "rooms",
              "floor": f"f{_floor_list(z.get('floors'))[0]}",
              "covers": [f"f{i}" for i in _floor_list(z.get("floors"))]}
             for z in zones]
    return {"nodes": nodes, "edges": []}


# ---------------------------------------------------------------------------
# T41：zone 打包 + vocab 裁剪
# ---------------------------------------------------------------------------

def _crop_vocab(zone: dict) -> dict:
    """vocab 裁剪：按 zone.function 从 program 裁房间词汇/面积区间。"""
    return {
        "program": zone.get("program", []),
        "requirements": [],  # 本 zone 相关 requirements（plan 顶层按 subject 匹配）
    }


def _gold_card_ptrs(zone: dict) -> list[dict]:
    """金例卡片指针（top-2，指向 golden 案例路径）。"""
    # 简化：返回空指针（T41 真实金例查询在 W4 CLI 接入 gold query 后补）
    return []


def build_zone_pack(zone: dict, geom: dict, merged: dict) -> dict:
    """单 zone 打包：geom 段 + 代表层切片 + vocab 裁剪 + 金例卡片。"""
    rep_floor = merged["representative"]
    slice_data = {
        "outline_mm": zone.get("outline_mm", []),
        "core": zone.get("core"),
        "core_anchor_mm": zone.get("core_anchor_mm"),
        "program": zone.get("program", []),
        "requirements": [],
    }
    return {
        "zone": zone["id"],
        "function": zone.get("function"),
        "geom": geom,
        "floors": {rep_floor: slice_data},
        "covers": merged["covers"],
        "vocab": _crop_vocab(zone),
        "gold_cards": _gold_card_ptrs(zone),
    }


# ---------------------------------------------------------------------------
# D35：skeleton 底座机械生成
# ---------------------------------------------------------------------------

def build_skeleton_base(plan: dict) -> dict:
    """机械生成 skeleton 底座——outline/core anchor 从 plan 注入（坐标根基唯一）。

    底座只锁坐标事实，避免主 agent 重写坐标导致错位：
    - outline：plan outline_mm **原样搬运**（多块/真弧/孔洞，绝对坐标）；
    - core anchor：plan core_anchor_mm 锁死（T4 锚点锁死；数组→多核带 id，D31）；
    - frame：从 plan site 继承 origin/north_deg，units 固定 mm。

    主 agent 读底座后**全权填充修改**：axis_grid/typology/core.extent|path/
    corridor/main_partitions/special_openings——底座不做限制（D35 用户拍板）。

    :param plan: plan.json dict
    :return: skeleton 底座 dict（非完整 skeleton——缺 axis_grid/typology 等主 agent 决策项）
    """
    site = plan.get("site") or {}
    zones_base = []
    for z in plan.get("zones", []):
        anchor = z.get("core_anchor_mm")
        if anchor is None:
            core_base = None                      # G-01：core 可选
        elif anchor and isinstance(anchor[0], (list, tuple)):
            # 多核：数组 → core 数组带 id（D31，供 rooms adjacent_to:"core:<id>"）
            core_base = [{"id": f"c{i}", "anchor": [float(a[0]), float(a[1])]}
                         for i, a in enumerate(anchor)]
        else:
            core_base = {"anchor": [float(anchor[0]), float(anchor[1])]}
        zones_base.append({
            "zone": z["id"],
            "outline": z.get("outline_mm") or [],  # D34：坐标根基，机械搬运
            "core": core_base,                     # anchor 锁死；extent|path 主 agent 填
            "corridor": None,
            "main_partitions": [],
            "special_openings": [],
        })
    return {
        "frame": {
            "units": "mm",
            "origin": site.get("origin", "lot_southwest"),
            "north_deg": site.get("north_deg", 0),
            "modulus": 300,  # 缺省住宅模数——主 agent 全权可改
        },
        "zones": zones_base,
    }


# ---------------------------------------------------------------------------
# 总装
# ---------------------------------------------------------------------------

def preprocess(plan: dict, out_dir: str) -> dict:
    """S0 全量预处理：校验 + 派生 + 归并 + 打包 → derived/。

    :param plan: plan.json dict
    :param out_dir: derived/ 输出目录
    :return: {"floors.json": {...}, "zone_packs": [...]}
    :raises ValueError: plan schema 非法 / 轮廓级摄取 FAIL
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. plan schema 校验（T40-1）
    plan_errors = validate_plan(plan)
    if plan_errors:
        raise ValueError(f"plan schema FAIL: {plan_errors[:3]}")

    # 2. 轮廓级摄取校验（T40-2）
    outline_errors = check_outline_plan(plan)
    if outline_errors:
        raise ValueError(f"轮廓级摄取 FAIL: {outline_errors[:3]}")
    align_errors = check_alignment_zones(plan)
    if align_errors:
        raise ValueError(f"多 zone 对齐 FAIL: {align_errors[:3]}")

    # 3. 楼层归并 + DAG（T40-3/4）
    merged = merge_representative_floors(plan)
    dag = derive_dag(plan)

    # 4. 派生 + zone 打包（T41）
    derived = derive(plan)
    zone_packs = {}
    for z in plan.get("zones", []):
        zid = z["id"]
        rep = merged[zid]["representative"]
        geom = derived["floors"].get(rep, {})
        pack = build_zone_pack(z, geom, merged[zid])
        zone_packs[zid] = pack
        (out / f"{zid}.json").write_text(
            json.dumps(pack, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    floors_json = {
        "dag": dag,
        "zones": merged,
        "representative_floors": {zid: m["representative"] for zid, m in merged.items()},
    }
    (out / "floors.json").write_text(
        json.dumps(floors_json, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # 5. skeleton 底座（D35：outline/core anchor 机械注入，主 agent 全权填充）
    skeleton_base = build_skeleton_base(plan)
    (out / "skeleton_base.json").write_text(
        json.dumps(skeleton_base, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    return {"floors.json": floors_json, "zone_packs": zone_packs,
            "skeleton_base.json": skeleton_base}

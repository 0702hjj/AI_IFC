#!/usr/bin/env python3
"""金例 rooms.std.json 迁移工具（维护用，幂等可重跑）——restore D 方向落地。

目标形态（restore D：rooms 承接骨架分区，分区内分墙）：
- partitions：承接骨架分区（{组名: 分区引用}，词表 outline / block:<id> / corridor）
- walls/labels 坐标在骨架坐标系内（与 skeleton outline 对齐，不在原始 DXF 坐标）
- 不声明 openings（D44 剥离）

迁移规则（机器确定性）：
1. 坐标平移：readback 图（或墙图 bbox）→ 骨架 outline 对齐
   a. readback.outline_mm 与骨架 outline 顶点数相同 → 质心差（精确）
   b. 局部图（顶点数不同）→ 骨架 core 质心 − 墙图质心（core 锚）
   c. 无 readback outline → 墙图 bbox 质心 − 骨架 outline bbox 质心
2. 逐墙落区：墙段中点落在 corridor_zone → corridor；blocks 多边形 → block:<id>；
   否则 outline（大画布）
3. partitions 重写：{main: outline, ...} + 按落区聚合的分区组
4. labels at 同步平移
5. 落盘前 normalize_rooms 验证（FAIL 不落盘）
6. 幂等：重复跑字节一致

用法：
  python scripts/tools/migrate_golden_rooms.py [--dry-run] [type/case ...]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = SKILL_ROOT / "references" / "golden"

sys.path.insert(0, str(SKILL_ROOT / "scripts" / "packages" / "floorgeom" / "src"))
from floorgeom.normalize import normalize_skeleton, normalize_rooms  # noqa: E402


def _centroid(pts: list[list[float]]) -> list[float]:
    if not pts:
        return [0.0, 0.0]
    return [sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)]


def _wall_bbox(rooms: dict) -> tuple[float, float, float, float] | None:
    coords = [p for w in rooms.get("walls") or [] for p in (w.get("axis") or [])]
    if not coords:
        return None
    return (min(p[0] for p in coords), min(p[1] for p in coords),
            max(p[0] for p in coords), max(p[1] for p in coords))


def _shift_point(p, dx, dy):
    # 落盘坐标近似取整（金例坐标树无浮点）
    return [int(round(p[0] + dx)), int(round(p[1] + dy))]


def _shift_pts(pts, dx, dy):
    return [[int(round(p[0] + dx)), int(round(p[1] + dy))] for p in pts]


def _perimeter(pts) -> float:
    if len(pts) < 2:
        return 0.0
    return sum(math.hypot(pts[(i + 1) % len(pts)][0] - pts[i][0],
                          pts[(i + 1) % len(pts)][1] - pts[i][1])
               for i in range(len(pts)))


def _compute_shift(readback: dict, skeleton_model: dict, rooms: dict) -> tuple[float, float]:
    """平移量（墙图 → 骨架坐标系）。

    锚选（按可靠度）：
    1. readback outline 与骨架 outline **形状相似**（顶点数同 + 周长比 0.8~1.2）
       → 质心差（精确）
    2. 墙图 bbox 跨度与骨架接近（比 0.6~1.6 = 全层墙图）→ bbox 质心差
    3. 局部墙图（跨度 << 骨架且 core 存在）→ core 质心 − 墙图质心
    """
    zone = skeleton_model["zones"][0]
    out_blocks = zone.get("outline") or []
    outline_verts = []
    for oblk in out_blocks:
        verts = (oblk.get("outer") or {}).get("vertices") or []
        if verts:
            outline_verts = verts
            break
    if not outline_verts:
        return 0.0, 0.0
    oc = _centroid(outline_verts)
    o_perim = _perimeter(outline_verts)
    span_o = max(max(p[0] for p in outline_verts) - min(p[0] for p in outline_verts),
                 max(p[1] for p in outline_verts) - min(p[1] for p in outline_verts))

    rb_outline = (readback or {}).get("outline_mm") or []
    if rb_outline and len(rb_outline) == len(outline_verts):
        ratio = _perimeter(rb_outline) / o_perim if o_perim else 0.0
        if 0.8 <= ratio <= 1.2:
            rc = _centroid(rb_outline)
            return oc[0] - rc[0], oc[1] - rc[1]

    wb = _wall_bbox(rooms)
    if not wb:
        return 0.0, 0.0
    wc = [(wb[0] + wb[2]) / 2.0, (wb[1] + wb[3]) / 2.0]

    # 幂等保护：墙图中心已在骨架 outline 附近（<20% 跨度）→ 已迁移，不再平移
    # （凹形轮廓/局部墙图质心不完全重合——无此判定会每次跑都漂移）
    if span_o and math.hypot(wc[0] - oc[0], wc[1] - oc[1]) < span_o * 0.2:
        return 0.0, 0.0

    span_w = max(wb[2] - wb[0], wb[3] - wb[1])
    cores = zone.get("cores") or []
    if cores and span_o and span_w < span_o * 0.6:
        core_pts = (cores[0].get("polygon_mm") or {}).get("vertices") or []
        if core_pts:
            cc = _centroid(core_pts)
            return cc[0] - wc[0], cc[1] - wc[1]
    return oc[0] - wc[0], oc[1] - wc[1]


def _partition_of(zone: dict, pt: list[float]) -> str:
    """墙段落区 → 分区引用。corridor（带 holes）> 切段 seg:<n> > block:<id> > outline。

    seg = 大区被切割线切出的段（restore D：rooms 回退到小区域边界里分房间）。
    单段大区（无切割线）时 seg:0 = 整个大区——挂它还是 outline 等价，
    但有段时按段承接（逐级分担）。"""
    cz = zone.get("corridor_zone") or {}
    pm = cz.get("polygon_mm") or {}
    cverts = pm.get("vertices") or []
    if cverts and _point_in_poly(pt, cverts, pm.get("holes") or []):
        return "corridor"
    segs = zone.get("segments") or []
    if len(segs) > 1:
        for sg in segs:
            spm = sg.get("polygon_mm") or {}
            verts = spm.get("vertices") or []
            if verts and _point_in_poly(pt, verts, spm.get("holes") or []):
                return sg.get("id")
    for b in zone.get("blocks") or []:
        bpm = b.get("polygon_mm") or {}
        verts = bpm.get("vertices") or []
        if verts and _point_in_poly(pt, verts, bpm.get("holes") or []):
            return f"block:{b.get('id')}"
    return "outline"


def _point_in_poly(pt: list[float], verts: list[list[float]],
                   holes: list[list[list[float]]] | None = None) -> bool:
    from shapely.geometry import Point, Polygon
    if len(verts) < 3:
        return False
    return Polygon(verts, holes or []).covers(Point(pt))


def migrate_rooms(rooms: dict, skeleton_model: dict, readback: dict | None) -> dict:
    dx, dy = _compute_shift(readback, skeleton_model, rooms)
    zone = skeleton_model["zones"][0]

    out = dict(rooms)
    out["walls"] = [
        {**w, "axis": _shift_pts(w.get("axis") or [], dx, dy)}
        for w in (rooms.get("walls") or [])
    ]
    out["labels"] = [
        {**lab, **({"at": _shift_point(lab["at"], dx, dy)} if "at" in lab else {})}
        for lab in (rooms.get("labels") or [])
    ]
    # 落区分组
    groups: dict[str, str] = {}
    for w in out["walls"]:
        pts = w.get("axis") or []
        if len(pts) >= 2:
            mid = [(pts[0][0] + pts[-1][0]) / 2, (pts[0][1] + pts[-1][1]) / 2]
        else:
            continue
        ref = _partition_of(zone, mid)
        groups.setdefault(ref, 0)
        groups[ref] += 1
    # 组名：main=outline；其余用引用名
    parts: dict[str, str] = {}
    for ref, _n in sorted(groups.items(), key=lambda kv: -kv[1]):
        if ref == "outline":
            parts["main"] = "outline"
        else:
            parts[ref.replace(":", "_")] = ref
    out["partitions"] = parts
    out.pop("openings", None)  # D44 剥离
    return out


def _canon(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def run(cases: list[str], dry_run: bool) -> int:
    targets = []
    for case_dir in sorted(GOLDEN_DIR.glob("*/*")):
        rel = str(case_dir.relative_to(GOLDEN_DIR))
        if not list(case_dir.glob("rooms.*.json")):
            continue
        if not cases or any(c.rstrip("/") == rel or rel.endswith(c) for c in cases):
            targets.append(rel)

    n_ok = n_fail = 0
    for rel in targets:
        case_dir = GOLDEN_DIR / rel
        room_files = sorted(case_dir.glob("rooms.*.json"))
        rp = room_files[0]
        if len(room_files) > 1:
            print(f'注意 {rel}: 多个 rooms 文件 {[f.name for f in room_files]}，迁移 {rp.name}')
        rooms = json.loads(rp.read_text(encoding="utf-8"))
        skel = json.loads((case_dir / "skeleton.json").read_text(encoding="utf-8"))
        sm = normalize_skeleton(skel)
        rb_path = case_dir / "readback.json"
        readback = json.loads(rb_path.read_text(encoding="utf-8")) if rb_path.exists() else None
        before = _canon(rooms)
        try:
            new_rooms = migrate_rooms(json.loads(json.dumps(rooms)), sm, readback)
            normalize_rooms(new_rooms, sm)  # FAIL 不落盘
            parts = new_rooms.get("partitions") or {}
            detail = (f"partitions={list(parts.values())} walls={len(new_rooms.get('walls') or [])} "
                      f"{'幂等(无变更)' if before == _canon(new_rooms) else '有变更'}")
            if dry_run:
                print(f'OK   {rel:32} {detail} (dry-run)')
            else:
                rp.write_text(json.dumps(new_rooms, ensure_ascii=False, indent=1) + "\n",
                              encoding="utf-8")
                print(f'OK   {rel:32} {detail}')
            n_ok += 1
        except Exception as e:
            print(f'FAIL {rel:32} {type(e).__name__}: {str(e)[:100]}')
            n_fail += 1
    print(f"\n{n_ok} OK / {n_fail} FAIL" + ("（--dry-run 未落盘）" if dry_run else ""))
    return 0 if n_fail == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--dry-run", action="store_true", help="只验证不落盘")
    ap.add_argument("cases", nargs="*", help="案例路径（type/case），缺省全部")
    args = ap.parse_args()
    return run(args.cases, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())

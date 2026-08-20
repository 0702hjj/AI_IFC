#!/usr/bin/env python3
"""金例 skeleton 干净迁移工具（维护用，幂等可重跑）。

契约硬化（D42）后的唯一合法形态：
- zone 无 axis_grid（轴网派生，机器算）
- core: anchor + vertices（平铺顶点环，绝对坐标）| path ring_edges
- corridor: form="path" + path ring_edges（四边拼合）
- main_partitions: {id, role, from:{ref,edge?,at}, to:{ref,edge?,at}} 切割线锚定
- blocks: {id, role, between:[cut ids], side} 认领
- special_openings: {at:[x,y], reason}

上游锚：aiplan/references/golden/<type>/<case>/plan.json
（outline_mm / core.vertices / core_anchor_mm 是几何真值，双端对齐原则）

迁移规则（硬化后）：
1. outline/core 直接对齐上游 plan.json 真值（不是靠旧 axis_grid 换算）
2. corridor ring(around core) → core bbox 外扩 width 的矩形 ring_edges
   corridor path 开线（轴网索引）→ 丢弃（无法构成闭合环带）
3. main_partitions 轴网索引 path → 端点匹配 outline/core/corridor 边界 → 切割线锚定；
   锚定不了（退化线/越界/ref 不可用）→ 丢弃，不产绝对 path
4. blocks 旧 path → 丢弃（between 认领是切割产物，旧独立块无法反推）
5. 落盘前 normalize_skeleton 验证（FAIL 不落盘）
6. 幂等：重复跑字节一致（canon 键序）

用法：
  python scripts/tools/migrate_golden_skeleton.py            # 全部案例
  python scripts/tools/migrate_golden_skeleton.py --dry-run  # 只验证不落盘
  python scripts/tools/migrate_golden_skeleton.py hotel/hotel_std_01 ...  # 指定案例
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = SKILL_ROOT / "references" / "golden"
# 上游 plan 落盘（aiplan 技能，几何真值）
AIPLAN_GOLDEN = SKILL_ROOT.parent / "aiplan" / "references" / "golden"

sys.path.insert(0, str(SKILL_ROOT / "scripts" / "packages" / "floorgeom" / "src"))
from floorgeom.normalize import normalize_skeleton, _expand_ring_edges  # noqa: E402


# ---------------------------------------------------------------------------
# 几何小工具（零判断：纯确定性换算/匹配）
# ---------------------------------------------------------------------------

def _extent_to_vertices(ext: dict, grid: dict) -> list | None:
    """旧 extent（轴网索引区间）→ 绝对坐标矩形顶点。坏索引 → None。"""
    try:
        xs = sorted([grid["x"][int(ext["x"][0])], grid["x"][int(ext["x"][1])]])
        ys = sorted([grid["y"][int(ext["y"][0])], grid["y"][int(ext["y"][1])]])
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    return [[xs[0], ys[0]], [xs[1], ys[0]], [xs[1], ys[1]], [xs[0], ys[1]]]


def _pt_on_edge(pt: list, p0: list, p1: list, tol: float = 100.0) -> float | None:
    """点在线段上的参数 t（0..1）；偏离 > tol mm → None。"""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    d2 = dx * dx + dy * dy
    if d2 < 1e-6:
        return None
    cross = abs(dx * (pt[1] - p0[1]) - dy * (pt[0] - p0[0]))
    if cross * cross / d2 > tol * tol:
        return None
    t = ((pt[0] - p0[0]) * dx + (pt[1] - p0[1]) * dy) / d2
    if t < -0.01 or t > 1.01:
        return None
    return max(0.0, min(1.0, t))


def _outward_dir(p0: list, p1: list) -> str:
    """边外法向方位（CCW 环右法向 = (dy,-dx)）。"""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    nx, ny = dy, -dx
    if abs(nx) > abs(ny):
        return "E" if nx > 0 else "W"
    return "N" if ny > 0 else "S"


def _ring_edges_of_edges(points: list) -> list[tuple[list, list]]:
    """顶点环 → 边段（环闭合）。"""
    return [(points[i], points[(i + 1) % len(points)]) for i in range(len(points))]


def _anchor_point(pt: list, outline_edges, corridor_outer, cores) -> dict | None:
    """点 → 锚定（outline 边 / corridor:outer / core 环，按此优先级）。"""
    for ei, (p0, p1) in enumerate(outline_edges):
        at = _pt_on_edge(pt, p0, p1)
        if at is not None:
            return {"ref": f"outline:edge:{ei}", "at": round(at, 3)}
    if corridor_outer:
        for p0, p1 in _ring_edges_of_edges(corridor_outer):
            at = _pt_on_edge(pt, p0, p1)
            if at is not None:
                return {"ref": "corridor:outer",
                        "edge": _outward_dir(p0, p1), "at": round(at, 3)}
    for cid, ring in (cores or {}).items():
        for p0, p1 in _ring_edges_of_edges(ring):
            at = _pt_on_edge(pt, p0, p1)
            if at is not None:
                return {"ref": f"core:{cid}",
                        "edge": _outward_dir(p0, p1), "at": round(at, 3)}
    return None


def _rect_ring_edges(x0: float, y0: float, x1: float, y1: float) -> dict:
    """矩形 → ring_edges 四边拼合（west/north/east/south）。"""
    return {"edges": {
        "west": [[x0, y0], [x0, y1]],
        "north": [[x0, y1], [x1, y1]],
        "east": [[x1, y1], [x1, y0]],
        "south": [[x1, y0], [x0, y0]],
    }}


# ---------------------------------------------------------------------------
# 迁移主逻辑
# ---------------------------------------------------------------------------

def migrate_skeleton(skel: dict, plan: dict | None) -> dict:
    """迁移单个 skeleton（干净协议）。plan 为上游 aiplan plan.json 真值。"""
    z = skel["zones"][0]
    grid = {
        "x": [float(v) for v in ((z.get("axis_grid") or {}).get("x") or [])],
        "y": [float(v) for v in ((z.get("axis_grid") or {}).get("y") or [])],
    }

    # 1) outline / core 对齐上游 plan 真值（双端对齐）
    if plan is not None:
        pz = (plan.get("zones") or [{}])[0]
        outline_mm = pz.get("outline_mm")
        if outline_mm:
            z["outline"] = [{"outer": {"vertices": o["outer"]["vertices"]},
                             **({"holes": o["holes"]} if o.get("holes") else {})}
                            for o in outline_mm]
        core_plan = pz.get("core") or {}
        # 上游多 core：core 是 list，每元素自己的 vertices；单 core：dict
        core_plans = core_plan if isinstance(core_plan, list) else ([core_plan] if core_plan else [])
        anchor_mm = pz.get("core_anchor_mm")
        # 上游多 core：core_anchor_mm 是 [[x,y],...]（每 core 一个）；单 core：单个 [x,y]
        anchors = []
        if isinstance(anchor_mm, list) and anchor_mm and isinstance(anchor_mm[0], list):
            anchors = anchor_mm
        elif anchor_mm:
            anchors = [anchor_mm]
        if core_plans and isinstance(z.get("core"), list):
            for i, c in enumerate(z["core"]):
                cp = core_plans[min(i, len(core_plans) - 1)]
                if cp.get("vertices"):
                    c["vertices"] = cp["vertices"]
                if anchors:
                    c["anchor"] = anchors[min(i, len(anchors) - 1)]
        elif core_plans and z.get("core") is not None:
            cp = core_plans[0]
            if cp.get("vertices"):
                z["core"]["vertices"] = cp["vertices"]
            if anchors:
                z["core"]["anchor"] = anchors[0]

    # 2) core 归一（extent → vertices；嵌套 {vertices,arcs} → 平铺）
    cores: dict[str, list] = {}
    core = z.get("core")
    core_list = core if isinstance(core, list) else [core] if core else []
    for ci, c in enumerate(core_list):
        cid = c.get("id") or f"core{ci}"
        if "vertices" in c:
            v = c["vertices"]
            if isinstance(v, dict):
                v = v.get("vertices", [])
            c["vertices"] = v
            cores[cid] = v
        elif "extent" in c:
            v = _extent_to_vertices(c["extent"], grid)
            if v is None:
                c["vertices"] = []
                continue
            del c["extent"]
            c["vertices"] = v
            cores[cid] = v

    # 3) corridor：ring(around core) → 矩形 ring_edges；开线 → 丢弃
    corr = z.get("corridor")
    if corr is not None:
        form = corr.get("form")
        if form == "path" and isinstance(corr.get("path"), dict) and "edges" in corr.get("path", {}):
            pass  # 已是 ring_edges
        elif form == "ring" and corr.get("around") == "core" and cores:
            w = float(corr.get("width_mm") or 0)
            first = next(iter(cores.values()))
            if first:
                xs = [p[0] for p in first]
                ys = [p[1] for p in first]
                corr["form"] = "path"
                corr["path"] = _rect_ring_edges(min(xs) - w, min(ys) - w,
                                                max(xs) + w, max(ys) + w)
                corr.pop("around", None)
        else:
            del z["corridor"]  # 开线等无法迁移 → 丢弃

    corridor_outer = None
    if corr is not None and isinstance(corr.get("path"), dict) and "edges" in corr.get("path", {}):
        try:
            corridor_outer = _expand_ring_edges(corr["path"], is_outer=True)["vertices"]
        except Exception:
            corridor_outer = None

    outline_edges: list[tuple[list, list]] = []
    for oblk in z.get("outline") or []:
        verts = (oblk.get("outer") or {}).get("vertices") or []
        outline_edges.extend(_ring_edges_of_edges(verts))

    # 4) main_partitions：只切割线锚定；轴网索引 path 端点匹配 → 锚定，否则丢弃
    migrated_parts = []
    for part in z.get("main_partitions") or []:
        if "from" in part:
            # 已有锚定——ref 目标必须可用
            refs = [part["from"].get("ref"), part["to"].get("ref")]
            if "corridor:outer" in refs and corridor_outer is None:
                continue
            migrated_parts.append(part)
            continue
        p = part.get("path")
        if not isinstance(p, list) or not p or not isinstance(p[0], dict):
            continue
        abs_pts = []
        for pt in p:
            try:
                abs_pts.append([grid["x"][int(pt["x"])], grid["y"][int(pt["y"])]])
            except (KeyError, IndexError, TypeError, ValueError):
                break
        if len(abs_pts) < 2 or abs_pts[0] == abs_pts[-1]:
            continue  # 退化线
        a = _anchor_point(abs_pts[0], outline_edges, corridor_outer, cores)
        b = _anchor_point(abs_pts[-1], outline_edges, corridor_outer, cores)
        if a and b:
            migrated_parts.append({
                "id": f"cut:{len(migrated_parts)}",
                "role": part.get("role", "partition"),
                "from": a, "to": b,
            })
    z["main_partitions"] = migrated_parts

    # 5) blocks：只留 between 认领
    z["blocks"] = [b for b in (z.get("blocks") or []) if "between" in b]

    # 6) 旧协议字段清干净
    z.pop("axis_grid", None)
    return skel


def _canon(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_plan(rel: str) -> dict | None:
    p = AIPLAN_GOLDEN / rel / "plan.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def run(cases: list[str], dry_run: bool) -> int:
    targets = []
    for case_dir in sorted(GOLDEN_DIR.glob("*/*")):
        rel = str(case_dir.relative_to(GOLDEN_DIR))
        if not (case_dir / "skeleton.json").exists():
            continue
        if not cases or any(c.rstrip("/") == rel or rel.endswith(c) for c in cases):
            targets.append(rel)
    if cases:
        missing = [c for c in cases
                   if not any(t == c or t.endswith(c) for t in targets)]
        if missing:
            print(f"未找到案例: {missing}")
            return 1

    n_ok = n_fail = 0
    for rel in targets:
        sp = GOLDEN_DIR / rel / "skeleton.json"
        skel = json.loads(sp.read_text(encoding="utf-8"))
        plan = load_plan(rel)
        before = _canon(skel)
        try:
            new_skel = migrate_skeleton(json.loads(json.dumps(skel)), plan)
            model = normalize_skeleton(new_skel)  # FAIL 不落盘
            after = _canon(new_skel)
            z = new_skel["zones"][0]
            corr = z.get("corridor")
            corr_txt = corr["form"] if corr else "无"
            core = z.get("core")
            core_n = len(core) if isinstance(core, list) else (1 if core else 0)
            detail = (f"cut={len(z.get('main_partitions') or [])} "
                      f"corridor={corr_txt} blocks={len(z.get('blocks') or [])} "
                      f"core_n={core_n} "
                      f"{'幂等(无变更)' if before == after else '有变更'}")
            if dry_run:
                print(f'OK   {rel:35} {detail} (dry-run)')
            else:
                sp.write_text(json.dumps(new_skel, ensure_ascii=False, indent=1) + "\n",
                              encoding="utf-8")
                print(f'OK   {rel:35} {detail}')
            n_ok += 1
        except Exception as e:
            print(f'FAIL {rel:35} {type(e).__name__}: {str(e)[:90]}')
            n_fail += 1
    print(f"\n{len(targets)} 案例：{n_ok} OK / {n_fail} FAIL"
          + ("（--dry-run 未落盘）" if dry_run else ""))
    return 0 if n_fail == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--dry-run", action="store_true", help="只验证不落盘")
    ap.add_argument("cases", nargs="*", help="案例路径（type/case），缺省全部")
    args = ap.parse_args()
    if not AIPLAN_GOLDEN.exists():
        print(f"警告：上游 aiplan golden 不存在（{AIPLAN_GOLDEN}），仅用骨架自身数据迁移")
    return run(args.cases, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())

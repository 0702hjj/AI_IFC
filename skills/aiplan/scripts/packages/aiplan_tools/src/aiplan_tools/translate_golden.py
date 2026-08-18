"""translate_golden.py —— 金例 design_intent → plan.json 翻译（D36）。

背景（2026-08-13 用户拍板）：aiplan 金例（references/golden/）的 design_intent.json
采用新格式（form.path.rings[].edges 方位分边 + segments 弧标注），plan 协议
（plan.schema.json）未动——本模块把金例翻译成 plan 契约格式：

- form.path.rings → outline_mm（resolve_path 已有：四边拼合 + segments 展开 + holes）
- core 数组 → core ring 数组 + core_anchor_mm 锚点数组（normalize 对齐契约）
- 补 plan required 字段：function（meta.type 映射）/floors（缺省单层）/
  floor_height_mm（缺省 3000）/program（金例无数据→占位，报告标注）

坐标轴检查（用户提醒）：金例 intent 坐标是归一化坐标（原点附近、正 Y），
source.dxf 是原生大地坐标——翻译报告两者 bbox 差异（平移/翻转量），
供下游（aidxfv3 金例 skeleton）对齐，禁止硬移植错位。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from aiplan_tools.normalize import normalize
from aiplan_tools.paths import REFS

# meta.type → plan function 映射
_TYPE_TO_FUNCTION = {
    "residence": "residence",
    "single_family": "residence",
    "retail": "retail",
    "office": "office",
    "hotel": "hotel",
}

_SCHEMA_PATH = REFS / "schemas" / "plan.schema.json"


def _bbox(pts: list[list[float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _outline_bbox(outline_mm: list[dict]) -> tuple[float, float, float, float]:
    pts = []
    for blk in outline_mm:
        pts.extend(blk["outer"]["vertices"])
    return _bbox(pts)


def source_dxf_bbox(dxf_path: Path) -> tuple[float, float, float, float] | None:
    """source.dxf 原生坐标范围（坐标轴对比用）。"""
    try:
        import ezdxf
    except ImportError:
        return None
    if not dxf_path.exists():
        return None
    doc = ezdxf.readfile(str(dxf_path))
    xs: list[float] = []
    ys: list[float] = []
    for e in doc.modelspace():
        try:
            t = e.dxftype()
            if t == "LINE":
                xs += [e.dxf.start.x, e.dxf.end.x]
                ys += [e.dxf.start.y, e.dxf.end.y]
            elif t == "LWPOLYLINE":
                for p in e.get_points():
                    xs.append(p[0])
                    ys.append(p[1])
        except Exception:
            continue
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def translate_intent(intent: dict, meta: dict) -> tuple[dict, list[str]]:
    """design_intent + meta → 完整 plan.json（过 plan schema）。

    :return: (plan dict, 翻译备注列表——占位字段/数据缺口在此标注)
    """
    notes: list[str] = []
    out = normalize(intent)

    btype = meta.get("type", "")
    function = _TYPE_TO_FUNCTION.get(btype, btype or "unknown")
    if btype not in _TYPE_TO_FUNCTION:
        notes.append(f"meta.type={btype!r} 无 function 映射，原样使用")

    zones = []
    for z in out["zones"]:
        zone = {
            "id": z["id"],
            "function": function,
            "floors": {"from": 1, "to": 1},   # 缺省单层（金例无楼层数据）
            "floor_height_mm": 3000,          # 缺省（金例无层高数据）
            "outline_mm": z["outline_mm"],
            "program": [{"room": "unspecified"}],  # 占位（金例无 program 数据）
        }
        for k in ("core", "core_anchor_mm", "typology_candidates", "position"):
            if k in z:
                zone[k] = z[k]
        zones.append(zone)
    notes.append("floors/floor_height_mm 为缺省（金例无楼层数据）；program 为占位（金例无房间配比数据）")

    # site：金例无地块数据——用 outline bbox 作 lot 占位，setbacks 0
    all_pts = []
    for z in zones:
        for blk in z["outline_mm"]:
            all_pts.extend(blk["outer"]["vertices"])
    x0, y0, x1, y1 = _bbox(all_pts)
    plan = {
        "version": 3,
        "project": intent.get("project", meta.get("case_id", "golden")),
        "site": {
            "lot_polygon_mm": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
            "origin": "lot_southwest",
            "north_deg": 0,
            "setbacks_mm": {"front": 0, "rear": 0, "left": 0, "right": 0},
        },
        "zones": zones,
        "design_rationale": out.get("design_rationale", ""),
    }
    notes.append("site.lot_polygon_mm 为 outline bbox 占位（金例无地块数据）")
    return plan, notes


def validate_translated(plan: dict) -> list[str]:
    """plan schema 校验（Draft 2020-12）。"""
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    v = Draft202012Validator(schema)
    return [f"{'/'.join(str(p) for p in e.absolute_path)}: {e.message}"
            for e in v.iter_errors(plan)]


def translate_case(case_dir: Path, write: bool = True) -> dict:
    """翻译单金例：design_intent.json + meta.json → plan.json（+ 坐标报告）。

    :return: {"case_id", "plan", "notes", "schema_errors", "coord_report"}
    """
    intent = json.loads((case_dir / "design_intent.json").read_text(encoding="utf-8"))
    meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    plan, notes = translate_intent(intent, meta)
    schema_errors = validate_translated(plan)

    # 坐标轴报告：intent 归一化坐标 vs source.dxf 原生坐标
    coord_report: dict = {"intent_bbox": None, "source_bbox": None, "note": ""}
    ob = _outline_bbox(plan["zones"][0]["outline_mm"]) if plan["zones"] else None
    coord_report["intent_bbox"] = [round(v, 1) for v in ob] if ob else None
    sb = source_dxf_bbox(case_dir / "source.dxf")
    if sb:
        coord_report["source_bbox"] = [round(v, 1) for v in sb]
        if ob:
            coord_report["note"] = (
                f"平移量≈({sb[0]-ob[0]:.0f}, {sb[1]-ob[1]:.0f})；"
                f"X 跨 intent {ob[2]-ob[0]:.0f} vs source {sb[2]-sb[0]:.0f}，"
                f"Y 跨 intent {ob[3]-ob[1]:.0f} vs source {sb[3]-sb[1]:.0f}"
                "——硬移植需做坐标变换（平移+可能 Y 翻转）"
            )
    else:
        coord_report["note"] = "无 source.dxf 或 ezdxf 不可用，跳过坐标对比"

    if write and not schema_errors:
        (case_dir / "plan.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {
        "case_id": meta.get("case_id", case_dir.name),
        "plan": plan,
        "notes": notes,
        "schema_errors": schema_errors,
        "coord_report": coord_report,
    }


def _main(argv: list[str]) -> int:
    """CLI：aiplan translate-golden [golden_root]（批量翻译金例 → plan.json）。"""
    root = Path(argv[0]) if argv else (REFS / "golden")
    cases = sorted(p.parent for p in root.rglob("design_intent.json"))
    if not cases:
        print(f"未找到金例（{root}）", file=sys.stderr)
        return 1
    fails = 0
    for case_dir in cases:
        r = translate_case(case_dir)
        status = "✓" if not r["schema_errors"] else "✗"
        print(f"{status} {r['case_id']}: {r['coord_report']['note']}")
        for e in r["schema_errors"]:
            print(f"    schema: {e}")
            fails += 1
    print(f"\n{len(cases)} 例翻译完成，schema 错误 {fails} 处")
    return 0 if fails == 0 else 1


def main() -> int:
    return _main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())

"""
ifc_inspect.py — IFC 模型几何检查器(按需使用,不是每次构建都跑)。

三个触发场景:
    1. design_review 报错(消息带 #stepid)→ --ids 扫该构件拿定位/几何细节再改代码
    2. 用户要求调整模型 → 先扫受影响区域的真实坐标,再改生成代码
    3. 用户回传外部修改过的 IFC → 扫描对比,Python 侧跟进

定位: design_review 是每次构建后的轻量闭环(结构树+问题清单);
      本工具是按需的构件级几何深挖(placement 世界矩阵/几何摘要/门窗挂载)。

Token 纪律(重要):
    大模型禁止全量扫描。先 --no-psets 摸底,再用过滤器定向深挖:
      --storey "Level 2"     只扫某层
      --class IfcWall        只扫某类(继承语义,含 IfcWallStandardCase)
      --ids 16584,43307      只看指定构件(全量 detail)
      --no-psets             去掉 property_sets(最大瘦身项)

扫描三层(基于 ifcquery 库函数):
    tree.tree()      → 空间骨架(楼层/空间,补 Elevation)
    info.info()      → 构件 placement 世界矩阵 + geometry_summary + psets
    util.element     → 墙 → 洞口 → 填充门窗 挂载关系反查

输出: analysis_results/<model>_structure.json

用法:
    python ifc_inspect.py <model.ifc> [--storey NAME] [--class CLS] [--ids 1,2] [--no-psets] [--out DIR]
"""

import argparse
import json
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.placement
from ifcquery import tree as tree_mod
from ifcquery import info as info_mod

# 全量扫描(含 psets)的构件类;其余(家具等)只做轻量扫描
_PSET_CLASSES = {
    "IfcWall", "IfcSlab", "IfcDoor", "IfcWindow", "IfcColumn", "IfcBeam",
    "IfcRoof", "IfcStair", "IfcStairFlight", "IfcRailing", "IfcCurtainWall",
    "IfcSpace", "IfcPlate", "IfcMember",
}


def _length_unit(model) -> str:
    """模型长度单位符号(mm/m/cm),供 LLM 解读坐标数值。"""
    try:
        project = model.by_type("IfcProject")[0]
        for u in project.UnitsInContext.Units:
            if u.is_a("IfcSIUnit") and u.UnitType == "LENGTHUNIT":
                prefix = u.Prefix or ""
                return {"MILLI": "mm", "CENTI": "cm", "": "m"}.get(prefix, f"{prefix}{u.Name}".lower())
    except Exception:
        pass
    return "unknown"


def _world_pos(element) -> list[float] | None:
    """构件世界坐标 [x, y, z](placement 矩阵平移列)。"""
    try:
        if element.ObjectPlacement:
            m = ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement)
            return [round(float(m[0][3]), 3), round(float(m[1][3]), 3), round(float(m[2][3]), 3)]
    except Exception:
        pass
    return None


def _wall_openings(model, wall) -> list[dict]:
    """墙 → 洞口 → 填充门窗(挂载关系反查)。

    注意: util.element.get_openings() 返回 IfcRelVoidsElement 关系实体,
    需 .RelatedOpeningElement 取洞口本体。
    """
    result = []
    try:
        for voids_rel in ifcopenshell.util.element.get_openings(wall):
            opening = voids_rel.RelatedOpeningElement
            entry = {"id": opening.id(), "type": opening.is_a()}
            if getattr(opening, "Name", None):
                entry["name"] = opening.Name
            pos = _world_pos(opening)
            if pos:
                entry["position"] = pos
            fillings = []
            for rel in getattr(opening, "HasFillings", []) or []:
                fill = rel.RelatedBuildingElement
                f = {"id": fill.id(), "type": fill.is_a()}
                if getattr(fill, "Name", None):
                    f["name"] = fill.Name
                fpos = _world_pos(fill)
                if fpos:
                    f["position"] = fpos
                fillings.append(f)
            if fillings:
                entry["filled_by"] = fillings
            result.append(entry)
    except Exception:
        pass
    return result


def _deep_round(obj, nd: int = 4):
    """递归把 float 圆整到 nd 位小数(压 placement 矩阵/几何摘要的 float 尾巴,省 token)。"""
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, list):
        return [_deep_round(x, nd) for x in obj]
    if isinstance(obj, dict):
        return {k: _deep_round(v, nd) for k, v in obj.items()}
    return obj


def _scan_element(model, element, with_psets: bool) -> dict:
    """单构件扫描:结构类全量(info.info),其余轻量;with_psets=False 仅去 property_sets。

    注意: 匹配 _PSET_CLASSES 用继承语义(IfcWallStandardCase 是 IfcWall 子类)。
    """
    if not any(element.is_a(c) for c in _PSET_CLASSES):
        entry = {"id": element.id(), "type": element.is_a()}
        if getattr(element, "Name", None):
            entry["name"] = element.Name
        pos = _world_pos(element)
        if pos:
            entry["position"] = pos
        return entry

    full = _deep_round(info_mod.info(model, element))
    entry = {
        "id": full["id"],
        "type": full["type"],
        "name": full.get("attributes", {}).get("Name"),
    }
    if full.get("placement"):
        entry["placement"] = full["placement"]  # 4×4 世界矩阵
    if full.get("geometry_summary"):
        entry["geometry_summary"] = full["geometry_summary"]
    if with_psets and full.get("property_sets"):
        entry["property_sets"] = full["property_sets"]
    if full.get("element_type"):
        entry["element_type"] = full["element_type"]
    if full.get("material"):
        entry["material"] = full["material"]
    if element.is_a("IfcWall"):
        openings = _wall_openings(model, element)
        if openings:
            entry["openings"] = openings
    return entry


def _enrich_tree(node: dict, model) -> dict:
    """给 tree.tree() 的节点补 Elevation,递归处理。"""
    if node.get("type") == "IfcBuildingStorey":
        try:
            node["elevation"] = model.by_id(node["id"]).Elevation
        except Exception:
            pass
    for child in node.get("children", []):
        _enrich_tree(child, model)
    return node


def _compact_tree(node: dict) -> dict:
    """过滤模式下压缩树: elements 名单 → element_counts 计数(token 纪律)。"""
    node.pop("elements", None)
    for child in node.get("children", []):
        _compact_tree(child)
    return node


def _in_storey(element, storey) -> bool:
    """判断空间是否属于某楼层(container 或 Decomposes 反链)。"""
    try:
        container = ifcopenshell.util.element.get_container(element)
        if container is not None and container.id() == storey.id():
            return True
    except Exception:
        pass
    for rel in getattr(element, "Decomposes", []) or []:
        if rel.RelatingObject.id() == storey.id():
            return True
    return False


def inspect(model, with_psets: bool = True, storey: str = None,
            cls: str = None, ids: list[int] = None) -> dict:
    """全量/定向扫描,返回结构 JSON dict。

    :param storey: 只扫该楼层(名称模糊匹配,大小写不敏感)
    :param cls: 只扫该类(继承语义,如 IfcWall 含 IfcWallStandardCase)
    :param ids: 只扫这些 step id(忽略楼层分组,平铺输出全量 detail)
    """
    result = {
        "schema": model.schema,
        "length_unit": _length_unit(model),
        "generated_by": "flows/ifc_inspect.py (ifcquery tree+info)",
    }
    filters = {k: v for k, v in [("storey", storey), ("class", cls), ("ids", ids)] if v}
    if filters:
        result["filters"] = filters

    # ── ids 定向模式: 平铺全量 detail,不走楼层分组 ──
    if ids:
        elements = []
        for eid in ids:
            try:
                e = model.by_id(eid)
            except RuntimeError:
                elements.append({"id": eid, "error": "not found"})
                continue
            entry = _scan_element(model, e, with_psets)
            container = None
            try:
                c = ifcopenshell.util.element.get_container(e)
                container = {"id": c.id(), "type": c.is_a(), "name": c.Name} if c else None
            except Exception:
                pass
            if container:
                entry["container"] = container
            elements.append(entry)
        result["elements"] = elements
        return result

    # ── 层 1: 空间骨架(全量模式完整输出;过滤模式压缩为计数,省 token) ──
    spatial_tree = tree_mod.tree(model)
    if isinstance(spatial_tree, dict) and "error" not in spatial_tree:
        result["spatial_tree"] = _enrich_tree(spatial_tree, model)
        if storey or cls:
            _compact_tree(result["spatial_tree"])
    else:
        result["spatial_tree"] = spatial_tree

    # ── 层 2: 楼层构件扫描(可用 storey/cls 过滤) ──
    storeys = list(model.by_type("IfcBuildingStorey"))
    if storey:
        storeys = [s for s in storeys if storey.lower() in (s.Name or "").lower()]
        if not storeys:
            result["error"] = f"no storey matching '{storey}'"
            return result

    storeys_out = []
    for st in storeys:
        st_entry = {"id": st.id(), "name": st.Name, "elevation": st.Elevation}
        spaces = [
            {"id": sp.id(), "name": sp.Name}
            for sp in model.by_type("IfcSpace")
            if _in_storey(sp, st)
        ]
        if spaces:
            st_entry["spaces"] = spaces
        by_class: dict[str, list] = {}
        for rel in getattr(st, "ContainsElements", []) or []:
            for e in rel.RelatedElements:
                if cls and not e.is_a(cls):
                    continue
                by_class.setdefault(e.is_a(), []).append(_scan_element(model, e, with_psets))
        st_entry["elements"] = {k: v for k, v in sorted(by_class.items())}
        st_entry["element_counts"] = {k: len(v) for k, v in sorted(by_class.items())}
        storeys_out.append(st_entry)
    result["storeys"] = storeys_out

    # 未被任何楼层包含的构件(悬挂预警,定向模式下跳过)
    if not filters:
        contained_ids = {
            e.id()
            for st in model.by_type("IfcBuildingStorey")
            for rel in getattr(st, "ContainsElements", []) or []
            for e in rel.RelatedElements
        }
        orphans = [
            {"id": e.id(), "type": e.is_a(), "name": getattr(e, "Name", None)}
            for c in ("IfcWall", "IfcSlab", "IfcDoor", "IfcWindow", "IfcColumn", "IfcBeam", "IfcRoof")
            for e in model.by_type(c)
            if e.id() not in contained_ids
        ]
        if orphans:
            result["orphan_elements"] = orphans
        result["stats"] = {
            "storey_count": len(storeys_out),
            "space_count": len(model.by_type("IfcSpace")),
            "wall_count": len(model.by_type("IfcWall")),
            "door_count": len(model.by_type("IfcDoor")),
            "window_count": len(model.by_type("IfcWindow")),
            "slab_count": len(model.by_type("IfcSlab")),
            "column_count": len(model.by_type("IfcColumn")),
            "orphan_count": len(orphans),
        }
    return result


def _default_out_dir() -> Path:
    """analysis_results/ 位于 AI_IFC 根目录(skills/aiifc/references/docs/flows/ 上五级)。"""
    try:
        return Path(__file__).resolve().parents[5] / "analysis_results"
    except Exception:
        return Path.cwd() / "analysis_results"


def main():
    parser = argparse.ArgumentParser(description="既有 IFC 模型结构扫描器(按需,勿每次构建跑)")
    parser.add_argument("ifc_file", help="IFC 文件路径")
    parser.add_argument("--storey", default=None, help="只扫该楼层(名称模糊匹配)")
    parser.add_argument("--cls", "--class", dest="cls", default=None,
                        help="只扫该类(继承语义,如 IfcWall)")
    parser.add_argument("--ids", default=None, help="只扫这些 step id,逗号分隔(全量 detail)")
    parser.add_argument("--no-psets", action="store_true", help="不输出 property_sets(瘦身)")
    parser.add_argument("--pretty", action="store_true", help="缩进格式输出(默认紧凑,LLM 读紧凑 JSON 无障碍)")
    parser.add_argument("--out", default="", help="输出目录(默认 AI_IFC/analysis_results/)")
    args = parser.parse_args()

    ids = [int(x) for x in args.ids.split(",")] if args.ids else None
    model = ifcopenshell.open(args.ifc_file)
    result = inspect(model, with_psets=not args.no_psets,
                     storey=args.storey, cls=args.cls, ids=ids)
    result["model"] = str(args.ifc_file)

    out_dir = Path(args.out) if args.out else _default_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_ids" if ids else ("_" + args.cls) if args.cls else ("_" + args.storey.replace(" ", "_")) if args.storey else ""
    out_path = out_dir / f"{Path(args.ifc_file).stem}{suffix}_structure.json"
    if args.pretty:
        text = json.dumps(result, indent=2, ensure_ascii=False, default=str)
    else:
        text = json.dumps(result, separators=(",", ":"), ensure_ascii=False, default=str)
    out_path.write_text(text, encoding="utf-8")

    kb = out_path.stat().st_size / 1024
    print(f"[ifc_inspect] {Path(args.ifc_file).name} unit={result['length_unit']}", end="")
    if filters := result.get("filters"):
        print(f" filters={filters}", end="")
    if stats := result.get("stats"):
        print(f" storeys={stats['storey_count']} walls={stats['wall_count']} "
              f"doors={stats['door_count']} windows={stats['window_count']}", end="")
        if stats["orphan_count"]:
            print(f" WARNING:{stats['orphan_count']} orphans", end="")
    print(f"\n  → {out_path} ({kb:.1f} KB)")


if __name__ == "__main__":
    main()

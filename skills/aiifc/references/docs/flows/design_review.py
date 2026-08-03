"""
design_review.py — 生成后设计质量审查。

检查优先级:
    SS  空间结构完整性(最高优先级,Project→Site→Building→Storey 链 + 构件挂载)
    GI  几何完整性 GI-01~06(包络闭合/窗贴墙/楼梯开洞/洞口包含/墙贴板/柱贴板)
    GEO Body 几何存在性 + 门窗洞口链接
    PR/RH/MC/CP/FD/SQ  SPATIAL_QUALITY.md 设计规则(保持现有实现)

P2 接地(research/check_strut/ifcquery_investigation.md §7):
    - GI-01 包络闭合: container 分组 + 墙轴线端点拓扑(无需几何内核)
    - GI-02 窗墙附着: FillsVoids → opening → VoidsElements 关系链 + 几何兜底
    - 可选碰撞: import ifcquery.clash (--clash 开启)

输出: analysis_results/<model>_analysis.json(含空间结构树,喂给 LLM 审查)

硬编码的 error 深挖(非文本纪律):
    run() 结束后自动从 error 消息提取 #stepid,扫描其 placement/geometry_summary/
    container 嵌入 report["error_elements"];门窗/洞口类 error 额外附 nearest_wall
    (墙轴线无 Axis 表示时从 Body 轮廓兜底估算)。LLM 拿到报告即有全部修复坐标,
    无需再手动调 ifc_inspect。

用法:
    # 独立运行(读 IFC 文件,写 analysis_results/)
    python design_review.py model.ifc [building_type] [--out DIR] [--no-json] [--clash]

    # 在 example 中调用(生成后审查)
    from flows.design_review import run
    report = run(model, building_type="school", model_name="my_school")
    # report["ok"] / report["errors"] / report["warnings"] / report["info"]

规则来源: references/SPATIAL_QUALITY.md
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
import ifcopenshell
import ifcopenshell.util.placement
import ifcopenshell.util.element

try:  # 包内导入(example: from flows.design_review import run)
    from flows.ifc_inspect import _scan_element
except ImportError:  # 独立运行(python docs/flows/design_review.py)
    try:
        from ifc_inspect import _scan_element
    except ImportError:
        _scan_element = None


# ═══ 基础工具 ═══

def _world_pos(element) -> tuple:
    """计算元素的世界坐标 (x, y, z),模型单位。"""
    if not element.ObjectPlacement:
        return (0.0, 0.0, 0.0)
    m = np.array(ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement))
    return (round(float(m[0][3]), 3), round(float(m[1][3]), 3), round(float(m[2][3]), 3))


def _has_body(element) -> bool:
    """检查元素是否有 Body 几何表示。"""
    if not element.Representation:
        return False
    for rep in element.Representation.Representations:
        if rep.RepresentationIdentifier == "Body":
            return True
    return False


def _get_psets_safe(element):
    try:
        return ifcopenshell.util.element.get_psets(element)
    except Exception:
        return {}


def _get_material_safe(element):
    try:
        return ifcopenshell.util.element.get_material(element)
    except Exception:
        return None


def _get_container_safe(element):
    try:
        return ifcopenshell.util.element.get_container(element)
    except Exception:
        return None


def _by_type_safe(model, cls) -> list:
    """schema 安全的 by_type:IFC2x3 无 IfcFurniture 等类时返回空表。"""
    try:
        return model.by_type(cls)
    except RuntimeError:
        return []


def _overlap(a, b) -> float:
    """两区间 [a0,a1] [b0,b1] 的重叠长度。"""
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


class DesignReviewer:
    """设计质量审查器。读 IFC 模型,先查空间结构(SS),再查几何完整性(GI),最后查设计规则。"""

    # SS-05 需要检查空间挂载的构件类
    _CONTAINED_CLASSES = (
        "IfcWall", "IfcSlab", "IfcDoor", "IfcWindow", "IfcColumn", "IfcBeam",
        "IfcStair", "IfcStairFlight", "IfcRailing", "IfcRoof", "IfcPlate",
        "IfcMember", "IfcCurtainWall", "IfcRamp", "IfcRampFlight",
        "IfcCovering", "IfcFurniture", "IfcBuildingElementProxy",
    )

    def __init__(self, model: ifcopenshell.file, building_type: str = "public"):
        self.model = model
        self.building_type = building_type  # residential / office / school / retail / public
        self.errors = []
        self.warnings = []
        self.info = []
        self.mm = self._length_unit_scale()  # 1mm = self.mm 个模型单位

    def run(self) -> dict:
        """执行全部规则检查,返回审查报告。"""
        self._check_spatial_structure()      # SS-01~06 最高优先级
        self._check_geometric_integrity()    # GI-01~06
        self._check_geometry_presence()      # GEO has_body
        self._check_proportion_rules()       # PR-01~04
        self._check_rhythm_rules()           # RH-02
        self._check_material_rules()         # MC-01/03
        self._check_facade_depth_rules()     # FD(stub)
        self._check_clashes()                # CLASH 穿模（结构构件互相穿透）

        ok = len(self.errors) == 0
        report = {
            "ok": ok,
            "building_type": self.building_type,
            "schema": self.model.schema,
            "length_unit_scale_mm": self.mm,
            "spatial_structure": self.build_spatial_tree(),
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "summary": f"{len(self.errors)} errors, {len(self.warnings)} warnings, {len(self.info)} info",
        }
        # 硬编码:error 涉及构件的几何细节自动嵌入(无需 LLM 再调 ifc_inspect)
        details = self._collect_error_details()
        if details:
            report["error_elements"] = details
        return report

    # ═══ error 构件自动深挖(硬编码,非文本纪律) ═══

    def _collect_error_details(self) -> dict:
        """从 error 消息提取 #stepid,自动扫描其 placement/geometry/container。

        门窗/洞口类 error 额外附 nearest_wall(修复附着问题必需的对照坐标)。
        返回 {step_id_str: element_detail}。
        """
        if _scan_element is None or not self.errors:
            return {}
        ids = []
        for msg in self.errors:
            ids.extend(int(m) for m in re.findall(r"#(\d+)", msg))
        details = {}
        for eid in dict.fromkeys(ids):  # 去重保序
            try:
                e = self.model.by_id(eid)
            except RuntimeError:
                continue
            entry = _scan_element(self.model, e, with_psets=False)
            container = _get_container_safe(e)
            if container is not None:
                entry["container"] = {"id": container.id(), "type": container.is_a(),
                                      "name": getattr(container, "Name", None)}
            if e.is_a("IfcWindow") or e.is_a("IfcDoor") or e.is_a("IfcOpeningElement"):
                near = self._nearest_wall(e)
                if near is not None:
                    entry["nearest_wall"] = near
            details[str(eid)] = entry
        return details

    def _nearest_wall(self, element) -> dict | None:
        """找 XY 距离最近的墙(用 GI-02 已算的墙轴线段),返回其扫描件+距离。"""
        segs = getattr(self, "_wall_segs", None)
        if not segs:
            return None
        wx, wy, _ = _world_pos(element)
        best, best_d = None, float("inf")
        for wall, x1, y1, x2, y2 in segs:
            dx, dy = x2 - x1, y2 - y1
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((wx - x1) * dx + (wy - y1) * dy) / L2))
            d = ((wx - (x1 + t * dx)) ** 2 + (wy - (y1 + t * dy)) ** 2) ** 0.5
            if d < best_d:
                best, best_d = wall, d
        if best is None:
            return None
        entry = _scan_element(self.model, best, with_psets=False)
        entry["distance_to_element"] = round(best_d / self.mm, 1)  # → mm
        return entry

    # ═══ SS 空间结构完整性(最高优先级) ═══

    def _length_unit_scale(self) -> float:
        """1mm 对应的模型单位数。mm→1.0, cm→0.1, m→0.001。"""
        try:
            project = self.model.by_type("IfcProject")[0]
            for u in project.UnitsInContext.Units:
                if u.is_a("IfcSIUnit") and u.UnitType == "LENGTHUNIT":
                    prefix = u.Prefix  # 可能为 None
                    if u.Name == "METRE":
                        return {None: 0.001, "MILLI": 1.0, "CENTI": 0.1, "DECI": 0.01}.get(prefix, 0.001)
        except Exception:
            pass
        return 1.0

    def _check_spatial_structure(self):
        """SS-01~06: 项目链/楼层标高/构件挂载/空间归属。"""
        m = self.model

        # SS-01: 唯一 IfcProject
        projects = m.by_type("IfcProject")
        if not projects:
            self.errors.append("[SS-01] no IfcProject in model")
            return
        if len(projects) > 1:
            self.warnings.append(f"[SS-01] multiple IfcProject ({len(projects)}), expected 1")
        project = projects[0]

        # SS-02: Project→Site→Building→Storey 聚合链(IsDecomposedBy)
        def _decomposed(parent, cls):
            return [o for rel in getattr(parent, "IsDecomposedBy", [])
                    for o in rel.RelatedObjects if o.is_a(cls)]

        sites = _decomposed(project, "IfcSite")
        if not sites:
            self.errors.append("[SS-02] IfcProject has no IfcSite aggregated")
        buildings = [b for s in sites for b in _decomposed(s, "IfcBuilding")]
        if sites and not buildings:
            if m.by_type("IfcBuilding"):
                self.warnings.append("[SS-02] IfcBuilding not aggregated under IfcSite")
                buildings = list(m.by_type("IfcBuilding"))
            else:
                self.errors.append("[SS-02] no IfcBuilding in model")
        storeys = [st for b in buildings for st in _decomposed(b, "IfcBuildingStorey")]
        all_storeys = list(m.by_type("IfcBuildingStorey"))
        if buildings and not storeys and all_storeys:
            self.warnings.append("[SS-02] IfcBuildingStorey not aggregated under IfcBuilding")
        if not all_storeys:
            self.errors.append("[SS-02] no IfcBuildingStorey in model")

        # SS-03: 每层 Elevation 必填(层高推导/图纸剖切/世界坐标都依赖它)
        for st in all_storeys:
            if st.Elevation is None:
                self.errors.append(
                    f"[SS-03] storey '{st.Name or st.GlobalId[:8]}' Elevation is None")

        # SS-04: 楼层标高不得重复
        elevs = [st.Elevation for st in all_storeys if st.Elevation is not None]
        if len(elevs) != len(set(elevs)):
            self.errors.append(f"[SS-04] duplicate storey elevations: {sorted(set(elevs))}")

        # SS-05: 建筑构件必须挂进空间结构(IfcRelContainedInSpatialStructure)
        uncontained: dict[str, list] = {}
        for cls in self._CONTAINED_CLASSES:
            for e in _by_type_safe(m, cls):
                if _get_container_safe(e) is None:
                    uncontained.setdefault(cls, []).append(f"{e.GlobalId[:8]}#{e.id()}")
        for cls, ids in sorted(uncontained.items()):
            sample = ", ".join(ids[:5]) + ("…" if len(ids) > 5 else "")
            self.errors.append(
                f"[SS-05] {len(ids)} {cls} not contained in any spatial structure: {sample}")

        # SS-06: IfcSpace 必须归属楼层(container 或 Decomposes 反链)
        for sp in m.by_type("IfcSpace"):
            if _get_container_safe(sp) is not None:
                continue
            if not getattr(sp, "Decomposes", None):
                self.warnings.append(
                    f"[SS-06] space '{sp.Name or sp.GlobalId[:8]}' not assigned to any storey")

    def build_spatial_tree(self) -> dict | None:
        """紧凑空间结构树:节点 + Elevation + 每类构件计数(喂 LLM 用)。"""
        projects = self.model.by_type("IfcProject")
        if not projects:
            return None

        def node(e):
            n = {"id": e.id(), "type": e.is_a()}
            if getattr(e, "Name", None):
                n["name"] = e.Name
            if e.is_a("IfcBuildingStorey"):
                n["elevation"] = e.Elevation
            children = [node(o) for rel in getattr(e, "IsDecomposedBy", [])
                        for o in rel.RelatedObjects]
            counts: dict[str, int] = {}
            for rel in getattr(e, "ContainsElements", []):
                for o in rel.RelatedElements:
                    counts[o.is_a()] = counts.get(o.is_a(), 0) + 1
            if children:
                n["children"] = children
            if counts:
                n["element_counts"] = dict(sorted(counts.items()))
            return n

        return node(projects[0])

    # ═══ GI 几何完整性规则 ═══

    def _wall_endpoints(self, wall) -> list[tuple] | None:
        """墙轴线两端点的世界 2D 坐标。优先 Axis 表示;无 Axis 时从 Body
        SweptSolid 轮廓估算(add_wall_representation 的墙长沿局部 X,矩形居中)。"""
        if not wall.Representation:
            return None
        m = np.array(ifcopenshell.util.placement.get_local_placement(wall.ObjectPlacement))

        def to_world(pts):
            return [(m[0][0] * x + m[0][1] * y + m[0][3],
                     m[1][0] * x + m[1][1] * y + m[1][3]) for x, y in pts]

        for rep in wall.Representation.Representations:
            if rep.RepresentationIdentifier != "Axis":
                continue
            for item in rep.Items:
                pts = None
                if item.is_a("IfcPolyline"):
                    pts = [(p.Coordinates[0], p.Coordinates[1]) for p in item.Points]
                elif item.is_a("IfcIndexedPolyCurve"):
                    pts = [(c[0], c[1]) for c in item.Points.CoordList]
                if pts and len(pts) >= 2:
                    world = to_world(pts)
                    return [world[0], world[-1]]

        # Body 轮廓兜底(无 Axis 表示的墙;取轮廓 y 中心线作墙轴)
        for rep in wall.Representation.Representations:
            if rep.RepresentationIdentifier != "Body":
                continue
            for item in rep.Items:
                if not item.is_a("IfcExtrudedAreaSolid"):
                    continue
                prof = item.SweptArea
                x_range = y_mid = None
                if prof.is_a("IfcRectangleProfileDef"):
                    half = float(prof.XDim) / 2
                    x_range = (-half, half)
                    y_mid = 0.0
                elif prof.is_a("IfcArbitraryClosedProfileDef"):
                    curve = prof.OuterCurve
                    coords = None
                    if curve.is_a("IfcPolyline"):
                        coords = [p.Coordinates for p in curve.Points]
                    elif curve.is_a("IfcIndexedPolyCurve"):
                        coords = list(curve.Points.CoordList)
                    if coords:
                        xs = [c[0] for c in coords]
                        ys = [c[1] for c in coords]
                        x_range = (min(xs), max(xs))
                        y_mid = (min(ys) + max(ys)) / 2
                if x_range:
                    world = to_world([(x_range[0], y_mid), (x_range[1], y_mid)])
                    return [world[0], world[-1]]
        return None

    def _is_exterior_wall(self, wall) -> bool:
        """外墙判定: pset IsExternal/Function=Exterior → 名称 Ext/外墙 兜底。"""
        psets = _get_psets_safe(wall)
        for pset in psets.values():
            if isinstance(pset, dict):
                if pset.get("IsExternal") is True:
                    return True
                if str(pset.get("Function", "")).lower() == "exterior":
                    return True
        name = (wall.Name or "")
        return "Ext" in name or "外墙" in name

    def _check_geometric_integrity(self):
        """GI-01~06: 外墙闭合/窗贴墙/楼梯开洞/洞口包含/墙贴板/柱贴板。"""
        storeys = self.model.by_type("IfcBuildingStorey")
        walls = self.model.by_type("IfcWall")  # 含 IfcWallStandardCase 子类
        windows = self.model.by_type("IfcWindow")
        stairs = self.model.by_type("IfcStairFlight")
        slabs = self.model.by_type("IfcSlab")
        columns = self.model.by_type("IfcColumn")
        openings = self.model.by_type("IfcOpeningElement")

        # GI-01: 外墙闭合(container 分组 + 墙轴线端点拓扑,P2 实现)
        for st in storeys:
            st_walls = [w for w in walls if _get_container_safe(w) is not None
                        and _get_container_safe(w).id() == st.id()]
            ext_walls = [w for w in st_walls if self._is_exterior_wall(w)]
            if not ext_walls:
                if len(st_walls) >= 3:
                    self.info.append(
                        f"[GI-01] {st.Name}: exterior walls not identifiable (no IsExternal/Ext), closure check skipped")
                continue
            # 端点聚类建图(union-find,欧氏距离 ≤300mm 吸附;
            # 网格取整会在墙偏移 ~100mm 时产生别名错误,改用距离聚类)
            snap = 300 * self.mm
            endpoints = []  # (x, y) per wall end
            wall_ends = []
            no_axis = 0
            for w in ext_walls:
                ep = self._wall_endpoints(w)
                if ep is None:
                    no_axis += 1
                    continue
                wall_ends.append(ep)
                endpoints.extend(ep)
            if not endpoints:
                self.info.append(
                    f"[GI-01] {st.Name}: no Axis representations on exterior walls, closure check skipped")
                continue
            # union-find 聚类
            parent = list(range(len(endpoints)))

            def find(i):
                while parent[i] != i:
                    parent[i] = parent[parent[i]]
                    i = parent[i]
                return i

            for i in range(len(endpoints)):
                for j in range(i + 1, len(endpoints)):
                    dx = endpoints[i][0] - endpoints[j][0]
                    dy = endpoints[i][1] - endpoints[j][1]
                    if dx * dx + dy * dy <= snap * snap:
                        pi, pj = find(i), find(j)
                        if pi != pj:
                            parent[pi] = pj
            degrees: dict[int, int] = {}
            idx = 0
            for ep in wall_ends:
                for _ in ep:
                    r = find(idx)
                    degrees[r] = degrees.get(r, 0) + 1
                    idx += 1
            # degree==1 = 真悬空端点(包络断口);degree==3+ = T/X 交接,允许
            dangling = sum(1 for d in degrees.values() if d == 1)
            if dangling:
                self.errors.append(
                    f"[GI-01] {st.Name}: envelope not closed — {dangling} dangling wall endpoints "
                    f"({len(ext_walls)} exterior walls, {no_axis} without axis)")
            elif no_axis:
                self.warnings.append(
                    f"[GI-01] {st.Name}: {no_axis}/{len(ext_walls)} exterior walls lack Axis representation, "
                    "closure verified only for axis-bearing walls")

        # GI-02: 窗贴墙(FillsVoids 关系链优先,几何位置兜底)
        wall_segs = []  # (x1,y1,x2,y2,z_base)
        self._wall_segs = []  # (wall, x1,y1,x2,y2) — 供 error 深挖找最近墙
        for w in walls:
            ep = self._wall_endpoints(w)
            if ep:
                wall_segs.append((ep[0][0], ep[0][1], ep[1][0], ep[1][1], _world_pos(w)[2]))
                self._wall_segs.append((w, ep[0][0], ep[0][1], ep[1][0], ep[1][1]))
        for win in windows:
            attached = False
            if win.FillsVoids:
                opening = win.FillsVoids[0].RelatingOpeningElement
                if opening.VoidsElements:
                    attached = True
            if attached:
                continue
            # 几何兜底: 窗心到某墙轴线段距离 < 500mm 且 z 重叠
            wx, wy, wz = _world_pos(win)
            tol = 500 * self.mm
            geo_ok = False
            for x1, y1, x2, y2, wz_base in wall_segs:
                dx, dy = x2 - x1, y2 - y1
                L2 = dx * dx + dy * dy
                t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((wx - x1) * dx + (wy - y1) * dy) / L2))
                dist = ((wx - (x1 + t * dx)) ** 2 + (wy - (y1 + t * dy)) ** 2) ** 0.5
                if dist <= tol and wz_base - 500 * self.mm <= wz <= wz_base + 5000 * self.mm:
                    geo_ok = True
                    break
            if geo_ok:
                self.warnings.append(
                    f"[GI-02] window {win.GlobalId[:8]}#{win.id()} near wall but has no FillsVoids link "
                    "(geometrically attached, semantically floating)")
            else:
                self.errors.append(
                    f"[GI-02] window {win.GlobalId[:8]}#{win.id()} not attached to any wall (floating)")

        # GI-03: 楼梯穿板开洞 (仅直跑穿透楼梯; 螺旋/悬浮楼梯豁免 — 多样性, SPATIAL_QUALITY GI-03)
        for stair in stairs:
            predef = getattr(stair, "PredefinedType", None)
            if predef not in (None, "STRAIGHT", "NOTDEFINED"):
                continue  # 非直跑 (SPIRAL/CURVED/悬浮) 豁免开孔检查
            sx, sy, sz = _world_pos(stair)
            slab_above = None
            for s in slabs:
                if s.PredefinedType == "LANDING":
                    continue  # Landing 是楼梯自身组件, 不算"穿板"
                _, _, slab_z = _world_pos(s)
                if slab_z > sz and slab_z - sz < 5000 * self.mm:
                    slab_above = s
                    break
            if slab_above:
                has_void = False
                brep_unverifiable = False
                if slab_above.Representation:
                    for rep in slab_above.Representation.Representations:
                        for item in rep.Items:
                            if hasattr(item, "SweptArea"):
                                if item.SweptArea.is_a("IfcArbitraryProfileDefWithVoids"):
                                    has_void = True
                            if item.is_a("IfcFacetedBrep") or item.is_a("IfcPolygonalFaceSet"):
                                brep_unverifiable = True  # Brep 开洞无法从轮廓判定
                if not has_void:
                    # 板经 IfcOpeningElement 开洞也算
                    for voids_rel in ifcopenshell.util.element.get_openings(slab_above):
                        has_void = True
                        break
                if not has_void:
                    if brep_unverifiable:
                        self.info.append(
                            f"[GI-03] stair {stair.GlobalId[:8]}#{stair.id()} passes through Brep slab "
                            f"{slab_above.Name} — opening not verifiable from profile")
                    else:
                        self.errors.append(
                            f"[GI-03] stair {stair.GlobalId[:8]}#{stair.id()} passes through slab "
                            f"{slab_above.Name} without opening")

        # GI-04: 洞口包含(洞口底 z 不低于宿主墙底 z)
        for opening in openings:
            if not opening.VoidsElements:
                continue
            host = opening.VoidsElements[0].RelatingBuildingElement
            oz = _world_pos(opening)[2]
            hz = _world_pos(host)[2]
            if oz < hz - 100 * self.mm:
                self.errors.append(
                    f"[GI-04] opening {opening.GlobalId[:8]}#{opening.id()} bottom z={oz} below host wall base z={hz}")

        # GI-05: 墙贴板(墙底 z 须对齐一个结构支撑面)
        # 支撑面 = FLOOR/ROOF/BASE 楼板 + IfcFooting；只排除 LANDING（楼梯休息平台不是墙的支撑）。
        # 注意与 GI-10 口径不同：GI-10 判"楼板覆盖/人能否站"只算 FLOOR；GI-05/06 判"墙柱有无支撑"
        # 含屋顶（女儿墙立在屋顶上）和基础（基础墙落在 BASE 板上）——否则女儿墙/基础墙会被误判 floating。
        bearing = [s for s in slabs if getattr(s, "PredefinedType", None) != "LANDING"] + _by_type_safe(self.model, "IfcFooting")
        for w in walls:
            wz = _world_pos(w)[2]
            aligned = False
            for s in bearing:
                sz = _world_pos(s)[2]
                if sz - 50 * self.mm <= wz <= sz + self._slab_depth(s) + 50 * self.mm:
                    aligned = True
                    break
            if bearing and not aligned:
                self.errors.append(f"[GI-05] wall {w.GlobalId[:8]}#{w.id()} base z={wz} not aligned to any slab")

        # GI-06: 柱贴板
        for c in columns:
            cz = _world_pos(c)[2]
            aligned = False
            for s in bearing:
                sz = _world_pos(s)[2]
                if sz - 50 * self.mm <= cz <= sz + self._slab_depth(s) + 50 * self.mm:
                    aligned = True
                    break
            if bearing and not aligned:
                self.errors.append(f"[GI-06] column {c.GlobalId[:8]}#{c.id()} base z={cz} not aligned to any slab")

        # GI-07: 填充件(门/窗)必须落在宿主墙厚范围内
        # 玻璃贴墙内侧/悬出墙外 = 填充放置错误(add_filling 不改位置,放置全靠自己)
        for fill in list(self.model.by_type("IfcDoor")) + list(self.model.by_type("IfcWindow")):
            if not fill.FillsVoids:
                continue
            opening = fill.FillsVoids[0].RelatingOpeningElement
            if not opening.VoidsElements:
                continue
            host = opening.VoidsElements[0].RelatingBuildingElement
            if not host.is_a("IfcWall"):
                continue
            ep = self._wall_endpoints(host)
            if ep is None:
                continue
            t = self._wall_thickness(host)
            fx, fy, _ = _world_pos(fill)
            x1, y1 = ep[0]
            x2, y2 = ep[1]
            dx, dy = x2 - x1, y2 - y1
            L2 = dx * dx + dy * dy
            tt = 0.0 if L2 == 0 else max(0.0, min(1.0, ((fx - x1) * dx + (fy - y1) * dy) / L2))
            dist = ((fx - (x1 + tt * dx)) ** 2 + (fy - (y1 + tt * dy)) ** 2) ** 0.5
            limit = t / 2 + 25 * self.mm
            if dist > limit:
                self.errors.append(
                    f"[GI-07] {fill.is_a()} {fill.GlobalId[:8]}#{fill.id()} offset "
                    f"{dist / self.mm:.0f}mm from wall centerline exceeds limit "
                    f"{limit / self.mm:.0f}mm (filling outside wall body — "
                    f"fill placement must center within wall thickness)")

        # GI-10: 楼板覆盖(防坠落:每层必须有足量楼板覆盖墙包络,杜绝"为过 GI-03 而掏空/省略楼板")
        for st in storeys:
            st_ext = [w for w in walls if _get_container_safe(w) is not None
                      and _get_container_safe(w).id() == st.id() and self._is_exterior_wall(w)]
            if len(st_ext) < 3:
                continue
            env_area = self._envelope_polygon_area(st_ext)
            if not env_area:
                continue
            st_floors = [s for s in slabs
                         if (s.PredefinedType not in ("LANDING", "ROOF", "BASE"))
                         and _get_container_safe(s) is not None
                         and _get_container_safe(s).id() == st.id()]
            net_floor = sum(self._slab_net_floor_area(s) for s in st_floors)
            if net_floor <= 0:
                self.errors.append(
                    f"[GI-10] {st.Name}: exterior walls present but NO floor slab — fall hazard")
            else:
                cov = net_floor / env_area
                if cov < 0.75:
                    self.errors.append(
                        f"[GI-10] {st.Name}: floor slab covers only {cov:.0%} of wall envelope "
                        f"({net_floor / 1e6:.0f}/{env_area / 1e6:.0f} m²) — fall hazard / over-voided")

        # GI-09: 楼梯联通性(每层楼梯最高踏步顶须抵达上一层标高 ±100mm;
        #         杜绝 rise≠层高 的"断梯"——踩空/到不了下一层)
        ordered = sorted([s for s in storeys if s.Elevation is not None], key=lambda s: s.Elevation)
        for i in range(len(ordered) - 1):
            z_hi = ordered[i + 1].Elevation
            flights = [sf for sf in stairs if _get_container_safe(sf) is not None
                       and _get_container_safe(sf).id() == ordered[i].id()]
            if not flights:
                continue
            max_top = max(_world_pos(sf)[2] + self._flight_height(sf) for sf in flights)
            if max_top < z_hi - 100 * self.mm:
                self.errors.append(
                    f"[GI-09] {ordered[i].Name}: stair tops out at {max_top / self.mm:.0f}mm, "
                    f"{(z_hi - max_top) / self.mm:.0f}mm below next floor {ordered[i+1].Name} "
                    f"({z_hi / self.mm:.0f}mm) — disconnected (stair rise ≠ storey height)")

        # GI-11（栏板强制检查）已移除：与 stairs_types "fall protection is contextual, not absolute"
        # 哲学冲突——螺旋/悬挑/书屋/单户楼梯可合法无 IfcRailing。栏板是否设置由 occupancy/code
        # 驱动（见 stairs_types.md fall protection 段），不由检查器强制为 error。

        # GI-12: 梯井卫生 —— 禁止"墙里面建小墙"(同层平行内墙相距 <1.2m 形成无用夹腔);
        #         正解:定楼梯尺寸贴既有墙,梯井旁留疏散通道,首层外墙开门。
        cav_tol = 1.2 * 1000 * self.mm  # 1.2m
        # 预计算每堵墙:端点+走向+底 z(只比较同层墙,避免跨层误报)
        infos = []
        for w in walls:
            if self._is_exterior_wall(w):
                continue  # 只查内墙夹腔(外墙双墙可能合法)
            oe = self._wall_orient_endpoints(w)
            if oe:
                infos.append((w, oe, _world_pos(w)[2]))
        seen = set()
        for a in range(len(infos)):
            wa, ea, za = infos[a]
            (ax1, ay1), (ax2, ay2), oa = ea
            for b in range(a + 1, len(infos)):
                wb, eb, zb = infos[b]
                if abs(za - zb) > 200 * self.mm:  # 不同层 → 跳过(非夹腔)
                    continue
                (bx1, by1), (bx2, by2), ob = eb
                if oa != ob:
                    continue  # 不平行
                if oa == "X":
                    along = _overlap((min(ax1, ax2), max(ax1, ax2)), (min(bx1, bx2), max(bx1, bx2)))
                    perp = abs((ay1 + ay2) / 2 - (by1 + by2) / 2)
                else:
                    along = _overlap((min(ay1, ay2), max(ay1, ay2)), (min(by1, by2), max(by1, by2)))
                    perp = abs((ax1 + ax2) / 2 - (bx1 + bx2) / 2)
                if perp < cav_tol and along > 1.0 * 1000 * self.mm and (a, b) not in seen:
                    seen.add((a, b))
                    self.errors.append(
                        f"[GI-12] parallel interior walls {wa.GlobalId[:8]}#{wa.id()} & "
                        f"{wb.GlobalId[:8]}#{wb.id()} only {perp / self.mm:.0f}mm apart over "
                        f"{along / self.mm:.0f}mm — sealed cavity ('small wall inside a wall'); "
                        f"size the stair to fit existing walls instead")

        # GI-13: 疏散梯侧边对齐（直跑梯周围须有墙；spiral/cantilever/escalator 豁免）
        # 轻量兜底：schema 的 shaft 轴线索引已从源头让疏散梯天然贴墙，此处只拦"明显悬空"。
        # 仅 STRAIGHT 直跑查（spiral/curved 豁免）；escalator 是 IfcBuildingElementProxy 不在 stairs 内天然豁免。
        # warning 非 error：cantilever 直跑可能合法悬空，留 LLM 判断。
        for sf in stairs:
            predef = getattr(sf, "PredefinedType", None)
            if predef not in (None, "STRAIGHT", "NOTDEFINED"):
                continue
            if not self._wall_segs:
                continue
            sx, sy, _ = _world_pos(sf)
            best_d = float("inf")
            for _, x1, y1, x2, y2 in self._wall_segs:
                dx, dy = x2 - x1, y2 - y1
                L2 = dx * dx + dy * dy
                t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((sx - x1) * dx + (sy - y1) * dy) / L2))
                d = ((sx - (x1 + t * dx)) ** 2 + (sy - (y1 + t * dy)) ** 2) ** 0.5
                if d < best_d:
                    best_d = d
            if best_d > 1.5:
                self.warnings.append(
                    f"[GI-13] stair flight {sf.GlobalId[:8]}#{sf.id()} >1.5m from nearest wall — "
                    f"if egress, use a wall-bound shaft (schema shaft axis indices); "
                    f"open/cantilever/spiral stairs ignore this warning")

    # ── GI-09/10/11/12 辅助 ──
    def _flight_height(self, st):
        if not st.Representation:
            return 0.0
        for rep in st.Representation.Representations:
            if rep.RepresentationIdentifier != "Body":
                continue
            for item in rep.Items:
                if item.is_a("IfcExtrudedAreaSolid"):
                    return float(item.Depth)
        return 0.0

    def _wall_orient_endpoints(self, wall):
        """墙轴线两端点(世界 2D)+ 走向('X' 沿 X / 'Y' 沿 Y)。GI-12 平行夹腔检测用。"""
        ep = self._wall_endpoints(wall)
        if not ep:
            return None
        (x1, y1), (x2, y2) = ep
        orient = "X" if abs(x2 - x1) >= abs(y2 - y1) else "Y"
        return ((x1, y1), (x2, y2), orient)

    # ── GI-10 / 楼板面积辅助 ──
    def _envelope_polygon_area(self, ext_walls):
        """外墙轴线首尾相接成闭合多边形 → shoelace 面积(模型单位²,含凹形庭院)。"""
        segs = []
        for w in ext_walls:
            ep = self._wall_endpoints(w)
            if ep:
                segs.append([(float(ep[0][0]), float(ep[0][1])), (float(ep[1][0]), float(ep[1][1]))])
        if len(segs) < 3:
            return None
        snap = 300 * self.mm
        poly = list(segs[0])
        used = {0}
        guard = 0
        while len(used) < len(segs) and guard < len(segs) * 2 + 4:
            guard += 1
            last = poly[-1]
            found = False
            for i, s in enumerate(segs):
                if i in used:
                    continue
                if (s[0][0] - last[0]) ** 2 + (s[0][1] - last[1]) ** 2 <= snap * snap:
                    poly.append(s[1]); used.add(i); found = True; break
                if (s[1][0] - last[0]) ** 2 + (s[1][1] - last[1]) ** 2 <= snap * snap:
                    poly.append(s[0]); used.add(i); found = True; break
            if not found:
                break
        n = len(poly)
        area = 0.0
        for i in range(n):
            x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
            area += x1 * y2 - x2 * y1
        return abs(area) / 2.0

    def _curve_area(self, curve):
        pts = None
        if curve.is_a("IfcPolyline"):
            pts = [p.Coordinates for p in curve.Points]
        elif curve.is_a("IfcIndexedPolyCurve"):
            pts = list(curve.Points.CoordList)
        if not pts or len(pts) < 3:
            return 0.0
        n = len(pts)
        area = 0.0
        for i in range(n):
            x1, y1 = pts[i][0], pts[i][1]
            x2, y2 = pts[(i + 1) % n][0], pts[(i + 1) % n][1]
            area += x1 * y2 - x2 * y1
        return abs(area) / 2.0

    def _profile_area(self, prof):
        if prof.is_a("IfcRectangleProfileDef"):
            return float(prof.XDim) * float(prof.YDim)
        curve = getattr(prof, "OuterCurve", None)
        if curve is not None:
            return self._curve_area(curve)
        return 0.0

    def _opening_area(self, opening):
        if not opening.Representation:
            return 0.0
        for rep in opening.Representation.Representations:
            if rep.RepresentationIdentifier != "Body":
                continue
            for item in rep.Items:
                if item.is_a("IfcExtrudedAreaSolid"):
                    return self._profile_area(item.SweptArea)
        return 0.0

    def _slab_net_floor_area(self, slab):
        """楼板净面积 = 轮廓外圈 − 内孔(WithVoids) − IfcOpeningElement 开洞(Method B)。"""
        outer = voids = 0.0
        if slab.Representation:
            for rep in slab.Representation.Representations:
                if rep.RepresentationIdentifier != "Body":
                    continue
                for item in rep.Items:
                    if not item.is_a("IfcExtrudedAreaSolid"):
                        continue
                    prof = item.SweptArea
                    outer = self._profile_area(prof)
                    if prof.is_a("IfcArbitraryProfileDefWithVoids"):
                        for ic in prof.InnerCurves:
                            voids += self._curve_area(ic)
                    break
                break
        for op in ifcopenshell.util.element.get_openings(slab):
            voids += self._opening_area(op)
        return max(outer - voids, 0.0)

    def _wall_thickness(self, wall) -> float:
        """墙厚(模型单位): Body SweptSolid 轮廓 y 跨度;矩形轮廓读 YDim。"""
        if wall.Representation:
            for rep in wall.Representation.Representations:
                if rep.RepresentationIdentifier != "Body":
                    continue
                for item in rep.Items:
                    if not item.is_a("IfcExtrudedAreaSolid"):
                        continue
                    prof = item.SweptArea
                    if prof.is_a("IfcRectangleProfileDef"):
                        return float(prof.YDim)
                    curve = getattr(prof, "OuterCurve", None)
                    pts = None
                    if curve is not None:
                        if curve.is_a("IfcPolyline"):
                            pts = [p.Coordinates for p in curve.Points]
                        elif curve.is_a("IfcIndexedPolyCurve"):
                            pts = list(curve.Points.CoordList)
                    if pts:
                        ys = [p[1] for p in pts]
                        return max(ys) - min(ys)
        return 200.0 * self.mm  # 默认 200mm

    def _slab_depth(self, slab) -> float:
        """获取板厚(模型单位)。"""
        if slab.Representation:
            for rep in slab.Representation.Representations:
                for item in rep.Items:
                    if hasattr(item, "Depth") and item.Depth is not None:
                        return float(item.Depth)
        return 150.0 * self.mm  # 默认 150mm

    # ═══ GEO Body 几何存在性 ═══
    def _check_geometry_presence(self):
        """检查所有产品都有 Body 几何,门窗有洞口链接。"""
        for wall in self.model.by_type("IfcWall"):
            if not _has_body(wall):
                self.errors.append(f"[GEO] wall {wall.GlobalId[:8]}#{wall.id()} has no body geometry")

        for door in self.model.by_type("IfcDoor"):
            if not _has_body(door):
                self.errors.append(f"[GEO] door {door.GlobalId[:8]}#{door.id()} has no body geometry")
        # NOTE: door/window 的 FillsVoids 链接由 GI-02 三级判定（有链 OK / 几何近 warning / 几何远 error），
        # 此处不重复——否则同一个 floating window 会被 GI-02 判 error、GEO 判 warning（严重性矛盾）。

        for window in self.model.by_type("IfcWindow"):
            if not _has_body(window):
                self.errors.append(f"[GEO] window {window.GlobalId[:8]}#{window.id()} has no body geometry")

        for opening in self.model.by_type("IfcOpeningElement"):
            if not _has_body(opening):
                self.errors.append(f"[GEO] opening {opening.GlobalId[:8]}#{opening.id()} has no body geometry")
            if not opening.VoidsElements:
                self.errors.append(f"[GEO] opening {opening.GlobalId[:8]}#{opening.id()} not linked to any wall")

        # 排除 IfcCurtainWall——聚合体,几何在 Plate/Member 上
        for cls in ("IfcColumn", "IfcBeam", "IfcSlab", "IfcStairFlight", "IfcRailing",
                    "IfcRoof", "IfcPlate", "IfcMember"):
            for e in _by_type_safe(self.model, cls):
                if not _has_body(e):
                    self.errors.append(f"[GEO] {cls} {e.GlobalId[:8]}#{e.id()} has no body geometry")

    # ═══ PR 比例规则 ═══
    def _check_proportion_rules(self):
        storeys = self.model.by_type("IfcBuildingStorey")
        windows = self.model.by_type("IfcWindow")
        walls = self.model.by_type("IfcWall")

        # PR-01: 窗墙比(按层)
        thresholds = {"residential": (0.15, 0.40), "office": (0.30, 0.70),
                      "school": (0.25, 0.50), "retail": (0.40, 0.80), "public": (0.25, 0.70)}
        lo, hi = thresholds.get(self.building_type, (0.25, 0.70))
        for st in storeys:
            st_windows = [w for w in windows if self._in_storey(w, st)]
            # WWR 是立面指标:只计外墙(否则内隔墙/核心筒会稀释真实窗墙比)
            st_walls = [w for w in walls if self._in_storey(w, st) and self._is_exterior_wall(w)]
            win_area = sum(self._window_area(w) for w in st_windows)
            wall_area = sum(self._wall_area(w) for w in st_walls)
            if wall_area > 0:
                ratio = win_area / wall_area
                if ratio < lo:
                    self.errors.append(
                        f"[PR-01] {st.Name} window-to-wall ratio {ratio:.2f} below min {lo} "
                        f"(daylight deficit: {win_area:.1f}/{wall_area:.1f} m²)")
                elif ratio > hi:
                    self.errors.append(
                        f"[PR-01] {st.Name} window-to-wall ratio {ratio:.2f} above max {hi} "
                        f"(excessive glazing: {win_area:.1f}/{wall_area:.1f} m²)")

        # PR-02: 柱间距
        columns = self.model.by_type("IfcColumn")
        if len(columns) >= 4:
            centers = [(_world_pos(c)[0], _world_pos(c)[1]) for c in columns]
            grid_snap = 100 * self.mm
            xs = sorted(set(round(x / grid_snap) * grid_snap for x, y in centers))
            ys = sorted(set(round(y / grid_snap) * grid_snap for x, y in centers))
            for dim, vals in [("X", xs), ("Y", ys)]:
                if len(vals) >= 2:
                    spacings = np.diff(vals) / self.mm / 1000.0  # 模型单位 → m
                    spacings = spacings[spacings >= 3.0]
                    lo, hi = (3.0, 9.0) if self.building_type == "residential" else (6.0, 12.0)
                    if len(spacings) > 0:
                        if np.any(spacings < lo):
                            self.errors.append(
                                f"[PR-02] column spacing {dim}: {np.min(spacings):.1f}m below min {lo}m")
                        if np.any(spacings > hi):
                            self.errors.append(
                                f"[PR-02] column spacing {dim}: {np.max(spacings):.1f}m above max {hi}m")

        # PR-03: 层高(首层允许挑高 5.5m,其他层 3.3-4.5m)
        ordered = sorted([s for s in storeys if s.Elevation is not None],
                         key=lambda s: s.Elevation)
        for i in range(len(ordered) - 1):
            h = (ordered[i + 1].Elevation - ordered[i].Elevation) / self.mm / 1000.0  # 模型单位 → m
            is_ground = (i == 0)
            if self.building_type == "residential":
                lo, hi = (2.8, 5.5) if is_ground else (2.8, 4.5)
            else:
                lo, hi = (3.3, 5.5) if is_ground else (3.3, 4.5)
            if h < lo:
                self.errors.append(
                    f"[PR-03] {ordered[i].Name}→{ordered[i+1].Name} height {h:.1f}m below min {lo}m")
            elif h > hi:
                self.errors.append(
                    f"[PR-03] {ordered[i].Name}→{ordered[i+1].Name} height {h:.1f}m above max {hi}m")

        # PR-04: 板厚
        for slab in self.model.by_type("IfcSlab"):
            if slab.Representation:
                for rep in slab.Representation.Representations:
                    for item in rep.Items:
                        if hasattr(item, "Depth") and item.Depth is not None:
                            d = item.Depth / self.mm / 1000.0  # 模型单位 → m
                            if d < 0.10:
                                self.errors.append(f"[PR-04] slab {slab.Name} depth {d:.2f}m below min 0.10m")
                            elif d > 0.25:
                                self.warnings.append(f"[PR-04] slab {slab.Name} depth {d:.2f}m above max 0.25m")

    # ═══ RH 韵律规则 ═══
    def _check_rhythm_rules(self):
        columns = self.model.by_type("IfcColumn")
        if len(columns) >= 4:
            centers = [(_world_pos(c)[0], _world_pos(c)[1]) for c in columns]
            grid_snap = 100 * self.mm
            xs = sorted(set(round(x / grid_snap) * grid_snap for x, y in centers))
            ys = sorted(set(round(y / grid_snap) * grid_snap for x, y in centers))
            for dim, vals in [("X", xs), ("Y", ys)]:
                if len(vals) >= 3:
                    spacings = np.diff(vals)
                    spacings = spacings[spacings >= 3000 * self.mm]
                    if len(spacings) > 1 and np.mean(spacings) > 0:
                        cv = np.std(spacings) / np.mean(spacings)
                        if cv > 0.10:
                            self.errors.append(
                                f"[RH-02] column grid {dim} CV {cv:.2f} exceeds max 0.10")

    # ═══ MC 材质规则 ═══
    def _check_material_rules(self):
        walls = self.model.by_type("IfcWall")
        if len(walls) >= 2:
            # MC-01: 基座-主体对比(L1 vs L2+)
            l1_walls = [w for w in walls if abs(_world_pos(w)[2]) < 100 * self.mm]
            l2_walls = [w for w in walls
                        if abs(_world_pos(w)[2] - 3300 * self.mm) < 500 * self.mm]
            if l1_walls and l2_walls:
                m1 = _get_material_safe(l1_walls[0])
                m2 = _get_material_safe(l2_walls[0])
                n1 = m1.Name if m1 and hasattr(m1, "Name") else None
                n2 = m2.Name if m2 and hasattr(m2, "Name") else None
                if n1 and n2 and n1 == n2:
                    self.warnings.append(
                        "[MC-01] base-body: no material contrast between L1 and L2")

        # MC-03: 材质数量
        materials = self.model.by_type("IfcMaterial")
        if len(materials) < 3:
            self.warnings.append(
                f"[MC-03] material count {len(materials)} below min 3")

    # ═══ FD 立面深度规则 ═══
    def _check_facade_depth_rules(self):
        # FD-01: 窗退入墙面深度(需详细几何分析,stub)
        pass

    # CP-02 (入口强调) 与 SQ-01 (中庭) 已移除：
    # - CP-02 旧实现 has_canopy 硬编码 False → 每次必报 warning（假阳性噪声）；检测入口强调需语义识别，留待后续实现
    # - SQ-01 旧实现仅按"层数≥3"判中庭缺失，小建筑误报；中庭应按"面积+进深"占比判，实现复杂，移除
    # 文档 SPATIAL_QUALITY.md 的 CP-02/SQ-01 规则保留作 design-time 参考，不自动检查


    # ═══ 可选: 碰撞检查(P2,需几何内核) ═══
    def check_clashes(self, classes=("IfcWall", "IfcSlab", "IfcColumn", "IfcBeam")) -> dict:
        """对指定类构件逐个跑 ifcquery.clash.clash(storey scope)。返回 {element_id: result}。"""
        from ifcquery import clash as clash_mod
        results = {}
        for cls in classes:
            for e in self.model.by_type(cls):
                r = clash_mod.clash(self.model, e, scope="storey")
                if r.get("pass") is False:
                    results[e.id()] = r
        return results

    def _check_clashes(self, classes=("IfcWall", "IfcSlab", "IfcColumn", "IfcBeam")):
        """CLASH 穿模检查（常规，纳入 run）：构件几何相交 → warning。
        ⚠ 已知局限：ifcquery.clash 默认 tolerance 2mm，只查几何相交，**不区分"正常结构接合"
        （墙-墙 T 接/L 接、墙-板接合、梁搭柱）与"异常穿模"** → 正常接合也会触发（假阳性）。
        故报 warning（非 error，不阻断交付），需人工复核；过滤明显的自交噪声（partner==自身）。
        ifcquery 不可用 → info 跳过（降级，不阻断主流程）。"""
        try:
            from ifcquery import clash as clash_mod
        except ImportError:
            self.info.append("[CLASH] clash check skipped: ifcquery not available in this env")
            return
        for cls in classes:
            for e in _by_type_safe(self.model, cls):
                try:
                    r = clash_mod.clash(self.model, e, scope="storey")
                except Exception:
                    continue  # 单元素 clash 失败不阻断整体
                if r.get("pass") is False:
                    clashes = r.get("checks", {}).get("intersection", {}).get("clashes", [])
                    # 过滤自交噪声（partner == 自身：ifcquery 偶把元素和自己的表示报 clash）
                    partners = []
                    for c in clashes:
                        el = c.get("element", {})
                        if el.get("id") == e.id():
                            continue
                        partners.append(f"#{el.get('id', '?')} {el.get('name', '')}".strip())
                    if not partners:
                        continue  # 全是自交，不报
                    self.warnings.append(
                        f"[CLASH] {e.is_a()} {e.GlobalId[:8]}#{e.id()} geometrically intersects "
                        f"{', '.join(partners[:3])} — incl. normal joints (T/slab), review for real penetration")

    # ═══ 辅助方法 ═══
    def _in_storey(self, element, storey):
        """判断元素是否属于某层(container 优先,z 坐标兜底)。"""
        try:
            container = _get_container_safe(element)
            if container is not None:
                return container.id() == storey.id()
            z = _world_pos(element)[2]
            if storey.Elevation is None:
                return False
            return abs(z - storey.Elevation) < 1000 * self.mm
        except Exception:
            return False

    def _window_area(self, window):
        """估算窗面积(m²)。"""
        if window.OverallHeight and window.OverallWidth:
            return (window.OverallHeight * window.OverallWidth) / (self.mm ** 2) / 1e6  # 模型单位² → m²
        return 2.0  # 默认估算

    def _wall_area(self, wall):
        """墙面积(m²)= Body 轮廓长度 × 挤出高度(模型单位→m²)。"""
        if wall.Representation:
            for rep in wall.Representation.Representations:
                if rep.RepresentationIdentifier != "Body":
                    continue
                for item in rep.Items:
                    if not item.is_a("IfcExtrudedAreaSolid"):
                        continue
                    depth = float(item.Depth)
                    prof = item.SweptArea
                    length = None
                    if prof.is_a("IfcRectangleProfileDef"):
                        length = float(prof.XDim)
                    else:
                        curve = getattr(prof, "OuterCurve", None)
                        coords = None
                        if curve is not None:
                            if curve.is_a("IfcPolyline"):
                                coords = [p.Coordinates for p in curve.Points]
                            elif curve.is_a("IfcIndexedPolyCurve"):
                                coords = list(curve.Points.CoordList)
                        if coords:
                            xs = [c[0] for c in coords]
                            length = max(xs) - min(xs)
                    if length is not None:
                        return (length * depth) / (self.mm ** 2) / 1e6
        return 10.0  # 兜底(无 Body 几何的墙)


def _default_out_dir() -> Path:
    """analysis_results/ 位于 AI_IFC 根目录(skills/aiifc/references/docs/flows/ 上五级)。"""
    try:
        return Path(__file__).resolve().parents[5] / "analysis_results"
    except Exception:
        return Path.cwd() / "analysis_results"


def run(model_or_path, building_type: str = "public", model_name: str = None,
        out_dir: str | Path = None, write_json: bool = None) -> dict:
    """
    统一入口: 接受 model 对象或 IFC 文件路径,返回审查报告。

    :param model_or_path: ifcopenshell.file 或 IFC 文件路径
    :param building_type: residential | office | school | retail | public
    :param model_name: 输出 JSON 的文件名前缀;传路径时默认为文件 stem
    :param out_dir: JSON 输出目录(默认 AI_IFC/analysis_results/)
    :param write_json: 是否写 JSON;默认路径输入时写、model 对象输入时不写
                       (model 对象想写需传 model_name)
    """
    path = None
    if isinstance(model_or_path, (str, Path)):
        path = Path(model_or_path)
        model = ifcopenshell.open(str(path))
        if model_name is None:
            model_name = path.stem
        if write_json is None:
            write_json = True
    else:
        model = model_or_path
        if write_json is None:
            write_json = model_name is not None

    reviewer = DesignReviewer(model, building_type)
    report = reviewer.run()
    if path:
        report["model"] = str(path)

    if write_json and model_name:
        out = Path(out_dir) if out_dir else _default_out_dir()
        out.mkdir(parents=True, exist_ok=True)
        out_path = out / f"{model_name}_analysis.json"
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str),
                            encoding="utf-8")
        report["json_path"] = str(out_path)

    return report


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        print("Usage: python design_review.py <model.ifc> [building_type] [--out DIR] [--no-json] [--clash]")
        print("  building_type: residential | office | school | retail | public")
        sys.exit(1)
    path = args[0]
    btype = args[1] if len(args) > 1 else "public"
    out_dir = None
    if "--out" in sys.argv:
        out_dir = sys.argv[sys.argv.index("--out") + 1]

    report = run(path, btype, out_dir=out_dir, write_json="--no-json" not in flags)

    print(f"[DESIGN REVIEW] {path}")
    print(f"  Type: {btype} | Schema: {report['schema']} | Unit scale: {report['length_unit_scale_mm']}")
    print(f"  {report['summary']}")
    if report["errors"]:
        print("\nERRORS:")
        for e in report["errors"]:
            print(f"  {e}")
    if report["warnings"]:
        print("\nWARNINGS:")
        for w in report["warnings"]:
            print(f"  {w}")
    if report["info"]:
        print("\nINFO:")
        for i in report["info"]:
            print(f"  {i}")

    # --clash 已废弃：CLASH 检查现已纳入 run() 主流程（→ WARNINGS [CLASH]，含正常接合假阳性）。
    # 保留 flag 向后兼容，复用 report 已有结果，不重跑。
    if "--clash" in flags:
        clash_warns = [w for w in report["warnings"] if w.startswith("[CLASH]")]
        if clash_warns:
            print(f"\nCLASHES (穿模，含正常接合假阳性，需复核): {len(clash_warns)} elements")
            for w in clash_warns[:10]:
                print(f"  {w}")
        elif any("clash check skipped" in i for i in report["info"]):
            print("\nCLASHES: skipped (ifcquery not available)")
        else:
            print("\nCLASHES: 0 (no geometric intersection)")

    if report.get("json_path"):
        print(f"\n→ {report['json_path']}")
    sys.exit(0 if report["ok"] else 1)

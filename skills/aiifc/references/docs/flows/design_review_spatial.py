"""
design_review_spatial.py — error 构件自动深挖 + SS 空间结构完整性检查（SpatialReviewMixin）。

拆分自 design_review.py（W-0049 文件行数门控），mixin 由 flows.design_review.DesignReviewer 组合。
"""

import re

try:  # 包内导入
    from flows.design_review_utils import (
        _scan_element, _world_pos, _get_container_safe, _by_type_safe,
    )
except ImportError:  # 独立运行
    from design_review_utils import (
        _scan_element, _world_pos, _get_container_safe, _by_type_safe,
    )


class SpatialReviewMixin:
    """error 深挖（_collect_error_details/_nearest_wall）+ SS-01~06 空间结构检查。"""

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

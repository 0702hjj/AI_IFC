"""
design_review_measure.py — 面积/厚度量取辅助 + GEO Body 几何存在性检查（MeasureMixin）。

拆分自 design_review.py（W-0049 文件行数门控），mixin 由 flows.design_review.DesignReviewer 组合。
"""

import ifcopenshell.util.element

try:  # 包内导入
    from flows.design_review_utils import _has_body, _by_type_safe
except ImportError:  # 独立运行
    from design_review_utils import _has_body, _by_type_safe


class MeasureMixin:
    """轮廓/板面积、墙厚/板厚等量取辅助 + GEO has_body 检查。"""

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

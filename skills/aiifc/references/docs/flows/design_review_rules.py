"""
design_review_rules.py — PR/RH/MC/FD 设计规则 + CLASH 碰撞检查（DesignRulesMixin）。

拆分自 design_review.py（W-0049 文件行数门控），mixin 由 flows.design_review.DesignReviewer 组合。
"""

import numpy as np

try:  # 包内导入
    from flows.design_review_utils import (
        _world_pos, _get_container_safe, _get_material_safe, _by_type_safe,
    )
except ImportError:  # 独立运行
    from design_review_utils import (
        _world_pos, _get_container_safe, _get_material_safe, _by_type_safe,
    )


class DesignRulesMixin:
    """PR-01~04 比例 / RH-02 韵律 / MC-01·03 材质 / FD(stub) / CLASH 穿模。"""

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

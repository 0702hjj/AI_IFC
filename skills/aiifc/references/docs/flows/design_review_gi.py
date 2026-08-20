"""
design_review_gi.py — GI-01~13 几何完整性规则（GeometricIntegrityMixin）。

拆分自 design_review.py（W-0049 文件行数门控），mixin 由 flows.design_review.DesignReviewer 组合。
"""

import numpy as np
import ifcopenshell.util.placement
import ifcopenshell.util.element

try:  # 包内导入
    from flows.design_review_utils import (
        _world_pos, _get_psets_safe, _get_container_safe, _by_type_safe, _overlap,
    )
except ImportError:  # 独立运行
    from design_review_utils import (
        _world_pos, _get_psets_safe, _get_container_safe, _by_type_safe, _overlap,
    )


class GeometricIntegrityMixin:
    """GI-01~13: 包络闭合/窗贴墙/楼梯开洞/洞口包含/墙贴板/柱贴板/填充居墙/楼板覆盖/楼梯联通/夹腔/梯贴墙。"""

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

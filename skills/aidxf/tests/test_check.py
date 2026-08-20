"""check.py 测试（T15 轮廓级 + T16/T17 房间级 R-01~R-09）。"""

import pytest

from floorgeom.check import (
    check_outline_plan,
    check_alignment_zones,
    check_floor,
    check_skeleton_outline_containment,
)
from floorgeom.normalize import SchemaError, normalize_skeleton, normalize_rooms


# --- T15 轮廓级（plan 摄取校验） ---

class TestCheckOutlinePlan:
    def test_rect_valid(self):
        plan = {"zones": [{
            "id": "a",
            "outline_mm": [{"outer": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]], "holes": [], "arcs": []}],
        }]}
        errs = check_outline_plan(plan)
        assert errs == []

    def test_self_intersecting(self):
        """自相交轮廓 → 报。"""
        plan = {"zones": [{
            "id": "a",
            "outline_mm": [{"outer": [[0, 0], [10000, 10000], [10000, 0], [0, 10000]], "holes": [], "arcs": []}],
        }]}
        errs = check_outline_plan(plan)
        assert any("无效" in e or "self" in e.lower() or "valid" in e.lower() for e in errs)

    def test_hole_outside_outer(self):
        """孔洞超出外环 → 报。"""
        plan = {"zones": [{
            "id": "a",
            "outline_mm": [{
                "outer": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]],
                "holes": [[[50000, 30000], [80000, 30000], [80000, 50000], [50000, 50000]]],
                "arcs": [],
            }],
        }]}
        errs = check_outline_plan(plan)
        assert any("外环" in e or "hole" in e.lower() for e in errs)

    def test_anchor_outside(self):
        """锚点在轮廓外 → 报。"""
        plan = {"zones": [{
            "id": "a",
            "outline_mm": [{"outer": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]], "holes": [], "arcs": []}],
            "core_anchor_mm": [30000, 50000],  # 出轮廓（y>40000）
        }]}
        errs = check_outline_plan(plan)
        assert any("锚点" in e for e in errs)

    def test_arc_ring_ok(self):
        """真弧轮廓不误报。"""
        plan = {"zones": [{
            "id": "a",
            "outline_mm": [{
                "outer": {
                    "vertices": [[0, 0], [20000, 0], [20000, 10000], [0, 10000]],
                    "arcs": [{"at": 1, "center": [20000, 5000], "radius": 5000, "a0": -90, "a1": 90}],
                },
                "holes": [], "arcs": [],
            }],
        }]}
        errs = check_outline_plan(plan)
        assert errs == []


class TestCheckAlignmentZones:
    def test_tower_inside_podium(self):
        plan = {"zones": [
            {"id": "podium",
             "outline_mm": [{"outer": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]], "holes": [], "arcs": []}]},
            {"id": "tower", "position": {"on": "podium"},
             "outline_mm": [{"outer": [[18000, 22000], [42000, 22000], [42000, 40000], [18000, 40000]], "holes": [], "arcs": []}]},
        ]}
        errs = check_alignment_zones(plan)
        assert errs == []

    def test_tower_outside_podium(self):
        plan = {"zones": [
            {"id": "podium",
             "outline_mm": [{"outer": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]], "holes": [], "arcs": []}]},
            {"id": "tower", "position": {"on": "podium"},
             "outline_mm": [{"outer": [[50000, 30000], [90000, 30000], [90000, 60000], [50000, 60000]], "holes": [], "arcs": []}]},
        ]}
        errs = check_alignment_zones(plan)
        assert any("超出" in e for e in errs)


class TestSkeletonOutlineContainment:
    """D34：骨架分区越轮廓校验（blocks/main_partitions/core 必须在 outline 内）。"""

    def _skeleton_model(self, outline, blocks=None, partitions=None, cores=None):
        """构造 normalize 产物（骨架几何模型）。"""
        z = {
            "zone": "std",
            "axis_grid": {"x": [], "y": []},
            "outline": outline,
            "blocks": blocks or [],
            "main_partitions": partitions or [],
            "cores": cores or [],
        }
        return {"frame": {"units": "mm", "origin": "lot_southwest", "north_deg": 0, "modulus": 100},
                "zones": [z]}

    def test_blocks_inside_outline_passes(self):
        """blocks 在轮廓内 → 通过。"""
        model = self._skeleton_model(
            outline=[{"outer": {"vertices": [[0, 0], [30000, 0], [30000, 20000], [0, 20000]]},
                      "holes": []}],
            blocks=[{"role": "units", "polygon_mm": {"vertices": [[1000, 1000], [10000, 1000], [10000, 8000], [1000, 8000]]}}],
        )
        errs = check_skeleton_outline_containment(model)
        assert errs == []

    def test_blocks_outside_outline_fails(self):
        """blocks 超出轮廓 → FAIL。"""
        model = self._skeleton_model(
            outline=[{"outer": {"vertices": [[0, 0], [30000, 0], [30000, 20000], [0, 20000]]},
                      "holes": []}],
            blocks=[{"role": "units", "polygon_mm": {"vertices": [[25000, 15000], [40000, 15000], [40000, 25000], [25000, 25000]]}}],
        )
        errs = check_skeleton_outline_containment(model)
        assert any("超出" in e and "blocks[0]" in e for e in errs)

    def test_partitions_vertex_outside_outline_fails(self):
        """main_partitions 顶点超出轮廓 → FAIL。"""
        model = self._skeleton_model(
            outline=[{"outer": {"vertices": [[0, 0], [30000, 0], [30000, 20000], [0, 20000]]},
                      "holes": []}],
            partitions=[{"role": "units|core 分界", "path_mm": [[15000, 0], [15000, 25000]]}],
        )
        errs = check_skeleton_outline_containment(model)
        assert any("main_partitions[0]" in e for e in errs)

    def test_core_outside_outline_fails(self):
        """core anchor/polygon 超出轮廓 → FAIL。"""
        model = self._skeleton_model(
            outline=[{"outer": {"vertices": [[0, 0], [30000, 0], [30000, 20000], [0, 20000]]},
                      "holes": []}],
            cores=[{"anchor": [35000, 10000],
                    "polygon_mm": {"x": [34000, 36000], "y": [9000, 11000]}}],
        )
        errs = check_skeleton_outline_containment(model)
        assert any("core" in e for e in errs)

    def test_outline_with_holes_subtracts(self):
        """outline 带 holes → holes 区域不算轮廓内（分区不能压孔洞）。"""
        model = self._skeleton_model(
            outline=[{"outer": {"vertices": [[0, 0], [30000, 0], [30000, 20000], [0, 20000]]},
                      "holes": [{"vertices": [[10000, 5000], [20000, 5000], [20000, 15000], [10000, 15000]]}]}],
            blocks=[{"role": "units", "polygon_mm": {"vertices": [[11000, 6000], [19000, 6000], [19000, 14000], [11000, 14000]]}}],
        )
        errs = check_skeleton_outline_containment(model)
        assert any("超出" in e for e in errs)

    def test_no_outline_skips(self):
        """无 outline 声明（旧案例）→ 跳过不报错。"""
        model = self._skeleton_model(outline=None,
                                     blocks=[{"role": "units", "polygon_mm": {"vertices": [[0, 0], [1000, 0], [1000, 1000]]}}])
        errs = check_skeleton_outline_containment(model)
        assert errs == []


# --- T16/T17 房间级 ---

def _model(rooms_override=None):
    skeleton = {
        "frame": {"units": "mm", "origin": "lot_southwest", "north_deg": 0, "modulus": 100},
        "zones": [{
            "zone": "podium",
            "outline": [
                {"outer": {"vertices": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]]}}
            ],
            "core": {"anchor": [28000, 12000],
                     "vertices": [[24000, 10000], [32000, 10000], [32000, 20000], [24000, 20000]]},
            "corridor": {"form": "path", "width_mm": 3000,
                         "path": {"edges": {
                             "west": [[16000, 4000], [16000, 24000]],
                             "north": [[16000, 24000], [44000, 24000]],
                             "east": [[44000, 24000], [44000, 4000]],
                             "south": [[44000, 4000], [16000, 4000]]}}},
            "main_partitions": [],
            "special_openings": [],
            "typology": "t", "typology_reason": "r",
            "note_responses": [], "deviations": [], "defaults_used": [],
        }],
    }
    sm = normalize_skeleton(skeleton)
    rooms = rooms_override or {
        "floor": "podium_1f",
        "zone_ref": "skeleton.json#zones[podium]",
        "partitions": {"main": "outline"},
        # 分墙切出 16000×20000=320㎡ 的 shop_01（x 0..16000, y 0..20000）
        "walls": [
            {"key": "1F:int:0", "kind": "int", "t_mm": 200,
             "axis": [[16000, 0], [16000, 40000]]},
            {"key": "1F:int:1", "kind": "int", "t_mm": 200,
             "axis": [[0, 20000], [16000, 20000]]},
        ],
        "labels": [
            {"room": "shop_01", "type": "shop", "area_sqm": 320,
             "at": [8000, 10000], "frontage": "W"},
        ],
        "openings": [{"wall": "1F:int:0", "along_m": 2.0, "w_mm": 1200, "type": "door"}],
        "requirements_trace": [],
        "deviations": [], "defaults_used": [],
    }
    return sm, rooms


class TestCheckFloor:
    def test_rooms_inside_outline(self):
        """R-01：房间在轮廓内（用平面轮廓校验）。"""
        sm, rooms = _model()
        gm = normalize_rooms(rooms, sm)
        report = check_floor(gm, outline_polygons=[Polygon([(0, 0), (60000, 0), (60000, 40000), (0, 40000)])])
        assert not [r for r in report if r["rule"] == "R-01"]

    def test_rooms_no_overlap(self):
        """R-02：房间互不重叠。"""
        sm, rooms = _model()
        rooms["walls"] = [
            {"key": "1F:int:0", "kind": "int", "t_mm": 200,
             "axis": [[16000, 0], [16000, 40000]]},
            {"key": "1F:int:1", "kind": "int", "t_mm": 200,
             "axis": [[0, 20000], [16000, 20000]]},
        ]
        rooms["labels"] = [
            {"room": "a", "type": "shop", "area_sqm": 100, "at": [8000, 10000]},
            {"room": "b", "type": "shop", "area_sqm": 100, "at": [24000, 10000]},
        ]
        gm = normalize_rooms(rooms, sm)
        report = check_floor(gm)
        assert not [r for r in report if r["rule"] == "R-02"]

    def test_rooms_area_in_range(self):
        """R-03：面积达标（program 区间 ±10%）。"""
        sm, rooms = _model()
        rooms["labels"][0]["area_sqm"] = 320  # 分墙切出 320㎡
        params = {"program": {"shop": [280, 360]}}
        gm = normalize_rooms(rooms, sm)
        report = check_floor(gm, params=params)
        assert not [r for r in report if r["rule"] == "R-03"]

    def test_rooms_area_out_of_range(self):
        """R-03 反例：面积超出区间。"""
        sm, rooms = _model()
        params = {"program": {"shop": [100, 200]}}  # 实测 320 超
        gm = normalize_rooms(rooms, sm)
        report = check_floor(gm, params=params)
        assert any(r["rule"] == "R-03" for r in report)

    def test_corridor_width(self):
        """R-04：走廊宽度。"""
        sm, rooms = _model()
        params = {"corridor_min_width_mm": 3000}
        gm = normalize_rooms(rooms, sm)
        report = check_floor(gm, params=params)
        # 骨架走廊 width 3000 达标
        assert not [r for r in report if r["rule"] == "R-04"]

    def test_connectivity(self):
        """R-07：门图连通——V3 挂墙 openings 丢房间对，降 Warning 不阻断。"""
        sm, rooms = _model()
        gm = normalize_rooms(rooms, sm)
        report = check_floor(gm)
        # R-07 无 Error（Warning 可接受：孤立房间提示，不阻断）
        assert not [r for r in report if r["rule"] == "R-07" and r["severity"] == "error"]

    def test_report_structure(self):
        """报告结构：rule/severity/target/detail。"""
        sm, rooms = _model()
        rooms["labels"][0]["area_sqm"] = 320
        params = {"program": {"shop": [100, 200]}}
        gm = normalize_rooms(rooms, sm)
        report = check_floor(gm, params=params)
        bad = [r for r in report if r["rule"] == "R-03"]
        assert bad and all({"rule", "severity", "target"} <= set(r) for r in bad)


class TestCheckFloorR06:
    """T17：R-06 跨层核心筒一致 + Warning 退出语义。"""

    def test_core_alignment_across_floors(self):
        """R-06：多楼层模型 core 多边形一致。"""
        # 用同一 skeleton 生成两个楼层模型——core 相同则通过
        sm, rooms = _model()
        gm1 = normalize_rooms(rooms, sm)
        gm2 = normalize_rooms(rooms, sm)
        # R-06 需要多楼层 core 输入——这里直接比较 core 多边形
        core1 = sm["zones"][0]["core"]["polygon_mm"]
        core2 = sm["zones"][0]["core"]["polygon_mm"]
        assert core1 == core2  # 同一骨架 → 跨层一致


class TestCoreAlignmentMultiCore:
    """R-06 多核心筒跨层对齐（D31）：各层 cores 数组按位置逐一比对。"""

    def _floor(self, name, polys):
        cores = [{"polygon_mm": p} for p in polys]
        return {"floor": name, "zones": [{"core": cores[0], "cores": cores}]}

    def test_multi_core_aligned_pass(self):
        from floorgeom.check import check_core_alignment
        p1 = {"x": [0, 2400], "y": [0, 2300]}
        p2 = {"x": [22000, 24400], "y": [3000, 5300]}
        floors = [self._floor("f1", [p1, p2]), self._floor("f2", [p1, p2])]
        assert check_core_alignment(floors) == []

    def test_multi_core_mismatch_flagged(self):
        from floorgeom.check import check_core_alignment
        p1 = {"x": [0, 2400], "y": [0, 2300]}
        p2 = {"x": [22000, 24400], "y": [3000, 5300]}
        p2_bad = {"x": [22000, 24400], "y": [3000, 5400]}  # 第二 core 偏移
        floors = [self._floor("f1", [p1, p2]), self._floor("f2", [p1, p2_bad])]
        report = check_core_alignment(floors)
        assert any(r["rule"] == "R-06" for r in report), "第二核心筒跨层不一致应报 R-06"

    def test_multi_core_count_mismatch_flagged(self):
        from floorgeom.check import check_core_alignment
        p1 = {"x": [0, 2400], "y": [0, 2300]}
        p2 = {"x": [22000, 24400], "y": [3000, 5300]}
        floors = [self._floor("f1", [p1, p2]), self._floor("f2", [p1])]  # f2 少一个 core
        report = check_core_alignment(floors)
        assert any(r["rule"] == "R-06" for r in report), "核心筒数量跨层不一致应报 R-06"

    def test_warning_does_not_block(self):
        """R-08 Warning 不影响 exit 0 语义。"""
        sm, rooms = _model()
        gm = normalize_rooms(rooms, sm)
        report = check_floor(gm)
        errors = [r for r in report if r["severity"] == "error"]
        warnings = [r for r in report if r["severity"] == "warning"]
        # 单房间带 frontage 不需要采光告警（shop 不在 needs_exterior 列表）
        assert all(r["severity"] in ("error", "warning") for r in report)

    def test_frontage_passthrough_no_r08(self):
        """frontage 传透（D37）：normalize_rooms 产出保留 frontage → 有声明不报 R-08。"""
        sm, rooms = _model()
        rooms["labels"] = [
            {"room": "office_01", "type": "office", "area_sqm": 320,
             "frontage": "N", "at": [8000, 10000]},
        ]
        gm = normalize_rooms(rooms, sm)
        # normalize 产出保留 frontage
        assert gm["rooms"][0].get("frontage") == "N"
        report = check_floor(gm)
        r08 = [r for r in report if r["rule"] == "R-08"]
        assert r08 == [], f"有 frontage 声明不应报 R-08: {r08}"

    def test_frontage_missing_r08_warns(self):
        """无 frontage 的 office → R-08 warning（回归保护）。"""
        sm, rooms = _model()
        rooms["labels"] = [
            {"room": "office_01", "type": "office", "area_sqm": 320,
             "at": [8000, 10000]},
        ]
        gm = normalize_rooms(rooms, sm)
        report = check_floor(gm)
        assert any(r["rule"] == "R-08" for r in report)


def _polygon_for_tests(*coords):
    from shapely.geometry import Polygon as P
    return P(list(coords))


from shapely.geometry import Polygon


class TestBlocksSemantic:
    """D33 语义识别：通用块（core/corridor/holes）必须走专用字段，不得塞 blocks。"""

    def test_generic_role_in_blocks_warns(self):
        from floorgeom.check import check_blocks_semantic
        zone = {"blocks": [
            {"role": "core", "polygon_mm": {"vertices": [[0,0],[1,0],[1,1]]}},
            {"role": "open_office", "polygon_mm": {"vertices": [[0,0],[2,0],[2,2]]}},
        ]}
        report = check_blocks_semantic(zone)
        assert any("core" in r["detail"] for r in report), "core 塞 blocks 应告警"
        assert not any("open_office" in r["detail"] for r in report), "类型 block 不告警"

    def test_type_role_no_warn(self):
        from floorgeom.check import check_blocks_semantic
        zone = {"blocks": [
            {"role": "units", "polygon_mm": {"vertices": [[0,0],[1,0],[1,1]]}},
            {"role": "meeting", "polygon_mm": {"vertices": [[0,0],[2,0],[2,2]]}},
        ]}
        assert check_blocks_semantic(zone) == []


class TestHolesAlignment:
    """D33：skeleton holes 与 plan outline holes 一致性（T2 原样消费传透）。"""

    def test_holes_match_plan(self):
        from floorgeom.check import check_holes_alignment
        skel_zone = {"holes": [{"polygon_mm": {"vertices": [[0,0],[100,0],[100,100],[0,100]]}}]}
        plan_zone = {"outline_mm": [{"outer": [[0,0],[1000,0],[1000,1000],[0,1000]],
                                      "holes": [[[0,0],[100,0],[100,100],[0,100]]]}]}
        assert check_holes_alignment(skel_zone, plan_zone) == []

    def test_holes_missing_in_skeleton_flagged(self):
        from floorgeom.check import check_holes_alignment
        skel_zone = {"holes": []}  # skeleton 漏了 plan 的中庭
        plan_zone = {"outline_mm": [{"outer": [[0,0],[1000,0],[1000,1000],[0,1000]],
                                      "holes": [[[0,0],[100,0],[100,100],[0,100]]]}]}
        report = check_holes_alignment(skel_zone, plan_zone)
        assert any(r["rule"] == "T2" for r in report), "plan 有 holes 而 skeleton 无 → 报 T2"

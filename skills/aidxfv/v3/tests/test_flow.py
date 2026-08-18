"""test_flow.py —— 模拟 skill 执行流程的端到端测验（W1 验收 + W5 冒烟雏形）。

场景：R-01 启发的独立住宅（L 形主楼 + 独立车库块）。
覆盖流程：S0 派生 → S0 摄取校验 → S1 骨架 normalize → S2 房间 normalize（五形式）
→ 机检 R-01~R-09 → 建造对账 reconcile（一致/不一致）→ 全流程确定性。

素材说明：形状取自 AI_CAD/data/floorplan_结构.dxf 的 A-FOOTPRINT（R-01），
坐标规范到正象限便于断言；保留 L 形主楼 + 车库块的形态特征。
"""

import pytest

from floorgeom.check import check_alignment_zones, check_floor, check_outline_plan
from floorgeom.derive import derive
from floorgeom.io import canon_bytes
from floorgeom.normalize import normalize_rooms, normalize_skeleton
from floorgeom.reconcile import reconcile
from floorgeom.room_graph import to_room_graph


# ---------------------------------------------------------------------------
# 场景素材：R-01 启发住宅
# ---------------------------------------------------------------------------

# 主楼 L 形（20m x 10m，右下缺 10m x 5m）+ 车库块（6m x 6m）
PLAN = {
    "version": 3,
    "project": "R01 启发住宅",
    "zones": [{
        "id": "house",
        "function": "residence",
        "floors": {"from": 1, "to": 1},
        "floor_height_mm": 3000,
        "outline_mm": [
            {
                "outer": [[0, 0], [20000, 0], [20000, 5000], [10000, 5000],
                          [10000, 10000], [0, 10000]],
                "holes": [],
                "arcs": [],
            },
            {
                "outer": [[20000, 0], [28000, 0], [28000, 6000], [20000, 6000]],
                "holes": [],
                "arcs": [],
            },
        ],
        "program": [
            {"room": "living", "count": 1, "area_sqm": [18, 30]},
            {"room": "bedroom", "count": 2, "area_sqm": [10, 16]},
            {"room": "kitchen", "count": 1, "area_sqm": [8, 14]},
            {"room": "bathroom", "count": 1, "area_sqm": [4, 12]},
            {"room": "garage", "count": 1, "area_sqm": [20, 40]},
        ],
    }],
}


# S1 主 agent 骨架声明（模拟 LLM 产出）
SKELETON = {
    "frame": {"units": "mm", "origin": "lot_southwest", "north_deg": 0, "modulus": 100},
    "zones": [{
        "zone": "house",
        "outline": [
            {"outer": {"vertices": [[0, 0], [20000, 0], [20000, 5000], [10000, 5000],
                                   [10000, 10000], [0, 10000]]}},
            {"outer": {"vertices": [[20000, 0], [28000, 0], [28000, 6000], [20000, 6000]]}},
        ],
        "core": None,  # G-01：住宅无核心筒
        "corridor": {
            "form": "path",
            "path": {"edges": {
                "west": [[6000, 2000], [6000, 8000]],
                "north": [[6000, 8000], [16000, 8000]],
                "east": [[16000, 8000], [16000, 2000]],
                "south": [[16000, 2000], [6000, 2000]]}},
            "width_mm": 1200,
        },
        "main_partitions": [],
        "special_openings": [],
        "typology": "单层住宅 L 形",
        "typology_reason": "edges 含南侧台阶，concave_corners 在右下，无孔",
        "note_responses": [],
        "deviations": [],
        "defaults_used": [],
    }],
}


# S2 rooms-worker 房间声明（模拟 LLM 产出）——D41 新结构：直接声明墙
ROOMS = {
    "floor": "house_1f",
    "zone_ref": "skeleton.json#zones[house]",
    "partitions": {"main": "outline"},
    "walls": [
        {"key": "1F:int:0", "kind": "int", "t_mm": 120,
         "axis": [[0, 2500], [20000, 2500]]},          # 下区北界（全宽）
        {"key": "1F:int:1", "kind": "int", "t_mm": 120,
         "axis": [[8000, 0], [8000, 2500]]},           # living/kitchen 分界
        {"key": "1F:int:2", "kind": "int", "t_mm": 120,
         "axis": [[12000, 0], [12000, 2500]]},         # kitchen/entry 分界
        {"key": "1F:int:3", "kind": "int", "t_mm": 120,
         "axis": [[0, 5000], [10000, 5000]]},          # 下区/上区分界（L 形台阶）
        {"key": "1F:int:4", "kind": "int", "t_mm": 120,
         "axis": [[4000, 5000], [4000, 7500]]},        # bathroom 东界
        {"key": "1F:int:5", "kind": "int", "t_mm": 120,
         "axis": [[0, 7500], [5000, 7500]]},           # bathroom/bedroom 下界
        {"key": "1F:int:6", "kind": "int", "t_mm": 120,
         "axis": [[5000, 5000], [5000, 10000]]},       # bedroom 分界（含空区东界）
        {"key": "1F:int:7", "kind": "int", "t_mm": 120,
         "axis": [[5000, 7500], [10000, 7500]]},       # bedroom_02 南界
        {"key": "1F:int:8", "kind": "int", "t_mm": 120,
         "axis": [[20000, 5000], [28000, 5000]]},      # 车库北界（8×5=40㎡）
    ],
    "labels": [
        {"room": "living_01", "type": "living", "area_sqm": 20,
         "at": [4000, 1250], "frontage": "S"},
        {"room": "kitchen_01", "type": "kitchen", "area_sqm": 10,
         "at": [10000, 1250]},
        {"room": "bedroom_01", "type": "bedroom", "area_sqm": 12,
         "at": [2500, 8750], "frontage": "N"},
        {"room": "bedroom_02", "type": "bedroom", "area_sqm": 12,
         "at": [7500, 8750], "frontage": "N"},
        {"room": "bathroom_01", "type": "bathroom", "area_sqm": 10,
         "at": [2000, 6250]},
        {"room": "entry_01", "type": "entry", "area_sqm": 8,
         "at": [16000, 1250]},
        {"room": "garage_01", "type": "garage", "area_sqm": 40,
         "at": [24000, 2500]},
    ],
    "openings": [
        {"wall": "1F:int:0", "along_m": 1.5, "w_mm": 900, "h_mm": 2100, "sill_mm": 0, "type": "door"},
        {"wall": "1F:int:0", "along_m": 8.0, "w_mm": 800, "h_mm": 2100, "sill_mm": 0, "type": "door"},
        {"wall": "1F:int:3", "along_m": 1.0, "w_mm": 900, "h_mm": 2100, "sill_mm": 0, "type": "door"},
        {"wall": "1F:int:4", "along_m": 1.5, "w_mm": 900, "h_mm": 2100, "sill_mm": 0, "type": "door"},
        {"wall": 0, "along_m": 18.0, "w_mm": 900, "h_mm": 2100, "sill_mm": 0, "type": "door"},
        {"wall": 1, "along_m": 0.8, "w_mm": 800, "h_mm": 2100, "sill_mm": 0, "type": "door"},
        {"wall": 1, "along_m": 1.4, "w_mm": 1000, "h_mm": 2100, "sill_mm": 0, "type": "door"},
    ],
    "requirements_trace": [
        {"requirement": "bedroom faces_south (must)",
         "satisfied_by": "bedroom_01..02 frontage=N（北带）——见骨架裁决"},
    ],
    "deviations": [],
    "defaults_used": [],
}


@pytest.fixture(scope="module")
def derived():
    return derive(PLAN)


@pytest.fixture(scope="module")
def skeleton_model():
    return normalize_skeleton(SKELETON)


def _normal_rooms():
    """正常版 rooms：bathroom 已是 between_axes（ROOMS 主 fixture 合规版）。"""
    return dict(ROOMS)


def _schema_error_rooms():
    """SchemaError 版：opening 挂不存在的墙 key（应回喂）。"""
    rooms = dict(ROOMS)
    rooms["openings"] = [
        {"wall": "1F:nope:9", "along_m": 1.0, "w_mm": 900, "type": "door"},
    ]
    return rooms


@pytest.fixture(scope="module")
def normal_rooms():
    return _normal_rooms()


# ---------------------------------------------------------------------------
# S0：派生
# ---------------------------------------------------------------------------

class TestFlowS0Derive:
    def test_floors_present(self, derived):
        assert "f1" in derived["floors"]

    def test_area_positive(self, derived):
        f = derived["floors"]["f1"]
        assert f["area_sqm"] > 0

    def test_edges_dirs(self, derived):
        f = derived["floors"]["f1"]
        assert any(e["dir"] in ("S", "N", "E", "W") for e in f["edges"])

    def test_concave_corner(self, derived):
        """L 形主楼有凹角。"""
        f = derived["floors"]["f1"]
        assert len(f["concave_corners"]) > 0

    def test_dominant_axes(self, derived):
        f = derived["floors"]["f1"]
        assert f["dominant_axes"]["x"] and f["dominant_axes"]["y"]

    def test_strip_area(self, derived):
        f = derived["floors"]["f1"]
        assert f["strip_area"]["per_m_x_sqm"] > 0


# ---------------------------------------------------------------------------
# S0：轮廓级摄取校验
# ---------------------------------------------------------------------------

class TestFlowS0OutlineCheck:
    def test_plan_passes_outline_check(self):
        assert check_outline_plan(PLAN) == []

    def test_plan_passes_alignment(self):
        assert check_alignment_zones(PLAN) == []

    def test_bad_plan_rejected(self):
        bad = {"zones": [{"id": "x", "outline_mm": [
            {"outer": [[0, 0], [10000, 10000], [10000, 0], [0, 10000]], "holes": [], "arcs": []},
        ]}]}
        assert check_outline_plan(bad) != []


# ---------------------------------------------------------------------------
# S1：骨架 normalize
# ---------------------------------------------------------------------------

class TestFlowS1Skeleton:
    def test_core_null_passthrough(self, skeleton_model):
        assert skeleton_model["zones"][0]["core"] is None


    def test_corridor_path(self, skeleton_model):
        """corridor ring_edges 分段 → path_mm 展开顶点。"""
        z = skeleton_model["zones"][0]
        assert z["corridor"]["form"] == "path"
        assert len(z["corridor"]["path_mm"]) >= 4


    def test_skeleton_deterministic(self):
        assert normalize_skeleton(SKELETON) == normalize_skeleton(SKELETON)


# ---------------------------------------------------------------------------
# S2：房间 normalize（五形式）
# ---------------------------------------------------------------------------

class TestFlowS2Rooms:
    @pytest.fixture
    def rooms_model(self, skeleton_model, normal_rooms):
        return normalize_rooms(normal_rooms, skeleton_model)

    def test_between_axes(self, rooms_model):
        k = next(r for r in rooms_model["rooms"] if r["id"] == "kitchen_01")
        # 新结构：多边形顶点（kitchen = x 8000..12000 × y 0..2500）
        verts = k["polygon_mm"]["vertices"]
        xs = sorted({round(v[0]) for v in verts})
        ys = sorted({round(v[1]) for v in verts})
        assert xs == [8000, 12000]
        assert ys == [0, 2500]

    def test_on_edge_after_chain(self, rooms_model):
        b1 = next(r for r in rooms_model["rooms"] if r["id"] == "bedroom_01")
        b2 = next(r for r in rooms_model["rooms"] if r["id"] == "bedroom_02")
        # 贴 N 边：b1 从 x=0 到 5000，b2 从 5000 到 10000
        xs1 = sorted({round(v[0]) for v in b1["polygon_mm"]["vertices"]})
        xs2 = sorted({round(v[0]) for v in b2["polygon_mm"]["vertices"]})
        # 节点化会引入中间断点（如 v2 与 h2 交点），只查边界范围
        assert xs1[0] == 0 and xs1[-1] == 5000
        assert xs2[0] == 5000 and xs2[-1] == 10000

    def test_path_closed_rect(self, rooms_model):
        e = next(r for r in rooms_model["rooms"] if r["id"] == "entry_01")
        # entry 分墙围出 x 12000..20000 × y 0..2500
        verts = e["polygon_mm"]["vertices"]
        assert [12000.0, 0.0] in verts
        assert [20000.0, 2500.0] in verts

    def test_area_measured(self, rooms_model):
        """实测回算写回。"""
        k = next(r for r in rooms_model["rooms"] if r["id"] == "kitchen_01")
        assert k["area_sqm_measured"] == pytest.approx(10.0)  # 4m x 2.5m

    def test_deterministic(self, skeleton_model, normal_rooms):
        a = normalize_rooms(normal_rooms, skeleton_model)
        b = normalize_rooms(normal_rooms, skeleton_model)
        assert a == b


class TestFlowS2RoomsSchemaError:
    def test_opening_wall_key_invalid(self, skeleton_model):
        """D41：opening 挂不存在的墙 key 必须回喂 SchemaError。"""
        from floorgeom.normalize import SchemaError
        with pytest.raises(SchemaError):
            normalize_rooms(_schema_error_rooms(), skeleton_model)


# ---------------------------------------------------------------------------
# S2：机检 R-01~R-09
# ---------------------------------------------------------------------------

class TestFlowCheck:
    @pytest.fixture
    def rooms_model(self, skeleton_model, normal_rooms):
        return normalize_rooms(normal_rooms, skeleton_model)

    def test_no_error_severity(self, rooms_model):
        """正常流程无 Error（走廊等 Warning 可接受）。"""
        from shapely.geometry import Polygon
        outline = [Polygon([[0, 0], [20000, 0], [20000, 5000], [10000, 5000],
                            [10000, 10000], [0, 10000]]),
                   Polygon([[20000, 0], [28000, 0], [28000, 6000], [20000, 6000]])]
        params = {"program": {"living": [18, 30], "bedroom": [10, 16],
                              "kitchen": [8, 14], "bathroom": [4, 12], "garage": [20, 40]}}
        report = check_floor(rooms_model, params=params, outline_polygons=outline)
        errors = [r for r in report if r["severity"] == "error"]
        assert errors == [], f"unexpected errors: {errors}"

    def test_rooms_inside_outline(self, rooms_model):
        """R-01：所有房间都在轮廓内（含车库块）。"""
        from shapely.geometry import Polygon
        outline = [Polygon([[0, 0], [20000, 0], [20000, 5000], [10000, 5000],
                            [10000, 10000], [0, 10000]]),
                   Polygon([[20000, 0], [28000, 0], [28000, 6000], [20000, 6000]])]
        report = check_floor(rooms_model, outline_polygons=outline)
        assert not [r for r in report if r["rule"] == "R-01"]

    def test_no_overlap(self, rooms_model):
        report = check_floor(rooms_model)
        assert not [r for r in report if r["rule"] == "R-02"]


# ---------------------------------------------------------------------------
# 建造：回读对账
# ---------------------------------------------------------------------------

class TestFlowReconcile:
    @pytest.fixture
    def rooms_model(self, skeleton_model, normal_rooms):
        return normalize_rooms(normal_rooms, skeleton_model)

    def _consistent_graph(self, rooms_model):
        """构造与 rooms 一致的回读图（模拟 readback 成功：DXF 画对了）。

        回读面积 = 声明 area_sqm（假设画得完全正确）；不一致时用 DXF 实测模拟。
        邻接 = 声明侧 normalize 已推的 neighbors[]（房间间共享边 + loc 语义）
        + corridor 门边（corridor 为 follows 无 polygon，声明侧无 corridor 邻接，
        回读侧单向补——reconcile 对 corridor 相关邻接豁免）。
        """
        shared = []
        for r in rooms_model.get("rooms", []):
            for nid in (r.get("neighbors") or []):
                shared.append(tuple(sorted((r["id"], nid))))
        corridor_edges = [("living_01", "corridor"), ("bedroom_01", "corridor"),
                          ("bedroom_02", "corridor"), ("kitchen_01", "corridor"),
                          ("entry_01", "corridor"), ("bathroom_01", "corridor"),
                          ("garage_01", "corridor")]
        return {
            "floor": "house_1f",
            "rooms": [{"id": r["id"], "area_sqm": r.get("area_sqm", r.get("area_sqm_measured", 0))}
                      for r in rooms_model["rooms"]],
            "adjacencies": sorted(set(shared + corridor_edges)),
            "doors": [{"between": ("living_01", "corridor")},
                      {"between": ("bedroom_01", "corridor")},
                      {"between": ("bedroom_02", "corridor")},
                      {"between": ("kitchen_01", "corridor")},
                      {"between": ("entry_01", "corridor")},
                      {"between": ("bathroom_01", "corridor")},
                      {"between": ("garage_01", "corridor")}],
        }

    def test_consistent_passes(self, rooms_model, normal_rooms):
        decl = to_room_graph(rooms_model)
        report = reconcile(decl, self._consistent_graph(rooms_model))
        assert not [f for f in report if f["severity"] == "error"]

    def test_area_perturbation_fails(self, rooms_model, normal_rooms):
        """人为改面积 → FAIL 可回喂 LLM。"""
        decl = to_room_graph(rooms_model)
        graph = self._consistent_graph(rooms_model)
        graph["rooms"][0]["area_sqm"] = 999.0  # 篡改
        report = reconcile(decl, graph)
        assert any(f["rule"] == "area" and f["severity"] == "error" for f in report)

    def test_missing_door_fails(self, rooms_model, normal_rooms):
        """回读邻接/门对超出声明共墙 → adjacency 防多 FAIL。

        V3：门图是几何共墙子集，只做单向防多；回读出现声明没有的邻接
        （如跨房间开门）→ adjacency error（door 独立检查已并入 adjacency）。
        """
        decl = to_room_graph(rooms_model)
        graph = self._consistent_graph(rooms_model)
        # 加一扇"声明侧不存在"的房间间门对（不在共享边邻接里 → 应 FAIL）
        graph["doors"] = graph["doors"] + [{"between": ("living_01", "bedroom_01")}]
        graph["adjacencies"] = graph["adjacencies"] + [("living_01", "bedroom_01")]
        report = reconcile(decl, graph)
        assert any(f["rule"] == "adjacency" and f["severity"] == "error" for f in report)


# ---------------------------------------------------------------------------
# 全流程：确定性（canon 字节一致）
# ---------------------------------------------------------------------------

class TestFlowDeterminism:
    def test_whole_flow_canon(self):
        d1 = derive(PLAN)
        d2 = derive(PLAN)
        assert canon_bytes(d1) == canon_bytes(d2)
        s1 = normalize_skeleton(SKELETON)
        s2 = normalize_skeleton(SKELETON)
        assert canon_bytes(s1) == canon_bytes(s2)

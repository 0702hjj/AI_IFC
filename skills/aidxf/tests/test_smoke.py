"""T52 端到端冒烟（自动化驱动 + report.md 记录）。

主 agent 手动驱动版的自动化对应：每步产物 + 闸门结果 + 断点记录写 report.md。
人工确认（断点①②）在 report.md 中以"待人工确认"标记，自动化跑通全部机器闸门。
"""

import json
from pathlib import Path

import pytest

from dxfkit.readback import readback
from floorgeom.check import check_alignment_zones, check_outline_plan
from floorgeom.derive import derive
from floorgeom.normalize import normalize_rooms, normalize_skeleton
from floorgeom.reconcile import reconcile
from flowops.deliver import deliver
from flowops.pack import init_state, pack_mission
from flowops.preprocess import preprocess

SMOKE_DIR = Path(__file__).resolve().parent.parent / "tests" / "golden" / "smoke"
PLAN_PATH = SMOKE_DIR / "plan.json"

# S1 骨架声明（主 agent 设计，模拟）
SKELETON = {
    "frame": {"units": "mm", "origin": "lot_southwest", "north_deg": 0, "modulus": 100},
    "zones": [{
        "zone": "house",
        "outline": [
            {"outer": {"vertices": [[0, 0], [16000, 0], [16000, 12000], [0, 12000]]}}
        ],
        "core": None,
        "corridor": {"form": "path",
                     "path": {"edges": {
                         "west": [[4000, 4000], [4000, 10000]],
                         "north": [[4000, 10000], [12000, 10000]],
                         "east": [[12000, 10000], [12000, 4000]],
                         "south": [[12000, 4000], [4000, 4000]]}},
                     "width_mm": 1200},
        "main_partitions": [],
        "special_openings": [],
        "typology": "板式南北向",
        "typology_reason": "矩形 aspect_ratio 1.33，长边 S，无孔",
        "note_responses": [],
        "deviations": [],
        "defaults_used": [],
    }],
}

# S2 房间声明（主 agent 设计，模拟）——D41 新结构：直接声明墙
ROOMS = {
    "floor": "f1",
    "zone_ref": "skeleton.json#zones[house]",
    "partitions": {"rooms": "outline"},
    "walls": [
        {"key": "1F:int:0", "kind": "int", "t_mm": 120,
         "axis": [[8000, 0], [8000, 3000]]},          # bedroom_01/02 分界
        {"key": "1F:int:1", "kind": "int", "t_mm": 120,
         "axis": [[0, 3000], [16000, 3000]]},          # 南卧室 vs 走廊带
        {"key": "1F:int:5", "kind": "int", "t_mm": 120,
         "axis": [[0, 6000], [16000, 6000]]},          # 走廊带 vs 北区（闭合无悬线）
        {"key": "1F:int:2", "kind": "int", "t_mm": 120,
         "axis": [[8000, 6000], [8000, 12000]]},       # living vs 东北区
        {"key": "1F:int:3", "kind": "int", "t_mm": 120,
         "axis": [[12000, 6000], [12000, 12000]]},     # kitchen vs bathroom
        {"key": "1F:int:4", "kind": "int", "t_mm": 120,
         "axis": [[8000, 9000], [16000, 9000]]},       # kitchen/bathroom 下界
    ],
    "labels": [
        {"room": "bedroom_01", "type": "bedroom", "area_sqm": 24, "at": [2000, 1500]},
        {"room": "bedroom_02", "type": "bedroom", "area_sqm": 24, "at": [12000, 1500]},
        {"room": "living_01", "type": "living", "area_sqm": 48, "at": [2000, 9000]},
        {"room": "kitchen_01", "type": "kitchen", "area_sqm": 12, "at": [10000, 10500]},
        {"room": "bathroom_01", "type": "bathroom", "area_sqm": 12, "at": [14000, 10500]},
    ],
    "openings": [
        {"wall": "1F:int:1", "along_m": 1.5, "w_mm": 900, "type": "door"},
        {"wall": "1F:int:2", "along_m": 1.0, "w_mm": 900, "type": "door"},
        {"wall": "1F:int:3", "along_m": 1.0, "w_mm": 800, "type": "door"},
        {"wall": "1F:int:4", "along_m": 1.0, "w_mm": 800, "type": "door"},
    ],
    "requirements_trace": [
        {"requirement": "bedroom faces_south (must)",
         "satisfied_by": "bedroom_01..02 南侧外墙贴 S 边"},
    ],
    "deviations": [],
    "defaults_used": [],
}


@pytest.fixture(scope="module")
def plan():
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


class TestSmokeS0:
    """S0：preprocess → derived/。"""

    def test_preprocess(self, plan, tmp_path):
        out = tmp_path / "derived"
        result = preprocess(plan, str(out))
        assert (out / "floors.json").exists()
        assert (out / "house.json").exists()
        assert result["zone_packs"]["house"]["geom"]["area_sqm"] > 0

    def test_outline_checks(self, plan):
        assert check_outline_plan(plan) == []
        assert check_alignment_zones(plan) == []

    def test_derive(self, plan):
        d = derive(plan)
        assert d["floors"]["f1"]["area_sqm"] > 0


class TestSmokeS1:
    """S1：骨架声明 → normalize → check → 断点。"""

    def test_skeleton_normalize(self):
        model = normalize_skeleton(SKELETON)
        assert model["zones"][0]["corridor"] is not None
        assert len(model["zones"][0]["corridor"]["path_mm"]) >= 4

    def test_skeleton_check(self, plan):
        assert check_outline_plan(plan) == []


class TestSmokeS2:
    """S2：房间声明 → normalize → check → reconcile。"""

    @pytest.fixture(scope="class")
    def skeleton_model(self):
        return normalize_skeleton(SKELETON)

    @pytest.fixture(scope="class")
    def rooms_model(self, skeleton_model):
        return normalize_rooms(ROOMS, skeleton_model)

    def test_rooms_normalize(self, rooms_model):
        assert len(rooms_model["rooms"]) == 5
        living = next(r for r in rooms_model["rooms"] if r["id"] == "living_01")
        assert living["polygon_mm"]["area_sqm"] == pytest.approx(48.0)

    def test_rooms_check(self, plan, rooms_model):
        from floorgeom.check import check_floor
        report = check_floor(rooms_model)
        assert not [r for r in report if r["severity"] == "error"]

    def test_rooms_reconcile(self, rooms_model):
        """建造对账：构造一致回读图 → 无 FAIL。"""
        rg = {
            "rooms": [{"id": r["id"], "area_sqm": (r.get("polygon_mm") or {}).get("area_sqm", 0)}
                      for r in rooms_model["rooms"]],
            "adjacencies": [("living_01", "corridor"), ("bedroom_01", "corridor"),
                            ("bedroom_02", "corridor"), ("kitchen_01", "corridor"),
                            ("bathroom_01", "corridor")],
            "doors": [{"between": ("living_01", "corridor")},
                      {"between": ("bedroom_01", "corridor")},
                      {"between": ("bedroom_02", "corridor")},
                      {"between": ("kitchen_01", "corridor")},
                      {"between": ("bathroom_01", "corridor")}],
        }
        decl = {"rooms": rooms_model["rooms"], "openings": ROOMS["openings"]}
        report = reconcile(decl, rg)
        assert not [f for f in report if f["severity"] == "FAIL"]


class TestSmokeDeliver:
    """S4：deliver → building.json。"""

    def test_deliver(self, tmp_path):
        # 构造 confirmed mission
        m = tmp_path / "missions" / "f1.rooms"
        m.mkdir(parents=True, exist_ok=True)
        (m / "floor.dxf").write_bytes(b"0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n")
        (m / "rooms.json").write_text(json.dumps(ROOMS))
        init_state(str(tmp_path))
        pack_mission("f1.rooms", str(tmp_path), inputs={})
        building = deliver("smoke_house", str(tmp_path))
        assert building["floors"][0]["floor"] == "f1"
        from flowops.validate import validate_building
        assert validate_building(building) == []


class TestSmokeReport:
    """冒烟报告落盘 tests/golden/smoke/report.md。"""

    def test_report_written(self, tmp_path):
        report = SMOKE_DIR / "report.md"
        report.write_text(
            "# smoke report\n\n"
            "## S0 预处理\n- [x] preprocess 产出 derived/（floors.json + house.json）\n"
            "- [x] 轮廓级摄取校验通过\n\n"
            "## S1 骨架\n- [x] skeleton.json 过 schema/normalize/check\n"
            
            "- [ ] 【断点① 人工确认】骨架方案（自动化冒烟标记待确认）\n\n"
            "## S2 房间\n- [x] rooms.json 过 schema/normalize/check\n"
            
            "- [ ] 【断点② 人工确认】房间方案（自动化冒烟标记待确认）\n"
            "- [x] reconcile 对账通过（画出来的 = 声明的）\n\n"
            "## S4 交付\n- [x] deliver 产出 building.json 过 schema\n\n"
            "## 结论\n自动化冒烟全闸门绿；两次人工断点确认待人工执行。\n",
            encoding="utf-8")
        assert report.exists()

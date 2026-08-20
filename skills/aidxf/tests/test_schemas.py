"""skeleton/rooms/building schema 正反例（W0 T02/T03/T04，TDD 冻结测试）。

纪律：schema 冻结后任何改动必须回 W0 重走本文件全部用例。
测试名按 W0 规定：test_skeleton_* / test_rooms_* / test_plan_schema_* / test_building_schema_*。
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "references" / "schemas"
AIPLAN_SCHEMAS = (
    Path(__file__).resolve().parent.parent.parent
    / "aiplan" / "references" / "schemas"
)

MODULUS = 100


def _load(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _validate(schema, doc):
    validator = Draft202012Validator(schema)
    return sorted(validator.iter_errors(doc), key=lambda e: ".".join(str(p) for p in e.absolute_path))


# ---------------------------------------------------------------------------
# skeleton.schema.json —— T02
# ---------------------------------------------------------------------------

SKELETON_SCHEMA = _load(SCHEMAS_DIR / "skeleton.schema.json")


def _skeleton_doc(**overrides):
    """geo_cognition §5 podium 示例补全的正例骨架。"""
    doc = {
        "frame": {"units": "mm", "origin": "lot_southwest", "north_deg": 0, "modulus": MODULUS},
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
            "main_partitions": [
                {"id": "cut:0", "role": "shop|arcade 分界",
                 "from": {"ref": "corridor:outer", "edge": "S", "at": 0.5},
                 "to": {"ref": "outline:edge:0", "at": 0.5}}
            ],
            "special_openings": [
                {"at": [24000, 18000], "reason": "note: 3层设备吊装孔"}
            ],
            "typology": "中庭环绕",
            "typology_reason": "holes[0] 居中 96㎡，deep_zone_ratio 0.18 → 环绕式",
            "note_responses": [{"note": "3层设备吊装孔", "response": "special_openings[0]"}],
            "deviations": [],
            "defaults_used": [],
        }],
    }
    for k, v in overrides.items():
        doc[k] = v
    return doc


class TestSkeletonPositive:
    """T02 正例：podium 示例补全。"""

    def test_skeleton_podium_full(self):
        assert _validate(SKELETON_SCHEMA, _skeleton_doc()) == []

    def test_skeleton_core_null_ok(self):
        """G-01：无核心筒建筑（单层住宅/弧厅）core 允许 null。"""
        doc = _skeleton_doc()
        doc["zones"][0]["core"] = None
        assert _validate(SKELETON_SCHEMA, doc) == []

    def test_skeleton_corridor_null_ok(self):
        """G-02：无独立走廊小建筑 corridor 允许 null。"""
        doc = _skeleton_doc()
        doc["zones"][0]["corridor"] = None
        assert _validate(SKELETON_SCHEMA, doc) == []

    def test_skeleton_multizone(self):
        """整楼一份按 zone 分段（plan_demo podium+tower 形态）。"""
        doc = _skeleton_doc()
        doc["zones"].append({
            "zone": "tower",
            "outline": [
                {"outer": {"vertices": [[18000, 22000], [42000, 22000], [42000, 40000], [18000, 40000]]}}
            ],
            "core": {"anchor": [30000, 30000],
                     "vertices": [[24000, 30000], [36000, 30000], [36000, 40000], [24000, 40000]]},
            "corridor": {"form": "path", "width_mm": 1500,
                         "path": {"edges": {
                             "west": [[20000, 24000], [20000, 38000]],
                             "north": [[20000, 38000], [40000, 38000]],
                             "east": [[40000, 38000], [40000, 24000]],
                             "south": [[40000, 24000], [20000, 24000]]}}},
            "main_partitions": [],
            "special_openings": [],
            "typology": "核心筒深板",
            "typology_reason": "core 居中，depth.max 20 > 16",
            "note_responses": [],
            "deviations": [],
            "defaults_used": [],
        })
        assert _validate(SKELETON_SCHEMA, doc) == []

    def test_skeleton_missing_frame(self):
        doc = _skeleton_doc()
        del doc["frame"]
        errors = _validate(SKELETON_SCHEMA, doc)
        assert errors and any("frame" in ".".join(str(p) for p in e.absolute_path) or e.message.startswith("'frame'") for e in errors)

    def test_skeleton_frame_missing_units(self):
        doc = _skeleton_doc()
        del doc["frame"]["units"]
        errors = _validate(SKELETON_SCHEMA, doc)
        assert errors and any("units" in e.message for e in errors)

    def test_skeleton_missing_anchor(self):
        """core 存在但缺 anchor（T4 锁锚前置字段）。"""
        doc = _skeleton_doc()
        del doc["zones"][0]["core"]["anchor"]
        errors = _validate(SKELETON_SCHEMA, doc)
        assert errors

    def test_skeleton_corridor_bad_form(self):
        doc = _skeleton_doc()
        doc["zones"][0]["corridor"]["form"] = "circle"
        errors = _validate(SKELETON_SCHEMA, doc)
        assert errors and any("circle" in e.message or "ring" in e.message or "path" in e.message for e in errors)

    def test_skeleton_extra_field(self):
        doc = _skeleton_doc()
        doc["zones"][0]["magic"] = True
        errors = _validate(SKELETON_SCHEMA, doc)
        assert any("magic" in e.message for e in errors)

    def test_skeleton_main_partition_missing_path(self):
        """main_partitions 必须带 path（划分线）。"""
        doc = _skeleton_doc()
        doc["zones"][0]["main_partitions"] = [{"role": "分界"}]
        errors = _validate(SKELETON_SCHEMA, doc)
        assert errors

    def test_skeleton_main_partition_path_negative_index(self):
        """path 顶点索引不能为负。"""
        doc = _skeleton_doc()
        doc["zones"][0]["main_partitions"] = [
            {"path": [{"x": -1, "y": 0}, {"x": 2, "y": 3}, {"x": 4, "y": 0}], "role": "分界"},
        ]
        errors = _validate(SKELETON_SCHEMA, doc)
        assert errors

    def test_skeleton_main_partition_path_too_few(self):
        """path 至少 2 点。"""
        doc = _skeleton_doc()
        doc["zones"][0]["main_partitions"] = [
            {"path": [{"x": 0, "y": 0}], "role": "分界"},
        ]
        errors = _validate(SKELETON_SCHEMA, doc)
        assert errors

    def test_skeleton_corridor_bad_form(self):
        """corridor form 只允许 ring/path（polygon 已删）。"""
        doc = _skeleton_doc()
        doc["zones"][0]["corridor"] = {"form": "polygon", "width_mm": 2400}
        errors = _validate(SKELETON_SCHEMA, doc)
        assert errors

    def test_skeleton_missing_zones(self):
        doc = _skeleton_doc()
        del doc["zones"]
        errors = _validate(SKELETON_SCHEMA, doc)
        assert errors

    def test_skeleton_top_additional_properties(self):
        doc = _skeleton_doc()
        doc["extras"] = []
        errors = _validate(SKELETON_SCHEMA, doc)
        assert any("extras" in e.message for e in errors)


# ---------------------------------------------------------------------------
# rooms.schema.json —— T03
# ---------------------------------------------------------------------------

ROOMS_SCHEMA = _load(SCHEMAS_DIR / "rooms.schema.json")


def _rooms_doc(**overrides):
    doc = {
        "floor": "tower_std",
        "zone_ref": "skeleton.json#zones[tower]",
        "partitions": {"office_se": "block:se"},
        "walls": [
            {"key": "1F:ext:0", "kind": "ext", "t_mm": 200, "axis": [[0, 0], [12000, 0]]},
            {"key": "1F:int:0", "kind": "int", "t_mm": 120, "path": [{"x": 1, "y": 0}, {"x": 1, "y": 2}]},
        ],
        "labels": [
            {"room": "office_01", "type": "office", "area_sqm": 45,
             "at": [3000, 2000]},
        ],
        "requirements_trace": [
            {"requirement": "office faces_south (must)",
             "satisfied_by": "office_01 南侧外墙贴 S 边"},
        ],
        "deviations": [],
        "defaults_used": [],
    }
    for k, v in overrides.items():
        doc[k] = v
    return doc


class TestRoomsWalls4Forms:
    """D39：rooms walls 4 形式（aiifc 对齐）+ key + opening 挂 key。"""

    def test_rooms_wall_straight_axis_points(self):
        """straight：axis 两点数组。"""
        doc = _rooms_doc()
        doc["walls"] = [{"key": "1F:int:0", "kind": "int", "t_mm": 120,
                         "axis": [[12000, 8000], [12000, 14000]]}]
        assert _validate(ROOMS_SCHEMA, doc) == []

    def test_rooms_wall_polyline_axis_points(self):
        """polyline：axis 3+ 点数组。"""
        doc = _rooms_doc()
        doc["walls"] = [{"key": "1F:ext:0", "kind": "ext", "t_mm": 200,
                         "axis": [[0, 0], [0, 24000], [24000, 24000]]}]
        assert _validate(ROOMS_SCHEMA, doc) == []

    def test_rooms_wall_key_optional(self):
        """key 缺省（机器自动分配）也合法。"""
        doc = _rooms_doc()
        doc["walls"] = [{"kind": "int", "t_mm": 120,
                         "axis": [[12000, 8000], [12000, 14000]]}]
        assert _validate(ROOMS_SCHEMA, doc) == []

    def test_rooms_openings_rejected(self):
        """D44：openings 剥离到 details——rooms 声明含 openings 被 schema 拒绝。"""
        doc = _rooms_doc()
        doc["openings"] = [{"wall": "1F:int:0", "along_m": 3.0, "w_mm": 900,
                            "type": "door"}]
        errs = _validate(ROOMS_SCHEMA, doc)
        assert any("openings" in str(e) for e in errs)

    def test_rooms_wall_axis_single_point_rejected(self):
        """axis 单点（两点式旧格式 from/to 也要求数组）→ 报错。"""
        doc = _rooms_doc()
        doc["walls"] = [{"key": "1F:int:0", "kind": "int", "t_mm": 120,
                         "axis": {"from": [0, 0], "to": [12000, 0]}}]
        errors = _validate(ROOMS_SCHEMA, doc)
        assert errors


# ---------------------------------------------------------------------------
# 副本存在性断言（T04）
# ---------------------------------------------------------------------------

class TestSchemaCopies:
    """T04：类型包/词表副本从 aiplan 拷入后存在。"""

    def test_plan_schema_copy_exists(self):
        assert (SCHEMAS_DIR / "plan.schema.json").exists()

    def test_predicate_vocabulary_copy_exists(self):
        vocab = SCHEMAS_DIR.parent / "vocabulary" / "predicate_vocabulary.md"
        assert vocab.exists()

    def test_building_types_copies_exist(self):
        """2026-08-11：类型包每类型一桶（building_types/<type>/）。"""
        btypes = SCHEMAS_DIR.parent / "building_types"
        for t in ("residence", "office", "retail"):
            d = btypes / t
            assert (d / f"{t}.md").exists(), f"missing {t}/{t}.md"
            assert (d / "skeleton_patterns.md").exists()

    def test_building_types_cases_exist(self):
        """2026-08-11：.rules.json 已删（.md 同源即事实源）；cases.json 保留（桶内）。"""
        btypes = SCHEMAS_DIR.parent / "building_types"
        for t in ("residence", "office", "retail"):
            assert (btypes / t / f"{t}.cases.json").exists()
            assert not (btypes / f"{t}.rules.json").exists()


# ---------------------------------------------------------------------------
# 波次 2（D40）：分层外推——切割线锚定 + blocks between 认领
# ---------------------------------------------------------------------------

class TestSkeletonPartitionCut:
    """D40：main_partitions 切割线锚定形态（from/to ref+at）。"""

    def test_skeleton_partition_cut_anchored(self):
        """切割线：from corridor:outer 到 outline:edge:0。"""
        doc = _skeleton_doc()
        doc["zones"][0]["main_partitions"] = [
            {"id": "cut:0", "role": "radial",
             "from": {"ref": "corridor:outer", "at": 0.0},
             "to": {"ref": "outline:edge:0", "at": 0.5}},
        ]
        assert _validate(SKELETON_SCHEMA, doc) == []

    def test_skeleton_partition_cut_missing_at_ok(self):
        """at 缺省（= 0.5 中点）合法。"""
        doc = _skeleton_doc()
        doc["zones"][0]["main_partitions"] = [
            {"id": "cut:0", "role": "cross",
             "from": {"ref": "outline:edge:1"},
             "to": {"ref": "outline:edge:3"}},
        ]
        assert _validate(SKELETON_SCHEMA, doc) == []

    def test_skeleton_partition_cut_missing_ref(self):
        """锚定缺 ref → 报错。"""
        doc = _skeleton_doc()
        doc["zones"][0]["main_partitions"] = [
            {"id": "cut:0", "role": "radial",
             "from": {"at": 0.5},
             "to": {"ref": "outline:edge:0"}},
        ]
        errors = _validate(SKELETON_SCHEMA, doc)
        assert errors


class TestSkeletonBlocksBetween:
    """D40：blocks between 认领段（切割线围成）。"""

    def test_skeleton_block_between(self):
        """blocks 用 between 引用两条切割线。"""
        doc = _skeleton_doc()
        doc["zones"][0]["main_partitions"] = [
            {"id": "cut:0", "role": "radial",
             "from": {"ref": "corridor:outer", "at": 0.0},
             "to": {"ref": "outline:edge:0", "at": 0.5}},
            {"id": "cut:1", "role": "radial",
             "from": {"ref": "corridor:outer", "at": 0.5},
             "to": {"ref": "outline:edge:1", "at": 0.5}},
        ]
        doc["zones"][0]["blocks"] = [
            {"id": "b0", "role": "open_office", "between": ["cut:0", "cut:1"]},
        ]
        assert _validate(SKELETON_SCHEMA, doc) == []

    def test_skeleton_block_between_missing(self):
        """between 缺 → 报错。"""
        doc = _skeleton_doc()
        doc["zones"][0]["blocks"] = [
            {"id": "b0", "role": "open_office"},
        ]
        errors = _validate(SKELETON_SCHEMA, doc)
        assert errors


# ---------------------------------------------------------------------------
# 波次 3（D41）：rooms 新结构——删 loc，partitions 承接 + walls + labels
# ---------------------------------------------------------------------------

class TestRoomsNewStructure:
    """D41：rooms 直接声明墙（不声明房间区域）。"""

    def _new_rooms_doc(self, **overrides):
        doc = {
            "floor": "tower_std",
            "zone_ref": "skeleton.json#zones[tower]",
            "partitions": {
                "office_se": "block:se",
                "meeting_core": "corridor",
            },
            "walls": [
                {"key": "1F:int:0", "kind": "int", "t_mm": 120,
                 "axis": [[12000, 8000], [12000, 14000]]},
                {"key": "1F:ext:0", "kind": "ext", "t_mm": 200,
                 "axis": [[0, 0], [0, 24000], [24000, 24000]]},
            ],
            "labels": [
                {"room": "office_01", "type": "office", "area_sqm": 45,
                 "at": [14000, 10000]},
                {"room": "meeting_01", "type": "meeting", "area_sqm": 60,
                 "at": [6000, 12000]},
            ],
            "requirements_trace": [
                {"requirement": "office faces_south (must)",
                 "satisfied_by": "office_01 南侧外墙贴 S 边"},
            ],
            "deviations": [],
            "defaults_used": [],
        }
        for k, v in overrides.items():
            doc[k] = v
        return doc

    def test_rooms_new_structure_full(self):
        assert _validate(ROOMS_SCHEMA, self._new_rooms_doc()) == []

    def test_rooms_labels_placemark(self):
        """stair 占位：labels 带 placemark。"""
        doc = self._new_rooms_doc()
        doc["labels"] = [
            {"room": "stair_01", "type": "stair", "at": [4000, 6000],
             "placemark": {"kind": "stair"}},
        ]
        assert _validate(ROOMS_SCHEMA, doc) == []

    def test_rooms_old_rooms_array_rejected(self):
        """旧 rooms[] 数组 → 报错（unknown property）。"""
        doc = self._new_rooms_doc()
        doc["rooms"] = [
            {"id": "office_01", "type": "office", "area_sqm": 45,
             "loc": {"between_axes": {"x": [0, 1], "y": [3, 4]}}},
        ]
        errors = _validate(ROOMS_SCHEMA, doc)
        assert errors

    def test_rooms_label_missing_at(self):
        """label 缺 at → 报错。"""
        doc = self._new_rooms_doc()
        doc["labels"] = [{"room": "office_01"}]
        errors = _validate(ROOMS_SCHEMA, doc)
        assert errors

    def test_rooms_infeasible_still_ok(self):
        """infeasible 形态保留。"""
        doc = {
            "floor": "tower_std",
            "status": "infeasible",
            "region": {"x": [0, 30000], "y": [0, 30000]},
            "reason": "面积缺口 38㎡",
            "evidence": {"required_sqm": 320, "available_sqm": 282},
        }
        assert _validate(ROOMS_SCHEMA, doc) == []

"""normalize rooms walls 测试（D41：墙解析/墙围区域/opening 挂墙）。

拆分自 test_normalize.py（W-0049 文件行数门控），夹具复用 test_normalize。
"""

import pytest

from floorgeom.normalize import SchemaError, normalize_skeleton, normalize_rooms
from test_normalize import _skeleton_doc  # noqa: F401


# ---------------------------------------------------------------------------
# 波次 3（D41）：rooms 直接声明墙——walls 解析/墙围区域/opening 挂墙
# ---------------------------------------------------------------------------

def _wall_rooms_skeleton():
    """形态族 D 夹具：12×6m outline（无 core/corridor）——rooms 在轮廓内画分墙。"""
    return {
        "frame": {"units": "mm", "origin": "lot_southwest", "north_deg": 0, "modulus": 100},
        "zones": [{
            "zone": "house",
            "axis_grid": {"x": [], "y": []},
            "outline": [
                {"outer": {"vertices": [[0, 0], [12000, 0], [12000, 6000], [0, 6000]]}}
            ],
            "typology": "独立块",
            "typology_reason": "single family",
            "note_responses": [],
            "deviations": [],
            "defaults_used": [],
        }],
    }


def _wall_rooms_doc(**overrides):
    """rooms：两道竖分墙 + 三个标签（三开间）+ 门挂墙。"""
    doc = {
        "floor": "house",
        "zone_ref": "skeleton.json#zones[house]",
        "partitions": {"main": "outline"},
        "walls": [
            {"key": "1F:int:0", "kind": "int", "t_mm": 120,
             "axis": [[4000, 0], [4000, 6000]]},
            {"key": "1F:int:1", "kind": "int", "t_mm": 120,
             "axis": [[8000, 0], [8000, 6000]]},
        ],
        "labels": [
            {"room": "bedroom_01", "type": "bedroom", "area_sqm": 24, "at": [2000, 3000]},
            {"room": "living_01", "type": "living", "area_sqm": 24, "at": [6000, 3000]},
            {"room": "bedroom_02", "type": "bedroom", "area_sqm": 24, "at": [10000, 3000]},
        ],
        "openings": [
            {"wall": "1F:int:0", "along_m": 2.0, "w_mm": 900, "type": "door"},
            {"wall": "1F:int:1", "along_m": 3.0, "w_mm": 900, "type": "door"},
        ],
        "requirements_trace": [],
        "deviations": [],
        "defaults_used": [],
    }
    for k, v in overrides.items():
        doc[k] = v
    return doc


class TestNormalizeRoomsWalls:
    """D41：rooms walls 解析 + 墙围区域 + opening 挂墙。"""

    def test_walls_parse_absolute(self):
        """walls axis（绝对坐标）→ 墙轴线线段。"""
        skel = normalize_skeleton(_wall_rooms_skeleton())
        m = normalize_rooms(_wall_rooms_doc(), skel)
        walls = {w["key"]: w for w in m["walls"]}
        assert walls["1F:int:0"]["line_mm"] == [[4000.0, 0.0], [4000.0, 6000.0]]

    def test_rooms_regions_polygonized(self):
        """墙 + 轮廓边 → 围出 3 区域；labels at 落区绑定。"""
        skel = normalize_skeleton(_wall_rooms_skeleton())
        m = normalize_rooms(_wall_rooms_doc(), skel)
        rooms = {r["room"]: r for r in m["rooms"]}
        assert set(rooms) == {"bedroom_01", "living_01", "bedroom_02"}
        # 三开间各 4×6 = 24㎡
        assert rooms["bedroom_01"]["polygon_mm"]["area_sqm"] == pytest.approx(24.0)
        assert rooms["living_01"]["polygon_mm"]["area_sqm"] == pytest.approx(24.0)

    def test_opening_along_wall(self):
        """opening 挂墙 key + along → 沿墙绝对位置。"""
        skel = normalize_skeleton(_wall_rooms_skeleton())
        m = normalize_rooms(_wall_rooms_doc(), skel)
        opens = {o["type"] + str(i): o for i, o in enumerate(m["openings"])}
        o0 = m["openings"][0]
        assert o0["wall_key"] == "1F:int:0"
        # along 2m 沿墙起点 [4000,0] → [4000, 2000]
        assert o0["at_mm"] == pytest.approx([4000.0, 2000.0])

    def test_opening_wall_key_invalid(self):
        """opening 挂不存在的墙 key → SchemaError。"""
        skel = normalize_skeleton(_wall_rooms_skeleton())
        doc = _wall_rooms_doc()
        doc["openings"] = [{"wall": "1F:nope:9", "along_m": 2.0, "w_mm": 900, "type": "door"}]
        with pytest.raises(SchemaError):
            normalize_rooms(doc, skel)

    def test_axis_grid_path_wall(self):
        """axis-grid path 索引粗轴网 → 折线分墙。"""
        skel = normalize_skeleton(_wall_rooms_skeleton())
        skel["zones"][0]["axis_grid_derived"] = {"x": [0, 4000, 8000, 12000],
                                                 "y": [0, 3000, 6000]}
        doc = _wall_rooms_doc()
        doc["walls"] = [
            {"key": "1F:int:0", "kind": "int", "t_mm": 120,
             "path": [{"x": 1, "y": 0}, {"x": 1, "y": 2}]},   # x=4000 竖墙（0→6000）
        ]
        doc["labels"] = [
            {"room": "a", "type": "living", "area_sqm": 24, "at": [2000, 3000]},
            {"room": "b", "type": "living", "area_sqm": 48, "at": [8000, 3000]},
        ]
        doc["openings"] = []
        m = normalize_rooms(doc, skel)
        walls = {w["key"]: w for w in m["walls"]}
        assert walls["1F:int:0"]["line_mm"] == [[4000.0, 0.0], [4000.0, 6000.0]]
        rooms = {r["room"]: r for r in m["rooms"]}
        assert rooms["a"]["polygon_mm"]["area_sqm"] == pytest.approx(24.0)
        assert rooms["b"]["polygon_mm"]["area_sqm"] == pytest.approx(48.0)

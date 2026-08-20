"""normalize 分层外推测试（D40：差集/切割/认领）。

拆分自 test_normalize.py（W-0049 文件行数门控），夹具复用 test_normalize。
"""

import pytest

from floorgeom.normalize import SchemaError, normalize_skeleton, normalize_rooms
from test_normalize import _skeleton_doc  # noqa: F401


# ---------------------------------------------------------------------------
# 波次 2（D40）：分层外推——差集/切割线/切段/认领
# ---------------------------------------------------------------------------

def _layered_skeleton_doc(**overrides):
    """分层外推夹具：30×30m outline + 20×20m corridor 外缘 + 10×10m core 居中。

    corridor zone = 20×20 − 10×10（环带）；大区 = 30×30 − 20×20（外环）。
    """
    doc = {
        "frame": {"units": "mm", "origin": "lot_southwest", "north_deg": 0, "modulus": 100},
        "zones": [{
            "zone": "tower",
            "axis_grid": {"x": [], "y": []},
            "outline": [
                {"outer": {"vertices": [[0, 0], [30000, 0], [30000, 30000], [0, 30000]]}}
            ],
            "core": {"anchor": [15000, 15000],
                     "vertices": [[10000, 10000], [20000, 10000], [20000, 20000], [10000, 20000]]},
            "corridor": {
                "form": "path", "width_mm": 5000,
                "path": {
                    "edges": {
                        "west": [[5000, 5000], [5000, 25000]],
                        "north": [[5000, 25000], [25000, 25000]],
                        "east": [[25000, 25000], [25000, 5000]],
                        "south": [[25000, 5000], [5000, 5000]],
                    },
                },
            },
            "main_partitions": [],
            "typology": "环形办公",
            "typology_reason": "core 居中",
            "note_responses": [],
            "deviations": [],
            "defaults_used": [],
        }],
    }
    for k, v in overrides.items():
        doc[k] = v
    return doc


class TestNormalizeLayeredPush:
    """D40：分层外推——corridor 差集 / 大区差集 / 切割切段 / blocks 认领。"""

    def test_corridor_zone_difference(self):
        """corridor zone = 外缘 − union(cores)（环带）。"""
        m = normalize_skeleton(_layered_skeleton_doc())
        z = m["zones"][0]
        cz = z["corridor_zone"]
        assert cz["polygon_mm"]["area_sqm"] == pytest.approx(300.0)  # 20×20 − 10×10 = 300㎡

    def test_big_zones_difference(self):
        """大区 = outline − corridor zone（外环 30×30 − 20×20 = 500㎡）。"""
        m = normalize_skeleton(_layered_skeleton_doc())
        z = m["zones"][0]
        bz = z["big_zones"]
        total = sum(b["polygon_mm"]["area_sqm"] for b in bz)
        assert total == pytest.approx(500.0)

    def test_cut_lines_anchored(self):
        """切割线 from/to 锚定 → 绝对坐标线段。"""
        doc = _layered_skeleton_doc()
        doc["zones"][0]["main_partitions"] = [
            {"id": "cut:0", "role": "radial",
             "from": {"ref": "corridor:outer", "edge": "N", "at": 0.5},
             "to": {"ref": "outline:edge:2", "at": 0.5}},
            {"id": "cut:1", "role": "radial",
             "from": {"ref": "corridor:outer", "edge": "S", "at": 0.5},
             "to": {"ref": "outline:edge:0", "at": 0.5}},
        ]
        m = normalize_skeleton(doc)
        z = m["zones"][0]
        cuts = {c["id"]: c for c in z["cuts"]}
        # cut:0 竖线：corridor N 边中点 (15000,25000) → outline N 边中点 (15000,30000)
        assert cuts["cut:0"]["line_mm"][0] == pytest.approx([15000.0, 25000.0])
        assert cuts["cut:0"]["line_mm"][1] == pytest.approx([15000.0, 30000.0])

    def test_segments_split_and_blocks_between(self):
        """2 条径向切割 → 大区切 2 段；blocks between + side 认领。"""
        doc = _layered_skeleton_doc()
        doc["zones"][0]["main_partitions"] = [
            {"id": "cut:0", "role": "radial",
             "from": {"ref": "corridor:outer", "edge": "N", "at": 0.5},
             "to": {"ref": "outline:edge:2", "at": 0.5}},
            {"id": "cut:1", "role": "radial",
             "from": {"ref": "corridor:outer", "edge": "S", "at": 0.5},
             "to": {"ref": "outline:edge:0", "at": 0.5}},
        ]
        doc["zones"][0]["blocks"] = [
            {"id": "b_east", "role": "open_office", "between": ["cut:0", "cut:1"], "side": "E"},
            {"id": "b_west", "role": "units", "between": ["cut:0", "cut:1"], "side": "W"},
        ]
        m = normalize_skeleton(doc)
        z = m["zones"][0]
        blocks = {b["id"]: b for b in z["blocks"]}
        assert len(z["cuts"]) == 2
        # 东西两块各约 250㎡（外环 500㎡ 对半）
        assert blocks["b_east"]["polygon_mm"]["area_sqm"] == pytest.approx(250.0, abs=1.0)
        assert blocks["b_west"]["polygon_mm"]["area_sqm"] == pytest.approx(250.0, abs=1.0)
        # 认领的段在正确侧：东块质心 x > 15000
        east_centroid = blocks["b_east"]["polygon_mm"]["centroid_mm"]
        assert east_centroid[0] > 15000

    def test_axis_grid_derived(self):
        """轴网派生：分区边界坐标集合（模型不手填）。"""
        m = normalize_skeleton(_layered_skeleton_doc())
        z = m["zones"][0]
        ag = z["axis_grid_derived"]
        # 无切割线场景：边界坐标 = outline/corridor/core 的顶点
        assert ag["x"] == [0.0, 5000.0, 10000.0, 20000.0, 25000.0, 30000.0]
        assert ag["y"] == [0.0, 5000.0, 10000.0, 20000.0, 25000.0, 30000.0]

    def test_partition_labels(self):
        """分区标签：段质心 BLOCK_<id>。"""
        doc = _layered_skeleton_doc()
        doc["zones"][0]["main_partitions"] = [
            {"id": "cut:0", "role": "radial",
             "from": {"ref": "corridor:outer", "edge": "N", "at": 0.5},
             "to": {"ref": "outline:edge:2", "at": 0.5}},
            {"id": "cut:1", "role": "radial",
             "from": {"ref": "corridor:outer", "edge": "S", "at": 0.5},
             "to": {"ref": "outline:edge:0", "at": 0.5}},
        ]
        doc["zones"][0]["blocks"] = [
            {"id": "b_east", "role": "open_office", "between": ["cut:0", "cut:1"], "side": "E"},
        ]
        m = normalize_skeleton(doc)
        z = m["zones"][0]
        labels = {l["block"]: l for l in z["partition_labels"]}
        assert "b_east" in labels
        lab = labels["b_east"]
        assert lab["tag"] == "BLOCK_b_east"
        assert lab["at_mm"][0] > 15000  # 东块质心



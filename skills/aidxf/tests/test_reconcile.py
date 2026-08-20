"""reconcile.py 测试（T18）：声明房间图 vs 回读房间图对账（V3 统一房间图契约）。"""

import pytest

from floorgeom.reconcile import reconcile
from floorgeom.room_graph import to_room_graph


def _decl_graph():
    """声明侧房间图（normalize 产物经 to_room_graph——从 loc 语义提取邻接）。"""
    return {
        "floor": "podium_1f",
        "rooms": [
            {"id": "shop_01", "type": "shop", "area_sqm": 320,
             "loc": {"adjacent_to": "corridor", "side": "S"}},
            {"id": "corridor", "type": "corridor", "area_sqm": 60,
             "loc": {"follows": "corridor"}},
        ],
        # to_room_graph 产出（loc.adjacent_to/follows 提取；挂墙 openings 无门对 → doors 空）
        "adjacencies": [("corridor", "shop_01")],
        "doors": [],
    }


def _readback_graph():
    """回读侧房间图（dxfkit readback.to_room_graph 产物）。"""
    return {
        "floor": "podium_1f",
        "rooms": [
            {"id": "shop_01", "area_sqm": 318.0},
            {"id": "corridor", "area_sqm": 61.0},
        ],
        "adjacencies": [("corridor", "shop_01")],
        "doors": [{"between": ("corridor", "shop_01")}],
    }


class TestReconcile:
    def test_consistent_passes(self):
        """完全一致 → 无 FAIL。"""
        report = reconcile(_decl_graph(), _readback_graph())
        assert not [f for f in report if f["severity"] == "error"]

    def test_area_mismatch(self):
        """面积差 >5% → FAIL。"""
        graph = _readback_graph()
        graph["rooms"][0]["area_sqm"] = 300.0  # 320 vs 300 = 6.25%
        report = reconcile(_decl_graph(), graph)
        assert any(f["rule"] == "area" and f["severity"] == "error" for f in report)

    def test_area_within_5_percent_passes(self):
        """面积差 <5% → 通过。"""
        graph = _readback_graph()
        graph["rooms"][0]["area_sqm"] = 310.0  # 3.1%
        report = reconcile(_decl_graph(), graph)
        assert not [f for f in report if f["rule"] == "area" and f["severity"] == "error"]

    def test_missing_room_in_readback(self):
        """回读缺房间 → FAIL。"""
        graph = _readback_graph()
        graph["rooms"] = [r for r in graph["rooms"] if r["id"] != "shop_01"]
        report = reconcile(_decl_graph(), graph)
        assert any(f["rule"] == "room_missing" and f["severity"] == "error" for f in report)

    def test_extra_room_in_readback(self):
        """回读多房间（画了没声明的）→ FAIL。"""
        graph = _readback_graph()
        graph["rooms"] = graph["rooms"] + [{"id": "extra_01", "area_sqm": 10}]
        report = reconcile(_decl_graph(), graph)
        assert any(f["rule"] == "room_missing" and "extra_01" in f["message"] for f in report)

    def test_adjacency_decl_superset_of_readback_passes(self):
        """声明几何共墙邻接 ⊇ 回读门图邻接 → 不报（V3 门图是共墙子集，常态）。

        回归：V3 每房一扇门（D44），声明侧 normalize 按几何共享边推 neighbors，
        回读侧 readback 只从画出的门推邻接——声明有回读无不是错误，删该检查。
        """
        graph = _readback_graph()
        graph["adjacencies"] = []  # 回读门图空（等价门图 ⊂ 声明共墙）
        report = reconcile(_decl_graph(), graph)
        assert not [f for f in report if f["rule"] == "adjacency" and f["severity"] == "error"]

    def test_adjacency_mismatch_readback_extra(self):
        """回读多邻接但声明缺 → FAIL。"""
        graph = _readback_graph()
        graph["adjacencies"] = [("corridor", "shop_01"), ("shop_01", "lobby")]
        graph["rooms"] = graph["rooms"] + [{"id": "lobby", "area_sqm": 20}]
        report = reconcile(_decl_graph(), graph)
        assert any(f["rule"] == "adjacency" and "lobby" in f["message"] for f in report)

    def test_adjacency_corridor_exempt(self):
        """走廊相关邻接豁免（声明侧 follows 走廊无法推 polygon）→ 不报。"""
        graph = _readback_graph()
        graph["adjacencies"] = [("corridor", "shop_01"), ("corridor", "stair_01")]
        graph["rooms"] = graph["rooms"] + [{"id": "stair_01", "area_sqm": 12}]
        report = reconcile(_decl_graph(), graph)
        corridor_fails = [f for f in report if f["rule"] == "adjacency" and "corridor" in f["message"]]
        assert not corridor_fails

    def test_adjacency_catches_readback_door_outside_decl(self):
        """回读门/邻接超出声明共墙 → adjacency 防多报错（door 检查已并入 adjacency）。

        回归：door 独立检查删除（2026-08-17）——声明侧 doors 恒空（learn_gold P2-3），
        door 数量差恒触发噪音；门超出共墙由 adjacency 单向防多统一抓。
        """
        graph = _readback_graph()
        graph["adjacencies"] = [("corridor", "shop_01"), ("shop_01", "lobby")]
        graph["rooms"] = graph["rooms"] + [{"id": "lobby", "area_sqm": 20}]
        report = reconcile(_decl_graph(), graph)
        assert any(f["rule"] == "adjacency" and f["severity"] == "error" for f in report)
        # door 检查已删：无独立 door rule
        assert not any(f["rule"] == "door" for f in report)

    def test_report_sorted(self):
        """报告按 rule 排序（确定性）。"""
        graph = _readback_graph()
        graph["doors"] = []
        graph["adjacencies"] = []
        report = reconcile(_decl_graph(), graph)
        rules = [f["rule"] for f in report]
        assert rules == sorted(rules)


class TestRoomGraph:
    def test_to_room_graph_consumes_neighbors(self):
        """to_room_graph 从 normalize 的 neighbors[] 提取邻接（不二次推导）。"""
        normalized = {
            "rooms": [
                {"id": "shop_01", "type": "shop", "area_sqm": 320, "neighbors": ["corridor"]},
                {"id": "corridor", "type": "corridor", "area_sqm": 60, "neighbors": ["shop_01"]},
            ],
            "openings": [{"wall": 0, "along_m": 2.0, "w_mm": 1200, "type": "door"}],
        }
        g = to_room_graph(normalized)
        assert set(g.keys()) == {"rooms", "adjacencies", "doors"}
        assert ("corridor", "shop_01") in g["adjacencies"]
        # 挂墙 openings 无房间对 → doors 空（learn_gold P2-3）
        assert g["doors"] == []

    def test_to_room_graph_no_neighbors(self):
        """无 neighbors 的房间不产邻接。"""
        normalized = {
            "rooms": [{"id": "a", "type": "room", "area_sqm": 10}],
        }
        g = to_room_graph(normalized)
        assert g["adjacencies"] == []


# ---------------------------------------------------------------------------
# 波次 4（1.1/1.2）：readback 退化（几何匹配）+ severity 统一（error/warning）
# ---------------------------------------------------------------------------

class TestReconcileD41Degrade:
    """D41/1.1：身份 = 质心落区几何匹配（不依赖标注命名）；severity 三档。"""

    def test_geometry_match_ignores_names(self):
        """decl 房间 id 与回读 id 不同 → 质心落区匹配（无 room_missing）。"""
        from floorgeom.reconcile import reconcile
        decl = {
            "rooms": [
                {"id": "office_01", "type": "office", "area_sqm": 24.0,
                 "centroid_mm": [2000.0, 3000.0]},
            ],
            "adjacencies": [], "doors": [],
        }
        read = {
            "rooms": [
                {"id": "space_7", "type": "unlabeled", "area_sqm": 24.0,
                 "polygon_mm": {"vertices": [[0, 0], [4000, 0], [4000, 6000], [0, 6000]]}},
            ],
            "adjacencies": [], "doors": [],
        }
        report = reconcile(decl, read)
        missing = [f for f in report if f["rule"] == "room_missing"]
        assert missing == [], f"几何匹配应命中：{missing}"

    def test_severity_unified_vocab(self):
        """severity 只出 error/warning/info（无 FAIL/WARNING 两套词）。"""
        from floorgeom.reconcile import reconcile
        decl = {"rooms": [{"id": "a", "area_sqm": 10, "centroid_mm": [0, 0]}],
                "adjacencies": [], "doors": []}
        read = {"rooms": [], "adjacencies": [], "doors": []}
        report = reconcile(decl, read)
        assert report
        for f in report:
            assert f["severity"] in ("error", "warning", "info")

    def test_room_missing_has_bbox(self):
        """room_missing 错误信息带 bbox（诊断化）。"""
        from floorgeom.reconcile import reconcile
        decl = {"rooms": [{"id": "a", "area_sqm": 10,
                           "centroid_mm": [1000.0, 1000.0],
                           "bbox_mm": [0.0, 0.0, 4000.0, 6000.0]}],
                "adjacencies": [], "doors": []}
        read = {"rooms": [], "adjacencies": [], "doors": []}
        report = reconcile(decl, read)
        missing = [f for f in report if f["rule"] == "room_missing"]
        assert missing
        assert "bbox" in missing[0]["message"] or "0.0" in missing[0]["message"]

    def test_room_graph_has_centroid(self):
        """to_room_graph 房间带 centroid_mm（几何匹配输入）。"""
        from floorgeom.room_graph import to_room_graph
        normalized = {
            "rooms": [
                {"id": "office_01", "type": "office", "area_sqm": 24.0,
                 "neighbors": [],
                 "polygon_mm": {"vertices": [[0, 0], [4000, 0], [4000, 6000], [0, 6000]],
                                "area_sqm": 24.0, "centroid_mm": [2000.0, 3000.0]}},
            ],
            "openings": [],
        }
        g = to_room_graph(normalized)
        assert g["rooms"][0]["centroid_mm"] == [2000.0, 3000.0]

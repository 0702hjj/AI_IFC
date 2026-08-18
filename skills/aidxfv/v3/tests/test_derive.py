"""derive.py 测试（T11 直边版 + T12 弧/孔/语境版）。"""

import json
import math
from pathlib import Path

import pytest

from floorgeom.derive import derive, _dir_of_segment, _region_of_point

GEOM_FIXTURES = Path(__file__).resolve().parent / "golden" / "geom"


def _load(name: str) -> dict:
    with open(GEOM_FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


def _plan_with_zone(zone: dict) -> dict:
    """把单 zone 包成 plan zones 数组（derive 输入 = 整 plan zones）。"""
    return {"zones": [zone]}


# --- 方位判定（T11 基础） ---

class TestDirOfSegment:
    def test_north(self):
        assert _dir_of_segment((0, 0), (0, 10)) == "N"

    def test_south(self):
        assert _dir_of_segment((0, 0), (0, -10)) == "S"

    def test_east(self):
        assert _dir_of_segment((0, 0), (10, 0)) == "E"

    def test_west(self):
        assert _dir_of_segment((0, 0), (-10, 0)) == "W"

    def test_ne(self):
        assert _dir_of_segment((0, 0), (5, 5)) == "NE"

    def test_se(self):
        assert _dir_of_segment((0, 0), (5, -5)) == "SE"

    def test_nw(self):
        assert _dir_of_segment((0, 0), (-5, 5)) == "NW"

    def test_sw(self):
        assert _dir_of_segment((0, 0), (-5, -5)) == "SW"

    def test_22deg_boundary_n(self):
        """±22.5° 归并边界：11° 偏角仍归 N。"""
        x, y = math.sin(math.radians(11)) * 10, math.cos(math.radians(11)) * 10
        assert _dir_of_segment((0, 0), (x, y)) == "N"


class TestRegionOfPoint:
    def test_center(self):
        assert _region_of_point(10, 10, 0, 0, 20, 20) == "center"

    def test_se(self):
        assert _region_of_point(18, 2, 0, 0, 20, 20) == "SE"

    def test_nw(self):
        assert _region_of_point(2, 18, 0, 0, 20, 20) == "NW"

    def test_sw(self):
        assert _region_of_point(2, 2, 0, 0, 20, 20) == "SW"

    def test_ne(self):
        assert _region_of_point(18, 18, 0, 0, 20, 20) == "NE"


# --- T11 直边版正例 ---

class TestDeriveStraightEdges:
    """rect_60x40 夹具：60m x 40m 矩形。"""

    @pytest.fixture
    def rect(self):
        zone = {
            "id": "rect",
            "outline_mm": [{"outer": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]], "holes": [], "arcs": []}],
        }
        return derive(_plan_with_zone(zone))["floors"]["f1"]

    def test_area(self, rect):
        assert rect["area_sqm"] == pytest.approx(2400.0, rel=1e-9)

    def test_bbox(self, rect):
        assert rect["bbox_m"]["w"] == pytest.approx(60.0)
        assert rect["bbox_m"]["d"] == pytest.approx(40.0)

    def test_aspect_ratio(self, rect):
        assert rect["aspect_ratio"] == pytest.approx(1.5)

    def test_perimeter(self, rect):
        assert rect["perimeter_m"] == pytest.approx(200.0)

    def test_edges_dirs(self, rect):
        dirs = sorted(e["dir"] for e in rect["edges"])
        assert dirs == ["E", "N", "S", "W"]

    def test_edges_kinds_line(self, rect):
        assert all(e["kind"] == "line" for e in rect["edges"])

    def test_exposure_sum(self, rect):
        s = sum(rect["exposure_m"].values())
        assert s == pytest.approx(200.0)

    def test_concave_corners_empty(self, rect):
        assert rect["concave_corners"] == []

    def test_dominant_axes(self, rect):
        assert rect["dominant_axes"]["x"] == [0, 60000]
        assert rect["dominant_axes"]["y"] == [0, 40000]

    def test_strip_area(self, rect):
        assert rect["strip_area"]["per_m_x_sqm"] == pytest.approx(40.0)  # 面积/宽
        assert rect["strip_area"]["per_m_y_sqm"] == pytest.approx(60.0)  # 面积/深

    def test_depth_max(self, rect):
        assert rect["depth"]["max_m"] == pytest.approx(40.0)

    def test_deep_zone_ratio_rect_20m(self, rect):
        """40m 深矩形，距边>8m 的中央区占比 >0。"""
        assert rect["depth"]["deep_zone_ratio"] > 0

    def test_floor_key(self, rect):
        assert rect["floor"] == "f1"


class TestDeriveLShape:
    """l_shape 夹具：L 形（有凹角）。"""

    @pytest.fixture
    def lshape(self):
        zone = {
            "id": "l",
            "outline_mm": [{
                "outer": [[0, 0], [40000, 0], [40000, 20000], [20000, 20000],
                          [20000, 40000], [0, 40000]],
                "holes": [], "arcs": [],
            }],
        }
        return derive(_plan_with_zone(zone))["floors"]["f1"]

    def test_area(self, lshape):
        # 60x40 缺 20x20 = 2400 - 400 = 1200㎡
        assert lshape["area_sqm"] == pytest.approx(1200.0)

    def test_concave_corner_detected(self, lshape):
        # 凹角在 (20000,20000)——bbox 0-40k 的正中心
        assert len(lshape["concave_corners"]) == 1
        c = lshape["concave_corners"][0]
        assert c["at_vertex"] == 3
        assert c["region"] == "center"

    def test_edges_more_than_4(self, lshape):
        assert len(lshape["edges"]) == 6


class TestDeriveConcave:
    """concave 夹具：带台阶凹口的复杂轮廓（R-01 简化版）。"""

    def test_concave_detected(self):
        zone = {
            "id": "c",
            "outline_mm": [{
                "outer": [[0, 0], [10000, 0], [10000, 3000], [5000, 3000],
                          [5000, 7000], [0, 7000]],
                "holes": [], "arcs": [],
            }],
        }
        g = derive(_plan_with_zone(zone))["floors"]["f1"]
        # 凹角仅在 (5000,3000)（L 形拐点）——面积 10*7 - 5*4 = 50㎡
        assert len(g["concave_corners"]) == 1
        assert g["area_sqm"] == pytest.approx(50.0)


# --- T12 弧/孔/语境版 ---

class TestDeriveArc:
    """真弧边：半圆厅（矩形 + 东端半圆）。"""

    @pytest.fixture
    def semicircle(self):
        # 矩形 20m x 10m，东端接 R=5000 半圆（弧从 (20000,0) 到 (20000,10000) 经圆心 (20000,5000)）
        zone = {
            "id": "arc",
            "outline_mm": [{
                "outer": {
                    "vertices": [[0, 0], [20000, 0], [20000, 10000], [0, 10000]],
                    "arcs": [{"at": 1, "center": [20000, 5000], "radius": 5000, "a0": -90, "a1": 90}],
                },
                "holes": [], "arcs": [],
            }],
        }
        return derive(_plan_with_zone(zone))["floors"]["f1"]

    def test_area(self, semicircle):
        # 矩形 200㎡ + 半圆 π*25/2 ≈ 39.27 → 239.27
        assert semicircle["area_sqm"] == pytest.approx(200 + math.pi * 25 / 2, rel=1e-2)

    def test_arc_edge_kind(self, semicircle):
        arc_edges = [e for e in semicircle["edges"] if e["kind"] == "arc"]
        assert len(arc_edges) == 1
        assert arc_edges[0]["arc"]["radius"] == pytest.approx(5000.0)

    def test_arc_edge_dir_e(self, semicircle):
        """弧段弦方位：从 (20000,0) 到 (20000,10000) 垂直向上 → N。"""
        arc_edges = [e for e in semicircle["edges"] if e["kind"] == "arc"]
        assert arc_edges[0]["dir"] == "N"

    def test_edges_total_length(self, semicircle):
        """周长 = 3 直线边（20000+10000+20000）+ 半圆弧长 π*5000。"""
        total = sum(e["len_m"] for e in semicircle["edges"])
        assert total == pytest.approx(20 + 10 + 20 + math.pi * 5, rel=1e-2)


class TestDeriveHoles:
    """真圆孔：矩形带圆孔。"""

    @pytest.fixture
    def with_hole(self):
        # 真圆孔：3 顶点 + 3 段 120° 弧（CCW，aiplan circle_ring 同款）
        zone = {
            "id": "hole",
            "outline_mm": [{
                "outer": [[0, 0], [24000, 0], [24000, 18000], [0, 18000]],
                "holes": [{
                    "vertices": [[9000, 6000], [15000, 9000], [9000, 12000]],
                    "arcs": [
                        {"at": 0, "center": [12000, 9000], "radius": 3000, "a0": 210, "a1": 330},
                        {"at": 1, "center": [12000, 9000], "radius": 3000, "a0": 330, "a1": 90},
                        {"at": 2, "center": [12000, 9000], "radius": 3000, "a0": 90, "a1": 210},
                    ],
                }],
                "arcs": [],
            }],
        }
        return derive(_plan_with_zone(zone))["floors"]["f1"]

    def test_net_area(self, with_hole):
        # 24*18 - π*9 = 432 - 28.27 ≈ 403.7
        assert with_hole["area_sqm"] == pytest.approx(432 - math.pi * 9, rel=1e-2)

    def test_hole_derived(self, with_hole):
        assert len(with_hole["holes"]) == 1
        h = with_hole["holes"][0]
        assert h["area_sqm"] == pytest.approx(math.pi * 9, rel=1e-2)
        assert h["region"] == "center"

    def test_deep_zone_with_hole(self, with_hole):
        assert with_hole["depth"]["deep_zone_ratio"] > 0


class TestDeriveCoreContext:
    """core_anchor 语境：relative + dist_to_edges。"""

    @pytest.fixture
    def core(self):
        zone = {
            "id": "ctx",
            "outline_mm": [{"outer": [[0, 0], [20000, 0], [20000, 20000], [0, 20000]], "holes": [], "arcs": []}],
            "core_anchor_mm": [5000, 5000],  # 左下偏
        }
        return derive(_plan_with_zone(zone))["floors"]["f1"]

    def test_core_anchor_abs(self, core):
        assert core["core_anchor"]["abs"] == [5000, 5000]

    def test_core_anchor_relative_sw(self, core):
        # 20x20 中心 (10k,10k)，锚 (5k,5k) → 偏SW（东南向自然语言）
        assert core["core_anchor"]["relative"] == "偏SW"

    def test_core_dist_to_edges(self, core):
        d = core["core_anchor"]["dist_to_edges_m"]
        assert d["W"] == pytest.approx(5.0)
        assert d["S"] == pytest.approx(5.0)
        assert d["N"] == pytest.approx(15.0)
        assert d["E"] == pytest.approx(15.0)


class TestDeriveMultiCore:
    """多核心筒锚点语境（D31）：plan core_anchor_mm 嵌套数组 或 core ring 数组。

    输出 core_anchors 数组（总是），core_anchor 兼容键（单=对象/多=首个）。
    """

    def _zone_multi_anchor(self):
        return {
            "id": "ctx",
            "outline_mm": [{"outer": [[0, 0], [44300, 0], [44300, 17200], [0, 17200]], "holes": [], "arcs": []}],
            "core_anchor_mm": [[10900, 10500], [32800, 13500]],  # 双锚点
        }

    def test_multi_anchor_array(self):
        z = self._zone_multi_anchor()
        f = derive(_plan_with_zone(z))["floors"]["f1"]
        assert isinstance(f["core_anchors"], list) and len(f["core_anchors"]) == 2
        assert f["core_anchors"][0]["abs"] == [10900, 10500]
        assert f["core_anchors"][1]["abs"] == [32800, 13500]

    def test_multi_anchor_compat_key(self):
        """core_anchor 兼容键 = 首个锚点。"""
        z = self._zone_multi_anchor()
        f = derive(_plan_with_zone(z))["floors"]["f1"]
        assert f["core_anchor"]["abs"] == [10900, 10500]

    def test_single_anchor_also_has_anchors(self):
        """单锚点也产 core_anchors（=[anchor]），向后兼容。"""
        zone = {
            "id": "ctx",
            "outline_mm": [{"outer": [[0, 0], [20000, 0], [20000, 20000], [0, 20000]], "holes": [], "arcs": []}],
            "core_anchor_mm": [5000, 5000],
        }
        f = derive(_plan_with_zone(zone))["floors"]["f1"]
        assert f["core_anchors"] == [f["core_anchor"]] or f["core_anchors"][0] == f["core_anchor"]

    def test_multi_core_ring_array(self):
        """core 为 ring 数组（多核心筒轮廓）→ 各质心进 core_anchors。"""
        zone = {
            "id": "ctx",
            "outline_mm": [{"outer": [[0, 0], [44300, 0], [44300, 17200], [0, 17200]], "holes": [], "arcs": []}],
            "core": [
                [[9700, 9380], [12100, 9380], [12100, 11660], [9700, 11660]],
                [[31600, 12380], [34000, 12380], [34000, 14660], [31600, 14660]],
            ],
        }
        f = derive(_plan_with_zone(zone))["floors"]["f1"]
        assert len(f["core_anchors"]) == 2
        assert f["core_anchors"][0]["abs"] == [10900, 10520]


class TestDeriveNeighborsAndDiff:
    """跨 zone 邻接 + 跨层差异。"""

    def test_neighbors(self):
        plan = {"zones": [
            {"id": "podium", "floors": {"from": 1, "to": 1},
             "outline_mm": [{"outer": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]], "holes": [], "arcs": []}]},
            {"id": "tower", "floors": {"from": 2, "to": 2},
             "outline_mm": [{"outer": [[18000, 22000], [42000, 22000], [42000, 40000], [18000, 40000]], "holes": [], "arcs": []}]},
        ]}
        g = derive(plan)
        # tower 的 floor f2 邻接 podium（共享底边）
        assert g["floors"]["f2"]["neighbors"]  # 非空

    def test_diff_from_prev(self):
        """渐退链：t10 大、t11 南内缩 3m → f11 有 inset。"""
        plan = {"zones": [
            {"id": "t", "floors": [10, 11],
             "outline_mm": [
                 {"outer": [[0, 0], [20000, 0], [20000, 20000], [0, 20000]], "holes": [], "arcs": []},
             ]},
        ]}
        # 为第二层构造不同 outline 需要 plan 支持 per-floor outline——当前 plan 单层 outline。
        # 用两个 zone（同名不同层）模拟渐退链：
        plan2 = {"zones": [
            {"id": "t", "floors": [10],
             "outline_mm": [{"outer": [[0, 0], [20000, 0], [20000, 20000], [0, 20000]], "holes": [], "arcs": []}]},
            {"id": "t", "floors": [11],
             "outline_mm": [{"outer": [[0, 0], [20000, 0], [20000, 17000], [0, 17000]], "holes": [], "arcs": []}]},
        ]}
        g = derive(plan2)
        assert g["floors"]["f10"]["diff_from_prev"] is None  # 首层无差量
        d = g["floors"]["f11"]["diff_from_prev"]
        assert d is not None
        assert d["floor"] == "f10"
        # 南边内缩 3000mm
        assert d["inset_mm"]["N"] == 3000

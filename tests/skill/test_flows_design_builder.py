import copy
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FLOWS_DIR = REPO_ROOT / "skills" / "aiifc" / "references" / "docs" / "flows"

sys.path.insert(0, str(FLOWS_DIR))

import design_builder
from design_builder import SchemaError


def _design():
    return {
        "meta": {"modulus": 0.1},
        "frame": {
            "footprint": [[0, 0], [12, 0], [12, 8], [0, 8]],
            "storeys": {"1F": 0.0},
            "axis_grid": {"x": [0, 4, 12], "y": [0, 8]},
        },
        "floors": {"1F": {}},
    }


def _with_floor(design, storey, floor):
    design["floors"][storey] = floor
    return design


class TestSchemaErrorFootprint:
    def test_footprint_fewer_than_3_points(self):
        design = _design()
        design["frame"]["footprint"] = [[0, 0], [12, 0]]
        with pytest.raises(SchemaError, match="footprint 需 ≥3 点"):
            design_builder.normalize(design)

    def test_closed_footprint_collapses_below_3_points(self):
        design = _design()
        design["frame"]["footprint"] = [[0, 0], [12, 0], [0, 0]]
        with pytest.raises(SchemaError, match="footprint 需 ≥3 点"):
            design_builder.normalize(design)


class TestSchemaErrorStoreys:
    def test_missing_storeys(self):
        design = _design()
        del design["frame"]["storeys"]
        with pytest.raises(SchemaError, match="frame.storeys 必填"):
            design_builder.normalize(design)

    def test_empty_storeys(self):
        design = _design()
        design["frame"]["storeys"] = {}
        with pytest.raises(SchemaError, match="frame.storeys 必填"):
            design_builder.normalize(design)


class TestSchemaErrorPathAxisGrid:
    def test_path_index_out_of_range(self):
        design = _with_floor(_design(), "1F", {
            "walls": [{"path": [{"x": 0, "y": 0}, {"x": 9, "y": 0}]}],
        })
        with pytest.raises(SchemaError, match="path 轴网索引越界"):
            design_builder.normalize(design)

    def test_path_missing_axis_key(self):
        design = _with_floor(_design(), "1F", {
            "walls": [{"path": [{"x": 0}, {"x": 1, "y": 0}]}],
        })
        with pytest.raises(SchemaError, match="path 轴网索引越界"):
            design_builder.normalize(design)

    def test_path_diagonal_segment_rejected(self):
        design = _with_floor(_design(), "1F", {
            "walls": [{"path": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]}],
        })
        with pytest.raises(SchemaError, match="不沿轴网"):
            design_builder.normalize(design)


class TestSchemaErrorStairShaft:
    def test_shaft_index_out_of_range(self):
        design = _with_floor(_design(), "1F", {
            "stairs": [{"type": "evac", "width": 1.2,
                        "shaft": {"x": [0, 9], "y": [0, 1]}}],
        })
        with pytest.raises(SchemaError, match="stairs shaft 轴网索引越界"):
            design_builder.normalize(design)

    def test_shaft_wrong_pair_length(self):
        design = _with_floor(_design(), "1F", {
            "stairs": [{"type": "evac", "width": 1.2,
                        "shaft": {"x": [0, 1, 2], "y": [0, 1]}}],
        })
        with pytest.raises(SchemaError, match="stairs shaft 轴网索引越界"):
            design_builder.normalize(design)


class TestDeterministicKeys:
    def test_same_input_same_output(self):
        design = _with_floor(_design(), "1F", {
            "walls": [
                {"axis": [[0, 0], [12, 0]]},
                {"axis": [[0, 8], [12, 8]], "kind": "ext"},
            ],
            "openings": [{"wall": 0, "along": 2.0, "w": 1.0, "h": 2.1, "type": "door"}],
        })
        assert design_builder.normalize(copy.deepcopy(design)) == \
               design_builder.normalize(copy.deepcopy(design))

    def test_auto_key_format(self):
        design = _with_floor(_design(), "1F", {
            "walls": [{"axis": [[0, 0], [12, 0]]}, {"axis": [[0, 8], [12, 8]]}],
            "openings": [{"wall": 0, "along": 2.0, "w": 1.0, "h": 2.1}],
            "stairs": [{"type": "open", "width": 1.0, "at": [2, 2]}],
        })
        feat = design_builder.normalize(design)
        assert [w["key"] for w in feat["walls"]] == ["1F:wall:0", "1F:wall:1"]
        assert [o["key"] for o in feat["openings"]] == ["1F:opening:0"]
        assert [s["key"] for s in feat["slabs"]] == ["1F:slab:0"]
        assert [s["key"] for s in feat["stairs"]] == ["1F:stair:0"]

    def test_explicit_keys_preserved(self):
        design = _with_floor(_design(), "1F", {
            "walls": [{"axis": [[0, 0], [12, 0]], "key": "W-SOUTH"}],
        })
        feat = design_builder.normalize(design)
        assert feat["walls"][0]["key"] == "W-SOUTH"


class TestTypicalStoreyExpansion:
    def test_typical_key_expands_to_listed_storeys(self):
        design = _design()
        design["frame"]["storeys"] = {"1F": 0.0, "2F": 3.0, "3F": 6.0}
        design["frame"]["typical"] = {"STD": ["2F", "3F"]}
        design["floors"] = {
            "1F": {"walls": [{"axis": [[0, 0], [12, 0]]}]},
            "STD": {"walls": [{"axis": [[0, 8], [12, 8]]}]},
        }
        feat = design_builder.normalize(design)
        by_storey = {}
        for w in feat["walls"]:
            by_storey.setdefault(w["storey"], []).append(w)
        assert set(by_storey) == {"1F", "2F", "3F"}
        assert by_storey["2F"][0]["axis"] == [(0.0, 8.0), (12.0, 8.0)]
        assert by_storey["3F"][0]["axis"] == [(0.0, 8.0), (12.0, 8.0)]
        assert by_storey["2F"][0]["key"] == "2F:wall:0"
        assert by_storey["3F"][0]["key"] == "3F:wall:0"

    def test_typical_storey_gets_default_slab(self):
        design = _design()
        design["frame"]["storeys"] = {"1F": 0.0, "2F": 3.0}
        design["frame"]["typical"] = {"STD": ["2F"]}
        design["floors"] = {
            "1F": {"walls": [{"axis": [[0, 0], [12, 0]]}]},
            "STD": {"walls": [{"axis": [[0, 8], [12, 8]]}]},
        }
        feat = design_builder.normalize(design)
        slab_storeys = sorted(s["storey"] for s in feat["slabs"])
        assert slab_storeys == ["1F", "2F"]
        for s in feat["slabs"]:
            assert s["t"] == 0.15
            assert s["profile"] == [(0.0, 0.0), (12.0, 0.0), (12.0, 8.0), (0.0, 8.0)]

    def test_empty_floor_def_produces_nothing(self):
        design = _design()
        design["floors"] = {"1F": {}}
        feat = design_builder.normalize(design)
        assert feat["walls"] == []
        assert feat["slabs"] == []


class TestArcChordApproximation:
    def _arc_wall(self, a0=0.0, a1=90.0, r=5.0):
        design = _with_floor(_design(), "1F", {
            "walls": [{"arc": {"center": [0, 0], "r": r, "a0": a0, "a1": a1}}],
        })
        return design_builder.normalize(design)["walls"][0]

    def test_segment_count_follows_12_degree_rule(self):
        wall = self._arc_wall(a0=0.0, a1=90.0)
        n = max(4, int(math.radians(90.0) / math.radians(12)))
        assert len(wall["axis"]) == n + 1

    def test_minimum_4_segments(self):
        wall = self._arc_wall(a0=0.0, a1=10.0)
        assert len(wall["axis"]) == 5

    def test_points_lie_on_circle(self):
        wall = self._arc_wall(a0=0.0, a1=90.0, r=5.0)
        for x, y in wall["axis"]:
            assert math.hypot(x, y) == pytest.approx(5.0, abs=1e-6)

    def test_endpoints_match_angles(self):
        wall = self._arc_wall(a0=0.0, a1=90.0, r=5.0)
        assert wall["axis"][0] == pytest.approx((5.0, 0.0), abs=1e-6)
        assert wall["axis"][-1] == pytest.approx((0.0, 5.0), abs=1e-6)


class TestFootprintClosure:
    def test_duplicate_closing_point_removed(self):
        design = _design()
        design["frame"]["footprint"] = [[0, 0], [12, 0], [12, 8], [0, 8], [0, 0]]
        feat = design_builder.normalize(design)
        assert feat["footprint"] == [(0.0, 0.0), (12.0, 0.0), (12.0, 8.0), (0.0, 8.0)]

    def test_bounds_from_footprint(self):
        feat = design_builder.normalize(_design())
        assert feat["bounds"] == {"x": [0.0, 12.0], "y": [0.0, 8.0]}

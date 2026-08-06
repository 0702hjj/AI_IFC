import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FLOWS_DIR = REPO_ROOT / "skills" / "aiifc" / "references" / "docs" / "flows"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

sys.path.insert(0, str(FLOWS_DIR))

ezdxf = pytest.importorskip("ezdxf")

import design_builder
import dxf_from_design


def _opening_lines(doc):
    return [
        e for e in doc.modelspace()
        if e.dxftype() == "LINE" and e.dxf.layer == dxf_from_design.LAYER_OPENING
    ]


def _line_length(e):
    return (e.dxf.end - e.dxf.start).magnitude


def _features_one_wall(axis, opening_type="door"):
    return {
        "storeys": {"1F": 0.0},
        "footprint": [[0, 0], [12, 0], [12, 8], [0, 8]],
        "walls": [{"storey": "1F", "axis": axis, "t": 0.2}],
        "openings": [
            {"storey": "1F", "wall": 0, "along": 2.0, "w": 1.0, "h": 2.1,
             "type": opening_type}
        ],
        "stairs": [],
    }


class TestStairShaft:
    def test_design_with_shaft_stair_generates_stair_layer(self):
        data, kind = dxf_from_design._load(FIXTURES / "sample_design_stair.json")
        assert kind == "design"
        doc = dxf_from_design.generate(data)
        stair_entities = [
            e for e in doc.modelspace() if e.dxf.layer == dxf_from_design.LAYER_STAIR
        ]
        assert stair_entities, "STAIR 图层应有楼梯实体"

    def test_normalized_features_with_shaft_stair(self):
        design = __import__("json").loads(
            (FIXTURES / "sample_design_stair.json").read_text(encoding="utf-8")
        )
        features = design_builder.normalize(design)
        doc = dxf_from_design.generate(features)
        stair_entities = [
            e for e in doc.modelspace() if e.dxf.layer == dxf_from_design.LAYER_STAIR
        ]
        assert stair_entities, "features 输入的 shaft 楼梯应落在 STAIR 图层"

    def test_shaft_rect_matches_axis_grid(self):
        design = __import__("json").loads(
            (FIXTURES / "sample_design_stair.json").read_text(encoding="utf-8")
        )
        features = design_builder.normalize(design)
        doc = dxf_from_design.generate(features)
        polys = [
            e for e in doc.modelspace()
            if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == dxf_from_design.LAYER_STAIR
        ]
        xs = sorted({p[0] for p in polys[0].get_points()})
        ys = sorted({p[1] for p in polys[0].get_points()})
        assert xs == [0, 4]
        assert ys == [4, 8]


class TestOpeningJamb:
    @pytest.mark.parametrize("axis", [
        [[0, 0], [12, 0]],    # 水平墙
        [[0, 0], [0, 8]],     # 垂直墙
        [[0, 0], [8, 8]],     # 斜向墙
        [[12, 0], [0, 0]],    # 反向水平墙
    ])
    def test_jamb_lines_nonzero_length(self, axis):
        doc = dxf_from_design.generate(_features_one_wall(axis))
        jambs = _opening_lines(doc)
        assert len(jambs) >= 2, "开口应有两条 jamb 线"
        for j in jambs:
            assert _line_length(j) > 1e-6, f"jamb 线退化为零长: axis={axis}"


class TestDoorArcOrientation:
    def _arc_start_angle(self, axis):
        doc = dxf_from_design.generate(_features_one_wall(axis))
        arcs = [
            e for e in doc.modelspace()
            if e.dxftype() == "ARC" and e.dxf.layer == dxf_from_design.LAYER_OPENING
        ]
        assert arcs, "门应画弧线"
        return arcs[0].dxf.start_angle

    def test_arc_start_follows_wall_direction(self):
        angle_h = self._arc_start_angle([[0, 0], [12, 0]])
        angle_v = self._arc_start_angle([[0, 0], [0, 8]])
        angle_rev = self._arc_start_angle([[12, 0], [0, 0]])
        assert angle_h == pytest.approx(0.0, abs=1e-6)
        assert angle_v == pytest.approx(90.0, abs=1e-6)
        assert angle_rev == pytest.approx(180.0, abs=1e-6)

    def test_arc_span_is_quarter_circle(self):
        doc = dxf_from_design.generate(_features_one_wall([[0, 0], [0, 8]]))
        arc = next(
            e for e in doc.modelspace()
            if e.dxftype() == "ARC" and e.dxf.layer == dxf_from_design.LAYER_OPENING
        )
        span = (arc.dxf.end_angle - arc.dxf.start_angle) % 360
        assert span == pytest.approx(90.0, abs=1e-6)


class TestScaleArgRemoved:
    def test_scale_arg_rejected(self, tmp_path, monkeypatch):
        out = tmp_path / "plan.dxf"
        monkeypatch.setattr(sys, "argv", [
            "dxf_from_design.py",
            str(FIXTURES / "sample_design.json"),
            "-o", str(out),
            "--scale", "100",
        ])
        with pytest.raises(SystemExit) as exc:
            dxf_from_design.main()
        assert exc.value.code != 0

    def test_main_runs_without_scale(self, tmp_path, monkeypatch, capsys):
        out = tmp_path / "plan.dxf"
        monkeypatch.setattr(sys, "argv", [
            "dxf_from_design.py",
            str(FIXTURES / "sample_design_stair.json"),
            "-o", str(out),
        ])
        dxf_from_design.main()
        assert out.exists() and out.stat().st_size > 0

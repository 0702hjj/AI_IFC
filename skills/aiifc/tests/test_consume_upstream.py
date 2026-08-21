"""consume_upstream 测试（上游产物 → design.json 转换器，cad->ifc 消费上游）。

链路：building.json（zones 记 modelId）+ bim_supplement.json + DXF outline → design.json
（DESIGN_JSON_SCHEMA 协议：frame{footprint,storeys,typical} + floors{walls,openings,roof}）。
精确几何直用（DXF outline_mm → footprint，mm→m）。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from aiifc.consume_upstream import consume_upstream

CLI = [sys.executable, "-m", "aiifc.cli"]


@pytest.fixture()
def upstream(tmp_path):
    building = tmp_path / "building.json"
    building.write_text(json.dumps({
        "version": 2, "project": "test",
        "zones": [{"zone": "tower", "floors_from": 1, "floors_to": 3,
                   "modelId": "m_0123456789abcdef", "typology": "residence"}],
    }), encoding="utf-8")
    bim = tmp_path / "bim.json"
    bim.write_text(json.dumps({"roof": {"type": "gable", "slope_deg": 30}}), encoding="utf-8")
    return str(building), str(bim), str(tmp_path)


def test_storeys_from_zones(upstream):
    b, bm, d = upstream
    design = consume_upstream(b, bm, d)
    storeys = design["frame"]["storeys"]
    assert storeys == {"1F": 0.0, "2F": 3.0, "3F": 6.0}


def test_typical_from_typology(upstream):
    b, bm, d = upstream
    design = consume_upstream(b, bm, d)
    typical = design["frame"].get("typical", {})
    assert "RESIDENCE" in typical
    assert typical["RESIDENCE"] == ["1F", "2F", "3F"]


def test_roof_from_bim(upstream):
    b, bm, d = upstream
    design = consume_upstream(b, bm, d)
    # bim roof → 各层（顶层）roof 字段
    assert design["floors"]["3F"].get("roof", {}).get("type") == "gable"


def test_meta_from_project(upstream):
    b, bm, d = upstream
    design = consume_upstream(b, bm, d)
    assert design["meta"]["name"] == "test"
    assert design["meta"]["units"] == "m"


def test_footprint_from_dxf(upstream, tmp_path):
    """footprint：首层 DXF outline（readback outline_mm，mm→m，精确几何直用）。"""
    b, bm, d = upstream
    # 造一个矩形轮廓 DXF
    from dxfkit import draw
    draw.reset_keys()
    doc = draw.new_doc()
    msp = doc.modelspace()
    draw.wall_run(msp, (0, 0), (10000, 0), 200, cuts=[])
    draw.wall_run(msp, (10000, 0), (10000, 8000), 200, cuts=[])
    draw.wall_run(msp, (10000, 8000), (0, 8000), 200, cuts=[])
    draw.wall_run(msp, (0, 8000), (0, 0), 200, cuts=[])
    dxf_path = tmp_path / "tower.dxf"
    doc.saveas(str(dxf_path))
    design = consume_upstream(b, bm, str(tmp_path))
    fp = design["frame"].get("footprint", [])
    assert len(fp) >= 3, "footprint 应 ≥3 点（闭合多边形）"
    # mm→m（10000mm → 10m）
    xs = [p[0] for p in fp]
    assert max(xs) == pytest.approx(10.0, abs=0.5)


def test_cli_consume_upstream(upstream, tmp_path):
    """CLI：aiifc consume-upstream → design.json 落盘。"""
    b, bm, d = upstream
    out = tmp_path / "design.json"
    r = subprocess.run(CLI + ["consume-upstream", "--building", b, "--bim", bm,
                              "--dxf-dir", d, "-o", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert out.is_file()
    design = json.loads(out.read_text(encoding="utf-8"))
    assert design["frame"]["storeys"] == {"1F": 0.0, "2F": 3.0, "3F": 6.0}


def _make_dxf(path, walls, arcs=None):
    """造 DXF：walls=[(p0,p1,t)] 直墙 + arcs=[(center,r,a0,a1)] 弧墙（WALL 图层）。"""
    from dxfkit import draw
    draw.reset_keys()
    doc = draw.new_doc()
    msp = doc.modelspace()
    for p0, p1, t in walls:
        draw.wall_run(msp, p0, p1, t, cuts=[])
    for center, r, a0, a1 in (arcs or []):
        msp.add_arc(center=center, radius=r, start_angle=a0, end_angle=a1,
                    dxfattribs={"layer": "WALL"})
    doc.saveas(str(path))


def test_dxf_walls_and_openings(tmp_path):
    """DXF 直墙 + 门窗 → floors.walls（axis）+ openings（沿墙 at→along）。"""
    dxf = tmp_path / "tower.dxf"
    _make_dxf(dxf, [
        ((0, 0), (10000, 0), 200), ((10000, 0), (10000, 8000), 200),
        ((10000, 8000), (0, 8000), 200), ((0, 8000), (0, 0), 200),
    ])
    building = tmp_path / "b.json"
    building.write_text('{"version":2,"project":"t","zones":[{"zone":"tower","floors_from":1,"floors_to":1,"modelId":"m_1"}]}')
    bim = tmp_path / "bim.json"
    bim.write_text('{}')
    design = consume_upstream(str(building), str(bim), str(tmp_path))
    f = design["floors"]["1F"]
    assert len(f["walls"]) >= 4, "直墙段应映射为 walls（axis 折线）"
    for w in f["walls"]:
        assert "axis" in w and len(w["axis"]) >= 2, "直墙 → axis 折线"
    assert len(f["slabs"]) == 1, "outline → slabs.profile"


def test_dxf_arc_wall(tmp_path):
    """DXF 弧墙（add_arc WALL 图层）→ floors.walls 的 arc 形态（center/r/a0/a1）——语义对齐。"""
    dxf = tmp_path / "curve.dxf"
    _make_dxf(dxf,
              [((0, 0), (10000, 0), 200), ((10000, 0), (10000, 8000), 200), ((0, 8000), (0, 0), 200)],
              arcs=[((5000, 8000), 5000, 0, 180)])
    building = tmp_path / "b.json"
    building.write_text('{"version":2,"project":"c","zones":[{"zone":"curve","floors_from":1,"floors_to":1,"modelId":"m_1"}]}')
    bim = tmp_path / "bim.json"
    bim.write_text('{}')
    design = consume_upstream(str(building), str(bim), str(tmp_path))
    arcs = [w for w in design["floors"]["1F"]["walls"] if "arc" in w]
    assert len(arcs) == 1, "弧墙应映射为 walls 的 arc 形态"
    arc = arcs[0]["arc"]
    assert arc["r"] == pytest.approx(5.0, abs=0.01)  # 5000mm → 5m
    assert arc["a0"] == 0.0 and arc["a1"] == 180.0
    assert arc["center"] == [5.0, 8.0]  # mm→m


def test_arc_design_json_passes_design_build(tmp_path):
    """含 arc 墙的 design.json 能过 design_builder（语义对齐——曲线可消费）。"""
    import subprocess as sp
    dxf = tmp_path / "curve.dxf"
    _make_dxf(dxf,
              [((0, 0), (10000, 0), 200), ((10000, 0), (10000, 8000), 200), ((0, 8000), (0, 0), 200)],
              arcs=[((5000, 8000), 5000, 0, 180)])
    building = tmp_path / "b.json"
    building.write_text('{"version":2,"project":"c","zones":[{"zone":"curve","floors_from":1,"floors_to":1,"modelId":"m_1"}]}')
    bim = tmp_path / "bim.json"
    bim.write_text('{}')
    design = consume_upstream(str(building), str(bim), str(tmp_path))
    design_path = tmp_path / "design.json"
    design_path.write_text(json.dumps(design, ensure_ascii=False))
    # design-build（design_builder 消费含 arc 的 design.json）
    r = sp.run(CLI + ["design-build", str(design_path), "-o", str(tmp_path / "feat.json")],
               capture_output=True, text=True,
               env={"AIIFC_FLOWS_DIR": "", **__import__("os").environ})
    # design_builder 需要 AIIFC_FLOWS_DIR——从 conftest 的 ROOT 推导
    import os
    env = dict(os.environ)
    env["AIIFC_FLOWS_DIR"] = str(Path(__file__).resolve().parents[1] / "references" / "docs" / "flows")
    r = sp.run(CLI + ["design-build", str(design_path), "-o", str(tmp_path / "feat.json")],
               capture_output=True, text=True, env=env)
    assert r.returncode == 0, f"design-build 失败（arc 墙语义不对齐）: {r.stdout} {r.stderr}"

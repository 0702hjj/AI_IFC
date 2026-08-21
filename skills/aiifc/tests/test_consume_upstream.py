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

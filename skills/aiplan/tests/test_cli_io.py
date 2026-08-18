"""CLI 参数加载契约测试（2026-08-17 卡顿修复）。

验收（对应卡顿根因）：
- `geom check --zones` 吃 normalize 落盘文件路径（不再 JSONDecodeError）
- `geom check --zones` 吃内联 JSON（兼容旧用法）
- `area` 吃 normalize 产物（ring object：outer={"vertices","arcs"}）→ 面积正确
- `area` 吃文件路径
- `derive --lot` 接受 dict（points 键）容错，不 KeyError: 0
- 共享加载器 load_json_arg：路径优先 / 内联兼容 / 空串报错
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
AIPLAN = str(HERE.parent / ".venv" / "bin" / "aiplan")

from aiplan_tools.json_arg import coerce_lot_points, load_json_arg  # noqa: E402
from aiplan_tools import area_breakdown as ab  # noqa: E402


# ── load_json_arg ──────────────────────────────────────────────────────────


def test_load_json_arg_inline():
    assert load_json_arg('[[0,0],[10,0]]') == [[0, 0], [10, 0]]


def test_load_json_arg_file(tmp_path):
    f = tmp_path / "zones.json"
    f.write_text('{"zones": [{"id": "std"}]}', encoding="utf-8")
    assert load_json_arg(str(f)) == {"zones": [{"id": "std"}]}


def test_load_json_arg_empty_raises():
    with pytest.raises(ValueError):
        load_json_arg("")


def test_coerce_lot_points_dict():
    """dict 抽 points（容错旧错误用法，防 KeyError: 0）。"""
    pts = coerce_lot_points({"points": [[0, 0], [60000, 0]]})
    assert pts == [[0, 0], [60000, 0]]


def test_coerce_lot_points_bare():
    assert coerce_lot_points([[0, 0], [60000, 0]]) == [[0, 0], [60000, 0]]


def test_coerce_lot_points_bad_dict_raises():
    with pytest.raises(ValueError):
        coerce_lot_points({"type": "polygon"})


# ── area 吃 normalize 产物（ring object）─────────────────────────────────


RING_OUTER = {"vertices": [[3000, 4500], [57000, 4500], [57000, 15000], [3000, 15000]], "arcs": []}
NORMALIZE_BLOCK = {"outer": RING_OUTER, "holes": [], "arcs": []}


def test_area_polygon_area_m2_ring_object():
    """ring object（normalize 产物）→ 面积 54×10.5 = 567㎡。"""
    assert ab.polygon_area_m2({"outer": RING_OUTER}) == pytest.approx(567.0)


def test_area_polygon_area_m2_normalize_list():
    """normalize 产物块列表 [{outer:{vertices}}] → 求和。"""
    assert ab.polygon_area_m2([NORMALIZE_BLOCK]) == pytest.approx(567.0)


def test_area_polygon_area_m2_normalize_top():
    """normalize 顶层 {"zones":[{outline_mm:[...]}]} → 取 zone 面积。"""
    doc = {"zones": [{"outline_mm": [NORMALIZE_BLOCK]}]}
    assert ab.polygon_area_m2(doc) == pytest.approx(567.0)


def test_area_cli_normalize_file(tmp_path):
    """CLI：area 吃 normalize 落盘文件（本次卡顿核心）。"""
    norm = {"zones": [{"outline_mm": [NORMALIZE_BLOCK]}]}
    f = tmp_path / "normalized.json"
    f.write_text(json.dumps(norm), encoding="utf-8")
    prog = '[{"room":"units","count":4,"area_sqm":124}]'
    r = subprocess.run([AIPLAN, "area", str(f), prog, "residence"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "zone 总面积: 567 ㎡" in r.stdout


def test_area_cli_ring_inline():
    """CLI：area 吃内联 ring object。"""
    outline = json.dumps([NORMALIZE_BLOCK])
    prog = '[{"room":"units","count":4,"area_sqm":124},{"room":"core","count":2,"area_sqm":36}]'
    r = subprocess.run([AIPLAN, "area", outline, prog, "residence"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "zone 总面积: 567 ㎡" in r.stdout


# ── geom check --zones 吃文件路径 ───────────────────────────────────────


def _zones_doc():
    return {"zones": [{
        "id": "std",
        "outline_mm": [NORMALIZE_BLOCK],
        "core_anchor_mm": [[16500, 12750], [43500, 12750]],
    }]}


def test_geom_check_zones_file(tmp_path):
    """geom check --zones 吃 normalize 落盘文件路径（本次卡顿核心）。"""
    f = tmp_path / "normalized.json"
    f.write_text(json.dumps(_zones_doc()), encoding="utf-8")
    lot = '[[0,0],[60000,0],[60000,20000],[0,20000]]'
    sb = '{"front":5000,"rear":3000,"left":3000,"right":3000}'
    r = subprocess.run([AIPLAN, "geom", "check", "--zones", str(f),
                        "--lot", lot, "--setbacks", sb],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "全 zone 轮廓 + 对齐校验通过" in r.stdout


def test_geom_check_zones_inline_still_works():
    """geom check --zones 吃内联 JSON（旧用法兼容）。"""
    doc = json.dumps(_zones_doc())
    lot = '[[0,0],[60000,0],[60000,20000],[0,20000]]'
    sb = '{"front":5000,"rear":3000,"left":3000,"right":3000}'
    r = subprocess.run([AIPLAN, "geom", "check", "--zones", doc,
                        "--lot", lot, "--setbacks", sb],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ── derive --lot dict 容错（CLI 层）─────────────────────────────────────


def test_derive_cli_lot_dict_points():
    """derive --lot 传 dict（points 键）不再 KeyError: 0。"""
    lot = '{"points": [[0,0],[60000,0],[60000,20000],[0,20000]]}'
    r = subprocess.run([AIPLAN, "derive", "--lot", lot], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert '"aspect_ratio"' in r.stdout


def test_derive_cli_lot_file(tmp_path):
    """derive --lot 吃文件路径。"""
    f = tmp_path / "lot.json"
    f.write_text('[[0,0],[60000,0],[60000,20000],[0,20000]]', encoding="utf-8")
    r = subprocess.run([AIPLAN, "derive", "--lot", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert '"aspect_ratio"' in r.stdout

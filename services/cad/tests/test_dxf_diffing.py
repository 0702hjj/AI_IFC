# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Semantic DXF diff engine tests (XDATA key alignment + keyless fallback).

Fixtures build real DXF files via cad_script_lib factories (reset_state +
add_entity + write_and_validate) so the AIDXF XDATA keys are present exactly
as the script-as-source pipeline produces them.
"""

from __future__ import annotations

import json
from pathlib import Path

import ezdxf
import pytest

import cad_script_lib

from app.dxf_diffing import compute_diff


def _build(path: Path, *ops) -> Path:
    """Build a DXF at path: reset state, apply ops(msp), write+validate."""
    cad_script_lib.reset_state()
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    for op in ops:
        op(msp)
    assert cad_script_lib.write_and_validate(doc, str(path))
    return path


def _line(key, start=(0, 0), end=(10, 0), **attribs):
    def op(msp):
        cad_script_lib.add_entity(
            msp, "LINE", key=key, start=start, end=end, dxfattribs=attribs or None
        )
    return op


def _circle(key, center=(5, 5), radius=2.0):
    def op(msp):
        cad_script_lib.add_entity(msp, "CIRCLE", key=key, center=center, radius=radius)
    return op


def _insert(key, name="BLK", insert=(0, 0)):
    def op(msp):
        if name not in msp.doc.blocks:
            blk = msp.doc.blocks.new(name)
            blk.add_line((0, 0), (1, 1))
        cad_script_lib.add_entity(msp, "INSERT", key=key, name=name, insert=insert)
    return op


def _changed_fields(diff, key):
    entry = next(c for c in diff["changed"] if c["key"] == key)
    return {c["field"]: (c["old"], c["new"]) for c in entry["changes"]}


class TestAlignment:
    def test_added_removed_by_xdata_key(self, tmp_path):
        base = _build(tmp_path / "base.dxf", _line("0:line:1"), _circle("0:circle:1"))
        target = _build(tmp_path / "target.dxf", _circle("0:circle:1"),
                        _line("0:line:2", end=(3, 3)))
        diff = compute_diff(str(base), str(target))
        assert diff["added"] == ["0:line:2"]
        assert diff["removed"] == ["0:line:1"]
        assert diff["changed"] == []

    def test_handle_change_still_aligned(self, tmp_path):
        """Same keys, shifted handles (junk entity created+deleted first) → no diff."""
        def junk(msp):
            e = msp.add_line((0, 0), (1, 1))
            msp.delete_entity(e)
        base = _build(tmp_path / "base.dxf", junk, _line("0:line:1"),
                      _circle("0:circle:1"))
        target = _build(tmp_path / "target.dxf", _line("0:line:1"),
                        _circle("0:circle:1"))
        base_doc, target_doc = ezdxf.readfile(str(base)), ezdxf.readfile(str(target))
        base_handles = [e.dxf.handle for e in base_doc.modelspace()]
        target_handles = [e.dxf.handle for e in target_doc.modelspace()]
        assert base_handles != target_handles  # 前置条件：handle 确实漂移
        diff = compute_diff(str(base), str(target))
        assert diff == {"added": [], "removed": [], "changed": []}

    def test_keyless_entities_counted_only(self, tmp_path):
        """无 XDATA：两侧一致 → 不报；只一侧有 → added/removed 带 nokey: 前缀。"""
        def keyless(msp):
            msp.add_line((0, 0), (5, 5))
            msp.add_circle((1, 1), 3)

        same_a = _build(tmp_path / "a.dxf", keyless)
        same_b = _build(tmp_path / "b.dxf", keyless)
        diff = compute_diff(str(same_a), str(same_b))
        assert diff == {"added": [], "removed": [], "changed": []}

        with_keyed = _build(tmp_path / "c.dxf", keyless, _line("0:line:1"))
        diff = compute_diff(str(same_a), str(with_keyed))
        assert diff["added"] == ["0:line:1"]
        assert diff["removed"] == []
        assert diff["changed"] == []

        extra_keyless = _build(tmp_path / "d.dxf", keyless,
                               lambda msp: msp.add_circle((9, 9), 1))
        diff = compute_diff(str(same_a), str(extra_keyless))
        assert len(diff["added"]) == 1
        assert diff["added"][0].startswith("nokey:CIRCLE:")
        assert diff["removed"] == []
        assert diff["changed"] == []

        diff = compute_diff(str(extra_keyless), str(same_a))
        assert len(diff["removed"]) == 1
        assert diff["removed"][0].startswith("nokey:CIRCLE:")
        assert diff["added"] == []
        assert diff["changed"] == []


class TestFieldDiff:
    def test_line_endpoint_change(self, tmp_path):
        base = _build(tmp_path / "base.dxf", _line("0:line:1", end=(10, 0)))
        target = _build(tmp_path / "target.dxf", _line("0:line:1", end=(12, 3)))
        fields = _changed_fields(compute_diff(str(base), str(target)), "0:line:1")
        assert fields["end"] == ([10.0, 0.0, 0.0], [12.0, 3.0, 0.0])
        assert "start" not in fields

    def test_circle_radius_change(self, tmp_path):
        base = _build(tmp_path / "base.dxf", _circle("0:circle:1", radius=2.0))
        target = _build(tmp_path / "target.dxf", _circle("0:circle:1", radius=3.5))
        fields = _changed_fields(compute_diff(str(base), str(target)), "0:circle:1")
        assert fields == {"radius": (2.0, 3.5)}

    def test_arc_angles_change(self, tmp_path):
        def arc(key, start_angle, end_angle):
            def op(msp):
                cad_script_lib.add_entity(
                    msp, "ARC", key=key, center=(0, 0), radius=4,
                    start_angle=start_angle, end_angle=end_angle)
            return op
        base = _build(tmp_path / "base.dxf", arc("0:arc:1", 0, 90))
        target = _build(tmp_path / "target.dxf", arc("0:arc:1", 15, 120))
        fields = _changed_fields(compute_diff(str(base), str(target)), "0:arc:1")
        assert fields["start_angle"] == (0.0, 15.0)
        assert fields["end_angle"] == (90.0, 120.0)
        assert "center" not in fields and "radius" not in fields

    def test_lwpolyline_points_and_bulge_change(self, tmp_path):
        def poly(key, bulge):
            def op(msp):
                cad_script_lib.add_entity(
                    msp, "LWPOLYLINE", key=key, format="xyb",
                    points=[(0, 0, 0.0), (10, 0, bulge), (10, 10, 0.0)])
            return op
        base = _build(tmp_path / "base.dxf", poly("0:lwpolyline:1", 0.0))
        target = _build(tmp_path / "target.dxf", poly("0:lwpolyline:1", 0.5))
        fields = _changed_fields(
            compute_diff(str(base), str(target)), "0:lwpolyline:1")
        assert set(fields) == {"points"}
        old_pts, new_pts = fields["points"]
        assert old_pts[1][-1] == 0.0  # bulge 参与签名（mcp 版漏此项）
        assert new_pts[1][-1] == 0.5

    def test_text_and_mtext_content_change(self, tmp_path):
        def text(key, value):
            def op(msp):
                cad_script_lib.add_entity(msp, "TEXT", key=key, text=value,
                                          insert=(1, 1))
            return op

        def mtext(key, value):
            def op(msp):
                cad_script_lib.add_entity(msp, "MTEXT", key=key, text=value,
                                          insert=(2, 2))
            return op
        base = _build(tmp_path / "base.dxf", text("0:text:1", "旧标注"),
                      mtext("0:mtext:1", "旧多行"))
        target = _build(tmp_path / "target.dxf", text("0:text:1", "新标注"),
                        mtext("0:mtext:1", "新多行"))
        diff = compute_diff(str(base), str(target))
        assert _changed_fields(diff, "0:text:1") == {"text": ("旧标注", "新标注")}
        assert _changed_fields(diff, "0:mtext:1") == {"text": ("旧多行", "新多行")}

    def test_insert_block_transform_change(self, tmp_path):
        base = _build(tmp_path / "base.dxf", _insert("0:insert:1", insert=(0, 0)))
        target = _build(tmp_path / "target.dxf", _insert("0:insert:1", insert=(4, 2)))
        fields = _changed_fields(compute_diff(str(base), str(target)), "0:insert:1")
        assert fields == {"insert": ([0.0, 0.0, 0.0], [4.0, 2.0, 0.0])}

    def test_layer_color_linetype_change(self, tmp_path):
        base = _build(tmp_path / "base.dxf", _line("0:line:1"))
        target = _build(
            tmp_path / "target.dxf",
            _line("0:line:1", layer="WALL", color=1, linetype="DASHED"))
        fields = _changed_fields(compute_diff(str(base), str(target)), "0:line:1")
        assert fields["layer"] == ("0", "WALL")
        assert fields["color"] == (256, 1)
        assert fields["linetype"] == ("BYLAYER", "DASHED")

    def test_coordinate_change_is_a_diff(self, tmp_path):
        """CAD 本质差异（相对 IFC v1）：几何坐标移动必须产生 diff。"""
        base = _build(tmp_path / "base.dxf", _line("0:line:1", start=(0, 0)))
        target = _build(tmp_path / "target.dxf", _line("0:line:1", start=(1, 0)))
        diff = compute_diff(str(base), str(target))
        fields = _changed_fields(diff, "0:line:1")
        assert fields["start"] == ([0.0, 0.0, 0.0], [1.0, 0.0, 0.0])

    def test_same_key_different_type_reports_type_change(self, tmp_path):
        base = _build(tmp_path / "base.dxf", _line("0:x:1"))
        target = _build(tmp_path / "target.dxf", _circle("0:x:1"))
        fields = _changed_fields(compute_diff(str(base), str(target)), "0:x:1")
        assert fields == {"type": ("LINE", "CIRCLE")}


class TestShape:
    def test_output_schema_sorted_deterministic(self, tmp_path):
        base = _build(
            tmp_path / "base.dxf",
            _line("0:line:9"), _line("0:line:1"), _circle("0:circle:1"),
        )
        target = _build(
            tmp_path / "target.dxf",
            _line("0:line:2"), _circle("0:circle:1", radius=9),
            _line("0:line:10"), _circle("0:circle:2"),
        )
        diff1 = compute_diff(str(base), str(target))
        diff2 = compute_diff(str(base), str(target))
        assert diff1 == diff2
        assert diff1["added"] == sorted(diff1["added"])
        assert diff1["removed"] == sorted(diff1["removed"])
        assert diff1["added"] == ["0:circle:2", "0:line:10", "0:line:2"]
        assert diff1["removed"] == ["0:line:1", "0:line:9"]
        assert [c["key"] for c in diff1["changed"]] == ["0:circle:1"]

    def test_jsonable_values(self, tmp_path):
        base = _build(tmp_path / "base.dxf", _line("0:line:1", end=(10, 0)))
        target = _build(
            tmp_path / "target.dxf",
            _line("0:line:1", end=(0.1234567891, 0)))
        diff = compute_diff(str(base), str(target))
        json.dumps(diff)  # 必须整体可序列化
        fields = _changed_fields(diff, "0:line:1")
        new_end = fields["end"][1]
        assert isinstance(new_end, list)
        assert all(isinstance(v, float) for v in new_end)
        assert new_end[0] == round(0.1234567891, 6)

    def test_empty_diff(self, tmp_path):
        path = _build(tmp_path / "same.dxf", _line("0:line:1"),
                      _circle("0:circle:1"))
        assert compute_diff(str(path), str(path)) == {
            "added": [], "removed": [], "changed": []}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

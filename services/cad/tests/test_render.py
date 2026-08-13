# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""render.json payload v2 tests: entity-keyed geometry + unsupported surfacing.

Covers build_render_payload (pure function) and the GET /models/{id}/render.json
endpoint + the run/save publish hook. Key contract: render 实体的 key 集合
（滤掉块展开产生的 key=None 子实体）必须等于 current.map.json 的 key 集合。
"""

from __future__ import annotations

import json
from pathlib import Path

import ezdxf
import pytest

import cad_script_lib

from app.render import build_render_payload

from tests.conftest import MODEL_ID

GOOD_SCRIPT = '''\
import sys

import ezdxf

from cad_script_lib import add_entity, write_and_validate

PARAMS = {"length": 10}

def build(params, out_path):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    add_entity(msp, "LINE", start=(0, 0), end=(params["length"], 0))
    write_and_validate(doc, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''

BASE = f"/models/{MODEL_ID}"


def _build(path: Path, *ops) -> Path:
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


def _entity(payload, predicate):
    return next(e for e in payload["entities"] if predicate(e))


def _render_path(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "render.json"


class TestEntityGeometry:
    def test_line_fields(self, tmp_path):
        path = _build(
            tmp_path / "m.dxf",
            _line("0:line:1", layer="WALL", color=1, linetype="DASHED"))
        payload = build_render_payload(str(path))
        assert payload["schemaVersion"] == 2
        entry = _entity(payload, lambda e: e["type"] == "LINE")
        assert entry["key"] == "0:line:1"
        assert entry["layer"] == "WALL"
        assert entry["color"] == 1
        assert entry["linetype"] == "DASHED"
        assert entry["start"] == [0.0, 0.0]
        assert entry["end"] == [10.0, 0.0]

    def test_circle_fields(self, tmp_path):
        def op(msp):
            cad_script_lib.add_entity(
                msp, "CIRCLE", key="0:circle:1", center=(5, 5), radius=2)
        payload = build_render_payload(str(_build(tmp_path / "m.dxf", op)))
        entry = _entity(payload, lambda e: e["type"] == "CIRCLE")
        assert entry["key"] == "0:circle:1"
        assert entry["center"] == [5.0, 5.0]
        assert entry["radius"] == 2.0

    def test_arc_fields(self, tmp_path):
        def op(msp):
            cad_script_lib.add_entity(
                msp, "ARC", key="0:arc:1", center=(0, 0), radius=4,
                start_angle=15, end_angle=120)
        payload = build_render_payload(str(_build(tmp_path / "m.dxf", op)))
        entry = _entity(payload, lambda e: e["type"] == "ARC")
        assert entry["key"] == "0:arc:1"
        assert entry["center"] == [0.0, 0.0]
        assert entry["radius"] == 4.0
        assert entry["start_angle"] == 15.0
        assert entry["end_angle"] == 120.0

    def test_text_fields(self, tmp_path):
        def op(msp):
            cad_script_lib.add_entity(
                msp, "TEXT", key="0:text:1", text="标注", insert=(1, 2), height=3.5)
        payload = build_render_payload(str(_build(tmp_path / "m.dxf", op)))
        entry = _entity(payload, lambda e: e["type"] == "TEXT")
        assert entry["key"] == "0:text:1"
        assert entry["text"] == "标注"
        assert entry["insert"] == [1.0, 2.0]
        assert entry["height"] == 3.5

    def test_mtext_fields(self, tmp_path):
        def op(msp):
            cad_script_lib.add_entity(
                msp, "MTEXT", key="0:mtext:1", text="多行", insert=(2, 3))
        payload = build_render_payload(str(_build(tmp_path / "m.dxf", op)))
        entry = _entity(payload, lambda e: e["type"] == "MTEXT")
        assert entry["key"] == "0:mtext:1"
        assert entry["text"] == "多行"
        assert entry["insert"] == [2.0, 3.0]

    def test_lwpolyline_explodes_to_line_and_arc_segments(self, tmp_path):
        """LWPOLYLINE 炸开：直线段 → LINE 条目；bulge 段 → ARC 条目（同 key）。"""
        def op(msp):
            cad_script_lib.add_entity(
                msp, "LWPOLYLINE", key="0:lwpolyline:1", format="xyb",
                points=[(0, 0, 0.0), (10, 0, 0.5), (10, 10, 0.0)])
        payload = build_render_payload(str(_build(tmp_path / "m.dxf", op)))
        segments = [
            e for e in payload["entities"] if e["key"] == "0:lwpolyline:1"]
        assert [s["type"] for s in segments] == ["LINE", "ARC"]
        line, arc = segments
        assert line["start"] == [0.0, 0.0]
        assert line["end"] == [10.0, 0.0]
        # bulge=0.5，弦 (10,0)→(10,10)：r=6.25，center=(6.25,5)
        assert arc["center"] == [6.25, 5.0]
        assert arc["radius"] == 6.25
        assert arc["start_angle"] == pytest.approx(306.869898, abs=1e-6)
        assert arc["end_angle"] == pytest.approx(413.130103, abs=1e-6)

    def test_closed_lwpolyline_adds_closing_segment(self, tmp_path):
        def op(msp):
            cad_script_lib.add_entity(
                msp, "LWPOLYLINE", key="0:lwpolyline:1", format="xyb",
                points=[(0, 0, 0.0), (10, 0, 0.0), (10, 10, 0.0)], closed=True)
        payload = build_render_payload(str(_build(tmp_path / "m.dxf", op)))
        segments = [
            e for e in payload["entities"] if e["key"] == "0:lwpolyline:1"]
        assert [s["type"] for s in segments] == ["LINE", "LINE", "LINE"]
        closing = segments[-1]
        assert closing["start"] == [10.0, 10.0]
        assert closing["end"] == [0.0, 0.0]

    def test_coordinates_keep_original_dxf_frame(self, tmp_path):
        """v2 不做 screen 归一化：原始 DXF 坐标保留，数字 round 6。"""
        path = _build(
            tmp_path / "m.dxf",
            _line("0:line:1", start=(1000.1234567891, -2000), end=(1001, 2001)))
        payload = build_render_payload(str(path))
        entry = _entity(payload, lambda e: e["type"] == "LINE")
        assert entry["start"] == [1000.123457, -2000.0]
        assert entry["end"] == [1001.0, 2001.0]


class TestInsertExpansion:
    def test_insert_entry_and_block_expansion(self, tmp_path):
        """INSERT 本体入 entities（name/insert/rotation/scale）；块内实体展开一层，
        应用 translate+rotate+uniform scale，子实体 key=None 且标 block 来源。"""
        def op(msp):
            blk = msp.doc.blocks.new("BLK")
            blk.add_line((0, 0), (1, 1))
            blk.add_circle((0, 0), 1)
            cad_script_lib.add_entity(
                msp, "INSERT", key="0:insert:1", name="BLK", insert=(10, 5),
                dxfattribs={"rotation": 90, "xscale": 2, "yscale": 2})
        payload = build_render_payload(str(_build(tmp_path / "m.dxf", op)))
        insert = _entity(payload, lambda e: e["type"] == "INSERT")
        assert insert["key"] == "0:insert:1"
        assert insert["name"] == "BLK"
        assert insert["insert"] == [10.0, 5.0]
        assert insert["rotation"] == 90.0
        assert insert["scale"] == 2.0
        children = [e for e in payload["entities"] if e.get("block") == "BLK"]
        assert {c["type"] for c in children} == {"LINE", "CIRCLE"}
        assert all(c["key"] is None for c in children)
        line = next(c for c in children if c["type"] == "LINE")
        # scale 2 + rotate 90°: (1,1) -> (-2,2); + insert (10,5)
        assert line["start"] == [10.0, 5.0]
        assert line["end"] == [8.0, 7.0]
        circle = next(c for c in children if c["type"] == "CIRCLE")
        assert circle["center"] == [10.0, 5.0]
        assert circle["radius"] == 2.0

    def test_insert_nonuniform_scale_goes_unsupported(self, tmp_path):
        """非等比 scale 不展开：INSERT 本体仍在 entities，unsupported 记一条。"""
        def op(msp):
            blk = msp.doc.blocks.new("BLK")
            blk.add_line((0, 0), (1, 1))
            cad_script_lib.add_entity(
                msp, "INSERT", key="0:insert:1", name="BLK", insert=(1, 1),
                dxfattribs={"xscale": 2, "yscale": 1})
        payload = build_render_payload(str(_build(tmp_path / "m.dxf", op)))
        insert = _entity(payload, lambda e: e["type"] == "INSERT")
        assert insert["key"] == "0:insert:1"
        assert not [e for e in payload["entities"] if e.get("block") == "BLK"]
        entry = _entity(
            {"entities": payload["unsupported"]},
            lambda e: e["type"] == "INSERT")
        assert entry["handle"]
        assert entry["coords"] == [1.0, 1.0]

    def test_nested_insert_goes_unsupported(self, tmp_path):
        """块内 INSERT（嵌套第二层）不展开，进 unsupported。"""
        def op(msp):
            inner = msp.doc.blocks.new("INNER")
            inner.add_line((0, 0), (1, 0))
            outer = msp.doc.blocks.new("OUTER")
            outer.add_blockref("INNER", (0, 0))
            cad_script_lib.add_entity(
                msp, "INSERT", key="0:insert:1", name="OUTER", insert=(0, 0))
        payload = build_render_payload(str(_build(tmp_path / "m.dxf", op)))
        nested = [u for u in payload["unsupported"] if u["type"] == "INSERT"]
        assert len(nested) == 1
        assert nested[0]["handle"]


class TestUnsupported:
    def test_unknown_entity_surfaced_not_dropped(self, tmp_path):
        def op(msp):
            msp.add_point((1, 2))
        payload = build_render_payload(str(_build(tmp_path / "m.dxf", op)))
        assert payload["entities"] == []
        assert len(payload["unsupported"]) == 1
        entry = payload["unsupported"][0]
        assert entry["type"] == "POINT"
        assert entry["handle"]
        assert entry["coords"] == [1.0, 2.0]


class TestPayloadShape:
    def test_bounds_cover_geometry(self, tmp_path):
        def op(msp):
            cad_script_lib.add_entity(
                msp, "LINE", key="0:line:1", start=(0, 0), end=(10, 0))
            cad_script_lib.add_entity(
                msp, "CIRCLE", key="0:circle:1", center=(5, 5), radius=2)
        payload = build_render_payload(str(_build(tmp_path / "m.dxf", op)))
        assert payload["bounds"] == {"min": [0.0, 0.0], "max": [10.0, 7.0]}

    def test_layers_listing(self, tmp_path):
        path = _build(tmp_path / "m.dxf", _line("0:line:1", layer="WALL"))
        payload = build_render_payload(str(path))
        names = {layer["name"] for layer in payload["layers"]}
        assert "WALL" in names
        wall = next(l for l in payload["layers"] if l["name"] == "WALL")
        assert isinstance(wall["color"], int)
        assert isinstance(wall["linetype"], str)

    def test_payload_json_serializable(self, tmp_path):
        path = _build(tmp_path / "m.dxf", _line("0:line:1"))
        json.dumps(build_render_payload(str(path)), ensure_ascii=False)


class TestKeyContract:
    def test_render_keys_match_current_map_keys(self, client, data_dir):
        """契约：render 实体 key 集合（滤 None）== current.map.json key 集合。"""
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        resp = client.post(f"{BASE}/script/run")
        assert resp.status_code == 200
        payload = client.get(f"{BASE}/render.json").json()
        with open(data_dir / "models" / MODEL_ID / "current.map.json",
                  encoding="utf-8") as fh:
            map_keys = set(json.load(fh)["map"])
        render_keys = {e["key"] for e in payload["entities"] if e["key"]}
        assert render_keys == map_keys == {"0:line:1"}


class TestEndpoint:
    def test_get_render_on_demand_for_upload_only_model(self, client):
        """无 render.json 时按 uploads dxf 即时生成（fixture 含 LINE+CIRCLE）。"""
        resp = client.get(f"{BASE}/render.json")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["schemaVersion"] == 2
        keys = {e["key"] for e in payload["entities"] if e["key"]}
        assert keys == {"0:line:1", "0:circle:1"}

    def test_get_render_404_unknown_model(self, client):
        resp = client.get("/models/m_ffffffffffffffff/render.json")
        assert resp.status_code == 404


class TestRunSaveHook:
    def test_run_publishes_render_json(self, client, data_dir):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        resp = client.post(f"{BASE}/script/run")
        assert resp.status_code == 200
        path = _render_path(data_dir)
        assert path.is_file()
        payload = json.loads(path.read_text(encoding="utf-8"))
        line = _entity(payload, lambda e: e["type"] == "LINE")
        assert line["end"] == [10.0, 0.0]
        # GET 走已发布文件
        assert client.get(f"{BASE}/render.json").json() == payload

    def test_save_updates_render_json(self, client, data_dir):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        assert client.post(f"{BASE}/script/save").status_code == 200
        client.put(f"{BASE}/script", json={"params": {"length": 42}})
        resp = client.post(f"{BASE}/script/save")
        assert resp.status_code == 200
        payload = json.loads(_render_path(data_dir).read_text(encoding="utf-8"))
        line = _entity(payload, lambda e: e["type"] == "LINE")
        assert line["end"] == [42.0, 0.0]

    def test_generation_failure_keeps_run_ok_and_deletes_stale(
            self, client, data_dir, monkeypatch):
        """render 生成失败不阻断 run 主流程，且删除旧 render.json 防错位。"""
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        assert client.post(f"{BASE}/script/run").status_code == 200
        assert _render_path(data_dir).is_file()

        import app.render as render_module

        def boom(_path):
            raise RuntimeError("render-boom")

        monkeypatch.setattr(render_module, "build_render_payload", boom)
        client.put(f"{BASE}/script", json={"params": {"length": 20}})
        resp = client.post(f"{BASE}/script/run")
        assert resp.status_code == 200
        assert not _render_path(data_dir).exists()

    def test_write_failure_keeps_run_ok_and_removes_stale(
            self, client, data_dir, monkeypatch):
        """render.json 写盘失败（os.replace OSError）不阻断 run，且删旧文件防错位。"""
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        assert client.post(f"{BASE}/script/run").status_code == 200
        assert _render_path(data_dir).is_file()

        import os as os_module

        import app.routes_scripts as routes_module

        real_replace = os_module.replace

        def boom(src, dst, *args, **kwargs):
            if str(dst).endswith("render.json"):
                raise OSError("disk-full")
            return real_replace(src, dst, *args, **kwargs)

        monkeypatch.setattr(routes_module.os, "replace", boom)
        client.put(f"{BASE}/script", json={"params": {"length": 20}})
        resp = client.post(f"{BASE}/script/run")
        assert resp.status_code == 200
        assert not _render_path(data_dir).exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

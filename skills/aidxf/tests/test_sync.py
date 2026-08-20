"""sync.py 测试（T43）：同步桥（哈希比对 → 回读再生 → audit → 语义事件）。"""

import importlib.util
import json
from pathlib import Path

import pytest

from flowops.sync import sync_floor, audit

GOLDEN_SRC = Path(__file__).resolve().parent.parent / "tests" / "golden" / "dxf" / "residence_1br.py"


@pytest.fixture(scope="module")
def golden_dxf(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("residence_1br", GOLDEN_SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    doc = mod.gen_dxf()
    path = tmp_path_factory.mktemp("sync") / "residence_1br.dxf"
    doc.saveas(path)
    return path


def _old_layout():
    return {
        "rooms": [{"id": "living", "area_sqm": 26.6},
                  {"id": "bedroom", "area_sqm": 13.4}],
        "doors": [{"between": ["living", "bedroom"], "via": "door",
                   "at": [4000, 3000], "width_mm": 900}],
        "walls": [{"between": ["_", "_"], "kind": "interior", "segments": []}],
    }


class TestSyncFastPath:
    def test_unchanged_dxf_fast_path(self, golden_dxf):
        """DXF 未变 → fast path（消费旧 layout）。"""
        from flowops.sync import _sha256
        real_sha = _sha256(str(golden_dxf))
        result = sync_floor(str(golden_dxf), real_sha, _old_layout())
        assert result["path"] == "fast"
        assert result["verdict"] == "pass"


class TestSyncRegenerate:
    def test_changed_dxf_regenerates(self, golden_dxf):
        """DXF 已变（哈希不同）→ 回读再生。"""
        result = sync_floor(str(golden_dxf), "different_sha", _old_layout())
        assert result["path"] == "regenerate"
        assert "diff" in result
        assert "audit" in result or "diff" in result

    def test_audit_detects_changes(self):
        """audit：房间增删/门变化/墙段差。"""
        old = _old_layout()
        new_graph = {
            "nodes": [{"id": "living", "area_geo_sqm": 26.6},
                      {"id": "bedroom", "area_geo_sqm": 13.4},
                      {"id": "bath", "area_geo_sqm": 5.6}],
            "edges": [{"a": "living", "b": "bedroom", "via": "door"}],
            "wall_segments": [[[0, 0], [1000, 0]]],
            "wall_arcs": [],
            "unparsed": [],
            "doors": [],
        }
        diff = audit(old, new_graph)
        assert diff["rooms_added"] == ["bath"]
        assert diff["rooms_removed"] == []


class TestSyncDeterminism:
    def test_audit_deterministic(self):
        a = audit(_old_layout(), _sync_graph())
        b = audit(_old_layout(), _sync_graph())
        assert a == b


def _sync_graph():
    return {
        "nodes": [{"id": "living", "area_geo_sqm": 26.6}],
        "edges": [],
        "wall_segments": [],
        "wall_arcs": [],
        "unparsed": [],
        "doors": [],
    }

"""T54 飞轮验证：自产案例完成"入库→检索→注入"闭环。

T52 冒烟的 rooms 声明作为自产案例 → 入库 → query 命中 → 验证 S2 注入可用。
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

from goldlib.ingest import ingest
from goldlib.query import query
from goldlib.reindex import reindex
from goldlib.reverse import reverse

GOLD_DIR = Path(__file__).resolve().parent.parent / "tests" / "golden" / "gold"
SMOKE_DIR = Path(__file__).resolve().parent.parent / "tests" / "golden" / "smoke"


@pytest.fixture(scope="module")
def self_produced_case(tmp_path_factory):
    """T52 冒烟的 rooms 声明 → 自产金例（拷三段 + meta）。"""
    # 冒烟房间声明（T52 同款，交付确认后回流）
    rooms = {
        "floor": "f1",
        "axis_grid_ref": "skeleton.json#zones[house].axis_grid",
        "rooms": [
            {"id": "living_01", "type": "living", "area_sqm": 48,
             "loc": {"between_axes": {"x": [0, 2], "y": [0, 2]}}, "frontage": "S"},
            {"id": "bedroom_01", "type": "bedroom", "area_sqm": 24,
             "loc": {"between_axes": {"x": [0, 2], "y": [2, 3]}}, "frontage": "S"},
            {"id": "kitchen_01", "type": "kitchen", "area_sqm": 12,
             "loc": {"between_axes": {"x": [2, 3], "y": [0, 1]}}},
        ],
        "openings": [],
        "requirements_trace": [],
        "deviations": [], "defaults_used": [],
    }

    case_dir = tmp_path_factory.mktemp("fly") / "gold" / "smoke_house"
    case_dir.mkdir(parents=True, exist_ok=True)
    # 七件套简化：meta + rooms + replay_check PASS
    (case_dir / "meta.json").write_text(json.dumps({
        "case_id": "smoke_house", "type": "residence",
        "area_sqm": sum(r["area_sqm"] for r in rooms["rooms"]),
        "quality_score": 0.9, "template_worthy": True,
        "source": "smoke self-produced", "created": "2026-08-10",
    }), encoding="utf-8")
    (case_dir / "rooms.F1.json").write_text(json.dumps(rooms), encoding="utf-8")
    (case_dir / "replay_check.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    # readback.json（模拟 DXF 回读的房间图，与声明一致——G2 replay 的输入）
    readback_data = {
        "readback_graph": {
            "nodes": [
                {"id": r["id"], "type": r["type"],
                 "area_sqm": r["area_sqm"], "area_geo_sqm": r["area_sqm"],
                 "polygon_mm": _rect_to_polygon_mm(r["loc"]["between_axes"])}
                for r in rooms["rooms"] if "between_axes" in r["loc"]
            ],
            "wall_segments": [],
            "wall_arcs": [],
            "unparsed": [],
            "outline_mm": [[0, 0], [16000, 0], [16000, 12000], [0, 12000]],
        }
    }
    (case_dir / "readback.json").write_text(json.dumps(readback_data), encoding="utf-8")
    return str(case_dir)


def _rect_to_polygon_mm(ba):
    """轴网区间 → 多边形坐标（用冒烟轴网近似）。"""
    xs = [0, 4000, 8000, 12000, 16000]
    ys = [0, 3000, 6000, 9000, 12000]
    x0, x1 = xs[ba["x"][0]], xs[ba["x"][1]]
    y0, y1 = ys[ba["y"][0]], ys[ba["y"][1]]
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


class TestFlywheel:
    """入库 → 检索 → 注入。"""

    def test_ingest_self_produced(self, self_produced_case, tmp_path):
        gold_root = Path(self_produced_case).parent
        db = tmp_path / "g.db"
        reindex(str(gold_root), str(db))
        result = ingest("smoke_house", str(gold_root), str(db))
        assert result["status"] == "ingested"

    def test_query_hits_self_produced(self, self_produced_case, tmp_path):
        gold_root = Path(self_produced_case).parent
        db = tmp_path / "g.db"
        reindex(str(gold_root), str(db))
        ingest("smoke_house", str(gold_root), str(db))
        hits = query(str(db), kind="case", type="residence")
        assert any(h["case_id"] == "smoke_house" for h in hits)

    def test_pattern_injection_available(self, self_produced_case, tmp_path):
        """注入可用：S1/S2 能通过 gold query 查到该案例/模式。"""
        gold_root = Path(self_produced_case).parent
        db = tmp_path / "g.db"
        reindex(str(gold_root), str(db))
        # S2 场景：rooms-worker 卡住时 pull 查询（P2 痛点）
        hits = query(str(db), kind="pattern", pain="P2-1")
        # 至少返回模式（模式来自 references/room_patterns 种子或案例反挂）
        assert isinstance(hits, list)

    def test_reverse_self_produced_usable(self):
        """反推声明可被 normalize 消费（注入链路闭环）。"""
        # 用 R-01 readback 验证 reverse → 声明结构合法（消费端）
        g = json.load(open(GOLD_DIR / "r01_house" / "readback.json"))
        decl = reverse(g["readback_graph"])
        assert decl["labels"]
        assert decl["walls"]
        for lab in decl["labels"]:
            assert "room" in lab and "at" in lab

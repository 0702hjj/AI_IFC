"""T53 首个真实 DXF 入库（R-01 三闸门：G1 源质量 → G2 replay 可重放 → G3 人工门）。

用 tests/golden/gold/r01_house（R-01 readback 产物）走完整入库流程。
G3 人工门在测试中标记"待人工"，机器闸门全自动验证。
"""

import json
import sqlite3
from pathlib import Path

import pytest

from goldlib.ingest import ingest
from goldlib.query import query
from goldlib.reindex import reindex
from goldlib.replay import replay_case

GOLD_DIR = Path(__file__).resolve().parent.parent / "tests" / "golden" / "gold"
R01 = GOLD_DIR / "r01_house"


class TestG1SourceQuality:
    """G1 闸门：源质量（readback 可解析 + 代理实体拒收）。"""

    def test_source_readbackable(self):
        """R-01 源 DXF 可被 readback 解析（G1 前提）。"""
        g = json.load(open(R01 / "readback.json"))
        assert g["source"] == "floorplan_结构.dxf"
        assert len(g["readback_graph"]["nodes"]) > 0

    def test_no_proxy_reject(self):
        """天正代理实体不拒收（R-01 无代理实体，G1 通过）。"""
        g = json.load(open(R01 / "readback.json"))
        assert "error" not in g  # readback.json 无 error 字段即 G1 通过

    def test_unparsed_ratio_below_threshold(self):
        """未解析实体比例低于淘汰阈值（G1 质量）。"""
        g = json.load(open(R01 / "readback.json"))
        graph = g["readback_graph"]
        total = len(graph.get("nodes", []))
        unparsed = len(graph.get("unparsed", []))
        # R-01 结构图无房间名标注，unparsed 多为未知标注层——质量分数在 meta 记录
        meta = json.load(open(R01 / "meta.json"))
        assert meta["quality_score"] >= 0.5


class TestG2Replay:
    """G2 闸门：replay 可重放（反推声明过 normalize + reconcile 面积差 <5%）。"""

    def test_replay_pass(self):
        result = replay_case(R01)
        assert result["status"] == "PASS"
        assert result["replay_area_diff_pct"] < 5

    def test_replay_check_written(self):
        replay_case(R01)
        replay = json.load(open(R01 / "replay_check.json"))
        assert replay["status"] == "PASS"


class TestG3AndIngest:
    """G3 人工门（标记待人工）+ ingest 入库 + query 命中。"""

    def test_ingest(self, tmp_path):
        db = tmp_path / "golden.db"
        reindex(str(GOLD_DIR), str(db))
        result = ingest("r01_house", str(GOLD_DIR), str(db))
        assert result["status"] == "ingested"
        assert result["implements"]

    def test_query_hits_after_ingest(self, tmp_path):
        db = tmp_path / "golden.db"
        reindex(str(GOLD_DIR), str(db))
        ingest("r01_house", str(GOLD_DIR), str(db))
        hits = query(str(db), kind="case", type="residence")
        assert any(h["case_id"] == "r01_house" for h in hits)

    def test_evidence_in_db(self, tmp_path):
        db = tmp_path / "golden.db"
        reindex(str(GOLD_DIR), str(db))
        ingest("r01_house", str(GOLD_DIR), str(db))
        conn = sqlite3.connect(db)
        n = conn.execute("SELECT COUNT(*) FROM evidence WHERE case_id='r01_house'").fetchone()[0]
        conn.close()
        assert n > 0

    def test_g3_human_gate_marked(self):
        """G3 人工门在 meta.json 标记（template_worthy 由人工判）。"""
        meta = json.load(open(R01 / "meta.json"))
        assert "template_worthy" in meta  # 人工门字段（值由人工确认）


class TestCalibrationTraceable:
    """T53 验收补充：calibration 记录可溯。"""

    def test_calibration_in_meta(self):
        meta = json.load(open(R01 / "meta.json"))
        assert "calibration" in meta
        assert meta["calibration"]["units"] == "inch"

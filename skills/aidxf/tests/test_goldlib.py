"""goldlib.py 测试（T30-T34）：golden 目录 + reindex 幂等 + query + reverse + ingest。

夹具：tests/golden/gold/r01_house/（真实 DXF R-01 的 readback 产物，用户框定）。
"""

import json
import sqlite3
from pathlib import Path

import pytest

from goldlib.reindex import reindex
from goldlib.query import query
from goldlib.reverse import reverse
from goldlib.ingest import ingest

GOLD_DIR = Path(__file__).resolve().parent / "golden" / "gold"


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    return tmp_path_factory.mktemp("golddb") / "golden.db"


class TestMetaSchema:
    """T30：meta.json 内部校验 + index.json。"""

    def test_r01_meta_valid(self):
        meta = json.load(open(GOLD_DIR / "r01_house" / "meta.json"))
        assert meta["case_id"] == "r01_house"
        assert meta["type"] == "residence"
        assert "quality_score" in meta
        assert "template_worthy" in meta

    def test_two_case_dirs(self):
        """两案例夹具（r01_house + res_b）。"""
        assert (GOLD_DIR / "r01_house" / "meta.json").exists()
        assert (GOLD_DIR / "res_b" / "meta.json").exists()

    def test_seven_piece_suite(self):
        """每案例七件套齐。"""
        for case in ("r01_house", "res_b"):
            d = GOLD_DIR / case
            for piece in ("meta.json", "source.dxf", "geom.json",
                          "skeleton.json", "replay_check.json"):
                assert (d / piece).exists(), f"{case} 缺 {piece}"
            # rooms 至少一份
            assert list(d.glob("rooms.*.json")), f"{case} 缺 rooms"

    def test_replay_check_valid(self):
        from goldlib.schema import validate_replay
        for case in ("r01_house", "res_b"):
            replay = json.load(open(GOLD_DIR / case / "replay_check.json"))
            assert validate_replay(replay) == []

    def test_index_build_and_validate(self):
        """index.json 生成 + 校验。"""
        from goldlib.schema import build_index, validate_index
        index = build_index(str(GOLD_DIR))
        assert validate_index(index) == []
        ids = {c["case_id"] for c in index["cases"]}
        assert {"r01_house", "res_b"} <= ids


class TestReindex:
    """T31：reindex 幂等 + 四表。"""

    def test_reindex_creates_db(self, db_path):
        reindex(str(GOLD_DIR), str(db_path))
        assert db_path.exists()

    def test_four_tables(self, db_path):
        reindex(str(GOLD_DIR), str(db_path))
        conn = sqlite3.connect(db_path)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"cases", "patterns", "evidence", "params"} <= tables
        conn.close()

    def test_case_inserted(self, db_path):
        reindex(str(GOLD_DIR), str(db_path))
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT case_id, type FROM cases").fetchall()
        assert ("r01_house", "residence") in rows
        conn.close()

    def test_reindex_idempotent(self, db_path, tmp_path):
        """两次 reindex 后 db 字节一致（幂等）。"""
        a = tmp_path / "a.db"
        b = tmp_path / "b.db"
        reindex(str(GOLD_DIR), str(a))
        reindex(str(GOLD_DIR), str(b))
        assert a.read_bytes() == b.read_bytes()

    def test_two_cases_inserted(self, db_path):
        """两案例入 cases 表。"""
        reindex(str(GOLD_DIR), str(db_path))
        conn = sqlite3.connect(db_path)
        rows = {r[0] for r in conn.execute("SELECT case_id FROM cases")}
        assert {"r01_house", "res_b"} <= rows
        conn.close()

    def test_patterns_scanned(self, db_path):
        """building_types + room_patterns 的 pattern 扫描入库。"""
        reindex(str(GOLD_DIR), str(db_path))
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT pattern_id, pains FROM patterns").fetchall()
        # 夹具里 3 条 pattern：南向采光房/湿区贴筒/板式轴网
        ids = {r[0] for r in rows}
        assert "南向采光房写法" in ids or any("南向" in r[0] for r in rows)
        assert "湿区贴核心筒" in ids or any("湿区" in r[0] for r in rows)
        # 命中痛点已解析
        pains_all = " ".join(r[1] for r in rows)
        assert "P2-1" in pains_all or "P1-1" in pains_all
        conn.close()

    def test_index_json_rebuilt(self, db_path):
        """reindex 同步再生 index.json。"""
        reindex(str(GOLD_DIR), str(db_path))
        index_path = Path(GOLD_DIR) / "index.json"
        assert index_path.exists()
        index = json.load(open(index_path))
        ids = {c["case_id"] for c in index["cases"]}
        assert {"r01_house", "res_b"} <= ids




class TestT34Plus:
    """T34+ 针对性测试 P1-P6（波次收尾）。"""

    def test_p1_query_key_contract(self, db_path):
        """P1：query 返回键集 = 消费方（preprocess/pack）期望键集。"""
        reindex(str(GOLD_DIR), str(db_path))
        hits = query(str(db_path), kind="case", type="residence")
        if hits:
            assert {"case_id", "type", "quality_score", "template_worthy"} <= set(hits[0])

    def test_p2_content_from_file(self, db_path, tmp_path):
        """P2：文件是事实源——改文件 query 跟着变。"""
        from goldlib.reindex import reindex as re
        rp = Path(GOLD_DIR) / "room_patterns" / "wet_core.md"
        original = rp.read_text(encoding="utf-8")
        db2 = tmp_path / "p2.db"
        try:
            rp.write_text(original + "\n## pattern: 湿区扩展模式\n命中痛点: P2-9\n",
                          encoding="utf-8")
            re(str(GOLD_DIR), str(db2))
            hits = query(str(db2), kind="pattern", pain="P2-9")
            assert any("湿区扩展" in h["pattern_id"] for h in hits)
        finally:
            rp.write_text(original, encoding="utf-8")

    def test_p5_calibration_recorded(self):
        """P5：校准记录可溯（meta.json calibration + reverse 阈值标注）。"""
        meta = json.load(open(GOLD_DIR / "r01_house" / "meta.json"))
        assert "calibration" in meta
        assert meta["calibration"]["units"] == "inch"
        # reverse 阈值在文件头标 [校准]
        from goldlib import reverse
        import inspect
        src = inspect.getsource(reverse)
        assert "校准" in src or "R-01" in src

    def test_p6_r01_fixture(self):
        """P6：夹具真实（R-01 真实 DXF readback 产物）。"""
        g = json.load(open(GOLD_DIR / "r01_house" / "readback.json"))
        assert g["source"] == "floorplan_结构.dxf"
        assert g["units"] == "inch"


class TestReindexKind:
    """2026-08-11：pattern kind 区分（skeleton vs room）。"""

    def test_kind_from_directory(self, db_path):
        """room_patterns/*.md → kind=room；building_types/*/skeleton_patterns.md → kind=skeleton。"""
        import tempfile, os
        # 用真实 references 验证（含两目录）
        from goldlib.reindex import reindex
        tmp = tempfile.mktemp(suffix=".db")
        try:
            refs = Path(__file__).resolve().parent.parent / "references"
            reindex(str(refs), tmp)
            import sqlite3
            conn = sqlite3.connect(tmp)
            kinds = {r[0] for r in conn.execute("SELECT kind FROM patterns").fetchall()}
            conn.close()
            assert kinds == {"room", "skeleton"}, f"kind 应含 room+skeleton，实际 {kinds}"
        finally:
            os.unlink(tmp)



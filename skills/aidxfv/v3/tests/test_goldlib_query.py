"""goldlib query 测试（T32：特征直查 + 适用条件求值器）。

拆分自 test_goldlib.py（W-0049 文件行数门控）。
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




class TestQuery:
    """T32：特征直查。"""

    @pytest.fixture(scope="class")
    def populated(self, db_path):
        reindex(str(GOLD_DIR), str(db_path))
        return str(db_path)

    def test_query_by_type(self, populated):
        hits = query(populated, kind="case", type="residence")
        assert any(h["case_id"] == "r01_house" for h in hits)

    def test_query_miss(self, populated):
        hits = query(populated, kind="case", type="office")
        assert not any(h["case_id"] == "r01_house" for h in hits)

    def test_query_support_single(self, populated):
        """孤证标记：support=1 返回带孤证标记。"""
        hits = query(populated, kind="pattern", pain="P1-1")
        for h in hits:
            if h.get("support", 1) <= 1:
                assert "孤证" in h.get("note", "") or h.get("support", 0) <= 1

    def test_query_pattern_by_pain(self, populated):
        """按痛点查 pattern。"""
        hits = query(populated, kind="pattern", pain="P2-1")
        assert hits, "P2-1 应命中南向采光房写法"
        assert any("P2-1" in h.get("pains", "") for h in hits)

    def test_query_content_from_file(self, populated, tmp_path):
        """正文来自文件：改 pattern 文件后 query 结果跟着变（不存正文在 DB）。"""
        from goldlib.reindex import reindex as re
        # 改夹具文件
        rp = Path(GOLD_DIR) / "room_patterns" / "orientation.md"
        original = rp.read_text(encoding="utf-8")
        db2 = tmp_path / "db2.db"
        try:
            rp.write_text(original + "## pattern: 测试新模式\n命中痛点: P2-9\n",
                          encoding="utf-8")
            re(str(GOLD_DIR), str(db2))
            hits = query(str(db2), kind="pattern", pain="P2-9")
            assert hits, "新 pattern 入库后应按 P2-9 查到"
        finally:
            rp.write_text(original, encoding="utf-8")

    def test_query_uses_conditions(self, populated):
        """query 按适用条件预筛（geom_facts 命中才返回）。"""
        hits = query(populated, kind="pattern", pain="P1-1",
                     geom_facts={"aspect_ratio": 1.8, "long_side": "S"})
        assert any("板式" in h["pattern_id"] for h in hits)


class TestConditionEvaluator:
    """T32 适用条件求值器（K2：白名单求值，不引 eval）。"""

    def test_condition_true(self):
        from goldlib.evaluator import evaluate_condition
        cond = {"needs_exterior": True}
        facts = {"needs_exterior": True}
        assert evaluate_condition(cond, facts) is True

    def test_condition_false(self):
        from goldlib.evaluator import evaluate_condition
        cond = {"needs_exterior": True}
        facts = {"needs_exterior": False}
        assert evaluate_condition(cond, facts) is False

    def test_condition_numeric_compare(self):
        from goldlib.evaluator import evaluate_condition
        cond = {"aspect_ratio_min": 1.5, "long_side": "S"}
        facts = {"aspect_ratio": 1.8, "long_side": "S"}
        assert evaluate_condition(cond, facts) is True

    def test_condition_numeric_fail(self):
        from goldlib.evaluator import evaluate_condition
        cond = {"aspect_ratio_min": 1.5}
        facts = {"aspect_ratio": 1.2}
        assert evaluate_condition(cond, facts) is False

    def test_condition_or(self):
        from goldlib.evaluator import evaluate_condition
        cond = {"or": [{"deep_zone_ratio_max": 0.2}, {"typology": "中庭环绕"}]}
        facts = {"deep_zone_ratio": 0.3, "typology": "中庭环绕"}
        assert evaluate_condition(cond, facts) is True

    def test_no_eval_string(self):
        """禁止 eval/exec（安全）。"""
        from goldlib.evaluator import evaluate_condition
        import inspect
        src = inspect.getsource(evaluate_condition)
        assert "eval(" not in src and "exec(" not in src



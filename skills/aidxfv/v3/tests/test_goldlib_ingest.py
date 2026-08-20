"""goldlib ingest/生产目录布局测试（references/golden/<type>/<case>/ 结构）。

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




class TestProductionLayout:
    """reindex 必须支持生产目录结构 references/golden/<type>/<case_id>/meta.json。

    复现 bug：_scan_cases 的 glob 是 `*/*/meta.json`（从 gold_dir 出发两层），
    但生产结构是 golden/<type>/<case_id>/ 三层（住宅楼 res_2s4u_std 入库发现
    cases 表为空）。测试夹具把案例直接放 gold/ 下掩盖了此问题。
    """

    def test_golden_type_case_three_level_scanned(self, tmp_path):
        """references/golden/<type>/<case_id>/meta.json 三层结构被扫描。"""
        from goldlib.reindex import _scan_cases
        gold = tmp_path / "references" / "golden" / "residence" / "res_x"
        gold.mkdir(parents=True)
        (gold / "meta.json").write_text(
            json.dumps({"case_id": "res_x", "type": "residence"}), encoding="utf-8")
        (gold / "skeleton.json").write_text("{}", encoding="utf-8")
        refs = tmp_path / "references"
        cases = _scan_cases(refs)
        ids = [c["case_id"] for c in cases]
        assert "res_x" in ids, f"三层生产结构应被扫描到，实际 {ids}"


class TestIngestArtifacts:
    """ingest 产物规范（住宅楼 res_2s4u_std 入库发现）。"""

    def test_evidence_at_path_real_rooms_file(self, db_path, tmp_path):
        """evidence at_path 必须指向真实 rooms 文件（非硬编码 rooms.F1.json）。"""
        import shutil, sqlite3
        from goldlib.ingest import ingest
        from goldlib.reindex import reindex
        # 复制真实夹具到 tmp（避免污染只读夹具），并把 rooms 文件改成非 F1 命名——
        # r01_house replay PASS（ ingest 前置可过），改名后硬编码 rooms.F1.json 才会暴露
        work = tmp_path / "gold"
        shutil.copytree(GOLD_DIR, work)
        case = work / "r01_house"
        (case / "rooms.F1.json").rename(case / "rooms.std.json")
        # 清空 implements：避免 reindex 预置 meta.json#implements 证据行
        # 占住 evidence 主键 (pattern_id, case_id)，掩盖 ingest 的 rooms at_path 写入
        meta_path = case / "meta.json"
        meta = json.loads(meta_path.read_text())
        meta["implements"] = []
        meta_path.write_text(json.dumps(meta, ensure_ascii=False))
        db = tmp_path / "g.db"
        reindex(str(work), str(db))
        r = ingest("r01_house", str(work), str(db))
        assert r.get("status") == "ingested", \
            f"ingest 应成功，实际 {r.get('status')}: {r.get('reason', '')}"
        conn = sqlite3.connect(str(db))
        paths = [row[0] for row in conn.execute(
            "SELECT at_path FROM evidence WHERE case_id='r01_house'").fetchall()]
        assert paths, "ingested 案例应有 evidence 记录"
        assert all("rooms.std.json" in p for p in paths), \
            f"at_path 应指向真实 rooms.std.json，实际 {paths}"
        assert not any("rooms.F1.json" in p for p in paths)

    def test_ingest_writes_meta_implements(self, db_path, tmp_path):
        """ingest 后案例 meta.json 的 implements 应回写命中模式。"""
        import shutil, sqlite3
        from goldlib.ingest import ingest
        from goldlib.reindex import reindex
        # 复制真实夹具（含 patterns）到 tmp，避免污染只读夹具
        work = tmp_path / "gold"
        shutil.copytree(GOLD_DIR, work)
        case = work / "r01_house"
        meta_path = case / "meta.json"
        meta = json.loads(meta_path.read_text())
        meta["implements"] = []  # 清空待回写
        meta_path.write_text(json.dumps(meta, ensure_ascii=False))
        db = tmp_path / "g.db"
        reindex(str(work), str(db))
        r = ingest("r01_house", str(work), str(db))
        assert r.get("status") == "ingested", \
            f"ingest 应成功，实际 {r.get('status')}: {r.get('reason', '')}"
        meta2 = json.loads(meta_path.read_text())
        assert len(meta2.get("implements", [])) > 0, \
            "ingest 后 meta.implements 应回写命中模式"


class TestBuildIndexProductionLayout:
    """build_index 必须支持生产结构 references/golden/<type>/<case_id>/meta.json。

    复现 bug：build_index 的 glob `*/*/meta.json` 从 references/ 出发只两层，
    漏扫 golden/<type>/<case_id>/ 三层 → index.json 的 cases 为空。
    """

    def test_build_index_three_level(self, tmp_path):
        from goldlib.schema import build_index
        case = tmp_path / "references" / "golden" / "residence" / "res_x"
        case.mkdir(parents=True)
        (case / "meta.json").write_text(json.dumps(
            {"case_id": "res_x", "type": "residence", "template_worthy": True}))
        idx = build_index(str(tmp_path / "references"))
        ids = [c["case_id"] for c in idx["cases"]]
        assert "res_x" in ids, f"三层生产结构应入 index，实际 {ids}"

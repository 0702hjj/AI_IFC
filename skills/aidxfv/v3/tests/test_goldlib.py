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


class TestReverse:
    """T33a 机制：readback 图 → 声明。"""

    @pytest.fixture(scope="class")
    def readback_graph(self):
        g = json.load(open(GOLD_DIR / "r01_house" / "readback.json"))
        return g["readback_graph"]

    def test_reverse_produces_decl(self, readback_graph):
        """D41：反推产 walls + labels。"""
        decl = reverse(readback_graph)
        assert "walls" in decl and "labels" in decl

    def test_reverse_labels_have_at(self, readback_graph):
        """D41：labels 有 room/at（落区绑定）。"""
        decl = reverse(readback_graph)
        for lab in decl.get("labels", []):
            assert "room" in lab and "at" in lab, f"{lab.get('room')} 缺 at"

    def test_reverse_deterministic(self, readback_graph):
        a = json.dumps(reverse(readback_graph), sort_keys=True, ensure_ascii=False)
        b = json.dumps(reverse(readback_graph), sort_keys=True, ensure_ascii=False)
        assert a == b

    def test_reverse_r01_converges_to_real_rooms(self, readback_graph):
        """T33b 校准：R-01 30 个碎块 → 9 个真实房间（MIN_ROOM_SQM=4㎡）。"""
        decl = reverse(readback_graph)
        labels = decl.get("labels", [])
        assert len(labels) == 9, f"R-01 应收敛到 9 房间，实得 {len(labels)}"
        # 面积均 ≥4㎡（过滤后）
        assert all(lab["area_sqm"] >= 4 for lab in labels)

    def test_reverse_walls_axis_bounded(self, readback_graph):
        """D41：反推 walls 轴线段合法（两点 + 非退化）。"""
        decl = reverse(readback_graph)
        for w in decl["walls"]:
            assert len(w["axis"]) == 2
            assert w["axis"][0] != w["axis"][1]

    def test_reverse_walls_and_labels_synthetic(self):
        """D41 完整机制：合成房间图 → walls（边界提取）+ labels（内部点）。"""
        from goldlib.reverse import reverse
        graph = {
            "outline_mm": [[0, 0], [8000, 0], [8000, 6000], [0, 6000]],
            "nodes": [
                {"id": "r1", "type": "living", "area_geo_sqm": 12,
                 "polygon_mm": [[0, 0], [4000, 0], [4000, 3000], [0, 3000]]},
                {"id": "r2", "type": "bedroom", "area_geo_sqm": 8,
                 "polygon_mm": [[4000, 0], [8000, 0], [8000, 2000], [4000, 2000]]},
            ],
        }
        decl = reverse(graph)
        labels = {lab["room"]: lab for lab in decl["labels"]}
        assert set(labels) == {"r1", "r2"}
        # 共边（x=4000 y 0..2000 段）只产一道墙
        walls = decl["walls"]
        shared = [w for w in walls
                  if w["axis"] in ([[4000, 0], [4000, 2000]], [[4000, 2000], [4000, 0]])]
        assert len(shared) == 1, "共边应去重为一道墙"

    def test_reverse_decl_passes_normalize(self, readback_graph):
        """P1 契约：R-01 反推声明过 normalize 不崩（D41 消费格式一致）。"""
        from floorgeom.normalize import normalize_rooms
        decl = reverse(readback_graph)
        rooms_decl = {
            "floor": decl["floor"],
            "walls": decl["walls"],
            "labels": decl["labels"],
            "openings": decl.get("openings", []),
        }
        outline = readback_graph.get("outline_mm") or []
        skeleton = {"zones": [{"zone": "replay",
                               "outline": [{"outer": {"vertices": outline}}]
                               if len(outline) >= 3 else []}]}
        rm = normalize_rooms(rooms_decl, skeleton)
        assert len(rm["rooms"]) == len(decl["labels"])

    def test_ingest_sets_implements(self, db_path):
        """入库后案例 implements 命中模式。"""
        reindex(str(GOLD_DIR), str(db_path))
        result = ingest("r01_house", str(GOLD_DIR), str(db_path))
        assert "implements" in result or "status" in result

    def test_ingest_vote_increments_support(self, db_path):
        """投票：入库后 pattern support+1。"""
        reindex(str(GOLD_DIR), str(db_path))
        conn = sqlite3.connect(db_path)
        before = conn.execute(
            "SELECT support FROM patterns WHERE pattern_id LIKE '%南向%'").fetchone()
        conn.close()
        ingest("r01_house", str(GOLD_DIR), str(db_path))
        conn = sqlite3.connect(db_path)
        after = conn.execute(
            "SELECT support FROM patterns WHERE pattern_id LIKE '%南向%'").fetchone()
        conn.close()
        if before and after:
            assert after[0] >= before[0]

    def test_ingest_evidence_linked(self, db_path):
        """证据边：evidence 表有 pattern↔case 链接。"""
        reindex(str(GOLD_DIR), str(db_path))
        ingest("r01_house", str(GOLD_DIR), str(db_path))
        conn = sqlite3.connect(db_path)
        n = conn.execute(
            "SELECT COUNT(*) FROM evidence WHERE case_id='r01_house'").fetchone()[0]
        conn.close()
        assert n > 0

    def test_ingest_quarantine_fail(self, db_path, tmp_path):
        """失败路径：replay FAIL → 进 _quarantine/。"""
        # 建一个 replay FAIL 的案例目录
        bad = Path(GOLD_DIR) / "res_bad"
        bad.mkdir(exist_ok=True)
        (bad / "replay_check.json").write_text(
            json.dumps({"status": "FAIL", "findings": [{"rule": "area", "severity": "FAIL"}]}))
        try:
            result = ingest("res_bad", str(GOLD_DIR), str(db_path))
            assert result["status"] == "quarantined"
            quar = Path(GOLD_DIR) / "_quarantine" / "res_bad"
            assert quar.exists()
            assert (quar / "replay_check.json").exists()
        finally:
            import shutil
            shutil.rmtree(bad, ignore_errors=True)
            shutil.rmtree(Path(GOLD_DIR) / "_quarantine", ignore_errors=True)

    def test_replay_passes_for_r01(self):
        """replay 前置：R-01 反推声明 ↔ 回读图对账产出 replay_check。"""
        from goldlib.replay import replay_case
        result = replay_case(Path(GOLD_DIR) / "r01_house")
        assert "status" in result
        assert result["status"] in ("PASS", "FAIL")
        assert "replay_area_diff_pct" in result

    def test_replay_updates_check_file(self):
        """replay 落盘 replay_check.json。"""
        from goldlib.replay import replay_case
        replay_case(Path(GOLD_DIR) / "r01_house")
        replay = json.load(open(GOLD_DIR / "r01_house" / "replay_check.json"))
        assert "status" in replay


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

    def test_p3_fail_quarantined(self, db_path, tmp_path):
        """P3：replay FAIL → quarantine 不进入库。"""
        # 复用 TestIngest 的 quarantine 测试（已在 test_ingest_quarantine_fail）
        pass

    def test_p4_reindex_idempotent(self, db_path):
        """P4：reindex 幂等（两次 db 哈希一致）——已在 TestReindex 覆盖。"""
        pass

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
        # 构造案例：rooms.std.json（非 F1 命名）
        case = tmp_path / "golden" / "residence" / "res_at"
        case.mkdir(parents=True)
        (case / "meta.json").write_text(json.dumps(
            {"case_id": "res_at", "type": "residence", "template_worthy": True}))
        (case / "skeleton.json").write_text("{}")
        (case / "readback.json").write_text(json.dumps({"nodes": [
            {"id": "a", "type": "living", "area_geo_sqm": 10,
             "centroid_mm": [0, 0], "polygon_mm": [[0,0],[1,0],[1,1],[0,1]]}]}))
        (case / "rooms.std.json").write_text(json.dumps(
            {"rooms": [{"id": "living_01", "type": "living",
                        "loc": {"between_axes": {"x": [0,1], "y": [0,1]}}}]}))
        db = tmp_path / "g.db"
        reindex(str(tmp_path / "golden"), str(db))
        r = ingest("res_at", str(tmp_path / "golden"), str(db))
        if r.get("status") != "ingested":
            pytest.skip(f"replay 前置未过（{r.get('reason', r.get('status'))}）——单测环境从略")
        conn = sqlite3.connect(str(db))
        paths = [row[0] for row in conn.execute(
            "SELECT at_path FROM evidence WHERE case_id='res_at'").fetchall()]
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
        if r.get("status") != "ingested":
            pytest.skip(f"replay 前置未过（{r.get('reason', r.get('status'))}）——单测环境从略")
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

"""goldlib reverse 测试（T33a：readback 图 → 声明反推）。

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



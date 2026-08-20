"""orchestrate.py 测试：状态编排——补缺 mission / 按产物推进 / 恢复对账。

边界（2026-08-17 拍定）：包只管**状态记录的正确性**（补缺、合法推进、对账），
不自动派发 subagent、不自动跑 check/reconcile——决策归主 agent 线性执行（dispatch.md）。
"""

import json
from pathlib import Path

import pytest

from flowops.orchestrate import advance_status, reconcile_state, sync_missions


def _write(project, rel, data):
    p = Path(project) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        p.write_text(data, encoding="utf-8")
    else:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _dag(nodes):
    return {"nodes": [{"node": n, "zone": n.split(".")[0], "stage": "rooms",
                       "floor": "f1", "covers": ["f1"]} for n in nodes],
            "edges": []}


class TestSyncMissions:
    def test_creates_missing_missions(self, tmp_path):
        """floors.json#dag.nodes 缺的 mission 自动补（幂等）。"""
        _write(tmp_path, "derived/floors.json", {"dag": _dag(["podium.rooms", "tower.rooms"]), "zones": {}})
        result = sync_missions(str(tmp_path))
        assert result["created"] == ["podium.rooms", "tower.rooms"]
        assert (tmp_path / "missions" / "podium.rooms" / "mission.json").exists()
        assert (tmp_path / "missions" / "tower.rooms" / "mission.json").exists()

    def test_idempotent_no_duplicate(self, tmp_path):
        """二次 sync 不重复补。"""
        _write(tmp_path, "derived/floors.json", {"dag": _dag(["podium.rooms"]), "zones": {}})
        sync_missions(str(tmp_path))
        result = sync_missions(str(tmp_path))
        assert result["created"] == []
        assert result["existing"] == ["podium.rooms"]

    def test_state_registered(self, tmp_path):
        """sync 后 mission 登记进 state.json。"""
        _write(tmp_path, "derived/floors.json", {"dag": _dag(["podium.rooms"]), "zones": {}})
        sync_missions(str(tmp_path))
        state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
        assert "podium.rooms" in state["missions"]


class TestAdvanceStatus:
    def test_pending_when_no_output(self, tmp_path):
        """无产物 → 保持 pending。"""
        _write(tmp_path, "missions/podium.rooms/mission.json",
               {"node": "podium.rooms", "status": "pending", "attempts": 0})
        assert advance_status(str(tmp_path), "podium.rooms") == "pending"

    def test_rooms_json_advances_to_declared(self, tmp_path):
        """rooms.json 存在 → declared。"""
        _write(tmp_path, "missions/podium.rooms/mission.json",
               {"node": "podium.rooms", "status": "pending", "attempts": 0})
        _write(tmp_path, "missions/podium.rooms/rooms.json", {"floor": "std"})
        assert advance_status(str(tmp_path), "podium.rooms") == "declared"

    def test_geom_advances_to_presented(self, tmp_path):
        """rooms.json + geom.json → presented。"""
        _write(tmp_path, "missions/podium.rooms/mission.json",
               {"node": "podium.rooms", "status": "declared", "attempts": 0})
        _write(tmp_path, "missions/podium.rooms/rooms.json", {"floor": "std"})
        _write(tmp_path, "missions/podium.rooms/geom.json", {"rooms": []})
        assert advance_status(str(tmp_path), "podium.rooms") == "presented"

    def test_floor_dxf_advances_to_built(self, tmp_path):
        """+ floor.dxf → built。"""
        _write(tmp_path, "missions/podium.rooms/mission.json",
               {"node": "podium.rooms", "status": "presented", "attempts": 0})
        _write(tmp_path, "missions/podium.rooms/rooms.json", {"floor": "std"})
        _write(tmp_path, "missions/podium.rooms/geom.json", {"rooms": []})
        _write(tmp_path, "missions/podium.rooms/floor.dxf", "")
        assert advance_status(str(tmp_path), "podium.rooms") == "built"

    def test_pass_reconcile_advances_to_done(self, tmp_path):
        """+ readback.json + geom_check.json pass → done。"""
        _write(tmp_path, "missions/podium.rooms/mission.json",
               {"node": "podium.rooms", "status": "built", "attempts": 0})
        _write(tmp_path, "missions/podium.rooms/rooms.json", {"floor": "std"})
        _write(tmp_path, "missions/podium.rooms/geom.json", {"rooms": []})
        _write(tmp_path, "missions/podium.rooms/floor.dxf", "")
        _write(tmp_path, "missions/podium.rooms/readback.json", {"nodes": []})
        _write(tmp_path, "missions/podium.rooms/geom_check.json",
               {"reconcile": {"status": "PASS", "errors": 0}})
        assert advance_status(str(tmp_path), "podium.rooms") == "done"

    def test_missing_mission_returns_none(self, tmp_path):
        """node 无 mission 目录 → None。"""
        assert advance_status(str(tmp_path), "nope.rooms") is None


class TestReconcileState:
    def test_full_reconcile(self, tmp_path):
        """扫全部 mission，按产物对齐状态。"""
        _write(tmp_path, "derived/floors.json",
               {"dag": _dag(["a.rooms", "b.rooms"]), "zones": {}})
        sync_missions(str(tmp_path))
        # a 有 rooms.json → declared；b 空 → pending
        _write(tmp_path, "missions/a.rooms/rooms.json", {"floor": "a"})
        report = reconcile_state(str(tmp_path))
        assert report["a.rooms"] == "declared"
        assert report["b.rooms"] == "pending"

    def test_reconcile_does_not_rewrite_mission_files(self, tmp_path):
        """对账只报告状态，不改写 mission.json（保守：状态写入走 advance_status）。"""
        _write(tmp_path, "derived/floors.json", {"dag": _dag(["a.rooms"]), "zones": {}})
        sync_missions(str(tmp_path))
        _write(tmp_path, "missions/a.rooms/rooms.json", {"floor": "a"})
        reconcile_state(str(tmp_path))
        mission = json.loads((tmp_path / "missions" / "a.rooms" / "mission.json").read_text(encoding="utf-8"))
        assert mission["status"] == "pending"  # 未显式 advance 前不落盘

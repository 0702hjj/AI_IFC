# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""routes_scripts endpoint surface: staging + run/save/rollback + script diffs.

HTTP-level coverage over the full script-as-source route set (Task 3 delivered
only pure-function modules). Mirrors services/ifc endpoint shapes; locate /
edit-call live in test_script_locate.py / test_script_edit.py (chunk B), the
semantic entity diff is chunk B and intentionally absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import ezdxf

from app import dxf_diffing, script_runner

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

GOOD_SCRIPT_V2 = GOOD_SCRIPT.replace('"length": 10', '"length": 20').replace(
    "end=(params[\"length\"], 0)", "end=(params[\"length\"], params[\"length\"])"
)

BROKEN_CONTRACT_SCRIPT = '''\
def build(params, out_path):
    open(out_path, "w").write("x")
'''

FAILING_SCRIPT = '''\
PARAMS = {"a": 1}

def build(params, out_path):
    raise RuntimeError("save-boom")

if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1])
'''

BASE = f"/models/{MODEL_ID}"


def _scripts_dir(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "scripts"


def _versions_dir(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "versions"


def _current_map(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "current.map.json"


def _upload(data_dir: Path) -> Path:
    return data_dir / "uploads" / f"{MODEL_ID}.dxf"


class TestGetAndStage:
    def test_get_script_404_without_script(self, client):
        resp = client.get(f"{BASE}/script")
        assert resp.status_code == 404

    def test_get_script_404_unknown_model(self, client):
        resp = client.get("/models/m_ffffffffffffffff/script")
        assert resp.status_code == 404

    def test_stage_and_get_full_script(self, client):
        resp = client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        assert resp.status_code == 200
        body = resp.json()
        assert body["staged"] == 1
        assert body["canUndo"] is True
        assert body["canRedo"] is False

        got = client.get(f"{BASE}/script").json()
        assert got["script"] == GOOD_SCRIPT
        assert got["staged"] == 1
        assert got["maxSteps"] == 10

    def test_stage_body_requires_exactly_one_of_script_params(self, client):
        both = client.put(
            f"{BASE}/script", json={"script": GOOD_SCRIPT, "params": {"length": 5}}
        )
        neither = client.put(f"{BASE}/script", json={"note": "x"})
        assert both.status_code == 422
        assert neither.status_code == 422

    def test_stage_invalid_contract_422_and_not_staged(self, client):
        resp = client.put(f"{BASE}/script", json={"script": BROKEN_CONTRACT_SCRIPT})
        assert resp.status_code == 422
        assert "PARAMS" in resp.json()["detail"]
        assert client.get(f"{BASE}/script").status_code == 404

    def test_stage_params_only_rewrites_params_block(self, client):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        resp = client.put(f"{BASE}/script", json={"params": {"length": 42}})
        assert resp.status_code == 200
        assert resp.json()["staged"] == 2
        params = client.get(f"{BASE}/script/params").json()["params"]
        assert params == {"length": 42}

    def test_stage_params_without_script_409(self, client):
        resp = client.put(f"{BASE}/script", json={"params": {"length": 5}})
        assert resp.status_code == 409

    def test_get_params(self, client):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        resp = client.get(f"{BASE}/script/params")
        assert resp.status_code == 200
        assert resp.json()["params"] == {"length": 10}

    def test_get_params_404_without_script(self, client):
        assert client.get(f"{BASE}/script/params").status_code == 404

    def test_get_script_seeds_from_saved_big_version(self, client, data_dir):
        """无暂存但有大版本脚本（如归档模型）→ GET /script 以最新大版本为基。"""
        scripts = _scripts_dir(data_dir)
        scripts.mkdir(parents=True)
        (scripts / "v1.py").write_text(GOOD_SCRIPT, encoding="utf-8")
        resp = client.get(f"{BASE}/script")
        assert resp.status_code == 200
        assert resp.json()["script"] == GOOD_SCRIPT


class TestStagingNavigation:
    def test_undo_redo(self, client):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT_V2})

        resp = client.post(f"{BASE}/script/undo")
        assert resp.status_code == 200
        assert resp.json()["script"] == GOOD_SCRIPT
        assert resp.json()["canRedo"] is True

        resp = client.post(f"{BASE}/script/redo")
        assert resp.status_code == 200
        assert resp.json()["script"] == GOOD_SCRIPT_V2
        assert resp.json()["canUndo"] is True

    def test_undo_at_oldest_409(self, client):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        assert client.post(f"{BASE}/script/undo").status_code == 200
        assert client.post(f"{BASE}/script/undo").status_code == 409

    def test_redo_at_newest_409(self, client):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        assert client.post(f"{BASE}/script/redo").status_code == 409

    def test_discard_returns_to_base(self, client):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT_V2})
        resp = client.post(f"{BASE}/script/discard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["discarded"] == 2
        assert body["script"] is None
        assert client.get(f"{BASE}/script").status_code == 404


class TestRun:
    def test_run_replaces_upload_and_publishes_map_envelope(self, client, data_dir):
        before = _upload(data_dir).read_bytes()
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        resp = client.post(f"{BASE}/script/run")
        assert resp.status_code == 200
        body = resp.json()
        assert body["modelId"] == MODEL_ID
        assert body["ok"] is True

        after = _upload(data_dir)
        assert after.read_bytes() != before
        doc = ezdxf.readfile(str(after))
        assert len(doc.modelspace().query("LINE")) == 1

        envelope = json.loads(_current_map(data_dir).read_text(encoding="utf-8"))
        assert envelope["scriptHash"] == script_runner.script_hash(GOOD_SCRIPT)
        assert "0:line:1" in envelope["map"]

    def test_run_returns_semantic_diff_counts(self, client):
        """run 响应附构件级 diff：fixture（LINE+CIRCLE）→ 生成（仅 LINE）。"""
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        resp = client.post(f"{BASE}/script/run")
        assert resp.status_code == 200, resp.text
        diff = resp.json()["semanticDiff"]
        assert set(diff) == {"added", "removed", "changed"}
        assert all(isinstance(diff[k], int) for k in diff)
        # fixture 的 LINE 与生成 LINE 同 key 同签名；CIRCLE 被移除
        assert diff["added"] == 0
        assert diff["removed"] == 1
        assert diff["changed"] == 0

    def test_second_run_diffs_against_previous_run(self, client):
        """第二次 run 的基线是上一次 run 的产物（同 key 实体对齐为 changed）。"""
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        assert client.post(f"{BASE}/script/run").status_code == 200
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT_V2})
        resp = client.post(f"{BASE}/script/run")
        assert resp.status_code == 200, resp.text
        diff = resp.json()["semanticDiff"]
        assert diff is not None
        # GOOD_SCRIPT_V2 只改 LINE 终点：同 key 对齐 → 1 changed，无增减
        assert diff["added"] == 0
        assert diff["removed"] == 0
        assert diff["changed"] == 1

    def test_run_semantic_diff_failure_degrades_to_none(
        self, client, monkeypatch
    ):
        """diff 引擎爆炸 → semanticDiff=None，run 本身仍 200（容错纪律）。"""

        def _boom(base_path: str, target_path: str) -> dict:
            raise RuntimeError("dxf diff exploded")

        monkeypatch.setattr(dxf_diffing, "compute_diff", _boom)
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        resp = client.post(f"{BASE}/script/run")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ok"] is True
        assert body["semanticDiff"] is None

    def test_run_without_script_409(self, client):
        assert client.post(f"{BASE}/script/run").status_code == 409

    def test_run_broken_script_422_upload_untouched(self, client, data_dir):
        before = _upload(data_dir).read_bytes()
        client.put(f"{BASE}/script", json={"script": FAILING_SCRIPT})
        resp = client.post(f"{BASE}/script/run")
        assert resp.status_code == 422
        assert "save-boom" in resp.json()["detail"]
        assert _upload(data_dir).read_bytes() == before


class TestSaveAndVersions:
    def test_save_creates_lockstep_pair(self, client, data_dir):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        resp = client.post(f"{BASE}/script/save", json={"note": "首版"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["version"] == "v1"
        assert body["staged"] == 0
        assert "alignment" not in body  # 分期决策：chunk A 不算对齐 diff

        assert (_scripts_dir(data_dir) / "v1.py").read_text(encoding="utf-8") == GOOD_SCRIPT
        assert (_scripts_dir(data_dir) / "v1.meta.json").is_file()
        assert (_scripts_dir(data_dir) / "v1.map.json").is_file()
        assert (_versions_dir(data_dir) / "v1.dxf").is_file()

    def test_save_failing_script_422_no_version(self, client, data_dir):
        client.put(f"{BASE}/script", json={"script": FAILING_SCRIPT})
        resp = client.post(f"{BASE}/script/save")
        assert resp.status_code == 422
        assert not list(_scripts_dir(data_dir).glob("v*.py"))
        # staging 保留，可修好再 save
        assert client.get(f"{BASE}/script").json()["script"] == FAILING_SCRIPT

    def test_second_save_prunes_older_dxf_keeps_scripts(self, client, data_dir):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        client.post(f"{BASE}/script/save")
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT_V2})
        resp = client.post(f"{BASE}/script/save")
        assert resp.json()["version"] == "v2"

        scripts = sorted(p.name for p in _scripts_dir(data_dir).glob("v*.py"))
        assert scripts == ["v1.py", "v2.py"]
        # 旧 DXF 快照可重建 → 裁剪；只留最新物化
        dxfs = sorted(p.name for p in _versions_dir(data_dir).glob("v*.dxf"))
        assert dxfs == ["v2.dxf"]

    def test_list_scripts_and_versions(self, client, data_dir):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        client.post(f"{BASE}/script/save", json={"note": "n1"})
        resp = client.get(f"{BASE}/scripts")
        assert resp.status_code == 200
        body = resp.json()
        assert [s["version"] for s in body["scripts"]] == ["v1"]
        assert body["scripts"][0]["note"] == "n1"
        assert [v["version"] for v in body["versions"]] == ["v1"]

    def test_list_scripts_empty_for_upload_only_model(self, client):
        body = client.get(f"{BASE}/scripts").json()
        assert body["scripts"] == []
        assert body["versions"] == []

    def test_get_versions_endpoint(self, client):
        assert client.get(f"{BASE}/versions").json() == {
            "versions": [],
            "current": None,
        }
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        client.post(f"{BASE}/script/save")
        body = client.get(f"{BASE}/versions").json()
        assert [v["version"] for v in body["versions"]] == ["v1"]
        assert body["current"] == "v1"


class TestRollback:
    def test_rollback_restores_script_and_reruns(self, client, data_dir):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        client.post(f"{BASE}/script/save")
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT_V2})
        client.post(f"{BASE}/script/save")

        resp = client.post(f"{BASE}/script/rollback", json={"version": "v1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["version"] == "v1"
        assert body["script"] == GOOD_SCRIPT
        # 重跑后的 uploads 与 map 回到 v1 脚本
        envelope = json.loads(_current_map(data_dir).read_text(encoding="utf-8"))
        assert envelope["scriptHash"] == script_runner.script_hash(GOOD_SCRIPT)

    def test_rollback_missing_version_404(self, client):
        resp = client.post(f"{BASE}/script/rollback", json={"version": "v9"})
        assert resp.status_code == 404


class TestScriptDiff:
    def _two_versions(self, client):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        client.post(f"{BASE}/script/save")
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT_V2})
        client.post(f"{BASE}/script/save")

    def test_diff_between_big_versions(self, client):
        self._two_versions(client)
        resp = client.post(f"{BASE}/script/diff", json={"base": "v1", "target": "v2"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["engine"] == "script"
        assert body["base"] == "v1" and body["target"] == "v2"
        assert body["stats"]["added"] > 0 or body["stats"]["removed"] > 0
        actions = {c["key"]: c["action"] for c in body["params_changes"]}
        assert actions == {"length": "modified"}
        assert "-PARAMS = {\"length\": 10}" in body["text_diff"]

    def test_diff_missing_version_404(self, client):
        self._two_versions(client)
        resp = client.post(f"{BASE}/script/diff", json={"base": "v1", "target": "v9"})
        assert resp.status_code == 404

    def test_staging_diff_last_two_steps(self, client):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT_V2})
        resp = client.get(f"{BASE}/script/staging/diff")
        assert resp.status_code == 200
        body = resp.json()
        assert body["from"] == 0 and body["to"] == 1
        actions = {c["key"]: c["action"] for c in body["params_changes"]}
        assert actions == {"length": "modified"}

    def test_staging_diff_explicit_range(self, client):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT_V2})
        resp = client.get(f"{BASE}/script/staging/diff", params={"from": 0, "to": 1})
        assert resp.status_code == 200
        assert resp.json()["from"] == 0

    def test_staging_diff_out_of_range_422(self, client):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT_V2})
        assert client.get(
            f"{BASE}/script/staging/diff", params={"from": 1, "to": 5}
        ).status_code == 422
        assert client.get(
            f"{BASE}/script/staging/diff", params={"from": 1, "to": 1}
        ).status_code == 422

    def test_staging_diff_fewer_than_two_steps_409(self, client):
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        assert client.get(f"{BASE}/script/staging/diff").status_code == 409

    def test_save_with_building_sidecar(self, client, data_dir):
        """C1：交付产物 building.json 存在时，save 随大版本 lockstep 落 v{n}.building.json。"""
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        # 模拟交付脚本已把 building.json 写到模型子树 deliver/ 区
        deliver = data_dir / "models" / MODEL_ID / "deliver"
        deliver.mkdir(parents=True, exist_ok=True)
        building = {"version": 1, "project": "p_x", "zones": [{"zone": "z1", "dxf": "z1.dxf"}]}
        (deliver / "building.json").write_text(json.dumps(building), encoding="utf-8")

        resp = client.post(f"{BASE}/script/save", json={"note": "含 building"})
        assert resp.status_code == 200
        assert resp.json()["version"] == "v1"
        sidecar = _scripts_dir(data_dir) / "v1.building.json"
        assert sidecar.is_file()
        assert json.loads(sidecar.read_text(encoding="utf-8"))["zones"][0]["zone"] == "z1"

    def test_save_without_building_sidecar_no_file(self, client, data_dir):
        """无 building 产物 → 不落 building sidecar（与 map 可空同纪律）。"""
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        resp = client.post(f"{BASE}/script/save", json={"note": "无 building"})
        assert resp.status_code == 200
        assert not (_scripts_dir(data_dir) / "v1.building.json").exists()

    def test_diff_includes_building_changes(self, client, data_dir):
        """C1+diff：script/diff 响应带 building sidecar 字段级差异（交付索引可追溯）。"""
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        deliver = data_dir / "models" / MODEL_ID / "deliver"
        deliver.mkdir(parents=True, exist_ok=True)
        (deliver / "building.json").write_text(
            json.dumps({"version": 1, "project": "p_x", "zones": [{"zone": "z1", "floors": 3}]}),
            encoding="utf-8",
        )
        client.post(f"{BASE}/script/save")  # v1 带 building
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT_V2})
        (deliver / "building.json").write_text(
            json.dumps({"version": 2, "project": "p_x", "zones": [{"zone": "z1", "floors": 4}]}),
            encoding="utf-8",
        )
        client.post(f"{BASE}/script/save")  # v2 带 building

        resp = client.post(f"{BASE}/script/diff", json={"base": "v1", "target": "v2"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["buildingChanges"] is not None
        ops = {c["op"] + " " + c["path"] for c in body["buildingChanges"]}
        assert "modify version" in ops
        assert "modify zones[0].floors" in ops

    def test_diff_building_sidecar_missing_null(self, client, data_dir):
        """一侧无 building sidecar → buildingChanges null（不阻断脚本 diff）。"""
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
        client.post(f"{BASE}/script/save")  # v1 无 building
        client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT_V2})
        client.post(f"{BASE}/script/save")  # v2 无 building
        resp = client.post(f"{BASE}/script/diff", json={"base": "v1", "target": "v2"})
        assert resp.status_code == 200
        assert resp.json()["buildingChanges"] is None

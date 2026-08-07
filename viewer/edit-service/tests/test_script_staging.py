# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Script staging buffer + script endpoints (WPS-style undo/redo, save/rollback)."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import script_staging, script_versions
from tests.conftest import MODEL_ID


def _script(marker: str) -> str:
    return (
        f'PARAMS = {{"marker": "{marker}"}}\n'
        "\n"
        "def build(params, out_path):\n"
        "    open(out_path, 'w').write('IFC:' + params['marker'])\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    import sys\n"
        "    build(PARAMS, sys.argv[1])\n"
    )


FAIL_SCRIPT = (
    'PARAMS = {"a": 1}\n'
    "\n"
    "def build(params, out_path):\n"
    "    raise RuntimeError('save-fail-marker')\n"
    "\n"
    'if __name__ == "__main__":\n'
    "    import sys\n"
    "    build(PARAMS, sys.argv[1])\n"
)


class TestScriptStagingBuffer:
    def test_push_undo_redo(self):
        st = script_staging.ScriptStaging(model_id="m")
        st.push("v-a")
        st.push("v-b")
        st.push("v-c")
        assert st.current() == "v-c"
        assert st.undo() and st.current() == "v-b"
        assert st.undo() and st.current() == "v-a"
        assert st.undo() and st.current() is None  # back to (empty) base
        assert not st.undo()
        assert st.redo() and st.current() == "v-a"
        assert st.redo() and st.redo() and st.current() == "v-c"
        assert not st.redo()

    def test_new_edit_drops_redo_tail(self):
        st = script_staging.ScriptStaging(model_id="m")
        st.push("a")
        st.push("b")
        st.undo()
        st.push("z")
        assert st.current() == "z"
        assert not st.can_redo()
        assert st.staged_count() == 2

    def test_max_steps_ring_buffer(self):
        st = script_staging.ScriptStaging(model_id="m")
        for i in range(15):
            st.push(f"s{i}")
        assert len(st.history) == script_staging.MAX_STEPS
        assert st.current() == "s14"
        steps_back = 0
        while st.undo():
            steps_back += 1
        assert steps_back == script_staging.MAX_STEPS

    def test_discard_and_save(self):
        st = script_staging.ScriptStaging(model_id="m")
        st.push("a")
        st.push("b")
        assert st.discard() == 2
        assert st.current() is None
        st.push("c")
        st.save()
        assert st.base == "c"
        assert st.staged_count() == 0

    def test_base_seed(self):
        st = script_staging.ScriptStaging(model_id="m", base="seed")
        assert st.current() == "seed"
        st.push("edit")
        st.undo()
        assert st.current() == "seed"


class TestScriptEndpointBasics:
    def test_get_script_404_without_script(self, client: TestClient):
        """老模型（只有 IFC 无脚本）：GET script/params 明确 404。"""
        r = client.get(f"/models/{MODEL_ID}/script")
        assert r.status_code == 404
        r = client.get(f"/models/{MODEL_ID}/script/params")
        assert r.status_code == 404

    def test_get_script_404_unknown_model(self, client: TestClient):
        r = client.get("/models/m_ffffffffffffffff/script")
        assert r.status_code == 404

    def test_scripts_list_empty_for_legacy_model(self, client: TestClient):
        r = client.get(f"/models/{MODEL_ID}/scripts")
        assert r.status_code == 200
        assert r.json()["scripts"] == []
        assert r.json()["versions"] == []

    def test_stage_undo_redo_discard(self, client: TestClient):
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("a")})
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("b")})
        r = client.get(f"/models/{MODEL_ID}/script")
        body = r.json()
        assert body["staged"] == 2 and body["canUndo"] is True
        assert '"marker": "b"' in body["script"]

        r = client.post(f"/models/{MODEL_ID}/script/undo")
        assert '"marker": "a"' in r.json()["script"]
        r = client.post(f"/models/{MODEL_ID}/script/redo")
        assert '"marker": "b"' in r.json()["script"]

        r = client.post(f"/models/{MODEL_ID}/script/discard")
        assert r.json()["discarded"] == 2
        assert client.get(f"/models/{MODEL_ID}/script").status_code == 404

    def test_undo_nothing_409(self, client: TestClient):
        assert client.post(f"/models/{MODEL_ID}/script/undo").status_code == 409
        assert client.post(f"/models/{MODEL_ID}/script/redo").status_code == 409

    def test_put_contract_violation_422_and_not_staged(self, client: TestClient):
        r = client.put(f"/models/{MODEL_ID}/script", json={"script": "x = 1\n"})
        assert r.status_code == 422
        assert client.get(f"/models/{MODEL_ID}/script").status_code == 404

    def test_put_requires_exactly_one_mode(self, client: TestClient):
        assert client.put(
            f"/models/{MODEL_ID}/script", json={}
        ).status_code == 422
        assert client.put(
            f"/models/{MODEL_ID}/script",
            json={"script": _script("a"), "params": {"x": 1}},
        ).status_code == 422

    def test_put_unknown_model_404(self, client: TestClient):
        r = client.put("/models/m_ffffffffffffffff/script",
                       json={"script": _script("a")})
        assert r.status_code == 404


class TestParamsMode:
    def test_params_only_update(self, client: TestClient):
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("a")})
        r = client.put(f"/models/{MODEL_ID}/script",
                       json={"params": {"marker": "patched"}})
        assert r.status_code == 200
        body = client.get(f"/models/{MODEL_ID}/script").json()
        assert body["staged"] == 2
        assert '"marker": "patched"' in body["script"].replace("'", '"') or \
            "'marker': 'patched'" in body["script"] or "patched" in body["script"]

    def test_params_mode_without_script_409(self, client: TestClient):
        r = client.put(f"/models/{MODEL_ID}/script", json={"params": {"x": 1}})
        assert r.status_code == 409

    def test_get_params(self, client: TestClient):
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("a")})
        r = client.get(f"/models/{MODEL_ID}/script/params")
        assert r.status_code == 200
        assert r.json()["params"] == {"marker": "a"}


class TestRunSaveRollback:
    def test_run_replaces_upload(self, client: TestClient, data_dir: Path):
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("run1")})
        r = client.post(f"/models/{MODEL_ID}/script/run")
        assert r.status_code == 200 and r.json()["ok"] is True
        ifc = data_dir / "uploads" / f"{MODEL_ID}.ifc"
        assert ifc.read_text() == "IFC:run1"

    def test_run_without_script_409(self, client: TestClient):
        assert client.post(f"/models/{MODEL_ID}/script/run").status_code == 409

    def test_run_unloads_registry_cache(self, client: TestClient, data_dir: Path):
        """run 后 registry 不得缓存旧 uploads 模型（实体编辑须看到新文件）。"""
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("r")})
        client.post(f"/models/{MODEL_ID}/script/run")
        app = client.app
        path = os.path.abspath(str(data_dir / "uploads" / f"{MODEL_ID}.ifc"))
        assert path not in app.state.registry._models

    def test_save_creates_script_and_ifc_version_pair(
        self, client: TestClient, data_dir: Path
    ):
        client.put(f"/models/{MODEL_ID}/script",
                   json={"script": _script("s1"), "note": "first"})
        r = client.post(f"/models/{MODEL_ID}/script/save", json={"note": "first"})
        assert r.status_code == 200, r.text
        assert r.json()["version"] == "v1"
        assert r.json()["staged"] == 0

        script_file = data_dir / "models" / MODEL_ID / "scripts" / "v1.py"
        ifc_file = data_dir / "models" / MODEL_ID / "versions" / "v1.ifc"
        assert script_file.is_file() and '"marker": "s1"' in script_file.read_text()
        assert ifc_file.is_file() and ifc_file.read_text() == "IFC:s1"
        # uploads 同步为重跑产物
        assert (data_dir / "uploads" / f"{MODEL_ID}.ifc").read_text() == "IFC:s1"

        r = client.get(f"/models/{MODEL_ID}/scripts")
        scripts = r.json()["scripts"]
        assert [s["version"] for s in scripts] == ["v1"]
        assert scripts[0]["note"] == "first"
        assert [v["version"] for v in r.json()["versions"]] == ["v1"]

        # staging cleared but base remains readable
        body = client.get(f"/models/{MODEL_ID}/script").json()
        assert body["staged"] == 0 and '"marker": "s1"' in body["script"]

    def test_save_failure_422_no_version(self, client: TestClient, data_dir: Path):
        client.put(f"/models/{MODEL_ID}/script", json={"script": FAIL_SCRIPT})
        r = client.post(f"/models/{MODEL_ID}/script/save")
        assert r.status_code == 422
        assert "save-fail-marker" in r.json()["detail"]
        # 不产生版本，staging 保留可修复后重试
        assert script_versions.list_scripts(str(data_dir), MODEL_ID) == []
        assert not (data_dir / "models" / MODEL_ID / "versions").exists()
        assert client.get(f"/models/{MODEL_ID}/script").json()["staged"] == 1

    def test_save_without_script_409(self, client: TestClient):
        assert client.post(f"/models/{MODEL_ID}/script/save").status_code == 409

    def test_rollback_restores_script_and_upload(
        self, client: TestClient, data_dir: Path
    ):
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("one")})
        client.post(f"/models/{MODEL_ID}/script/save")
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("two")})
        client.post(f"/models/{MODEL_ID}/script/save")

        r = client.post(f"/models/{MODEL_ID}/script/rollback", json={"version": "v1"})
        assert r.status_code == 200, r.text
        assert r.json()["version"] == "v1"
        assert '"marker": "one"' in r.json()["script"]
        # staging 重置到 v1 脚本，uploads 重跑为 v1 产物
        body = client.get(f"/models/{MODEL_ID}/script").json()
        assert body["staged"] == 0 and '"marker": "one"' in body["script"]
        assert (data_dir / "uploads" / f"{MODEL_ID}.ifc").read_text() == "IFC:one"

    def test_rollback_unknown_version_404(self, client: TestClient):
        r = client.post(f"/models/{MODEL_ID}/script/rollback", json={"version": "v9"})
        assert r.status_code == 404

    def test_full_flow_stage_run_save_list_rollback(self, client: TestClient):
        """验收标准全流程：PUT → run → undo/redo → save → scripts 列表 → rollback。"""
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("f1")})
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("f2")})
        client.post(f"/models/{MODEL_ID}/script/undo")
        client.post(f"/models/{MODEL_ID}/script/redo")
        assert client.post(f"/models/{MODEL_ID}/script/run").status_code == 200
        r = client.post(f"/models/{MODEL_ID}/script/save", json={"note": "flow"})
        assert r.json()["version"] == "v1"
        r = client.get(f"/models/{MODEL_ID}/scripts")
        assert r.json()["scripts"][0]["version"] == "v1"
        r = client.post(f"/models/{MODEL_ID}/script/rollback", json={"version": "v1"})
        assert r.status_code == 200


def _archive_big_version(data_dir: Path, version: str, marker: str) -> None:
    """模拟 chat 归档形态：只有 scripts/v{n}.py，无 staging 缓冲。"""
    scripts = data_dir / "models" / MODEL_ID / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / f"{version}.py").write_text(_script(marker), encoding="utf-8")


class TestSeedFromBigVersion:
    """chat 产出的模型：agent 写 staging，Go 只归档 scripts/v{n}.py，edit-service
    无 staging 记录 → GET /script 曾 404（M5 终审 C1）。staging 为空且存在大版本时，
    以最新大版本脚本 seed base；已有 staging 不被覆盖。"""

    def test_get_script_seeds_from_latest_big_version(
        self, client: TestClient, data_dir: Path
    ):
        _archive_big_version(data_dir, "v1", "chat-v1")
        r = client.get(f"/models/{MODEL_ID}/script")
        assert r.status_code == 200
        body = r.json()
        assert '"marker": "chat-v1"' in body["script"]
        assert body["staged"] == 0
        assert body["canUndo"] is False and body["canRedo"] is False
        # 幂等：再 GET 不变
        assert client.get(f"/models/{MODEL_ID}/script").json() == body

    def test_get_params_seeded(self, client: TestClient, data_dir: Path):
        _archive_big_version(data_dir, "v1", "chat-v1")
        r = client.get(f"/models/{MODEL_ID}/script/params")
        assert r.status_code == 200
        assert r.json()["params"] == {"marker": "chat-v1"}

    def test_seed_uses_newest_big_version(self, client: TestClient, data_dir: Path):
        _archive_big_version(data_dir, "v1", "old")
        _archive_big_version(data_dir, "v2", "new")
        r = client.get(f"/models/{MODEL_ID}/script")
        assert '"marker": "new"' in r.json()["script"]

    def test_seed_persisted_to_disk(self, client: TestClient, data_dir: Path):
        """seed 落盘：重启（新 registry）后 GET 仍 200。"""
        _archive_big_version(data_dir, "v1", "persisted")
        assert client.get(f"/models/{MODEL_ID}/script").status_code == 200
        staging_file = data_dir / "models" / MODEL_ID / "script_staging.json"
        assert staging_file.is_file()
        assert "persisted" in staging_file.read_text(encoding="utf-8")

    def test_seed_does_not_override_existing_staging(
        self, client: TestClient, data_dir: Path
    ):
        _archive_big_version(data_dir, "v1", "base")
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("edit")})
        r = client.get(f"/models/{MODEL_ID}/script")
        assert '"marker": "edit"' in r.json()["script"]
        assert r.json()["staged"] == 1

    def test_reseed_after_discard(self, client: TestClient, data_dir: Path):
        """seed 后 discard 清掉暂存 → current 回 base（seed 的 v1）而非 404。"""
        _archive_big_version(data_dir, "v1", "base")
        client.get(f"/models/{MODEL_ID}/script")  # seed base
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("edit")})
        r = client.post(f"/models/{MODEL_ID}/script/discard")
        assert '"marker": "base"' in r.json()["script"]

    def test_concurrent_gets_seed_consistently(
        self, client: TestClient, data_dir: Path
    ):
        _archive_big_version(data_dir, "v1", "conc")
        with ThreadPoolExecutor(max_workers=4) as pool:
            bodies = list(
                pool.map(
                    lambda _: client.get(f"/models/{MODEL_ID}/script").json(),
                    range(4),
                )
            )
        assert all('"marker": "conc"' in b["script"] for b in bodies)
        assert len({b["script"] for b in bodies}) == 1


class TestPerModelLock:
    def test_concurrent_saves_serialize_into_distinct_versions(
        self, client: TestClient, data_dir: Path
    ):
        """并发 save 必须串行化：无锁时 next_n 竞争会丢版本（routes_design 已知缺口）。"""
        client.put(f"/models/{MODEL_ID}/script", json={"script": _script("c0")})
        client.post(f"/models/{MODEL_ID}/script/save")

        def save_one(i: int) -> int:
            client.put(f"/models/{MODEL_ID}/script", json={"script": _script(f"c{i}")})
            return client.post(f"/models/{MODEL_ID}/script/save").status_code

        with ThreadPoolExecutor(max_workers=4) as pool:
            codes = list(pool.map(save_one, range(1, 5)))
        assert codes == [200] * 4
        scripts = script_versions.list_scripts(str(data_dir), MODEL_ID)
        assert len(scripts) == 5  # v1 + 4 并发 save，互不覆盖

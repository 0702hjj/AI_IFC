# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Script diff tests (big versions + staging steps)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import script_diff, script_versions
from tests.conftest import MODEL_ID

SCRIPT_A = (
    'PARAMS = {"width": 12.0, "height": 3.0, "name": "a"}\n'
    "\n"
    "def build(params, out_path):\n"
    "    open(out_path, 'w').write('IFC:' + str(params['width']))\n"
    "\n"
    'if __name__ == "__main__":\n'
    "    import sys\n"
    "    build(PARAMS, sys.argv[1])\n"
)

# width 改、name 删、depth 增
SCRIPT_B = (
    'PARAMS = {"width": 14.0, "height": 3.0, "depth": 8.0}\n'
    "\n"
    "def build(params, out_path):\n"
    "    open(out_path, 'w').write('IFC:' + str(params['width']))\n"
    "\n"
    'if __name__ == "__main__":\n'
    "    import sys\n"
    "    build(PARAMS, sys.argv[1])\n"
)

NO_PARAMS_SCRIPT = "x = 1\n"


class TestTextDiff:
    def test_unified_diff_marks_changed_lines(self):
        r = script_diff.diff_scripts(SCRIPT_A, SCRIPT_B, "v1", "v2")
        text = r["text_diff"]
        assert "--- v1" in text and "+++ v2" in text
        assert '-PARAMS = {"width": 12.0, "height": 3.0, "name": "a"}' in text
        assert '+PARAMS = {"width": 14.0, "height": 3.0, "depth": 8.0}' in text
        assert r["stats"] == {"added": 1, "removed": 1}

    def test_identical_scripts_empty_diff(self):
        r = script_diff.diff_scripts(SCRIPT_A, SCRIPT_A, "v1", "v1")
        assert r["text_diff"] == ""
        assert r["stats"] == {"added": 0, "removed": 0}
        assert r["params_changes"] == []


class TestParamsChanges:
    def test_added_removed_modified_keys(self):
        changes = script_diff.params_changes(SCRIPT_A, SCRIPT_B)
        by_key = {c["key"]: c for c in changes}
        assert set(by_key) == {"width", "name", "depth"}
        assert by_key["width"] == {"key": "width", "action": "modified",
                                   "old": 12.0, "new": 14.0}
        assert by_key["name"] == {"key": "name", "action": "removed", "old": "a"}
        assert by_key["depth"] == {"key": "depth", "action": "added", "new": 8.0}

    def test_missing_params_block_treated_as_empty(self):
        assert script_diff.params_changes(NO_PARAMS_SCRIPT, SCRIPT_A) == [
            {"key": "height", "action": "added", "new": 3.0},
            {"key": "name", "action": "added", "new": "a"},
            {"key": "width", "action": "added", "new": 12.0},
        ]
        assert script_diff.params_changes(NO_PARAMS_SCRIPT, NO_PARAMS_SCRIPT) == []


def _save_script_version(data_dir: Path, script: str, note: str = "") -> str:
    return script_versions.save(
        str(data_dir), MODEL_ID, script,
        str(data_dir / "uploads" / f"{MODEL_ID}.ifc"), note=note,
    )


class TestScriptDiffEndpoint:
    def test_diff_between_big_versions(self, client: TestClient, data_dir: Path):
        _save_script_version(data_dir, SCRIPT_A, "a")
        _save_script_version(data_dir, SCRIPT_B, "b")
        r = client.post(f"/models/{MODEL_ID}/script/diff",
                        json={"base": "v1", "target": "v2"})
        assert r.status_code == 200
        body = r.json()
        assert body["base"] == "v1" and body["target"] == "v2"
        assert body["engine"] == "script"
        assert "--- v1" in body["text_diff"]
        assert body["stats"] == {"added": 1, "removed": 1}
        keys = {c["key"] for c in body["params_changes"]}
        assert keys == {"width", "name", "depth"}

    def test_missing_version_404(self, client: TestClient, data_dir: Path):
        _save_script_version(data_dir, SCRIPT_A)
        r = client.post(f"/models/{MODEL_ID}/script/diff",
                        json={"base": "v1", "target": "v9"})
        assert r.status_code == 404

    def test_unknown_model_404(self, client: TestClient):
        r = client.post("/models/m_0000000000000000/script/diff",
                        json={"base": "v1", "target": "v2"})
        assert r.status_code == 404


def _stage(client: TestClient, script: str) -> None:
    r = client.put(f"/models/{MODEL_ID}/script", json={"script": script})
    assert r.status_code == 200, r.text


class TestStagingDiffEndpoint:
    def test_default_diffs_last_two_steps(self, client: TestClient):
        _stage(client, SCRIPT_A)
        _stage(client, SCRIPT_B)
        r = client.get(f"/models/{MODEL_ID}/script/staging/diff")
        assert r.status_code == 200
        body = r.json()
        assert body["from"] == 0 and body["to"] == 1
        assert '+PARAMS = {"width": 14.0, "height": 3.0, "depth": 8.0}' in body["text_diff"]
        keys = {c["key"] for c in body["params_changes"]}
        assert keys == {"width", "name", "depth"}

    def test_explicit_from_to(self, client: TestClient):
        _stage(client, SCRIPT_A)
        _stage(client, SCRIPT_B)
        _stage(client, SCRIPT_A)
        r = client.get(f"/models/{MODEL_ID}/script/staging/diff?from=0&to=2")
        assert r.status_code == 200
        body = r.json()
        assert body["from"] == 0 and body["to"] == 2
        assert body["text_diff"] == "" and body["params_changes"] == []

    def test_fewer_than_two_staged_409(self, client: TestClient):
        _stage(client, SCRIPT_A)
        r = client.get(f"/models/{MODEL_ID}/script/staging/diff")
        assert r.status_code == 409

    def test_out_of_range_422(self, client: TestClient):
        _stage(client, SCRIPT_A)
        _stage(client, SCRIPT_B)
        assert client.get(
            f"/models/{MODEL_ID}/script/staging/diff?from=0&to=5").status_code == 422
        assert client.get(
            f"/models/{MODEL_ID}/script/staging/diff?from=1&to=1").status_code == 422

    def test_unknown_model_404(self, client: TestClient):
        r = client.get("/models/m_0000000000000000/script/staging/diff")
        assert r.status_code == 404

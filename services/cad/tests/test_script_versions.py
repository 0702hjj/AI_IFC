# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""script_versions: big-version snapshots (scripts/v{n}.py + versions/v{n}.dxf)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import script_versions, versions
from tests.conftest import MODEL_ID

SCRIPT_A = 'PARAMS = {"a": 1}\n'


class TestScriptVersions:
    def test_save_writes_script_dxf_and_meta(self, tmp_path: Path, dxf_path: Path):
        data_dir = str(tmp_path)
        version = script_versions.save(
            data_dir, MODEL_ID, SCRIPT_A, str(dxf_path), note="n1"
        )
        assert version == "v1"
        base = tmp_path / "models" / MODEL_ID
        assert (base / "scripts" / "v1.py").read_text() == SCRIPT_A
        assert (base / "versions" / "v1.dxf").read_bytes() == dxf_path.read_bytes()
        meta = json.loads((base / "scripts" / "v1.meta.json").read_text())
        assert meta["note"] == "n1" and meta["version"] == "v1"

    def test_save_increments_and_lists_oldest_first(
        self, tmp_path: Path, dxf_path: Path
    ):
        data_dir = str(tmp_path)
        assert script_versions.save(data_dir, MODEL_ID, SCRIPT_A, str(dxf_path)) == "v1"
        assert script_versions.save(
            data_dir, MODEL_ID, SCRIPT_A, str(dxf_path), note="x"
        ) == "v2"
        listed = script_versions.list_scripts(data_dir, MODEL_ID)
        assert [s["version"] for s in listed] == ["v1", "v2"]
        assert listed[0]["note"] == "" and listed[1]["note"] == "x"
        assert all("createdAt" in s for s in listed)

    def test_lockstep_with_existing_snapshots(self, tmp_path: Path, dxf_path: Path):
        """versions/ 已占 v1/v2 时，脚本大版本取 max(两侧 next) 保证成对不冲突。"""
        data_dir = str(tmp_path)
        versions.snapshot(data_dir, MODEL_ID, str(dxf_path))
        versions.snapshot(data_dir, MODEL_ID, str(dxf_path))
        version = script_versions.save(data_dir, MODEL_ID, SCRIPT_A, str(dxf_path))
        assert version == "v3"
        base = tmp_path / "models" / MODEL_ID
        assert (base / "scripts" / "v3.py").is_file()
        assert (base / "versions" / "v3.dxf").is_file()
        assert (base / "versions" / "v1.dxf").is_file()

    def test_prune_rebuildable_snapshots(self, tmp_path: Path, dxf_path: Path):
        """只留最新物化：有脚本的旧 versions/v{m}.dxf 被裁剪；无脚本的快照保留。"""
        data_dir = str(tmp_path)
        script_versions.save(data_dir, MODEL_ID, SCRIPT_A, str(dxf_path))
        versions.snapshot(data_dir, MODEL_ID, str(dxf_path))  # v2, no script
        script_versions.save(data_dir, MODEL_ID, SCRIPT_A, str(dxf_path))
        base = tmp_path / "models" / MODEL_ID / "versions"
        assert not (base / "v1.dxf").exists()  # rebuildable -> pruned
        assert (base / "v2.dxf").is_file()  # no script -> preserved
        assert (base / "v3.dxf").is_file()  # latest stays materialized

    def test_load_script(self, tmp_path: Path, dxf_path: Path):
        data_dir = str(tmp_path)
        script_versions.save(data_dir, MODEL_ID, SCRIPT_A, str(dxf_path))
        assert script_versions.load_script(data_dir, MODEL_ID, "v1") == SCRIPT_A
        with pytest.raises(KeyError):
            script_versions.load_script(data_dir, MODEL_ID, "v9")
        with pytest.raises(KeyError):
            script_versions.load_script(data_dir, MODEL_ID, "bogus")

    def test_script_path_validation(self, tmp_path: Path):
        assert script_versions.script_path(str(tmp_path), MODEL_ID, "../etc") is None
        assert script_versions.script_path(str(tmp_path), MODEL_ID, "v1") is None

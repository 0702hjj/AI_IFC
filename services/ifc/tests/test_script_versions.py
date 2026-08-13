# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""script_versions: big-version snapshots (scripts/v{n}.py + versions/v{n}.ifc)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import script_versions, versions
from tests.conftest import FIXTURE_IFC, MODEL_ID

SCRIPT_A = 'PARAMS = {"a": 1}\n'


def _src_ifc(tmp_path: Path) -> str:
    dst = tmp_path / "src.ifc"
    dst.write_bytes(FIXTURE_IFC.read_bytes())
    return str(dst)


class TestScriptVersions:
    def test_save_writes_script_ifc_and_meta(self, tmp_path: Path):
        src = _src_ifc(tmp_path)
        data_dir = str(tmp_path)
        version = script_versions.save(data_dir, MODEL_ID, SCRIPT_A, src, note="n1")
        assert version == "v1"
        base = tmp_path / "models" / MODEL_ID
        assert (base / "scripts" / "v1.py").read_text() == SCRIPT_A
        assert (base / "versions" / "v1.ifc").read_bytes() == FIXTURE_IFC.read_bytes()
        meta = json.loads((base / "scripts" / "v1.meta.json").read_text())
        assert meta["note"] == "n1" and meta["version"] == "v1"

    def test_save_increments_and_lists_oldest_first(self, tmp_path: Path):
        src = _src_ifc(tmp_path)
        data_dir = str(tmp_path)
        assert script_versions.save(data_dir, MODEL_ID, SCRIPT_A, src) == "v1"
        assert script_versions.save(data_dir, MODEL_ID, SCRIPT_A, src, note="x") == "v2"
        listed = script_versions.list_scripts(data_dir, MODEL_ID)
        assert [s["version"] for s in listed] == ["v1", "v2"]
        assert listed[0]["note"] == "" and listed[1]["note"] == "x"
        assert all("createdAt" in s for s in listed)

    def test_lockstep_with_entity_edit_versions(self, tmp_path: Path):
        """实体编辑已占 v1/v2 时，脚本大版本取 max(两侧 next) 保证成对不冲突。"""
        src = _src_ifc(tmp_path)
        data_dir = str(tmp_path)
        versions.snapshot(data_dir, MODEL_ID, src)
        versions.snapshot(data_dir, MODEL_ID, src)
        version = script_versions.save(data_dir, MODEL_ID, SCRIPT_A, src)
        assert version == "v3"
        base = tmp_path / "models" / MODEL_ID
        assert (base / "scripts" / "v3.py").is_file()
        assert (base / "versions" / "v3.ifc").is_file()
        assert (base / "versions" / "v1.ifc").is_file()

    def test_load_script(self, tmp_path: Path):
        src = _src_ifc(tmp_path)
        data_dir = str(tmp_path)
        script_versions.save(data_dir, MODEL_ID, SCRIPT_A, src)
        assert script_versions.load_script(data_dir, MODEL_ID, "v1") == SCRIPT_A
        with pytest.raises(KeyError):
            script_versions.load_script(data_dir, MODEL_ID, "v9")
        with pytest.raises(KeyError):
            script_versions.load_script(data_dir, MODEL_ID, "bogus")

    def test_script_path_validation(self, tmp_path: Path):
        assert script_versions.script_path(str(tmp_path), MODEL_ID, "../etc") is None
        assert script_versions.script_path(str(tmp_path), MODEL_ID, "v1") is None

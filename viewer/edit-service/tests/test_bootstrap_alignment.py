# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Bootstrap 原件保留 + save 对齐报告（Task 7，spec §5.4）。

plain 态模型（无脚本版本、staging 空）首次 PUT /script 时，把上传原件原子复制到
``models/{id}/bootstrap.ifc``，防后续 run 覆盖 uploads 后原件丢失；首个大版本
save 时响应携带 ``alignment``（bootstrap vs 生成 v1 的语义 diff 计数），作为
bootstrap 复现质量的验收信号。无 bootstrap 或 diff 失败 → ``alignment=None``，
绝不让对齐计算拖垮已落盘的 save。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import diffing, script_versions
from tests.conftest import FIXTURE_IFC, MODEL_ID

WALL_SCRIPT = '''\
import sys

import ifcopenshell

from script_lib import create_entity, create_skeleton, write_and_validate

PARAMS = {{"key": "{key}"}}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    body, _ = create_skeleton(model)
    w = create_entity(model, "IfcWall", key=params["key"], name="W1")
    write_and_validate(model, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''


def _wall_script(key: str = "s1:wall:1") -> str:
    return WALL_SCRIPT.format(key=key)


def _bootstrap_path(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "bootstrap.ifc"


def _seed_version_without_bootstrap(data_dir: Path) -> str:
    """模拟特性上线前的存量模型：有大版本脚本，但无 bootstrap.ifc。"""
    ifc = data_dir / "uploads" / f"{MODEL_ID}.ifc"
    return script_versions.save(
        str(data_dir), MODEL_ID, _wall_script("s1:wall:0"), str(ifc)
    )


class TestBootstrapPreservation:
    def test_first_stage_copies_original_to_bootstrap(
        self, client: TestClient, data_dir: Path
    ):
        r = client.put(f"/models/{MODEL_ID}/script", json={"script": _wall_script()})
        assert r.status_code == 200, r.text
        bootstrap = _bootstrap_path(data_dir)
        assert bootstrap.is_file()
        assert bootstrap.read_bytes() == FIXTURE_IFC.read_bytes()

    def test_bootstrap_survives_run_overwrite(
        self, client: TestClient, data_dir: Path
    ):
        """run 覆盖 uploads 后，bootstrap.ifc 仍是上传原件。"""
        client.put(f"/models/{MODEL_ID}/script", json={"script": _wall_script()})
        r = client.post(f"/models/{MODEL_ID}/script/run")
        assert r.status_code == 200, r.text
        uploads = data_dir / "uploads" / f"{MODEL_ID}.ifc"
        assert uploads.read_bytes() != FIXTURE_IFC.read_bytes()
        assert _bootstrap_path(data_dir).read_bytes() == FIXTURE_IFC.read_bytes()

    def test_bootstrap_not_recreated_after_first_save(
        self, client: TestClient, data_dir: Path
    ):
        """后续 save/暂存不覆盖已存在的 bootstrap.ifc。"""
        client.put(f"/models/{MODEL_ID}/script", json={"script": _wall_script()})
        client.post(f"/models/{MODEL_ID}/script/save")
        client.put(
            f"/models/{MODEL_ID}/script", json={"script": _wall_script("s1:wall:2")}
        )
        assert _bootstrap_path(data_dir).read_bytes() == FIXTURE_IFC.read_bytes()

    def test_stage_with_existing_versions_creates_no_bootstrap(
        self, client: TestClient, data_dir: Path
    ):
        """存量 script-backed 模型（无 bootstrap.ifc）暂存时不补建。"""
        _seed_version_without_bootstrap(data_dir)
        r = client.put(f"/models/{MODEL_ID}/script", json={"script": _wall_script()})
        assert r.status_code == 200, r.text
        assert not _bootstrap_path(data_dir).exists()


class TestSaveAlignment:
    def test_first_save_returns_alignment_counts(
        self, client: TestClient, data_dir: Path
    ):
        client.put(f"/models/{MODEL_ID}/script", json={"script": _wall_script()})
        r = client.post(f"/models/{MODEL_ID}/script/save", json={})
        assert r.status_code == 200, r.text
        alignment = r.json()["alignment"]
        assert set(alignment) == {"added", "removed", "changed"}
        assert all(isinstance(alignment[k], int) for k in alignment)
        # 原件与生成 v1 的 GlobalId 不重叠：原件构件全部 removed，生成全部 added
        assert alignment["added"] >= 1
        assert alignment["removed"] >= 1
        assert alignment["changed"] == 0

    def test_save_alignment_none_without_bootstrap(
        self, client: TestClient, data_dir: Path
    ):
        _seed_version_without_bootstrap(data_dir)
        client.put(f"/models/{MODEL_ID}/script", json={"script": _wall_script()})
        r = client.post(f"/models/{MODEL_ID}/script/save", json={})
        assert r.status_code == 200, r.text
        assert r.json()["alignment"] is None

    def test_alignment_failure_does_not_fail_save(
        self, client: TestClient, data_dir: Path, monkeypatch: pytest.MonkeyPatch
    ):
        def _boom(old_path: str, new_path: str) -> dict:
            raise RuntimeError("ifcdiff exploded")

        monkeypatch.setattr(diffing, "compute_diff", _boom)
        client.put(f"/models/{MODEL_ID}/script", json={"script": _wall_script()})
        r = client.post(f"/models/{MODEL_ID}/script/save", json={})
        assert r.status_code == 200, r.text
        assert r.json()["alignment"] is None
        # 版本本身已落盘
        assert script_versions.list_scripts(str(data_dir), MODEL_ID)

# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Design-JSON semantic diff + IFC fingerprint diff endpoints."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from app import design_diff, ifc_fingerprint
from tests.conftest import FIXTURE_IFC, MODEL_ID


def _design_a():
    return {
        "meta": {"name": "t"},
        "frame": {"storeys": {"1F": 0.0}},
        "floors": {
            "1F": {
                "walls": [
                    {"axis": [[0, 0], [12, 0]], "t": 0.2, "kind": "ext", "key": "1F:wall:0"},
                    {"axis": [[0, 8], [12, 8]], "t": 0.2, "kind": "ext", "key": "1F:wall:1"},
                ],
                "openings": [
                    {"wall": 0, "along": 3.0, "w": 1.5, "h": 1.5, "sill": 0.9,
                     "type": "window", "key": "1F:opening:0"},
                ],
                "slabs": [{"t": 0.15, "key": "1F:slab:0"}],
            }
        },
    }


def _design_b():
    # 墙1 变厚且 end 移动；墙2 删除；开一扇门；板不变
    return {
        "meta": {"name": "t"},
        "frame": {"storeys": {"1F": 0.0}},
        "floors": {
            "1F": {
                "walls": [
                    {"axis": [[0, 0], [14, 0]], "t": 0.3, "kind": "ext", "key": "1F:wall:0"},
                ],
                "openings": [
                    {"wall": 0, "along": 3.0, "w": 1.5, "h": 1.5, "sill": 0.9,
                     "type": "window", "key": "1F:opening:0"},
                    {"wall": 0, "along": 8.0, "w": 1.0, "h": 2.1, "sill": 0.0,
                     "type": "door", "key": "1F:opening:1"},
                ],
                "slabs": [{"t": 0.15, "key": "1F:slab:0"}],
            }
        },
    }


class TestDesignDiff:
    def test_added_removed_modified(self):
        r = design_diff.design_diff(_design_a(), _design_b())
        by_key = {c["key"]: c for c in r["changed"]}
        assert r["added"] == 1 and r["removed"] == 1 and r["modified"] == 1
        # 修改的墙：thickness 与 axis[1]
        mod = by_key["1F:wall:0"]["changes"]
        fields = {m["field"] for m in mod}
        assert "t" in fields and "axis[1]" in fields
        # 移除的墙 / 新增的门
        assert by_key["1F:wall:1"]["action"] == "removed"
        assert by_key["1F:opening:1"]["action"] == "added"
        assert by_key["1F:opening:1"]["type"] == "IfcDoor"

    def test_identical_designs_no_changes(self):
        r = design_diff.design_diff(_design_a(), _design_a())
        assert r["changed"] == []


class TestDesignDiffEndpoints:
    def _save_design(self, data_dir: Path, design, note: str):
        # design JSON 端点已随 W-0011 下线；直接经 design_versions 落盘造版本。
        from app import design_versions

        return design_versions.save(
            str(data_dir), MODEL_ID, design,
            str(data_dir / "uploads" / f"{MODEL_ID}.ifc"), note=note,
        )

    def test_design_diff_between_big_versions(self, client: TestClient, data_dir: Path):
        self._save_design(data_dir, _design_a(), "a")
        self._save_design(data_dir, _design_b(), "b")
        r = client.post(f"/models/{MODEL_ID}/design/diff", json={"base": "v1", "target": "v2"})
        assert r.status_code == 200
        body = r.json()
        assert body["engine"] == "design-json"
        assert body["added"] == 1 and body["removed"] == 1 and body["modified"] == 1

    def test_design_diff_missing_version_404(self, client: TestClient):
        r = client.post(f"/models/{MODEL_ID}/design/diff", json={"base": "v9", "target": "v10"})
        assert r.status_code == 404

    def test_ifc_diff_endpoint(self, client: TestClient, tmp_path: Path, data_dir: Path):
        # 造两个版本的 IFC 快照
        vdir = data_dir / "models" / MODEL_ID / "versions"
        vdir.mkdir(parents=True)
        shutil.copy(FIXTURE_IFC, vdir / "v1.ifc")
        shutil.copy(FIXTURE_IFC, vdir / "v2.ifc")
        r = client.post(f"/models/{MODEL_ID}/design/diff-ifc", json={"base": "v1", "target": "v2"})
        assert r.status_code == 200
        assert r.json()["engine"] == "ifc-fingerprint"


class TestIfcFingerprint:
    def test_identical_files_no_diff(self):
        r = ifc_fingerprint.ifc_fingerprint_diff(str(FIXTURE_IFC), str(FIXTURE_IFC))
        assert r["changed"] == []

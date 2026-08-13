# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""IFC 存储策略（spec §5.5 / I5）：只物化最新大版本，历史按需沙箱重建 + LRU 缓存。

- save v{n} 成功后删除可重建（有 scripts/v{m}.py）的旧 versions/v{m}.ifc；
  实体编辑快照（无脚本）属迁移期保留，不动。
- materialize_version：快照在 → 直接返回；快照缺失但脚本在 → 沙箱重跑进
  ``models/{id}/ifc_cache/v{n}.ifc``（LRU 上限 4，按 mtime 淘汰最旧）；
  两者皆无 → FileNotFoundError。
- POST /diff 对缺失快照走同一重建路径；重建产物与原快照**语义** diff 为空
  （字节因 IFC 头时间戳不同必然不等，I5 只保证语义稳定）。
"""

from __future__ import annotations

import dataclasses
import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import diffing, script_versions, versions
from app.config import load_settings
from tests.conftest import FIXTURE_IFC, MODEL_ID

EMPTY_DIFF = {"added": [], "removed": [], "changed": []}


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


# 全确定性契约脚本（I5）：create_skeleton 骨架实体走确定性路径（W-0023），
# 两次 run 骨架 GlobalId 一致、语义 diff 为空，无需脚本侧手动固定。
REAL_IFC_SCRIPT = '''\
import sys

import ifcopenshell

from script_lib import create_skeleton, write_and_validate

PARAMS = {"name": "lazy-v1", "storeys": {"1F": 0.0}}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    create_skeleton(model, name=params["name"], storeys=params["storeys"])
    write_and_validate(model, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''


def _settings(data_dir: Path):
    return dataclasses.replace(load_settings(), data_dir=str(data_dir))


def _dirs(data_dir: Path) -> tuple[Path, Path, Path]:
    base = data_dir / "models" / MODEL_ID
    return base / "scripts", base / "versions", base / "ifc_cache"


def _put_and_save(client: TestClient, script: str) -> str:
    r = client.put(f"/models/{MODEL_ID}/script", json={"script": script})
    assert r.status_code == 200, r.text
    r = client.post(f"/models/{MODEL_ID}/script/save")
    assert r.status_code == 200, r.text
    return r.json()["version"]


class TestSavePrunesOldSnapshots:
    def test_save_removes_older_ifc_snapshots(
        self, client: TestClient, data_dir: Path
    ):
        v1 = _put_and_save(client, _script("m1"))
        v2 = _put_and_save(client, _script("m2"))
        assert (v1, v2) == ("v1", "v2")

        scripts, versions_dir, _ = _dirs(data_dir)
        # 只剩最新物化快照；旧快照删除，脚本/map/meta 全量保留
        assert not (versions_dir / "v1.ifc").exists()
        assert (versions_dir / "v2.ifc").read_text() == "IFC:m2"
        assert (scripts / "v1.py").is_file()
        assert (scripts / "v1.meta.json").is_file()
        assert (scripts / "v2.py").is_file()

        body = client.get(f"/models/{MODEL_ID}/scripts").json()
        assert [s["version"] for s in body["scripts"]] == ["v1", "v2"]
        assert [v["version"] for v in body["versions"]] == ["v2"]

    def test_save_prunes_only_rebuildable_snapshots(
        self, client: TestClient, data_dir: Path
    ):
        """实体编辑快照（无对应脚本）属迁移期保留，save 不得误删。"""
        scripts, versions_dir, _ = _dirs(data_dir)
        versions_dir.mkdir(parents=True)
        src = FIXTURE_IFC.read_bytes()
        (versions_dir / "v1.ifc").write_bytes(src)  # 迁移期存量：无脚本
        (versions_dir / "v2.ifc").write_bytes(src)

        v3 = _put_and_save(client, _script("m3"))
        assert v3 == "v3"  # lockstep：max(两侧 next)
        assert (versions_dir / "v1.ifc").is_file()
        assert (versions_dir / "v2.ifc").is_file()
        assert (versions_dir / "v3.ifc").is_file()
        assert (scripts / "v3.py").is_file()

        v4 = _put_and_save(client, _script("m4"))
        assert v4 == "v4"
        # v3 有脚本 → 可重建 → 删除；v1/v2 无脚本 → 保留；v4 最新物化
        assert not (versions_dir / "v3.ifc").exists()
        assert (versions_dir / "v1.ifc").is_file()
        assert (versions_dir / "v2.ifc").is_file()
        assert (versions_dir / "v4.ifc").is_file()


class TestMaterializeVersion:
    def test_returns_existing_snapshot_without_rebuild(self, data_dir: Path):
        from app import ifc_materialize

        settings = _settings(data_dir)
        src = data_dir / "src.ifc"
        src.write_text("IFC:latest")
        script_versions.save(str(data_dir), MODEL_ID, _script("m1"), str(src))
        path = ifc_materialize.materialize_version(
            str(data_dir), MODEL_ID, "v1", settings
        )
        assert path == str(data_dir / "models" / MODEL_ID / "versions" / "v1.ifc")
        _, _, cache = _dirs(data_dir)
        assert not cache.exists()

    def test_rebuilds_from_script_into_cache(self, data_dir: Path):
        from app import ifc_materialize

        settings = _settings(data_dir)
        src = data_dir / "src.ifc"
        src.write_text("IFC:placeholder")
        script_versions.save(str(data_dir), MODEL_ID, _script("m1"), str(src))
        src.write_text("IFC:placeholder2")
        script_versions.save(str(data_dir), MODEL_ID, _script("m2"), str(src))

        _, versions_dir, cache = _dirs(data_dir)
        assert not (versions_dir / "v1.ifc").exists()  # 已被 save 清理
        path = ifc_materialize.materialize_version(
            str(data_dir), MODEL_ID, "v1", settings
        )
        assert path == str(cache / "v1.ifc")
        assert Path(path).read_text() == "IFC:m1"

    def test_cache_hit_does_not_rerun(self, data_dir: Path):
        from app import ifc_materialize

        settings = _settings(data_dir)
        src = data_dir / "src.ifc"
        src.write_text("IFC:p1")
        script_versions.save(str(data_dir), MODEL_ID, _script("m1"), str(src))
        src.write_text("IFC:p2")
        script_versions.save(str(data_dir), MODEL_ID, _script("m2"), str(src))

        path = Path(
            ifc_materialize.materialize_version(str(data_dir), MODEL_ID, "v1", settings)
        )
        # 哨兵：命中缓存必须原样返回，不得重跑覆盖
        path.write_text("sentinel-cached")
        again = ifc_materialize.materialize_version(
            str(data_dir), MODEL_ID, "v1", settings
        )
        assert again == str(path)
        assert path.read_text() == "sentinel-cached"

    def test_missing_snapshot_and_script_raises(self, data_dir: Path):
        from app import ifc_materialize

        with pytest.raises(FileNotFoundError):
            ifc_materialize.materialize_version(
                str(data_dir), MODEL_ID, "v9", _settings(data_dir)
            )

    def test_lru_evicts_oldest_beyond_cap(self, data_dir: Path):
        from app import ifc_materialize

        settings = _settings(data_dir)
        src = data_dir / "src.ifc"
        for i in range(1, 7):
            src.write_text(f"IFC:p{i}")
            script_versions.save(
                str(data_dir), MODEL_ID, _script(f"m{i}"), str(src)
            )
        _, _, cache = _dirs(data_dir)
        # v1..v5 走缓存（v6 快照仍在）；按序物化并显式固化 mtime 顺序
        paths = []
        for i in range(1, 6):
            p = Path(
                ifc_materialize.materialize_version(
                    str(data_dir), MODEL_ID, f"v{i}", settings
                )
            )
            os.utime(p, (1_000_000 + i, 1_000_000 + i))
            paths.append(p)
        cached = sorted(p.name for p in cache.glob("v*.ifc"))
        assert cached == ["v2.ifc", "v3.ifc", "v4.ifc", "v5.ifc"]
        assert not (cache / "v1.ifc").exists()  # 最旧被淘汰
        # 淘汰后 v1 仍可再重建（可重建性不因淘汰丢失）
        path = ifc_materialize.materialize_version(
            str(data_dir), MODEL_ID, "v1", settings
        )
        assert Path(path).read_text() == "IFC:m1"


class TestDiffRebuild:
    def test_diff_old_version_rebuilds_from_script(
        self, client: TestClient, data_dir: Path
    ):
        _put_and_save(client, REAL_IFC_SCRIPT)
        _put_and_save(client, REAL_IFC_SCRIPT.replace("lazy-v1", "lazy-v2"))

        _, versions_dir, cache = _dirs(data_dir)
        assert not (versions_dir / "v1.ifc").exists()

        r = client.post(
            f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["added"] == [] and payload["removed"] == []
        assert payload["changed"]  # name 参数变了 → 语义 diff 非空
        assert (cache / "v1.ifc").is_file()
        # diff 结果缓存照常落在 versions/ 下
        assert (versions_dir / "diff-v1-v2.json").is_file()

    def test_diff_rebuild_target_current(
        self, client: TestClient, data_dir: Path
    ):
        _put_and_save(client, REAL_IFC_SCRIPT)
        _put_and_save(client, REAL_IFC_SCRIPT)
        _, versions_dir, _ = _dirs(data_dir)
        assert not (versions_dir / "v1.ifc").exists()
        r = client.post(
            f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "current"}
        )
        assert r.status_code == 200, r.text
        assert r.json() == {
            "base": "v1", "target": "current", **EMPTY_DIFF
        }

    def test_diff_404_when_no_snapshot_and_no_script(self, client: TestClient):
        _put_and_save(client, REAL_IFC_SCRIPT)
        for body in ({"base": "v9", "target": "v1"}, {"base": "v1", "target": "v9"}):
            r = client.post(f"/models/{MODEL_ID}/diff", json=body)
            assert r.status_code == 404, body

    def test_diff_rebuild_failure_returns_422(
        self, client: TestClient, data_dir: Path
    ):
        """版本存在（脚本在）但沙箱重建跑挂 → 422（非 404/500），不产出缓存。"""
        _put_and_save(client, REAL_IFC_SCRIPT)
        _put_and_save(client, REAL_IFC_SCRIPT)
        scripts, versions_dir, cache = _dirs(data_dir)
        assert not (versions_dir / "v1.ifc").exists()
        # 篡改 v1 脚本：契约形态合法（过静态门）但运行时必炸
        (scripts / "v1.py").write_text(
            'PARAMS = {"a": 1}\n'
            "\n"
            "def build(params, out_path):\n"
            "    raise RuntimeError('rebuild-broken-marker')\n"
            "\n"
            'if __name__ == "__main__":\n'
            "    import sys\n"
            "    build(PARAMS, sys.argv[1])\n",
            encoding="utf-8",
        )
        r = client.post(
            f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
        )
        assert r.status_code == 422, r.text
        assert "rebuild-broken-marker" in r.json()["detail"]
        assert not (cache / "v1.ifc").exists()  # 失败不留半截缓存

    def test_concurrent_diffs_across_lru_eviction_no_500(
        self, client: TestClient, data_dir: Path
    ):
        """并发 diff 跨 ≥5 个版本触发 LRU 淘汰：物化+读取在模型锁内，无 500。

        锁本身是修复（淘汰 os.remove 与 compute_diff 打开之间的窗口被关闭）；
        本测试为并发烟雾验证，不断言特定时序。
        """
        from concurrent.futures import ThreadPoolExecutor

        for i in range(1, 7):
            _put_and_save(client, REAL_IFC_SCRIPT.replace("lazy-v1", f"lazy-v{i}"))
        _, versions_dir, _ = _dirs(data_dir)
        assert [p.name for p in versions_dir.glob("v*.ifc")] == ["v6.ifc"]

        def diff_one(base: int) -> int:
            return client.post(
                f"/models/{MODEL_ID}/diff",
                json={"base": f"v{base}", "target": "v6"},
            ).status_code

        with ThreadPoolExecutor(max_workers=5) as pool:
            codes = list(pool.map(diff_one, [1, 2, 3, 4, 5] * 2))
        assert codes == [200] * 10

    def test_rebuilt_ifc_semantically_empty_diff(
        self, client: TestClient, data_dir: Path, tmp_path: Path
    ):
        """I5 确定性：迁移期保留的原快照与重建产物语义 diff 为空（字节不等）。"""
        from app import ifc_materialize

        _put_and_save(client, REAL_IFC_SCRIPT)
        _, versions_dir, _ = _dirs(data_dir)
        original = tmp_path / "original-v1.ifc"
        shutil.copyfile(versions_dir / "v1.ifc", original)
        _put_and_save(client, REAL_IFC_SCRIPT)  # v2 save → v1.ifc 被清理
        assert not (versions_dir / "v1.ifc").exists()

        rebuilt = ifc_materialize.materialize_version(
            str(data_dir), MODEL_ID, "v1", client.app.state.settings
        )
        assert Path(rebuilt).read_bytes() != original.read_bytes()  # 头时间戳不同
        assert diffing.compute_diff(str(original), rebuilt) == EMPTY_DIFF

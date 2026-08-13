# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""DXF 存储策略（镜像 ifc test_ifc_lazy_materialize.py）：只物化最新大版本，
历史按需沙箱重建 + LRU 缓存（dxf_cache/）。

- save v{n} 成功后裁剪可重建（有 scripts/v{m}.py）的旧 versions/v{m}.dxf
  （裁剪本身是 chunk A script_versions 的职责，此处只作物化前置断言）。
- materialize_version：快照在 → 直接返回；快照缺失但脚本在 → 沙箱重跑进
  ``models/{id}/dxf_cache/v{n}.dxf``（LRU 上限 4，按 mtime 淘汰最旧）；
  两者皆无 → FileNotFoundError。
- POST /diff 对缺失快照走同一重建路径；重建产物与原快照**语义** diff 为空
  （确定性 rebuild：reset_state + 显式 XDATA key）。
"""

from __future__ import annotations

import dataclasses
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import dxf_diffing, script_versions
from app.config import load_settings

from tests.conftest import MODEL_ID

EMPTY_DIFF = {"added": [], "removed": [], "changed": []}

# 全确定性契约脚本：显式 XDATA key + reset_state（沙箱 inner runner 负责），
# 两次 run key 全同、语义 diff 为空。
REAL_DXF_SCRIPT = '''\
import sys

import ezdxf

from cad_script_lib import add_entity, write_and_validate

PARAMS = {"x": 10}

def build(params, out_path):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    add_entity(msp, "LINE", key="0:line:1", start=(0, 0), end=(params["x"], 0))
    add_entity(msp, "CIRCLE", key="0:circle:1", center=(5, 5), radius=2)
    write_and_validate(doc, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''


def _settings(data_dir: Path):
    return dataclasses.replace(load_settings(), data_dir=str(data_dir))


def _dirs(data_dir: Path) -> tuple[Path, Path, Path]:
    base = data_dir / "models" / MODEL_ID
    return base / "scripts", base / "versions", base / "dxf_cache"


def _put_and_save(client: TestClient, script: str) -> str:
    r = client.put(f"/models/{MODEL_ID}/script", json={"script": script})
    assert r.status_code == 200, r.text
    r = client.post(f"/models/{MODEL_ID}/script/save")
    assert r.status_code == 200, r.text
    return r.json()["version"]


class TestMaterializeVersion:
    def test_returns_existing_snapshot_without_rebuild(
        self, data_dir: Path, dxf_path: Path
    ):
        from app import dxf_materialize

        settings = _settings(data_dir)
        script_versions.save(str(data_dir), MODEL_ID, REAL_DXF_SCRIPT, str(dxf_path))
        path = dxf_materialize.materialize_version(
            str(data_dir), MODEL_ID, "v1", settings
        )
        assert path == str(data_dir / "models" / MODEL_ID / "versions" / "v1.dxf")
        _, _, cache = _dirs(data_dir)
        assert not cache.exists()

    def test_rebuilds_from_script_into_cache(self, data_dir: Path, dxf_path: Path):
        from app import dxf_materialize

        settings = _settings(data_dir)
        script_versions.save(str(data_dir), MODEL_ID, REAL_DXF_SCRIPT, str(dxf_path))
        script_versions.save(str(data_dir), MODEL_ID, REAL_DXF_SCRIPT, str(dxf_path))

        _, versions_dir, cache = _dirs(data_dir)
        assert not (versions_dir / "v1.dxf").exists()  # 已被 save 裁剪
        path = dxf_materialize.materialize_version(
            str(data_dir), MODEL_ID, "v1", settings
        )
        assert path == str(cache / "v1.dxf")
        assert Path(path).is_file()
        # 重建产物可被 diff 消费：与物化源（同一脚本产物）语义 diff 为空
        assert dxf_diffing.compute_diff(str(dxf_path), path) == EMPTY_DIFF

    def test_cache_hit_does_not_rerun(self, data_dir: Path, dxf_path: Path):
        from app import dxf_materialize

        settings = _settings(data_dir)
        script_versions.save(str(data_dir), MODEL_ID, REAL_DXF_SCRIPT, str(dxf_path))
        script_versions.save(str(data_dir), MODEL_ID, REAL_DXF_SCRIPT, str(dxf_path))

        path = Path(
            dxf_materialize.materialize_version(str(data_dir), MODEL_ID, "v1", settings)
        )
        # 哨兵：命中缓存必须原样返回，不得重跑覆盖
        original = path.read_bytes()
        path.write_bytes(b"sentinel-cached")
        again = dxf_materialize.materialize_version(
            str(data_dir), MODEL_ID, "v1", settings
        )
        assert again == str(path)
        assert path.read_bytes() == b"sentinel-cached"
        assert original != b"sentinel-cached"

    def test_missing_snapshot_and_script_raises(self, data_dir: Path):
        from app import dxf_materialize

        with pytest.raises(FileNotFoundError):
            dxf_materialize.materialize_version(
                str(data_dir), MODEL_ID, "v9", _settings(data_dir)
            )

    def test_lru_evicts_oldest_beyond_cap(self, data_dir: Path, dxf_path: Path):
        from app import dxf_materialize

        settings = _settings(data_dir)
        for _ in range(6):
            script_versions.save(
                str(data_dir), MODEL_ID, REAL_DXF_SCRIPT, str(dxf_path)
            )
        _, _, cache = _dirs(data_dir)
        # v1..v5 走缓存（v6 快照仍在）；按序物化并显式固化 mtime 顺序
        for i in range(1, 6):
            p = Path(
                dxf_materialize.materialize_version(
                    str(data_dir), MODEL_ID, f"v{i}", settings
                )
            )
            os.utime(p, (1_000_000 + i, 1_000_000 + i))
        cached = sorted(p.name for p in cache.glob("v*.dxf"))
        assert cached == ["v2.dxf", "v3.dxf", "v4.dxf", "v5.dxf"]
        assert not (cache / "v1.dxf").exists()  # 最旧被淘汰
        # 淘汰后 v1 仍可再重建（可重建性不因淘汰丢失）
        path = dxf_materialize.materialize_version(
            str(data_dir), MODEL_ID, "v1", settings
        )
        assert dxf_diffing.compute_diff(str(dxf_path), path) == EMPTY_DIFF


class TestDiffRebuild:
    def test_diff_old_version_rebuilds_from_script(
        self, client: TestClient, data_dir: Path
    ):
        _put_and_save(client, REAL_DXF_SCRIPT)
        _put_and_save(client, REAL_DXF_SCRIPT.replace('"x": 10', '"x": 20'))

        _, versions_dir, cache = _dirs(data_dir)
        assert not (versions_dir / "v1.dxf").exists()

        r = client.post(
            f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["added"] == [] and payload["removed"] == []
        assert payload["changed"]  # x 参数变了 → 语义 diff 非空
        assert (cache / "v1.dxf").is_file()
        # diff 结果缓存照常落在 versions/ 下
        assert (versions_dir / "diff-v1-v2.json").is_file()

    def test_diff_rebuild_target_current(
        self, client: TestClient, data_dir: Path
    ):
        _put_and_save(client, REAL_DXF_SCRIPT)
        _put_and_save(client, REAL_DXF_SCRIPT)
        _, versions_dir, _ = _dirs(data_dir)
        assert not (versions_dir / "v1.dxf").exists()
        r = client.post(
            f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "current"}
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"base": "v1", "target": "current", **EMPTY_DIFF}

    def test_diff_404_when_no_snapshot_and_no_script(self, client: TestClient):
        _put_and_save(client, REAL_DXF_SCRIPT)
        for body in ({"base": "v9", "target": "v1"}, {"base": "v1", "target": "v9"}):
            r = client.post(f"/models/{MODEL_ID}/diff", json=body)
            assert r.status_code == 404, body

    def test_diff_rebuild_failure_returns_422(
        self, client: TestClient, data_dir: Path
    ):
        """版本存在（脚本在）但沙箱重建跑挂 → 422（非 404/500），不产出缓存。"""
        _put_and_save(client, REAL_DXF_SCRIPT)
        _put_and_save(client, REAL_DXF_SCRIPT)
        scripts, versions_dir, cache = _dirs(data_dir)
        assert not (versions_dir / "v1.dxf").exists()
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
        assert not (cache / "v1.dxf").exists()  # 失败不留半截缓存

    def test_concurrent_diffs_across_lru_eviction_no_500(
        self, client: TestClient, data_dir: Path
    ):
        """并发 diff 跨 ≥5 个版本触发 LRU 淘汰：物化+读取在模型锁内，无 500。

        并发烟雾验证，不断言特定时序（镜像 ifc 同款）。
        """
        # 诊断（W-0036）：不把服务端异常就地抛出，统一走状态码 + 响应体 dump。
        client.raise_server_exceptions = False
        for i in range(1, 7):
            _put_and_save(
                client, REAL_DXF_SCRIPT.replace('"x": 10', f'"x": {10 * i}')
            )
        _, versions_dir, _ = _dirs(data_dir)
        assert [p.name for p in versions_dir.glob("v*.dxf")] == ["v6.dxf"]

        def diff_one(base: int) -> tuple[int, str]:
            resp = client.post(
                f"/models/{MODEL_ID}/diff",
                json={"base": f"v{base}", "target": "v6"},
            )
            return resp.status_code, resp.text

        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(diff_one, [1, 2, 3, 4, 5] * 2))
        codes = [code for code, _ in results]
        # 诊断（W-0036 方案 1）：失败时 dump 每个请求的状态码 + 响应体，
        # 让低频竞态的下一次失败自解释（状态码分布 + 服务端 detail）。
        assert codes == [200] * 10, (
            "concurrent diff failures: "
            + repr([(i, code, body) for i, (code, body) in enumerate(results) if code != 200])
            + f"; all codes={codes}"
        )

    def test_rebuilt_dxf_semantically_empty_diff(
        self, client: TestClient, data_dir: Path, tmp_path: Path
    ):
        """确定性：被裁剪前的原快照与重建产物语义 diff 为空。"""
        from app import dxf_materialize

        _put_and_save(client, REAL_DXF_SCRIPT)
        _, versions_dir, _ = _dirs(data_dir)
        original = tmp_path / "original-v1.dxf"
        shutil.copyfile(versions_dir / "v1.dxf", original)
        _put_and_save(client, REAL_DXF_SCRIPT)  # v2 save → v1.dxf 被裁剪
        assert not (versions_dir / "v1.dxf").exists()

        rebuilt = dxf_materialize.materialize_version(
            str(data_dir), MODEL_ID, "v1", client.app.state.settings
        )
        assert dxf_diffing.compute_diff(str(original), rebuilt) == EMPTY_DIFF

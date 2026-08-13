# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""POST /models/{id}/diff endpoint tests (semantic entity diff, mirrors ifc test_diff.py).

版本对经两次 script/save 造出（save 会裁剪旧物化快照，v1 走 dxf_cache 重建——
物化语义本身的覆盖在 test_dxf_lazy_materialize.py）。异步纪律：超时/worker 测试
只用条件等待（event + deadline 轮询），禁止固定 sleep。
"""

from __future__ import annotations

import json
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import dxf_diffing, route_common, routes_diff
from app.main import create_app

from tests.conftest import MODEL_ID

DIFF_SCRIPT_V1 = '''\
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

DIFF_SCRIPT_V2 = DIFF_SCRIPT_V1.replace(
    "end=(params[\"x\"], 0)", "end=(params[\"x\"], params[\"x\"])"
)

DIFF_SCRIPT_V3 = DIFF_SCRIPT_V2.replace(
    'add_entity(msp, "CIRCLE", key="0:circle:1", center=(5, 5), radius=2)',
    'add_entity(msp, "CIRCLE", key="0:circle:1", center=(5, 5), radius=2)\n'
    '    add_entity(msp, "LINE", key="0:line:2", start=(0, 1), end=(1, 1))',
)


def _versions_dir(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "versions"


def _put_and_save(client: TestClient, script: str) -> str:
    r = client.put(f"/models/{MODEL_ID}/script", json={"script": script})
    assert r.status_code == 200, r.text
    r = client.post(f"/models/{MODEL_ID}/script/save")
    assert r.status_code == 200, r.text
    return r.json()["version"]


def test_diff_changed_fields(client: TestClient, data_dir: Path) -> None:
    assert _put_and_save(client, DIFF_SCRIPT_V1) == "v1"
    assert _put_and_save(client, DIFF_SCRIPT_V2) == "v2"

    resp = client.post(f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"})
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["base"] == "v1"
    assert payload["target"] == "v2"
    assert payload["added"] == []
    assert payload["removed"] == []
    changed = {c["key"]: c["changes"] for c in payload["changed"]}
    assert set(changed) == {"0:line:1"}
    fields = {c["field"] for c in changed["0:line:1"]}
    assert fields == {"end"}


def test_diff_added_and_removed_by_key(client: TestClient) -> None:
    _put_and_save(client, DIFF_SCRIPT_V1)
    _put_and_save(client, DIFF_SCRIPT_V3)

    payload = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
    ).json()
    assert payload["added"] == ["0:line:2"]
    assert payload["removed"] == []


def test_diff_target_current_and_no_cache(client: TestClient, data_dir: Path) -> None:
    _put_and_save(client, DIFF_SCRIPT_V1)
    r = client.put(f"/models/{MODEL_ID}/script", json={"script": DIFF_SCRIPT_V2})
    assert r.status_code == 200, r.text
    r = client.post(f"/models/{MODEL_ID}/script/run")
    assert r.status_code == 200, r.text

    resp = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "current"}
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["target"] == "current"
    assert "0:line:1" in {c["key"] for c in payload["changed"]}
    assert not (_versions_dir(data_dir) / "diff-v1-current.json").exists()


def test_diff_result_cached(client: TestClient, data_dir: Path) -> None:
    _put_and_save(client, DIFF_SCRIPT_V1)
    _put_and_save(client, DIFF_SCRIPT_V2)
    first = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
    ).json()
    cache_file = _versions_dir(data_dir) / "diff-v1-v2.json"
    assert cache_file.is_file()
    assert json.loads(cache_file.read_text(encoding="utf-8")) == first

    cached = json.loads(cache_file.read_text(encoding="utf-8"))
    cached["added"] = ["sentinel-from-cache"]
    cache_file.write_text(json.dumps(cached), encoding="utf-8")
    second = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
    ).json()
    assert second["added"] == ["sentinel-from-cache"]
    assert second["changed"] == first["changed"]


def test_diff_unknown_version_returns_404(client: TestClient) -> None:
    _put_and_save(client, DIFF_SCRIPT_V1)
    for body in ({"base": "v9", "target": "v1"}, {"base": "v1", "target": "v9"}):
        resp = client.post(f"/models/{MODEL_ID}/diff", json=body)
        assert resp.status_code == 404, body


def test_concurrent_same_pair_diff_cache_publish_no_500(
    client: TestClient, data_dir: Path, dxf_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """同 (base,target) 并发 diff 双双未命中结果缓存：发布不得共享 tmp 名（W-0036）。

    修复前两个 handler 写同一 ``diff-{base}-{target}.json.tmp``：一方
    ``os.replace`` 把 tmp 改名后，另一方的 ``os.replace`` 必抛
    FileNotFoundError → 500。用 barrier 确定性排出该交错：两写者都写完
    tmp 后才放行 → 并发 replace（compute 段被模型锁串行，无法也不需要
    对齐——只要 B 的结果缓存检查先于 A 的发布，而发布被 dump barrier
    挡住等 B，时序即被锁死）。全程条件等待，无固定 sleep。
    """
    # 直接落两个快照（绕开沙箱/物化），只演练 diff 结果缓存的发布路径
    versions_dir = _versions_dir(data_dir)
    versions_dir.mkdir(parents=True)
    shutil.copy(dxf_path, versions_dir / "v1.dxf")
    shutil.copy(dxf_path, versions_dir / "v2.dxf")

    empty_diff = {"added": [], "removed": [], "changed": []}

    real_dump = json.dump
    dump_barrier = threading.Barrier(2)

    def _rendezvous_dump(obj: object, fh: object, **kwargs: object) -> None:
        real_dump(obj, fh, **kwargs)
        dump_barrier.wait(10)  # 两写者都写完 tmp 后才放行 → 并发 os.replace

    monkeypatch.setattr(routes_diff.json, "dump", _rendezvous_dump)
    # 不把服务端异常就地抛出，统一走状态码断言
    client.raise_server_exceptions = False

    def diff_one(_: int) -> tuple[int, str]:
        resp = client.post(
            f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
        )
        return resp.status_code, resp.text

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(diff_one, range(2)))
    codes = [code for code, _ in results]
    assert codes == [200, 200], f"concurrent same-pair diff failures: {results!r}"
    # 结果缓存完整可读，且无残留 tmp 文件
    cache_file = versions_dir / "diff-v1-v2.json"
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    assert payload == {"base": "v1", "target": "v2", **empty_diff}
    assert [p.name for p in versions_dir.glob("diff-v1-v2.json*")] == [
        "diff-v1-v2.json"
    ]


def test_diff_without_any_commit_returns_404(client: TestClient) -> None:
    resp = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "current"}
    )
    assert resp.status_code == 404


def test_diff_missing_params_returns_422(client: TestClient) -> None:
    assert client.post(f"/models/{MODEL_ID}/diff", json={}).status_code == 422
    assert (
        client.post(f"/models/{MODEL_ID}/diff", json={"base": "v1"}).status_code
        == 422
    )


def test_diff_bad_model_id_returns_422(client: TestClient) -> None:
    assert (
        client.post(
            "/models/not_a_valid_id/diff", json={"base": "v1", "target": "v2"}
        ).status_code
        == 422
    )


def test_diff_missing_model_returns_404(client: TestClient) -> None:
    resp = client.post(
        "/models/m_ffffffffffffffff/diff", json={"base": "v1", "target": "v2"}
    )
    assert resp.status_code == 404


def test_diff_compute_timeout_returns_504(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """compute_diff 阻塞超过 CAD_SERVICE_DIFF_TIMEOUT_S → 504，而非挂住 handler。"""
    done = threading.Event()

    def _blocking_diff(*args: object, **kwargs: object) -> dict:
        done.wait(10)
        return {}

    monkeypatch.setattr(dxf_diffing, "compute_diff", _blocking_diff)
    monkeypatch.setenv("VIEWER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("CAD_SERVICE_DIFF_TIMEOUT_S", "1")
    client = TestClient(create_app())
    try:
        _put_and_save(client, DIFF_SCRIPT_V1)
        _put_and_save(client, DIFF_SCRIPT_V2)

        start = time.monotonic()
        resp = client.post(
            f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
        )
        elapsed = time.monotonic() - start

        assert resp.status_code == 504
        assert resp.json()["detail"] == "diff timed out"
        assert elapsed < 8  # 未等残余 worker 跑完就返回
        assert not (_versions_dir(data_dir) / "diff-v1-v2.json").exists()
    finally:
        done.set()  # 放行残余 worker，避免泄漏进后续测试的执行器


def test_timeout_abandoned_worker_serializes_next_diff(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """504 后残余 worker 仍持模型锁：同模型下一次 diff 排队而非并发计算、无 500。

    回归语义镜像 ifc B4：超时返回后锁不得随 handler 释放——下一次请求的 worker
    必须等在残余 worker 后面，max_active 恒为 1。全程条件等待（event + 带 deadline
    轮询），无固定 sleep（AGENTS 纪律 5）。
    """
    active = 0
    max_active = 0
    entered = threading.Event()
    release = threading.Event()
    state_lock = threading.Lock()

    def _blocking_diff(*args: object, **kwargs: object) -> dict:
        nonlocal active, max_active
        with state_lock:
            active += 1
            max_active = max(max_active, active)
        entered.set()
        release.wait(15)  # 阻塞直到测试放行，模拟超时后残余 worker 仍占锁计算
        with state_lock:
            active -= 1
        return {}

    # model_lock 获取尝试计数：第二次尝试即「下一请求 worker 已排队等锁」的可观测条件
    real_model_lock = route_common.model_lock
    attempts = 0
    attempts_lock = threading.Lock()
    second_attempted = threading.Event()

    def _spy_model_lock(model_id: str) -> threading.RLock:
        nonlocal attempts
        with attempts_lock:
            attempts += 1
            if attempts >= 2:
                second_attempted.set()
        return real_model_lock(model_id)

    monkeypatch.setattr(dxf_diffing, "compute_diff", _blocking_diff)
    monkeypatch.setattr(routes_diff, "model_lock", _spy_model_lock)
    monkeypatch.setenv("VIEWER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("CAD_SERVICE_DIFF_TIMEOUT_S", "1")
    client = TestClient(create_app())
    _put_and_save(client, DIFF_SCRIPT_V1)
    _put_and_save(client, DIFF_SCRIPT_V2)

    try:
        first = client.post(
            f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
        )
        assert first.status_code == 504
        assert entered.wait(5)  # 残余 worker 已进入 compute_diff 并持有锁

        with ThreadPoolExecutor(max_workers=1) as pool:
            second = pool.submit(
                client.post,
                f"/models/{MODEL_ID}/diff",
                json={"base": "v1", "target": "v2"},
            )
            # 条件等待：第二请求 worker 已尝试取锁（被残余 worker 挡住）
            assert second_attempted.wait(5)
            assert max_active == 1  # 未并发进入 compute_diff
            release.set()  # 放行残余 worker → 释放锁 → 下一请求接着跑完
            second_resp = second.result(timeout=15)
    finally:
        release.set()

    assert second_resp.status_code == 200
    assert (_versions_dir(data_dir) / "diff-v1-v2.json").exists()

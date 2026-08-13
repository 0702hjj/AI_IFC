# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Version snapshot + diff endpoint tests."""

from __future__ import annotations

import json
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import ifcopenshell
import ifcopenshell.api.root
import pytest
from fastapi.testclient import TestClient

from app import diffing, routes_diff
from app.main import create_app
from conftest import MODEL_ID

WALL_GUID = "3ZYW59sxj8lei475l7EhLU"
WALL_NAME = "Wall for Test Example"


def _versions_dir(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "versions"


def _write_rename_versions(data_dir: Path, name: str, *, update_current: bool = False) -> None:
    """Write v1 = original upload, v2 = wall renamed (snapshots written directly).

    The commit endpoint is retired (410); version fixtures are written to
    ``versions/`` by hand instead.
    """
    versions = _versions_dir(data_dir)
    versions.mkdir(parents=True, exist_ok=True)
    uploads = data_dir / "uploads" / f"{MODEL_ID}.ifc"
    shutil.copy(uploads, versions / "v1.ifc")
    model = ifcopenshell.open(str(uploads))
    model.by_guid(WALL_GUID).Name = name
    model.write(str(versions / "v2.ifc"))
    if update_current:
        model.write(str(uploads))


def test_get_versions_lists_snapshots_and_current(client: TestClient, data_dir: Path) -> None:
    resp = client.get(f"/models/{MODEL_ID}/versions")
    assert resp.status_code == 200
    assert resp.json() == {"versions": [], "current": None}

    _write_rename_versions(data_dir, "新名字")
    payload = client.get(f"/models/{MODEL_ID}/versions").json()
    assert [v["version"] for v in payload["versions"]] == ["v1", "v2"]
    assert payload["current"] == "v2"
    assert all(v["createdAt"] for v in payload["versions"])


def test_get_versions_missing_model_returns_404(client: TestClient) -> None:
    assert client.get("/models/m_ffffffffffffffff/versions").status_code == 404


def test_diff_attribute_change(client: TestClient, data_dir: Path) -> None:
    _write_rename_versions(data_dir, "新名字")
    resp = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["base"] == "v1"
    assert payload["target"] == "v2"
    assert payload["added"] == []
    assert payload["removed"] == []
    changed = {c["guid"]: c["changes"] for c in payload["changed"]}
    assert WALL_GUID in changed
    assert {c["field"] for c in changed[WALL_GUID]} == {"Name"}
    assert changed[WALL_GUID] == [
        {"field": "Name", "old": WALL_NAME, "new": "新名字"}
    ]


def _write_versions_with_added_and_removed(data_dir: Path) -> tuple[str, str]:
    """v1 = original + extra wall; v2 = original + different extra wall."""
    versions = _versions_dir(data_dir)
    versions.mkdir(parents=True)
    uploads = data_dir / "uploads" / f"{MODEL_ID}.ifc"

    model = ifcopenshell.open(str(uploads))
    wall_v1 = ifcopenshell.api.root.create_entity(
        model, ifc_class="IfcWall", name="Only in v1"
    )
    model.write(str(versions / "v1.ifc"))

    model = ifcopenshell.open(str(uploads))
    wall_v2 = ifcopenshell.api.root.create_entity(
        model, ifc_class="IfcWall", name="Only in v2"
    )
    model.write(str(versions / "v2.ifc"))
    return wall_v1.GlobalId, wall_v2.GlobalId


def test_diff_added_and_removed_by_guid(client: TestClient, data_dir: Path) -> None:
    removed_guid, added_guid = _write_versions_with_added_and_removed(data_dir)
    resp = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["added"] == [added_guid]
    assert payload["removed"] == [removed_guid]


def test_diff_excludes_geometry_noise(client: TestClient, data_dir: Path) -> None:
    _write_rename_versions(data_dir, "新名字")
    payload = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
    ).json()
    for entry in payload["changed"]:
        for change in entry["changes"]:
            assert "Representation" not in change["field"]
            assert "Geometry" not in change["field"]
            assert "ObjectPlacement" not in change["field"]


def test_diff_target_current_and_no_cache(client: TestClient, data_dir: Path) -> None:
    _write_rename_versions(data_dir, "新名字", update_current=True)
    resp = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "current"}
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["target"] == "current"
    assert WALL_GUID in {c["guid"] for c in payload["changed"]}
    assert not (_versions_dir(data_dir) / "diff-v1-current.json").exists()


def test_diff_result_cached(client: TestClient, data_dir: Path) -> None:
    _write_rename_versions(data_dir, "新名字")
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


def test_diff_unknown_version_returns_404(client: TestClient, data_dir: Path) -> None:
    _write_rename_versions(data_dir, "新名字")
    for body in ({"base": "v9", "target": "v2"}, {"base": "v1", "target": "v9"}):
        resp = client.post(f"/models/{MODEL_ID}/diff", json=body)
        assert resp.status_code == 404, body


def test_concurrent_same_pair_diff_cache_publish_no_500(
    client: TestClient, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """同 (base,target) 并发 diff 双双未命中结果缓存：发布不得共享 tmp 名（W-0037）。

    修复前两个 handler 写同一 ``diff-{base}-{target}.json.tmp``：一方
    ``os.replace`` 把 tmp 改名后，另一方的 ``os.replace`` 必抛
    FileNotFoundError → 500。用 barrier 确定性排出该交错：两写者都写完
    tmp 后才放行 → 并发 replace（compute 段被模型锁串行，无法也不需要
    对齐——只要 B 的结果缓存检查先于 A 的发布，而发布被 dump barrier
    挡住等 B，时序即被锁死）。全程条件等待，无固定 sleep。
    镜像 services/cad 的 W-0036 修复（commit 0f12428）。
    """
    # 直接落两个相同快照（绕开沙箱/物化），只演练 diff 结果缓存的发布路径
    versions_dir = _versions_dir(data_dir)
    versions_dir.mkdir(parents=True)
    uploads = data_dir / "uploads" / f"{MODEL_ID}.ifc"
    shutil.copy(uploads, versions_dir / "v1.ifc")
    shutil.copy(uploads, versions_dir / "v2.ifc")

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
        client.post("/models/not_a_valid_id/diff", json={"base": "v1", "target": "v2"}).status_code
        == 422
    )
    assert client.get("/models/not_a_valid_id/versions").status_code == 422


def test_diff_missing_model_returns_404(client: TestClient) -> None:
    resp = client.post(
        "/models/m_ffffffffffffffff/diff", json={"base": "v1", "target": "v2"}
    )
    assert resp.status_code == 404


def test_diff_compute_timeout_returns_504(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """compute_diff 阻塞超过 DIFF_TIMEOUT_S → 504，而不是无限挂住 handler 线程。"""
    _write_rename_versions(data_dir, "新名字")

    def _blocking_diff(*args: object, **kwargs: object) -> dict:
        time.sleep(5)
        return {}

    monkeypatch.setattr(diffing, "compute_diff", _blocking_diff)
    monkeypatch.setenv("VIEWER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("EDIT_SERVICE_DIFF_TIMEOUT_S", "1")
    client = TestClient(create_app())

    start = time.monotonic()
    resp = client.post(
        f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
    )
    elapsed = time.monotonic() - start

    assert resp.status_code == 504
    assert resp.json()["detail"] == "diff timed out"
    assert elapsed < 4  # 未等阻塞的 compute_diff 跑完（5s）就返回
    assert not (_versions_dir(data_dir) / "diff-v1-v2.json").exists()


def test_timeout_abandoned_worker_serializes_next_diff(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """504 后残余 worker 仍持模型锁：同模型下一次 diff 排队而非并发计算、无 500。

    回归 B4 修复（并发 500）：超时返回后锁不得随 handler 释放——下一次请求的
    worker 必须等在残余 worker 后面，max_active 恒为 1。
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor

    _write_rename_versions(data_dir, "新名字")

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
        release.wait(10)  # 阻塞直到测试放行，模拟超时后残余 worker 仍占锁计算
        with state_lock:
            active -= 1
        return {}

    monkeypatch.setattr(diffing, "compute_diff", _blocking_diff)
    monkeypatch.setenv("VIEWER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("EDIT_SERVICE_DIFF_TIMEOUT_S", "1")
    client = TestClient(create_app())

    first = client.post(f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"})
    assert first.status_code == 504
    assert entered.wait(5)  # 残余 worker 已进入 compute_diff 并持有锁

    with ThreadPoolExecutor(max_workers=1) as pool:
        second = pool.submit(
            client.post, f"/models/{MODEL_ID}/diff", json={"base": "v1", "target": "v2"}
        )
        time.sleep(0.3)  # 让第二次请求进入执行器并尝试取锁
        assert max_active == 1  # 被残余 worker 的锁挡住，未并发进入 compute_diff
        release.set()  # 放行残余 worker → 释放锁 → 下一次请求接着跑完
        second_resp = second.result(timeout=10)

    assert second_resp.status_code == 200
    assert (_versions_dir(data_dir) / "diff-v1-v2.json").exists()

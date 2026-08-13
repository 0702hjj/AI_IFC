# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Version listing and model diff endpoints.

``GET .../versions`` lists the immutable commit snapshots; ``POST .../diff``
compares two snapshots (or a snapshot against the current upload state) and
returns the flat GlobalId-keyed schema consumed by the web Diff Viewer.

Diff results between two immutable snapshots are cached next to them at
``versions/diff-{base}-{target}.json``. Diffs against ``target="current"``
are never cached: the uploads file is mutable, so there is no stable cache
key.

Historical big versions keep no materialized IFC (spec §5.5): a missing
snapshot with a surviving script is rebuilt on demand into the LRU cache
(``ifc_materialize.materialize_version``); with neither it is a 404.
The per-model lock (shared with script/entity edits) is acquired by the
executor worker itself, covering rebuild + diff read: the LRU eviction's
``os.remove`` can never race a resolved cache path that ``compute_diff``
has not opened yet, nor the cache-hit ``utime``. Holding it in the worker
(not the handler) also means a 504 timeout does not release it: the
abandoned worker finishes under the lock, so the next request serializes
behind it instead of reopening the concurrent-write window.
"""

from __future__ import annotations

import atexit
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, Callable, Dict

from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import BaseModel

from . import diffing, ifc_materialize, versions
from .config import Settings
from .route_common import MODEL_ID_PATTERN, model_lock, model_upload_path

router = APIRouter()

# diff 计算（ifcopenshell/ifcdiff + 沙箱重建）是 CPU 密集，阻塞在 sync handler 的
# 线程里会占死 FastAPI threadpool。用独立线程池执行，handler 侧 future.result(timeout)
# 超时即返回 504；残余 worker 继续跑完（per-model 锁由 worker 持有，见模块 docstring），
# handler 不等待也不释放锁。
_DIFF_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="diff")
atexit.register(_DIFF_EXECUTOR.shutdown, wait=False)


class DiffBody(BaseModel):
    """Body of POST /models/{id}/diff. target also accepts "current"."""

    base: str
    target: str


def _version_or_404(
    settings: Settings, data_dir: str, model_id: str, version: str
) -> str:
    """Snapshot path, rebuilding from the version's script when pruned (I5)."""
    try:
        return ifc_materialize.materialize_version(data_dir, model_id, version, settings)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"version not found: {version}")


def _run_diff_with_timeout(settings: Settings, compute: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    """Run diff compute in the executor; 504 when it exceeds DIFF_TIMEOUT_S.

    残余线程继续跑完是接受语义（B4）：worker 全程持有 per-model 锁（见 post_diff），
    超时返回 504 后残余 worker 仍在锁内安全完成物化/读取，不会重开并发写窗口；
    handler 不因它继续占用而阻塞返回，丢弃的只是 CPU 时间。

    饱和降级态（接受）：executor max_workers=2 时，两个超时 diff 各占一个 worker
    直至跑完；排队中的后续 diff 在 future.result(timeout) 内等不到空闲 worker
    → 必然 504，调用方应把 504 当「diff 未完成」重试。
    """
    future = _DIFF_EXECUTOR.submit(compute)
    try:
        return future.result(timeout=settings.diff_timeout_s)
    except FutureTimeoutError:
        raise HTTPException(status_code=504, detail="diff timed out")


@router.get("/models/{id}/versions")
def get_versions(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """List version snapshots for a model (empty + current=null before any commit)."""
    model_upload_path(request, id)
    data_dir = request.app.state.settings.data_dir
    listed = versions.list_versions(data_dir, id)
    return {
        "versions": listed,
        "current": listed[-1]["version"] if listed else None,
    }


@router.post("/models/{id}/diff")
def post_diff(
    request: Request, body: DiffBody, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Diff two model versions (or base version vs the current upload state)."""
    current_path = model_upload_path(request, id)
    settings = request.app.state.settings
    data_dir = settings.data_dir

    cache_path = None
    if body.target != "current":
        cache_path = os.path.join(
            versions.versions_dir(data_dir, id), f"diff-{body.base}-{body.target}.json"
        )
        if os.path.isfile(cache_path):
            with open(cache_path, "r", encoding="utf-8") as fh:
                return json.load(fh)

    # 锁由 executor worker 持有（acquire/release 同在 worker 线程，RLock 语义合法）：
    # 覆盖物化+读取全程。超时返回 504 也不释放锁——残余 worker 继续锁内跑完，下一个
    # 请求的 worker 排队等锁 → 同模型并发物化/读写窗口关闭（曾可并发 500）。
    def _compute_payload() -> Dict[str, Any]:
        with model_lock(request, id):
            # 快照重建 + compute_diff 整体包进超时：materialize_version 也可能触发
            # 沙箱重跑脚本（CPU 密集），同样受 DIFF_TIMEOUT_S 约束。
            base_path = _version_or_404(settings, data_dir, id, body.base)
            if body.target == "current":
                target_path = current_path
            else:
                target_path = _version_or_404(settings, data_dir, id, body.target)
            return {
                "base": body.base,
                "target": body.target,
                **diffing.compute_diff(base_path, target_path),
            }

    payload = _run_diff_with_timeout(settings, _compute_payload)

    if cache_path is not None:
        # tmp 名必须按写者唯一：同 (base,target) 的并发请求都未命中结果缓存时，
        # 计算虽被模型锁串行，发布段却在锁外——共享 tmp 名会让一方的 os.replace
        # 把另一方在写的 tmp 改名，第二个 replace 抛 FileNotFoundError → 500
        # （W-0037，镜像 services/cad 的 W-0036 修复）。唯一 tmp + replace
        # 后者覆盖前者，两次发布同 payload 等价。
        tmp = f"{cache_path}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, cache_path)
    return payload

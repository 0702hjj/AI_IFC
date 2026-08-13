# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Script-as-source endpoints: WPS-style staging + sandboxed run + big versions.

The build script is the single source of truth for generated DXF models:

- ``PUT /models/{id}/script`` — stage a script edit (full replace, or
  params-only via ``{"params": {...}}`` which rewrites the PARAMS block
  server-side). Undo/redo buffer, 10 steps.
- ``GET  /models/{id}/script`` — current staged script (or last saved base).
  404 for upload-only models with no script.
- ``GET  /models/{id}/script/params`` — ast-extracted PARAMS (form feed).
- ``POST /models/{id}/script/undo|redo|discard`` — WPS-style navigation.
- ``POST /models/{id}/script/run`` — sandbox-run the staged script and
  atomically replace ``uploads/{id}.dxf`` + publish
  ``models/{id}/current.map.json`` (no version).
- ``POST /models/{id}/script/save`` — sandbox-run, then snapshot
  ``scripts/v{n}.py`` + ``versions/v{n}.dxf`` (atomic, lockstep). A failed
  run → 422 and no version. The response carries no ``alignment`` field
  (chunk A decision; bootstrap diff counts are not computed).
- ``GET  /models/{id}/scripts`` — list big versions (scripts + snapshots).
- ``POST /models/{id}/script/rollback`` — restore a big version's script
  into staging, re-run it into uploads.
- ``POST /models/{id}/script/diff`` — unified text diff + PARAMS changes
  between two big versions (script text diff is chunk A; the *entity-level
  semantic* diff engine is chunk B).
- ``GET  /models/{id}/script/staging/diff`` — small-version diff between
  two staging steps.
- ``GET  /models/{id}/versions`` — materialized DXF snapshot listing.

- ``GET  /models/{id}/script/locate?key=`` — XDATA key → CallSite
  (line/col/snippet/origin/params_keys)；staging 与 map 分叉 → 200 降级
  ``{"found": false, "stale": true}``（绝不跳错误行）。
- ``POST /models/{id}/script/edit-call`` — libcst 标量改写定位到的调用点
  实参，沙箱 run + staging.push；任何失败 422 零副作用，stale map → 409
  fail-closed，origin=traced → 422。

Chunk B (explicitly absent here): entity-level semantic diff.

All mutating endpoints hold the per-model lock. 校验隔离：所有
``raise HTTPException`` 住在 verify* 函数（route_common.py 豁免），
由 tests/test_verify_isolation.py 机器强制（空白名单）。
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field

from . import (
    render,
    script_diff,
    script_edit,
    script_params,
    script_runner,
    script_staging,
    script_versions,
    versions,
)

from .route_common import MODEL_ID_PATTERN, model_lock, model_upload_path

logger = logging.getLogger(__name__)

router = APIRouter()

VERSION_NAME_PATTERN = r"^v\d+$"


class ScriptBody(BaseModel):
    """Body of PUT /models/{id}/script: exactly one of script / params."""

    script: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    note: str = ""


class SaveBody(BaseModel):
    """Optional body of POST /models/{id}/script/save."""

    note: str = ""


class RollbackBody(BaseModel):
    """Body of POST /models/{id}/script/rollback."""

    version: str = Field(..., pattern=VERSION_NAME_PATTERN)


class ScriptDiffBody(BaseModel):
    """Body of POST /models/{id}/script/diff: two big versions."""

    base: str = Field(..., pattern=VERSION_NAME_PATTERN)
    target: str = Field(..., pattern=VERSION_NAME_PATTERN)


class EditCallBody(BaseModel):
    """Body of POST /models/{id}/script/edit-call: scalar argument rewrite."""

    key: str
    argument: str
    value: Any  # 服务端强校验为标量（str/int/float/bool）


def verify_script_body(body: ScriptBody) -> None:
    """stage_script 请求规则：script / params 恰好二选一。"""
    if (body.script is None) == (body.params is None):
        raise HTTPException(
            status_code=422, detail="exactly one of script / params required"
        )


def verify_params_target(staging: script_staging.ScriptStaging) -> str:
    """params 改写前置条件：必须存在当前脚本（满足则返回它）。"""
    current = staging.current()
    if current is None:
        raise HTTPException(status_code=409, detail="no script to update params on")
    return current


def verify_params_text(
    staging: script_staging.ScriptStaging, params: Dict[str, Any]
) -> str:
    """params-only 改写：前置检查 + PARAMS 块重写，重写错误统一翻译 422。"""
    try:
        return script_params.replace_params(verify_params_target(staging), params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def verify_script_contract(request: Request, text: str) -> None:
    """脚本契约校验：validate_script_text 错误的唯一 HTTP 翻译点。"""
    errors = script_runner.validate_script_text(request.app.state.settings, text)
    if errors:
        raise HTTPException(
            status_code=422, detail="脚本契约校验失败: " + "; ".join(errors)
        )


def verify_current_script(
    staging: script_staging.ScriptStaging, status_code: int
) -> str:
    """当前脚本必须存在（读端点 404 / 写端点 409，由调用方定语义）。"""
    current = staging.current()
    if current is None:
        raise HTTPException(status_code=status_code, detail="no script for model")
    return current


def verify_extracted_params(current: str) -> Dict[str, Any]:
    """PARAMS ast 提取错误的唯一 HTTP 翻译点（422）。"""
    try:
        return script_params.extract_params(current)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def verify_undo_available(staging: script_staging.ScriptStaging) -> None:
    if not staging.can_undo():
        raise HTTPException(status_code=409, detail="nothing to undo")


def verify_redo_available(staging: script_staging.ScriptStaging) -> None:
    if not staging.can_redo():
        raise HTTPException(status_code=409, detail="nothing to redo")


def verify_script_version(data_dir: str, model_id: str, version: str) -> str:
    """大版本脚本必须存在（满足则返回脚本全文，404 的唯一翻译点）。"""
    try:
        return script_versions.load_script(data_dir, model_id, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


def verify_step_pair(
    staging: script_staging.ScriptStaging, from_: Optional[int], to: Optional[int]
) -> Tuple[int, int]:
    """staging diff 的步区间校验：至少两步（409），区间合法（422）。"""
    newest = staging.cursor
    if newest < 1:
        raise HTTPException(status_code=409, detail="fewer than two staged steps")
    i = newest - 1 if from_ is None else from_
    j = newest if to is None else to
    if not (0 <= i < j <= newest):
        raise HTTPException(
            status_code=422,
            detail=f"steps out of range: from={i} to={j} (valid 0..{newest}, from < to)",
        )
    return i, j


def verify_map_fresh(
    map_hash: Optional[str],
    entries: Optional[Dict[str, Any]],
    current: str,
    key: str,
) -> Dict[str, Any]:
    """edit-call 前置：map 缺失 → 404；staging 与 map 分叉 → 409 fail-closed。

    map 行号只对生成它的那份脚本有效，放行过期 map 会把改写落到错误的调用上。
    """
    if entries is None:
        raise HTTPException(status_code=404, detail=f"callsite not found: {key}")
    if _map_is_stale(map_hash, current):
        raise HTTPException(
            status_code=409,
            detail="staging has un-run edits; run the script before edit-call",
        )
    return entries


def verify_editable_origin(entries: Dict[str, Any], key: str) -> Dict[str, Any]:
    """callsite 必须存在且可自动改写（origin=traced → 422，提示直接改脚本）。"""
    entry = entries.get(key)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"callsite not found: {key}")
    if entry.get("origin") == "traced":
        raise HTTPException(
            status_code=422,
            detail="callsite not auto-editable (traced); edit the script directly",
        )
    return entry


def verify_rewritten_script(
    current: str, entry: Dict[str, Any], argument: str, value: Any
) -> str:
    """libcst 标量重写错误的唯一 HTTP 翻译点（422）。"""
    try:
        return script_edit.rewrite_call_argument(
            current, entry["line"], argument, value
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _staging(request: Request, model_id: str) -> script_staging.ScriptStaging:
    return request.app.state.script_staging.get(model_id)


def _bootstrap_path(request: Request, model_id: str) -> str:
    return os.path.join(
        request.app.state.settings.data_dir, "models", model_id, "bootstrap.dxf"
    )


def _preserve_bootstrap(
    request: Request, model_id: str, staging: script_staging.ScriptStaging
) -> None:
    """plain 态模型首次暂存脚本时，把上传原件原子复制为 bootstrap.dxf。

    必须发生在任何 run 覆盖 uploads 之前；已有大版本或 bootstrap 已存在则跳过
    （存量 script-backed 模型不补建）。调用方须持有模型锁。
    """
    bootstrap = _bootstrap_path(request, model_id)
    if os.path.exists(bootstrap) or staging.current() is not None:
        return
    data_dir = request.app.state.settings.data_dir
    if script_versions.list_scripts(data_dir, model_id):
        return
    uploads = os.path.join(data_dir, "uploads", f"{model_id}.dxf")
    os.makedirs(os.path.dirname(bootstrap), exist_ok=True)
    tmp = bootstrap + ".tmp"
    shutil.copyfile(uploads, tmp)
    os.replace(tmp, bootstrap)


def _staging_or_seed(request: Request, model_id: str) -> script_staging.ScriptStaging:
    """Staging for read endpoints; empty staging + existing big versions → seed
    base from the newest big version (archived models have scripts/v{n}.py but
    no staging buffer, so GET /script would otherwise 404).

    Idempotent (seed_base is a no-op once a current script exists); the seed
    mutation runs under the per-model lock with a re-check.
    """
    staging = _staging(request, model_id)
    if staging.current() is not None:
        return staging
    data_dir = request.app.state.settings.data_dir
    scripts = script_versions.list_scripts(data_dir, model_id)
    if not scripts:
        return staging
    with model_lock(model_id):
        staging = _staging(request, model_id)
        if staging.current() is None:
            latest = script_versions.load_script(
                data_dir, model_id, scripts[-1]["version"]
            )
            staging.seed_base(latest)
    return staging


def _current_map_path(request: Request, model_id: str) -> str:
    return os.path.join(
        request.app.state.settings.data_dir, "models", model_id, "current.map.json"
    )


def _read_current_map(map_path: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """读取 current.map.json 发布信封：返回 (script_hash, entries)。

    信封为 ``{"scriptHash": sha256(script), "map": {...}}``（run_script 发布）。
    文件缺失/损坏/非对象 → (None, None)；旧版裸 map（无信封）→ (None, {})，
    调用侧按过期处理（edit-call 409 / locate stale），绝不对形状变化 500。
    """
    if not os.path.isfile(map_path):
        return None, None
    try:
        with open(map_path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None, None
    if not isinstance(raw, dict):
        return None, None
    script_hash = raw.get("scriptHash")
    entries = raw.get("map")
    if not isinstance(script_hash, str) or not isinstance(entries, dict):
        return None, {}
    return script_hash, entries


def _map_is_stale(script_hash: Optional[str], current: Optional[str]) -> bool:
    """map 与 staging 当前脚本不同源（含无脚本可比对的旧版裸 map）→ 过期。"""
    if script_hash is None or current is None:
        return True
    return script_hash != script_runner.script_hash(current)


def _publish_render_json(request: Request, model_id: str, dxf_path: str) -> None:
    """run/save 后原子发布 render.json（tmp + os.replace，与 map sidecar 同纪律）。

    生成失败不阻断 run/save 主流程：记 warning 并删除旧 render.json，
    防止旧 payload 与新 uploads dxf 错位（map 侧车同纪律）。
    调用方须持有模型锁（唯一写者，tmp 名无竞争）。
    """
    dest = os.path.join(
        request.app.state.settings.data_dir, "models", model_id, "render.json"
    )
    try:
        payload = render.build_render_payload(dxf_path)
    except Exception:
        logger.warning(
            "render.json 生成失败，删除旧文件防错位: model=%s", model_id,
            exc_info=True,
        )
        if os.path.exists(dest):
            os.remove(dest)
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    os.replace(tmp, dest)


def _run_into_uploads(request: Request, model_id: str, script: str) -> str:
    """Sandbox-run script into uploads/{id}.dxf; publish the run's ScriptMap
    envelope to ``models/{id}/current.map.json``.

    Unlike services/ifc there is no ModelRegistry/PendingStore — the run is
    the only writer of the upload, so no cache invalidation is needed.
    """
    dxf_path = model_upload_path(request, model_id)
    script_runner.run_script(
        request.app.state.settings, script, dxf_path,
        map_out=_current_map_path(request, model_id),
    )
    _publish_render_json(request, model_id, dxf_path)
    return dxf_path


@router.get("/models/{id}/script")
def get_script(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Return the current script (staged state, or last saved base)."""
    model_upload_path(request, id)
    staging = _staging_or_seed(request, id)
    current = verify_current_script(staging, 404)
    return {
        "modelId": id,
        "script": current,
        "staged": staging.staged_count(),
        "canUndo": staging.can_undo(),
        "canRedo": staging.can_redo(),
        "maxSteps": script_staging.MAX_STEPS,
    }


@router.put("/models/{id}/script")
def stage_script(
    request: Request,
    body: ScriptBody,
    id: str = Path(pattern=MODEL_ID_PATTERN),
) -> Dict[str, Any]:
    """Stage a script edit: full replace, or params-only PARAMS-block rewrite."""
    model_upload_path(request, id)
    verify_script_body(body)
    with model_lock(id):
        staging = _staging(request, id)
        if body.script is not None:
            text = body.script
        else:
            text = verify_params_text(staging, body.params or {})
        verify_script_contract(request, text)
        _preserve_bootstrap(request, id, staging)
        staging.push(text)
        return {
            "modelId": id,
            "staged": staging.staged_count(),
            "canUndo": staging.can_undo(),
            "canRedo": staging.can_redo(),
        }


@router.get("/models/{id}/script/params")
def get_script_params(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Return the current script's PARAMS dict (ast extraction, no execution)."""
    model_upload_path(request, id)
    staging = _staging_or_seed(request, id)
    current = verify_current_script(staging, 404)
    return {"modelId": id, "params": verify_extracted_params(current)}


@router.post("/models/{id}/script/undo")
def undo_script(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    with model_lock(id):
        staging = _staging(request, id)
        verify_undo_available(staging)
        staging.undo()
        return {"modelId": id, "script": staging.current(), "canRedo": staging.can_redo()}


@router.post("/models/{id}/script/redo")
def redo_script(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    with model_lock(id):
        staging = _staging(request, id)
        verify_redo_available(staging)
        staging.redo()
        return {"modelId": id, "script": staging.current(), "canUndo": staging.can_undo()}


@router.post("/models/{id}/script/discard")
def discard_script(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Throw staged edits away; back to the last saved big version. No version."""
    with model_lock(id):
        staging = _staging(request, id)
        dropped = staging.discard()
        return {"modelId": id, "discarded": dropped, "script": staging.current()}


@router.post("/models/{id}/script/run")
def run_script_endpoint(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Sandbox-run the current staged script into uploads (preview; no version)."""
    model_upload_path(request, id)
    with model_lock(id):
        current = verify_current_script(_staging(request, id), 409)
        _run_into_uploads(request, id, current)
        return {"modelId": id, "ok": True}


@router.post("/models/{id}/script/save")
def save_script(
    request: Request,
    id: str = Path(pattern=MODEL_ID_PATTERN),
    body: SaveBody | None = None,
) -> Dict[str, Any]:
    """Promote the staged script to a big version (run → snapshot script+DXF).

    A failed sandbox run → 422 and no version; staging is preserved so the
    script can be fixed and saved again. The response carries no ``alignment``
    field (chunk A decision).
    """
    model_upload_path(request, id)
    with model_lock(id):
        staging = _staging(request, id)
        current = verify_current_script(staging, 409)
        dxf_path = _run_into_uploads(request, id, current)
        note = body.note if body is not None else ""
        map_path = _current_map_path(request, id)
        map_text: Optional[str] = None
        if os.path.isfile(map_path):
            with open(map_path, "r", encoding="utf-8") as fh:
                map_text = fh.read()
        version = script_versions.save(
            request.app.state.settings.data_dir, id, current, dxf_path,
            note=note, map_text=map_text,
        )
        staging.save()
        return {"modelId": id, "version": version, "staged": 0}


@router.get("/models/{id}/scripts")
def list_scripts(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """List script big versions (empty for upload-only models)."""
    model_upload_path(request, id)
    data_dir = request.app.state.settings.data_dir
    return {
        "modelId": id,
        "scripts": script_versions.list_scripts(data_dir, id),
        "versions": versions.list_versions(data_dir, id),
    }


@router.get("/models/{id}/versions")
def get_versions(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """List materialized DXF snapshots (empty + current=null before any save)."""
    model_upload_path(request, id)
    data_dir = request.app.state.settings.data_dir
    listed = versions.list_versions(data_dir, id)
    return {
        "versions": listed,
        "current": listed[-1]["version"] if listed else None,
    }


@router.post("/models/{id}/script/rollback")
def rollback_script(
    request: Request,
    body: RollbackBody,
    id: str = Path(pattern=MODEL_ID_PATTERN),
) -> Dict[str, Any]:
    """Restore a big version's script into staging and re-run it into uploads."""
    model_upload_path(request, id)
    with model_lock(id):
        data_dir = request.app.state.settings.data_dir
        script = verify_script_version(data_dir, id, body.version)
        staging = request.app.state.script_staging.reset(id, base=script)
        _run_into_uploads(request, id, script)
        return {"modelId": id, "version": body.version, "script": staging.current()}


@router.post("/models/{id}/script/diff")
def diff_script_versions(
    request: Request,
    body: ScriptDiffBody,
    id: str = Path(pattern=MODEL_ID_PATTERN),
) -> Dict[str, Any]:
    """Big-version script diff: unified text diff + PARAMS changes + stats."""
    model_upload_path(request, id)
    data_dir = request.app.state.settings.data_dir
    base = verify_script_version(data_dir, id, body.base)
    target = verify_script_version(data_dir, id, body.target)
    return {
        "base": body.base,
        "target": body.target,
        "engine": "script",
        **script_diff.diff_scripts(base, target, body.base, body.target),
    }


@router.get("/models/{id}/script/staging/diff")
def diff_staging_steps(
    request: Request,
    id: str = Path(pattern=MODEL_ID_PATTERN),
    from_: Optional[int] = Query(default=None, alias="from", ge=0),
    to: Optional[int] = Query(default=None, ge=0),
) -> Dict[str, Any]:
    """Small-version diff between two staging steps (default: the last two).

    Step indices address the staged states ``history[0..cursor]`` (0-based).
    Lightweight inline text diff + PARAMS changes; visible to both AI and user.
    """
    model_upload_path(request, id)
    staging = _staging(request, id)
    i, j = verify_step_pair(staging, from_, to)
    base, target = staging.history[i], staging.history[j]
    return {
        "from": i,
        "to": j,
        **script_diff.diff_scripts(base, target, f"step{i}", f"step{j}"),
    }


@router.get("/models/{id}/script/locate")
def locate_callsite(
    request: Request, key: str = Query(...), id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Locate the script callsite for an XDATA key (key → CallSite).

    Unlike services/ifc the key is the direct input (no guid→designKey hop,
    no registry). staging 与 map 分叉（未 run 的暂存/undo/旧版裸 map）→ 200
    降级 ``{"found": false, "stale": true}``：行号不可信，绝不让前端跳到
    错误行。
    """
    model_upload_path(request, id)
    map_hash, entries = _read_current_map(_current_map_path(request, id))
    if entries is None:
        return {"found": False, "key": key}
    staging = _staging_or_seed(request, id)
    if _map_is_stale(map_hash, staging.current()):
        return {"found": False, "key": key, "stale": True}
    entry = entries.get(key)
    if entry is None:
        return {"found": False, "key": key}
    return {"found": True, "key": key, **entry}


@router.post("/models/{id}/script/edit-call")
def edit_call(
    request: Request, body: EditCallBody, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Rewrite one scalar argument at a located callsite, then sandbox-run.

    顺序：定位 → 重写 → 契约校验+沙箱 run → staging.push；任何失败 422 零副作用。
    origin=traced 的调用点不可自动改写 → 422。
    staging 与 map 分叉（未 run 的暂存/undo/旧版裸 map）→ 409 fail-closed：
    map 行号只对生成它的那份脚本有效，放行会把改写落到错误的调用上。
    """
    model_upload_path(request, id)
    with model_lock(id):
        staging = _staging(request, id)
        current = verify_current_script(staging, 409)
        map_hash, entries = _read_current_map(_current_map_path(request, id))
        entries = verify_map_fresh(map_hash, entries, current, body.key)
        entry = verify_editable_origin(entries, body.key)
        text = verify_rewritten_script(current, entry, body.argument, body.value)
        _run_into_uploads(request, id, text)
        staging.push(text)
        return {"modelId": id, "staged": staging.staged_count(), "script": text}

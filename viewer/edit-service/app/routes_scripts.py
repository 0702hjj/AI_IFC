# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Script-as-source endpoints: WPS-style staging + sandboxed run + big versions.

The build script is the single source of truth for generated models:

- ``PUT /models/{id}/script`` — stage a script edit (full replace, or
  params-only via ``{"params": {...}}`` which rewrites the PARAMS block
  server-side). Undo/redo buffer, 10 steps.
- ``GET  /models/{id}/script`` — current staged script (or last saved base).
  404 for legacy models that only have an IFC upload.
- ``GET  /models/{id}/script/params`` — ast-extracted PARAMS (form feed).
- ``POST /models/{id}/script/undo|redo|discard`` — WPS-style navigation.
- ``POST /models/{id}/script/run`` — sandbox-run the staged script and
  atomically replace ``uploads/{id}.ifc`` (no version).
- ``POST /models/{id}/script/save`` — sandbox-run, then snapshot
  ``scripts/v{n}.py`` + ``versions/v{n}.ifc`` (atomic, lockstep). A failed
  run → 422 and no version. The v{n-1}↔v{n} diff is computed on demand by
  the diff endpoints (W-0012), not here.
- ``GET  /models/{id}/scripts`` — list big versions.
- ``POST /models/{id}/script/rollback`` — restore a big version's script
  into staging, re-run it into uploads.
- ``GET  /models/{id}/script/locate?guid=...`` — guid → designKey →
  CallSite (from ``models/{id}/current.map.json``).
- ``POST /models/{id}/script/edit-call`` — libcst scalar-argument rewrite at
  a located callsite; sandbox-validated, staged on success (Task 4).

All mutating endpoints hold the per-model lock (keyed by the uploads path,
shared with entity edits) — the retired design routes lacked this and could
lose versions under concurrent saves.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from typing import Any, Dict, Optional

import ifcopenshell.util.element
from fastapi import APIRouter, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field

from . import (
    diffing,
    script_diff,
    script_edit,
    script_params,
    script_runner,
    script_staging,
    script_versions,
    versions,
)

logger = logging.getLogger(__name__)

router = APIRouter()

MODEL_ID_PATTERN = r"^m_[0-9a-f]{16}$"
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

    designKey: str
    argument: str
    value: Any  # 服务端强校验为标量（str/int/float/bool）


def _upload_path(request: Request, model_id: str) -> str:
    path = os.path.join(
        request.app.state.settings.data_dir, "uploads", f"{model_id}.ifc"
    )
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="model not found")
    return path


def _lock(request: Request, model_id: str):
    """Per-model lock keyed by the uploads path (shared with entity edits)."""
    path = os.path.join(
        request.app.state.settings.data_dir, "uploads", f"{model_id}.ifc"
    )
    return request.app.state.registry.lock(path)


def _staging(request: Request, model_id: str) -> script_staging.ScriptStaging:
    return request.app.state.script_staging.get(model_id)


def _bootstrap_path(request: Request, model_id: str) -> str:
    return os.path.join(
        request.app.state.settings.data_dir, "models", model_id, "bootstrap.ifc"
    )


def _preserve_bootstrap(
    request: Request, model_id: str, staging: script_staging.ScriptStaging
) -> None:
    """plain 态模型首次暂存脚本时，把上传原件原子复制为 bootstrap.ifc（§5.4）。

    必须发生在任何 run 覆盖 uploads 之前；已有大版本或 bootstrap 已存在则跳过
    （存量 script-backed 模型不补建）。调用方须持有模型锁。
    """
    bootstrap = _bootstrap_path(request, model_id)
    if os.path.exists(bootstrap) or staging.current() is not None:
        return
    data_dir = request.app.state.settings.data_dir
    if script_versions.list_scripts(data_dir, model_id):
        return
    uploads = os.path.join(data_dir, "uploads", f"{model_id}.ifc")
    os.makedirs(os.path.dirname(bootstrap), exist_ok=True)
    tmp = bootstrap + ".tmp"
    shutil.copyfile(uploads, tmp)
    os.replace(tmp, bootstrap)


def _staging_or_seed(request: Request, model_id: str) -> script_staging.ScriptStaging:
    """Staging for read endpoints; empty staging + existing big versions → seed
    base from the newest big version (chat-archived models have scripts/v{n}.py
    but no staging buffer, so GET /script used to 404 — M5 终审 C1).

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
    with _lock(request, model_id):
        staging = _staging(request, model_id)
        if staging.current() is None:
            latest = script_versions.load_script(
                data_dir, model_id, scripts[-1]["version"]
            )
            staging.seed_base(latest)
    return staging


def _current_or_409(staging: script_staging.ScriptStaging) -> str:
    current = staging.current()
    if current is None:
        raise HTTPException(status_code=409, detail="no script for model")
    return current


@router.get("/models/{id}/script")
def get_script(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Return the current script (staged state, or last saved base)."""
    _upload_path(request, id)
    staging = _staging_or_seed(request, id)
    current = staging.current()
    if current is None:
        raise HTTPException(status_code=404, detail="no script for model")
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
    _upload_path(request, id)
    if (body.script is None) == (body.params is None):
        raise HTTPException(
            status_code=422, detail="exactly one of script / params required"
        )
    with _lock(request, id):
        staging = _staging(request, id)
        if body.script is not None:
            text = body.script
        else:
            current = staging.current()
            if current is None:
                raise HTTPException(
                    status_code=409, detail="no script to update params on"
                )
            try:
                text = script_params.replace_params(current, body.params or {})
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))
        errors = script_runner.validate_script_text(request.app.state.settings, text)
        if errors:
            raise HTTPException(
                status_code=422, detail="脚本契约校验失败: " + "; ".join(errors)
            )
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
    _upload_path(request, id)
    staging = _staging_or_seed(request, id)
    current = staging.current()
    if current is None:
        raise HTTPException(status_code=404, detail="no script for model")
    try:
        params = script_params.extract_params(current)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"modelId": id, "params": params}


@router.post("/models/{id}/script/undo")
def undo_script(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    with _lock(request, id):
        staging = _staging(request, id)
        if not staging.undo():
            raise HTTPException(status_code=409, detail="nothing to undo")
        return {"modelId": id, "script": staging.current(), "canRedo": staging.can_redo()}


@router.post("/models/{id}/script/redo")
def redo_script(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    with _lock(request, id):
        staging = _staging(request, id)
        if not staging.redo():
            raise HTTPException(status_code=409, detail="nothing to redo")
        return {"modelId": id, "script": staging.current(), "canUndo": staging.can_undo()}


@router.post("/models/{id}/script/discard")
def discard_script(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Throw staged edits away; back to the last saved big version. No version."""
    with _lock(request, id):
        staging = _staging(request, id)
        dropped = staging.discard()
        return {"modelId": id, "discarded": dropped, "script": staging.current()}


def _current_map_path(request: Request, model_id: str) -> str:
    return os.path.join(
        request.app.state.settings.data_dir, "models", model_id, "current.map.json"
    )


def _run_into_uploads(request: Request, id: str, script: str) -> str:
    """Sandbox-run script into uploads/{id}.ifc and drop the registry cache.

    The run replaces the IFC the pending entries were applied to, so any
    pending entries are flagged ``needs_replay`` before the unload (the LRU
    ``on_evict`` hook only fires on capacity eviction, not here). The run's
    ScriptMap is published to ``models/{id}/current.map.json``.
    """
    ifc_path = _upload_path(request, id)
    script_runner.run_script(
        request.app.state.settings, script, ifc_path,
        map_out=_current_map_path(request, id),
    )
    store = request.app.state.pending
    store._ensure(id)
    store.mark_needs_replay(id)
    request.app.state.registry.unload(ifc_path)
    return ifc_path


@router.post("/models/{id}/script/run")
def run_script_endpoint(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Sandbox-run the current staged script into uploads (preview; no version)."""
    _upload_path(request, id)
    with _lock(request, id):
        current = _current_or_409(_staging(request, id))
        _run_into_uploads(request, id, current)
        return {"modelId": id, "ok": True}


@router.post("/models/{id}/script/save")
def save_script(
    request: Request,
    id: str = Path(pattern=MODEL_ID_PATTERN),
    body: SaveBody | None = None,
) -> Dict[str, Any]:
    """Promote the staged script to a big version (run → snapshot script+IFC).

    A failed sandbox run → 422 and no version; staging is preserved so the
    script can be fixed and saved again.
    """
    _upload_path(request, id)
    with _lock(request, id):
        staging = _staging(request, id)
        current = _current_or_409(staging)
        ifc_path = _run_into_uploads(request, id, current)
        note = body.note if body is not None else ""
        map_path = _current_map_path(request, id)
        map_text: Optional[str] = None
        if os.path.isfile(map_path):
            with open(map_path, "r", encoding="utf-8") as fh:
                map_text = fh.read()
        version = script_versions.save(
            request.app.state.settings.data_dir, id, current, ifc_path,
            note=note, map_text=map_text,
        )
        staging.save()
        return {
            "modelId": id,
            "version": version,
            "staged": 0,
            "alignment": _bootstrap_alignment(request, id, ifc_path),
        }


def _bootstrap_alignment(
    request: Request, model_id: str, ifc_path: str
) -> Optional[Dict[str, int]]:
    """bootstrap.ifc（上传原件）vs 本次生成 IFC 的语义 diff 计数（§5.4）。

    版本已落盘，对齐计算失败绝不让 save 失败——记日志返回 None。
    """
    bootstrap = _bootstrap_path(request, model_id)
    if not os.path.isfile(bootstrap):
        return None
    try:
        diff = diffing.compute_diff(bootstrap, ifc_path)
    except Exception:
        logger.exception("bootstrap alignment diff failed for model %s", model_id)
        return None
    return {
        "added": len(diff["added"]),
        "removed": len(diff["removed"]),
        "changed": len(diff["changed"]),
    }


@router.get("/models/{id}/scripts")
def list_scripts(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """List script big versions (empty for legacy IFC-only models)."""
    _upload_path(request, id)
    data_dir = request.app.state.settings.data_dir
    return {
        "modelId": id,
        "scripts": script_versions.list_scripts(data_dir, id),
        "versions": versions.list_versions(data_dir, id),
    }


@router.post("/models/{id}/script/rollback")
def rollback_script(
    request: Request,
    body: RollbackBody,
    id: str = Path(pattern=MODEL_ID_PATTERN),
) -> Dict[str, Any]:
    """Restore a big version's script into staging and re-run it into uploads."""
    _upload_path(request, id)
    with _lock(request, id):
        data_dir = request.app.state.settings.data_dir
        try:
            script = script_versions.load_script(data_dir, id, body.version)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        staging = request.app.state.script_staging.reset(id, base=script)
        _run_into_uploads(request, id, script)
        return {"modelId": id, "version": body.version, "script": staging.current()}


def _load_script_or_404(data_dir: str, model_id: str, version: str) -> str:
    try:
        return script_versions.load_script(data_dir, model_id, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/models/{id}/script/diff")
def diff_script_versions(
    request: Request,
    body: ScriptDiffBody,
    id: str = Path(pattern=MODEL_ID_PATTERN),
) -> Dict[str, Any]:
    """Big-version script diff: unified text diff + PARAMS changes + stats.

    This is the primary AI-facing diff (the retired design-JSON diff's
    replacement); the IFC semantic diff stays at POST /models/{id}/diff.
    """
    _upload_path(request, id)
    data_dir = request.app.state.settings.data_dir
    base = _load_script_or_404(data_dir, id, body.base)
    target = _load_script_or_404(data_dir, id, body.target)
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
    _upload_path(request, id)
    staging = _staging(request, id)
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
    base, target = staging.history[i], staging.history[j]
    return {
        "from": i,
        "to": j,
        **script_diff.diff_scripts(base, target, f"step{i}", f"step{j}"),
    }


@router.get("/models/{id}/script/locate")
def locate_callsite(
    request: Request, guid: str = Query(...), id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Locate the script callsite for an IFC element (guid → designKey → CallSite)."""
    ifc_path = _upload_path(request, id)
    model = request.app.state.registry.load(ifc_path)
    try:
        element = model.by_guid(guid)
    except RuntimeError:
        raise HTTPException(status_code=404, detail=f"element not found: {guid}")
    psets = ifcopenshell.util.element.get_psets(element)
    key = (psets.get("Pset_AIIFC") or {}).get("designKey")
    if not key:
        return {"found": False}
    map_path = _current_map_path(request, id)
    entry = None
    if os.path.isfile(map_path):
        with open(map_path, encoding="utf-8") as fh:
            entry = json.load(fh).get(key)
    if entry is None:
        return {"found": False, "designKey": key}
    return {"found": True, "designKey": key, **entry}


@router.post("/models/{id}/script/edit-call")
def edit_call(
    request: Request, body: EditCallBody, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Rewrite one scalar argument at a located callsite, then sandbox-run.

    顺序：定位 → 重写 → 契约校验+沙箱 run → staging.push；任何失败 422 零副作用。
    origin=traced 的调用点不可自动改写 → 422。
    """
    _upload_path(request, id)
    with _lock(request, id):
        staging = _staging(request, id)
        current = _current_or_409(staging)
        map_path = _current_map_path(request, id)
        entry = None
        if os.path.isfile(map_path):
            with open(map_path, encoding="utf-8") as fh:
                entry = json.load(fh).get(body.designKey)
        if entry is None:
            raise HTTPException(
                status_code=404, detail=f"callsite not found: {body.designKey}"
            )
        if entry.get("origin") == "traced":
            raise HTTPException(
                status_code=422,
                detail="callsite not auto-editable (traced); edit the script directly",
            )
        try:
            text = script_edit.rewrite_call_argument(
                current, entry["line"], body.argument, body.value
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        _run_into_uploads(request, id, text)
        staging.push(text)
        return {"modelId": id, "staged": staging.staged_count(), "script": text}

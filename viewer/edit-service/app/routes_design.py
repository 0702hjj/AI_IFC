# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Design-JSON endpoints: WPS-style staging + big-version save/rollback.

The design JSON is the source of truth for generated models. This router
replaces the per-step IFC commit chain for generated models:

- ``PUT /models/{id}/design`` — stage a design JSON edit (undo/redo buffer, 10 steps).
- ``GET  /models/{id}/design`` — current staged design (or last saved).
- ``POST /models/{id}/design/undo|redo|discard`` — WPS-style navigation / throw away.
- ``POST /models/{id}/design/save`` — promote staged design to a big version
  (discard staging, snapshot design JSON + derived IFC, compute one diff downstream).
- ``GET  /models/{id}/designs`` — list big versions.
- ``POST /models/{id}/design/rollback`` — restore a big version's design JSON.

No per-step history is persisted: only big versions (save points) exist.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import BaseModel, Field

from . import design_staging, design_versions, regenerate, versions

router = APIRouter()

MODEL_ID_PATTERN = r"^m_[0-9a-f]{16}$"
VERSION_NAME_PATTERN = r"^v\d+$"


class DesignBody(BaseModel):
    """Body of PUT /models/{id}/design."""

    design: Dict[str, Any] = Field(..., description="full design JSON state")
    note: str = ""


class SaveBody(BaseModel):
    """Optional body of POST /models/{id}/design/save."""

    note: str = ""


class RollbackBody(BaseModel):
    """Body of POST /models/{id}/design/rollback."""

    version: str = Field(..., pattern=VERSION_NAME_PATTERN)


def _design_upload_path(request: Request, model_id: str) -> str:
    path = f"{request.app.state.settings.data_dir}/uploads/{model_id}.ifc"
    if not __import__("os").path.isfile(path):
        raise HTTPException(status_code=404, detail="model not found")
    return path


@router.get("/models/{id}/design")
def get_design(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Return the current design JSON (staged state, or last saved)."""
    staging = request.app.state.design_staging.get(id)
    return {
        "modelId": id,
        "design": staging.current(),
        "staged": staging.staged_count(),
        "canUndo": staging.can_undo(),
        "canRedo": staging.can_redo(),
        "maxSteps": design_staging.MAX_STEPS,
    }


@router.put("/models/{id}/design")
def stage_design(
    request: Request,
    body: DesignBody,
    id: str = Path(pattern=MODEL_ID_PATTERN),
) -> Dict[str, Any]:
    """Stage a design JSON edit (WPS-style push to the undo/redo buffer)."""
    _design_upload_path(request, id)
    staging = request.app.state.design_staging.get(id)
    staging.push(body.design)
    return {
        "modelId": id,
        "staged": staging.staged_count(),
        "canUndo": staging.can_undo(),
        "canRedo": staging.can_redo(),
    }


@router.post("/models/{id}/design/undo")
def undo_design(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    staging = request.app.state.design_staging.get(id)
    if not staging.undo():
        raise HTTPException(status_code=409, detail="nothing to undo")
    return {"modelId": id, "design": staging.current(), "canRedo": staging.can_redo()}


@router.post("/models/{id}/design/redo")
def redo_design(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    staging = request.app.state.design_staging.get(id)
    if not staging.redo():
        raise HTTPException(status_code=409, detail="nothing to redo")
    return {"modelId": id, "design": staging.current(), "canUndo": staging.can_undo()}


@router.post("/models/{id}/design/discard")
def discard_design(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Throw staged edits away; back to the last saved big version. No diff, no version."""
    staging = request.app.state.design_staging.get(id)
    dropped = staging.discard()
    return {"modelId": id, "discarded": dropped, "design": staging.current()}


@router.post("/models/{id}/design/save")
def save_design(
    request: Request,
    id: str = Path(pattern=MODEL_ID_PATTERN),
    body: SaveBody | None = None,
) -> Dict[str, Any]:
    """Promote staged design to a big version (discard staging + snapshot design+IFC).

    The IFC file must already be regenerated from the staged design before this
    call; this endpoint snapshots it as the big version.
    """
    ifc_path = _design_upload_path(request, id)
    staging = request.app.state.design_staging.get(id)
    note = body.note if body is not None else ""
    version = design_versions.save(
        request.app.state.settings.data_dir, id, staging.current(), ifc_path, note=note
    )
    staging.save()
    return {"modelId": id, "version": version, "staged": 0}


@router.get("/models/{id}/designs")
def list_designs(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    return {
        "modelId": id,
        "designs": design_versions.list_designs(request.app.state.settings.data_dir, id),
        "versions": versions.list_versions(request.app.state.settings.data_dir, id),
    }


@router.post("/models/{id}/design/regenerate")
def regenerate_design(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Regenerate the derived IFC from the current staged design JSON.

    Runs the aiifc build pipeline (design_builder → build_script_template)
    and atomically replaces ``uploads/{id}.ifc``. Call before ``save`` so the
    regenerated IFC becomes part of the big version.
    """
    ifc_path = _design_upload_path(request, id)
    staging = request.app.state.design_staging.get(id)
    return regenerate.regenerate(request.app.state.settings, staging.current(), ifc_path)


@router.post("/models/{id}/design/rollback")
def rollback_design(
    request: Request,
    body: RollbackBody,
    id: str = Path(pattern=MODEL_ID_PATTERN),
) -> Dict[str, Any]:
    """Restore a big version's design JSON; regeneration is downstream."""
    design = design_versions.rollback(request.app.state.settings.data_dir, id, body.version)
    staging = request.app.state.design_staging.reset(id, base=design)
    return {"modelId": id, "version": body.version, "design": staging.current()}

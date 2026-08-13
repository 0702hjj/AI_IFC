# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Entity-edit surface: the L1 direct-edit chain is retired (410 Gone).

Script-as-source (spec 2026-08-08-script-editing-unified-design.md §9): all
editing goes through the build script; IFC is a pure build artifact, so the
pending→commit true-edit chain no longer mutates it. The retired endpoints
answer 410 (permanent retirement, not 404). Surviving surface:

- ``GET .../pending`` / ``GET .../history``: read-only views of the pending
  store / persisted edit history (history stays append-only via
  routes_user_edits; spec §5.5 历史只读).
- ``DELETE .../pending``: clears the pending store (script-run replay
  bookkeeping, W-0009).

The retired implementation can be recovered from git history (rollback
anchor fb55a8a).
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Path, Request

from . import history
from .pending import PendingStore
from .route_common import MODEL_ID_PATTERN, model_upload_path

router = APIRouter()

RETIRED_DETAIL = "direct IFC editing retired: edit the build script (script-as-source)"


def _pending(request: Request) -> PendingStore:
    return request.app.state.pending


def _retired() -> None:
    raise HTTPException(status_code=410, detail=RETIRED_DETAIL)


@router.put("/models/{id}/entities/{guid}")
def put_entity(id: str = Path(pattern=MODEL_ID_PATTERN), guid: str = Path()) -> None:
    """Retired: edit the build script instead of mutating the IFC directly."""
    _retired()


@router.get("/models/{id}/entities/{guid}/editable-schema")
def get_editable_schema(id: str = Path(pattern=MODEL_ID_PATTERN), guid: str = Path()) -> None:
    """Retired: no typed edit form without direct editing."""
    _retired()


@router.delete("/models/{id}/entities/{guid}")
def delete_entity(id: str = Path(pattern=MODEL_ID_PATTERN), guid: str = Path()) -> None:
    """Retired: edit the build script instead of deleting entities directly."""
    _retired()


@router.post("/models/{id}/commit")
def commit_pending(id: str = Path(pattern=MODEL_ID_PATTERN)) -> None:
    """Retired: script save (script/save) is the only version checkpoint."""
    _retired()


@router.get("/models/{id}/pending")
def get_pending(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> List[Dict[str, Any]]:
    """List the current pending changes for a model (read-only)."""
    return _pending(request).get(id)


@router.delete("/models/{id}/pending")
def discard_pending(request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)) -> Dict[str, Any]:
    """Discard pending changes: reload the in-memory model from disk."""
    path = model_upload_path(request, id)
    registry = request.app.state.registry
    with registry.lock(path):
        registry.unload(path)
        registry.load(path)
        dropped = len(_pending(request).get(id))
        _pending(request).set(id, [])
    return {"discarded": dropped}


@router.get("/models/{id}/history")
def get_history(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> List[Dict[str, Any]]:
    """List the persisted edit history for a model (read-only)."""
    return history.load_history(request.app.state.settings.data_dir, id)

# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Entity edit endpoints: pending changes, two-phase commit, history.

``PUT`` applies field/pset edits to the in-memory model and records a
pending change; nothing touches the IFC on disk until ``POST .../commit``
saves the model and appends the entries to the persistent history. A failed
``PUT`` rolls the entity back to its pre-request state (fields and psets)
and leaves no pending entry. ``DELETE .../pending`` discards pending changes
by reloading the model from disk.

The pending queue itself is persisted per model (see pending.PendingStore:
``models/{id}/pending.json``, atomic writes), so uncommitted entries survive
a service restart.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal

import ifcopenshell.api.pset
import ifcopenshell.util.element
from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import BaseModel, Field

from . import history, versions
from .pending import PendingStore

router = APIRouter()

MODEL_ID_PATTERN = r"^m_[0-9a-f]{16}$"


class Provenance(BaseModel):
    """Who performed an edit: the web UI or an AI agent."""

    source: Literal["UI", "AI"] = "UI"


class EditBody(BaseModel):
    """Body of PUT /models/{id}/entities/{guid}."""

    fields: Dict[str, Any] = Field(default_factory=dict)
    psets: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    author: str = "local-user"
    provenance: Provenance = Field(default_factory=Provenance)


class CommitBody(BaseModel):
    """Optional body of POST /models/{id}/commit."""

    operation: Literal["update", "migrate"] = "update"


def _model_path(request: Request, model_id: str) -> str:
    path = os.path.join(
        request.app.state.settings.data_dir, "uploads", f"{model_id}.ifc"
    )
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="model not found")
    return path


def _pending(request: Request) -> PendingStore:
    return request.app.state.pending


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _attribute_names(entity: ifcopenshell.entity_instance) -> set:
    return {entity.attribute_name(i) for i in range(len(entity))}


def _validate(body: EditBody, entity: ifcopenshell.entity_instance) -> None:
    """Validate the whole request before anything is applied (atomicity)."""
    attr_names = _attribute_names(entity)
    for field_name in body.fields:
        if field_name not in attr_names:
            raise HTTPException(
                status_code=422, detail=f"unknown attribute: {field_name}"
            )
    for pset_name, props in body.psets.items():
        for key, value in props.items():
            if value is not None and not isinstance(value, (str, int, float, bool)):
                raise HTTPException(
                    status_code=422,
                    detail=f"unsupported value type for {pset_name}.{key}",
                )


def _rollback_psets(
    model: ifcopenshell.file,
    entity: ifcopenshell.entity_instance,
    requested: Dict[str, Dict[str, Any]],
    old_values: Dict[str, Dict[str, Any]],
) -> None:
    """Restore psets touched by a failed PUT to their pre-request state."""
    current_values = ifcopenshell.util.element.get_psets(entity)
    for pset_name in requested:
        old = old_values.get(pset_name)
        current = current_values.get(pset_name)
        old_id = old.get("id") if old else None
        current_id = current.get("id") if current else None
        if current_id is not None and current_id != old_id:
            ifcopenshell.api.pset.remove_pset(
                model, product=entity, pset=model.by_id(current_id)
            )
        if old is not None:
            old_props = {k: v for k, v in old.items() if k != "id"}
            now_props = ifcopenshell.util.element.get_psets(entity).get(pset_name, {})
            restore = {k: None for k in now_props if k not in old_props and k != "id"}
            restore.update(old_props)
            ifcopenshell.api.pset.edit_pset(
                model, pset=model.by_id(old_id), properties=restore
            )


@router.put("/models/{id}/entities/{guid}")
def put_entity(
    request: Request,
    body: EditBody,
    id: str = Path(pattern=MODEL_ID_PATTERN),
    guid: str = Path(),
) -> Dict[str, Any]:
    """Apply edits to the in-memory model and record a pending change."""
    if not body.fields and not body.psets:
        raise HTTPException(status_code=422, detail="fields or psets required")
    path = _model_path(request, id)
    registry = request.app.state.registry
    with registry.lock(path):
        model = registry.load(path)
        try:
            entity = model.by_guid(guid)
        except RuntimeError:
            raise HTTPException(status_code=404, detail="entity not found")

        _validate(body, entity)

        changes: List[Dict[str, Any]] = []
        old_fields: Dict[str, Any] = {}
        try:
            for field_name in body.fields:
                old_fields[field_name] = getattr(entity, field_name)
            for field_name, new_value in body.fields.items():
                setattr(entity, field_name, new_value)
                changes.append(
                    {
                        "field": field_name,
                        "oldValue": _jsonable(old_fields[field_name]),
                        "newValue": new_value,
                    }
                )
        except (TypeError, ValueError) as exc:
            for field_name, old_value in old_fields.items():
                setattr(entity, field_name, old_value)
            raise HTTPException(status_code=422, detail=f"invalid field value: {exc}")

        existing_psets = ifcopenshell.util.element.get_psets(entity)
        try:
            for pset_name, props in body.psets.items():
                old_props = existing_psets.get(pset_name, {})
                items = list(props.items())
                pset = ifcopenshell.api.pset.add_pset(model, product=entity, name=pset_name)
                ifcopenshell.api.pset.edit_pset(model, pset=pset, properties=dict(props))
                for key, value in items:
                    changes.append(
                        {
                            "field": f"{pset_name}.{key}",
                            "oldValue": _jsonable(old_props.get(key)),
                            "newValue": value,
                        }
                    )
        except Exception as exc:
            for field_name, old_value in old_fields.items():
                setattr(entity, field_name, old_value)
            _rollback_psets(model, entity, body.psets, existing_psets)
            raise HTTPException(status_code=500, detail=f"pset edit failed: {exc}")

        entry = {
            "id": "e_" + secrets.token_hex(6),
            "guid": guid,
            "changes": changes,
            "author": body.author,
            "provenance": body.provenance.model_dump(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _pending(request).append(id, entry)
        return entry


@router.get("/models/{id}/pending")
def get_pending(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> List[Dict[str, Any]]:
    """List the current pending changes for a model."""
    return _pending(request).get(id)


@router.post("/models/{id}/commit")
def commit_pending(
    request: Request,
    id: str = Path(pattern=MODEL_ID_PATTERN),
    body: CommitBody | None = None,
) -> Dict[str, Any]:
    """Atomically save all pending changes to disk and append them to history.

    The first commit snapshots the original upload as ``v1`` before saving;
    every commit snapshots the newly saved file as the next version. The
    optional body stamps ``operation`` onto the committed entries (default
    ``update``; Go's override migration passes ``migrate``).
    """
    path = _model_path(request, id)
    registry = request.app.state.registry
    data_dir = request.app.state.settings.data_dir
    operation = body.operation if body is not None else "update"
    with registry.lock(path):
        pending = _pending(request).get(id)
        if not pending:
            raise HTTPException(status_code=409, detail="no pending changes")
        if not versions.list_versions(data_dir, id):
            versions.snapshot(data_dir, id, path)
        registry.save(path)
        versions.snapshot(data_dir, id, path)
        entries = [dict(entry, operation=operation) for entry in pending]
        history.append_history(data_dir, id, entries)
        _pending(request).set(id, [])
    return {"committed": len(entries), "entries": entries}


@router.delete("/models/{id}/pending")
def discard_pending(request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)) -> Dict[str, Any]:
    """Discard pending changes: reload the in-memory model from disk."""
    path = _model_path(request, id)
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
    """List the persisted edit history for a model."""
    return history.load_history(request.app.state.settings.data_dir, id)

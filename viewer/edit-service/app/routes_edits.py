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
from typing import Any, Dict, List, Literal, Optional

import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.util.element
import ifcopenshell.util.schema
from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import BaseModel, Field

from . import history, versions
from .pending import PendingStore

router = APIRouter()

MODEL_ID_PATTERN = r"^m_[0-9a-f]{16}$"


class Provenance(BaseModel):
    """Who performed an edit: the web UI, an AI agent, or an external user edit.

    ``origin`` further qualifies USER edits (e.g. ``upload`` for a modified
    IFC/DXF file parsed by the MCP server).
    """

    source: Literal["UI", "AI", "USER"] = "UI"
    origin: Optional[str] = None


class EditBody(BaseModel):
    """Body of PUT /models/{id}/entities/{guid}."""

    fields: Dict[str, Any] = Field(default_factory=dict)
    psets: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    author: str = "local-user"
    provenance: Provenance = Field(default_factory=Provenance)


class CommitBody(BaseModel):
    """Optional body of POST /models/{id}/commit."""

    operation: Literal["update", "migrate"] = "update"


class DeleteBody(BaseModel):
    """Optional body of DELETE /models/{id}/entities/{guid}."""

    author: str = "local-user"
    provenance: Provenance = Field(default_factory=Provenance)


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


_SIMPLE_KIND = {
    "<string>": "string",
    "<integer>": "int",
    "<real>": "float",
    "<number>": "float",
    "<boolean>": "bool",
    "<logical>": "bool",
}


def _enum_items(
    attribute: "ifcopenshell.ifcopenshell_wrapper.attribute",
) -> Optional[tuple]:
    """Return enumeration items if the attribute is an enum, else None."""
    attr_type = attribute.type_of_attribute()
    if attr_type.as_named_type() is None:
        return None
    declared = attr_type.declared_type()
    if type(declared).__name__ != "enumeration_type":
        return None
    return tuple(declared.enumeration_items())


def _attribute_kind(attribute: "ifcopenshell.ifcopenshell_wrapper.attribute") -> Optional[Dict[str, Any]]:
    """Map a schema attribute to an editable kind, or None when not editable.

    Editable kinds: string/int/float/bool (from simple types, unwrapping
    nested type declarations) and enum (with legal values). Entity,
    aggregate, select and binary attributes are not editable.
    """
    attr_type = attribute.type_of_attribute()
    if attr_type.as_named_type() is None:
        return None
    declared = attr_type.declared_type()
    if type(declared).__name__ == "enumeration_type":
        return {"kind": "enum", "enumValues": list(declared.enumeration_items())}
    if type(declared).__name__ != "type_declaration":
        return None
    inner = declared
    for _ in range(16):
        nxt = inner.declared_type()
        if type(nxt).__name__ != "type_declaration":
            inner = nxt
            break
        inner = nxt
    kind = _SIMPLE_KIND.get(str(inner))
    if kind is None:
        return None
    return {"kind": kind}


def _scalar_kind(value: Any) -> Optional[str]:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    return None


def _validate(body: EditBody, entity: ifcopenshell.entity_instance) -> None:
    """Validate the whole request before anything is applied (atomicity)."""
    attr_names = _attribute_names(entity)
    enum_attrs: Dict[str, set] = {}
    for attribute in ifcopenshell.util.schema.get_declaration(entity).all_attributes():
        items = _enum_items(attribute)
        if items is not None:
            enum_attrs[attribute.name()] = set(items)
    for field_name, value in body.fields.items():
        if field_name not in attr_names:
            raise HTTPException(
                status_code=422, detail=f"unknown attribute: {field_name}"
            )
        if field_name in enum_attrs and value is not None:
            if not isinstance(value, str) or value not in enum_attrs[field_name]:
                raise HTTPException(
                    status_code=422,
                    detail=f"invalid enum value for {field_name}: {value}",
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


def _replay_entry(model: ifcopenshell.file, entry: Dict[str, Any]) -> None:
    """Re-apply one pending entry to a model freshly opened from disk.

    Entries carry complete edit instructions: ``changes[].field`` is either a
    direct attribute name or ``"<pset>.<prop>"`` and ``newValue`` the scalar
    to set; delete entries carry ``action: "delete"``.
    """
    guid = entry.get("guid")
    try:
        entity = model.by_guid(guid)
    except RuntimeError:
        if entry.get("action") == "delete":
            return  # already gone from the on-disk model
        raise
    if entry.get("action") == "delete":
        ifcopenshell.api.root.remove_product(model, product=entity)
        return
    fields: Dict[str, Any] = {}
    psets: Dict[str, Dict[str, Any]] = {}
    for change in entry.get("changes", []):
        field = change["field"]
        if "." in field:
            pset_name, key = field.split(".", 1)
            psets.setdefault(pset_name, {})[key] = change["newValue"]
        else:
            fields[field] = change["newValue"]
    for field_name, value in fields.items():
        setattr(entity, field_name, value)
    for pset_name, props in psets.items():
        pset = ifcopenshell.api.pset.add_pset(model, product=entity, name=pset_name)
        ifcopenshell.api.pset.edit_pset(model, pset=pset, properties=props)


def _ensure_replayed(request: Request, model_id: str, model: ifcopenshell.file) -> None:
    """Replay restored/evicted pending entries onto the in-memory model.

    Entries restored from ``pending.json`` (or whose model was LRU-evicted)
    describe edits the current in-memory model never saw. Entries that fail
    to replay (e.g. entity gone from the on-disk file) are marked ``stale``
    and persisted; commit refuses stale entries.

    The restore (``_ensure``) runs before the flag check: after a cold
    restart the flag only gets set when the entries are restored, so a
    read-only first request (e.g. editable-schema) must restore first.
    """
    store = _pending(request)
    entries = store._ensure(model_id)
    if not store.needs_replay(model_id):
        return
    for entry in entries:
        try:
            _replay_entry(model, entry)
        except Exception:  # noqa: BLE001 - any replay failure marks the entry stale
            entry["stale"] = True
    store.set(model_id, entries)


def _stale_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [entry for entry in entries if entry.get("stale")]


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
        _ensure_replayed(request, id, model)
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
        except (TypeError, ValueError, RuntimeError) as exc:
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
            "provenance": body.provenance.model_dump(exclude_none=True),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _pending(request).append(id, entry)
        return entry


@router.get("/models/{id}/entities/{guid}/editable-schema")
def get_editable_schema(
    request: Request,
    id: str = Path(pattern=MODEL_ID_PATTERN),
    guid: str = Path(),
) -> Dict[str, Any]:
    """Typed edit form schema for an entity.

    ``fields`` lists editable direct attributes (name/kind/current value,
    ``enumValues`` for enum kinds like PredefinedType); ``psets`` lists
    editable scalar properties (str/int/float/bool). Non-scalar attributes
    (entities, aggregates, selects) and GlobalId are excluded.
    """
    path = _model_path(request, id)
    registry = request.app.state.registry
    with registry.lock(path):
        model = registry.load(path)
        _ensure_replayed(request, id, model)
        try:
            entity = model.by_guid(guid)
        except RuntimeError:
            raise HTTPException(status_code=404, detail="entity not found")
        fields: List[Dict[str, Any]] = []
        for attribute in ifcopenshell.util.schema.get_declaration(entity).all_attributes():
            name = attribute.name()
            if name == "GlobalId":
                continue
            info = _attribute_kind(attribute)
            if info is None:
                continue
            item: Dict[str, Any] = {
                "name": name,
                "kind": info["kind"],
                "value": _jsonable(getattr(entity, name)),
            }
            if info["kind"] == "enum":
                item["enumValues"] = info["enumValues"]
            fields.append(item)
        psets: List[Dict[str, Any]] = []
        for pset_name, props in ifcopenshell.util.element.get_psets(entity).items():
            properties: List[Dict[str, Any]] = []
            for prop_name, value in props.items():
                if prop_name == "id":
                    continue
                kind = _scalar_kind(value)
                if kind is None:
                    continue
                properties.append({"name": prop_name, "kind": kind, "value": value})
            psets.append({"name": pset_name, "properties": properties})
    return {"guid": guid, "ifcType": entity.is_a(), "fields": fields, "psets": psets}


@router.delete("/models/{id}/entities/{guid}")
def delete_entity(
    request: Request,
    body: Optional[DeleteBody] = None,
    id: str = Path(pattern=MODEL_ID_PATTERN),
    guid: str = Path(),
) -> Dict[str, Any]:
    """Delete an entity into the pending flow (effective on commit).

    ``remove_product`` cascades: psets, placement/representation, material,
    type, containment, aggregation, nesting and void/fill relationships are
    cleaned up. IfcProject and spatial structure elements are refused (422).
    On an unexpected delete failure the in-memory model is reloaded from disk
    and pending is dropped, keeping the two consistent.
    """
    path = _model_path(request, id)
    registry = request.app.state.registry
    with registry.lock(path):
        model = registry.load(path)
        _ensure_replayed(request, id, model)
        try:
            entity = model.by_guid(guid)
        except RuntimeError:
            raise HTTPException(status_code=404, detail="entity not found")
        if entity.is_a("IfcProject") or entity.is_a("IfcSpatialStructureElement"):
            raise HTTPException(
                status_code=422,
                detail="cannot delete project or spatial structure elements",
            )
        old_name = getattr(entity, "Name", None)
        try:
            ifcopenshell.api.root.remove_product(model, product=entity)
        except Exception as exc:
            registry.unload(path)
            registry.load(path)
            _pending(request).set(id, [])
            raise HTTPException(status_code=500, detail=f"entity delete failed: {exc}")
        body = body or DeleteBody()
        entry = {
            "id": "e_" + secrets.token_hex(6),
            "guid": guid,
            "action": "delete",
            "changes": [
                {"field": "__deleted__", "oldValue": _jsonable(old_name), "newValue": None}
            ],
            "author": body.author,
            "provenance": body.provenance.model_dump(exclude_none=True),
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
    ``update``; Go's override migration passes ``migrate``). Pending entries
    restored from disk (or orphaned by LRU eviction) are replayed onto the
    re-opened model first; entries that cannot be replayed are ``stale``
    and refuse the commit (409) instead of snapshotting an unmodified IFC.
    """
    path = _model_path(request, id)
    registry = request.app.state.registry
    data_dir = request.app.state.settings.data_dir
    operation = body.operation if body is not None else "update"
    with registry.lock(path):
        model = registry.load(path)
        store = _pending(request)
        pending = store._ensure(id)
        if not pending:
            raise HTTPException(status_code=409, detail="no pending changes")
        _ensure_replayed(request, id, model)
        stale = _stale_entries(pending)
        if stale:
            ids = ", ".join(entry.get("id", "?") for entry in stale)
            raise HTTPException(
                status_code=409,
                detail=(
                    f"stale pending entries cannot be replayed: {ids}; "
                    "discard pending changes (DELETE /pending) to proceed"
                ),
            )
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

# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Generic DXF layer/entity-level comparison (ezdxf).

Deliberately layout-agnostic: no attempt to reverse-engineer rooms/walls from
geometry (that reconstruction belongs to the cad pipeline). Entities are
matched by handle across the two files; per layer we report added/removed/
modified counts, and TEXT/MTEXT content changes are surfaced separately.

Handle alignment assumes the user edited a copy of the original file: a DXF
re-saved by a CAD application gets all-new handles, and every entity will be
reported as added/removed instead of modified.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import ezdxf

_PRECISION = 6


def _point(value: Any) -> List[float]:
    return [round(float(v), _PRECISION) for v in value]


def _signature(entity: Any) -> Optional[Tuple[Tuple[str, Any], ...]]:
    """Key attributes per entity type; None = tracked by count only."""
    dxftype = entity.dxftype()
    dxf = entity.dxf
    if dxftype == "LINE":
        return (("start", _point(dxf.start)), ("end", _point(dxf.end)))
    if dxftype == "LWPOLYLINE":
        points = tuple(tuple(_point(p)) for p in entity.get_points("xy"))
        return (("points", points),)
    if dxftype == "CIRCLE":
        return (("center", _point(dxf.center)), ("radius", round(dxf.radius, _PRECISION)))
    if dxftype == "ARC":
        return (
            ("center", _point(dxf.center)),
            ("radius", round(dxf.radius, _PRECISION)),
            ("start_angle", round(dxf.start_angle, _PRECISION)),
            ("end_angle", round(dxf.end_angle, _PRECISION)),
        )
    if dxftype == "TEXT":
        return (("text", dxf.text), ("insert", _point(dxf.insert)))
    if dxftype == "MTEXT":
        return (("text", entity.text), ("insert", _point(dxf.insert)))
    if dxftype == "INSERT":
        return (("name", dxf.name), ("insert", _point(dxf.insert)))
    return None


def _entry(entity: Any) -> Dict[str, Any]:
    layer = entity.dxf.layer
    handle = entity.dxf.handle
    return {
        "locator": f"dxf:{layer}/{entity.dxftype()}/{handle}",
        "layer": layer,
        "type": entity.dxftype(),
        "handle": handle,
    }


def _entities_by_handle(doc: Any) -> Dict[str, Any]:
    return {e.dxf.handle: e for e in doc.modelspace()}


def dxf_diff(base_path: str, new_path: str) -> Dict[str, Any]:
    """Compare two DXF files at layer/entity granularity."""
    base = _entities_by_handle(ezdxf.readfile(base_path))
    new = _entities_by_handle(ezdxf.readfile(new_path))

    added: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    modified: List[Dict[str, Any]] = []
    texts: List[Dict[str, Any]] = []
    layers: Dict[str, Dict[str, int]] = {}

    def bump(layer: str, key: str) -> None:
        stats = layers.setdefault(layer, {"added": 0, "removed": 0, "modified": 0})
        stats[key] += 1

    for handle in sorted(new, key=lambda h: int(h, 16)):
        if handle not in base:
            entry = _entry(new[handle])
            added.append(entry)
            bump(entry["layer"], "added")

    for handle in sorted(base, key=lambda h: int(h, 16)):
        if handle not in new:
            entry = _entry(base[handle])
            removed.append(entry)
            bump(entry["layer"], "removed")

    for handle in sorted(set(base) & set(new), key=lambda h: int(h, 16)):
        old_entity, new_entity = base[handle], new[handle]
        entry = _entry(new_entity)
        if old_entity.dxftype() != new_entity.dxftype():
            changes = [
                {"field": "type", "old": old_entity.dxftype(), "new": new_entity.dxftype()}
            ]
        else:
            old_sig = dict(_signature(old_entity) or ())
            new_sig = dict(_signature(new_entity) or ())
            changes = [
                {"field": field, "old": _jsonable(old_sig.get(field)),
                 "new": _jsonable(new_sig.get(field))}
                for field in sorted(set(old_sig) | set(new_sig))
                if old_sig.get(field) != new_sig.get(field)
            ]
        if changes:
            modified.append({**entry, "changes": changes})
            bump(entry["layer"], "modified")
            text_change = next((c for c in changes if c["field"] == "text"), None)
            if text_change is not None:
                texts.append(
                    {"locator": entry["locator"], "layer": entry["layer"],
                     "old": text_change["old"], "new": text_change["new"]}
                )

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "layers": layers,
        "texts": texts,
    }


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)

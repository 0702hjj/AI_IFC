"""Adapt IfcDiff output to the flat diff schema consumed by the web Diff Viewer.

IfcDiff natively reports only booleans per changed element
(``attributes_changed`` etc.) plus a raw DeepDiff for properties. This module
runs IfcDiff with attribute/property relationships only (geometry is never
checked, so representation/geometry noise is excluded by construction) and
then reduces each changed element to attribute-level ``old``/``new`` pairs,
keyed by GlobalId.
"""

from __future__ import annotations

from typing import Any, Dict, List

import ifcopenshell
import ifcopenshell.util.element
from ifcdiff import IfcDiff


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _is_entity_value(value: Any) -> bool:
    if isinstance(value, ifcopenshell.entity_instance):
        return True
    return isinstance(value, tuple) and any(
        isinstance(v, ifcopenshell.entity_instance) for v in value
    )


def _element_changes(
    old: ifcopenshell.entity_instance, new: ifcopenshell.entity_instance
) -> List[Dict[str, Any]]:
    """Attribute/pset-level old->new changes between two versions of an entity.

    Entity-valued attributes (ObjectPlacement, Representation, ...) are
    skipped so geometry-representation internals never leak into the diff.
    """
    changes: List[Dict[str, Any]] = []
    old_info, new_info = old.get_info(), new.get_info()
    for key in sorted(set(old_info) | set(new_info)):
        if key in ("type", "GlobalId"):
            continue
        old_value, new_value = old_info.get(key), new_info.get(key)
        if _is_entity_value(old_value) or _is_entity_value(new_value):
            continue
        if old_value != new_value:
            changes.append(
                {"field": key, "old": _jsonable(old_value), "new": _jsonable(new_value)}
            )
    old_psets = ifcopenshell.util.element.get_psets(old)
    new_psets = ifcopenshell.util.element.get_psets(new)
    for pset_name in sorted(set(old_psets) | set(new_psets)):
        old_props = old_psets.get(pset_name, {})
        new_props = new_psets.get(pset_name, {})
        for prop in sorted((set(old_props) | set(new_props)) - {"id"}):
            old_value, new_value = old_props.get(prop), new_props.get(prop)
            if old_value != new_value:
                changes.append(
                    {
                        "field": f"{pset_name}.{prop}",
                        "old": _jsonable(old_value),
                        "new": _jsonable(new_value),
                    }
                )
    return changes


def compute_diff(old_path: str, new_path: str) -> Dict[str, Any]:
    """Diff two IFC files; return {"added", "removed", "changed"} by GlobalId."""
    old = ifcopenshell.open(old_path)
    new = ifcopenshell.open(new_path)
    differ = IfcDiff(old, new, relationships=["attributes", "property"], is_shallow=False)
    differ.diff()
    changed = []
    for guid in sorted(differ.change_register):
        try:
            old_element = old.by_guid(guid)
            new_element = new.by_guid(guid)
        except RuntimeError:
            continue
        changes = _element_changes(old_element, new_element)
        if changes:
            changed.append({"guid": guid, "changes": changes})
    return {
        "added": sorted(differ.added_elements),
        "removed": sorted(differ.deleted_elements),
        "changed": changed,
    }

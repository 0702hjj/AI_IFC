# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""IFC semantic-fingerprint diff (fallback for external / non-design models).

Path B of the diff engine: when a model has no design JSON provenance (e.g.
externally uploaded IFC), compare two IFC files at the element level by a
lightweight semantic fingerprint instead of raw STEP:

- key: ``Pset_AIIFC.designKey`` when present (link back to design JSON),
  else the GlobalId.
- fingerprint: element type + Name + PredefinedType + property sets.

Two elements are "modified" when their fingerprints differ. This is coarse
(no geometry decomposition) but cheap and stable, and it covers the
design-JSON-diff gap for external files.
"""

from __future__ import annotations

from typing import Any, Dict, List

import ifcopenshell
import ifcopenshell.util.element

# 参与指纹的元素类（排除纯空间/表示基础设施）。
_ELEMENT_TYPES = ("IfcElement", "IfcSpace")


def _fingerprint(model: ifcopenshell.file) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for ifc_type in _ELEMENT_TYPES:
        for e in model.by_type(ifc_type):
            psets = ifcopenshell.util.element.get_psets(e)
            aii = (psets.get("Pset_AIIFC") or {}) if isinstance(psets, dict) else {}
            key = aii.get("designKey") or e.GlobalId
            result[key] = {
                "type": e.is_a(),
                "name": getattr(e, "Name", None),
                "predefined": getattr(e, "PredefinedType", None),
                "psets": {k: v for k, v in psets.items() if k != "Pset_AIIFC"},
            }
    return result


def _entry_diff_key(entry: Dict[str, Any]) -> str:
    return entry.get("name") or entry.get("type") or "?"


def ifc_fingerprint_diff(path_a: str, path_b: str) -> Dict[str, Any]:
    """Element-level semantic diff between two IFC files, keyed by designKey/GlobalId."""
    a = _fingerprint(ifcopenshell.open(path_a))
    b = _fingerprint(ifcopenshell.open(path_b))
    changed: List[Dict[str, Any]] = []
    for key in sorted(a):
        if key not in b:
            changed.append({"key": key, "type": a[key]["type"],
                            "human_label": _entry_diff_key(a[key]), "action": "removed"})
    for key in sorted(b):
        if key not in a:
            changed.append({"key": key, "type": b[key]["type"],
                            "human_label": _entry_diff_key(b[key]), "action": "added"})
    for key in sorted(a):
        if key in b and a[key] != b[key]:
            changes: List[Dict[str, Any]] = []
            for field in sorted(set(a[key]) | set(b[key])):
                if a[key].get(field) != b[key].get(field):
                    changes.append({"field": field, "old": a[key].get(field),
                                    "new": b[key].get(field)})
            changed.append({"key": key, "type": b[key]["type"],
                            "human_label": _entry_diff_key(b[key]), "changes": changes})
    return {"changed": changed,
            "added": sum(1 for c in changed if c.get("action") == "added"),
            "removed": sum(1 for c in changed if c.get("action") == "removed"),
            "modified": sum(1 for c in changed if "changes" in c)}

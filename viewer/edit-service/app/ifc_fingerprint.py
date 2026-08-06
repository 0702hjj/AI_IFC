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

from . import diff_summary

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


def _entry_changes(old: Dict[str, Any], new: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{"field": field, "old": old.get(field), "new": new.get(field)}
            for field in sorted(set(old) | set(new)) if old.get(field) != new.get(field)]


def ifc_fingerprint_diff(path_a: str, path_b: str) -> Dict[str, Any]:
    """Element-level semantic diff between two IFC files, keyed by designKey/GlobalId."""
    a = _fingerprint(ifcopenshell.open(path_a))
    b = _fingerprint(ifcopenshell.open(path_b))
    return diff_summary.summarize_changes(a, b, _entry_diff_key, _entry_changes)

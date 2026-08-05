# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Design-JSON semantic diff between two big versions.

The design JSON is the source of truth; big versions snapshot it
(designs/v{n}.json). This module diffs two snapshots at the semantic level,
keyed by the stable ``key`` of each element (wall/opening/slab/stair):

- an element present only in base → ``removed``
- an element present only in target → ``added``
- an element in both → field-level ``changes`` (old/new)

This is deliberately lightweight and readable ("wall axis end 12→14",
"opening width 1.5→1.8"), unlike per-field IFC audit logs. No per-step
history: only big-version pairs are ever compared.
"""

from __future__ import annotations

from typing import Any, Dict, List

# 参与字段级比较的标量类型；列表/嵌套结构（axis/profile）整体比较。
_SCALAR = (str, int, float, bool)


def _flatten_elements(design: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Collect every design element into {key: {kind, type, data}} across storeys."""
    result: Dict[str, Dict[str, Any]] = {}
    floors = design.get("floors", {})
    for storey_name, floor in floors.items():
        if not isinstance(floor, dict):
            continue
        for kind, ifc_type in (("walls", "IfcWall"), ("openings", None),
                               ("slabs", "IfcSlab"), ("stairs", "IfcStair")):
            for idx, item in enumerate(floor.get(kind, [])):
                if not isinstance(item, dict):
                    continue
                key = item.get("key") or f"{storey_name}:{kind.rstrip('s')}:{idx}"
                data = {k: v for k, v in item.items() if k != "key"}
                result[key] = {
                    "kind": kind.rstrip("s"),
                    "type": ifc_type or _opening_type(item),
                    "storey": storey_name,
                    "data": data,
                }
    return result


def _opening_type(op: Dict[str, Any]) -> str:
    return "IfcDoor" if op.get("type") == "door" else "IfcWindow"


def _human_label(entry: Dict[str, Any]) -> str:
    storey = entry.get("storey", "?")
    kind = entry.get("kind", "?")
    data = entry.get("data", {})
    if kind == "wall" and isinstance(data.get("axis"), list) and len(data["axis"]) >= 2:
        ax = data["axis"]
        return f"{storey} 墙 {len(ax) - 1} 段 @ {ax[0]}→{ax[-1]}"
    if kind == "opening":
        t = "门" if data.get("type") == "door" else "窗"
        return f"{storey} {t} w={data.get('w')}m"
    if kind == "slab":
        return f"{storey} 板"
    if kind == "stair":
        return f"{storey} 楼梯 ({data.get('type', '')})"
    return f"{storey} {kind}"


def _field_changes(old: Dict[str, Any], new: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Field-level old/new for scalar fields; whole-value compare for structures."""
    changes: List[Dict[str, Any]] = []
    for field in sorted(set(old) | set(new)):
        if field in ("key",):
            continue
        ov, nv = old.get(field, "<none>"), new.get(field, "<none>")
        if ov == nv:
            continue
        if isinstance(ov, _SCALAR) and isinstance(nv, _SCALAR):
            changes.append({"field": field, "old": ov, "new": nv})
        elif isinstance(ov, list) and isinstance(nv, list) and len(ov) == len(nv):
            # 结构字段逐点比较（axis/profile），避免整体替换噪声
            for i, (oa, na) in enumerate(zip(ov, nv)):
                if oa != na:
                    changes.append({"field": f"{field}[{i}]", "old": oa, "new": na})
        else:
            changes.append({"field": field, "old": ov, "new": nv})
    return changes


def design_diff(base: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
    """Semantic diff of two design JSONs; keyed by stable element ``key``."""
    b = _flatten_elements(base)
    t = _flatten_elements(target)
    changed: List[Dict[str, Any]] = []
    for key in sorted(b):
        if key not in t:
            changed.append({"key": key, "type": b[key]["type"],
                            "human_label": _human_label(b[key]), "action": "removed"})
    for key in sorted(t):
        if key not in b:
            changed.append({"key": key, "type": t[key]["type"],
                            "human_label": _human_label(t[key]), "action": "added"})
    for key in sorted(b):
        if key in t:
            changes = _field_changes(b[key]["data"], t[key]["data"])
            if changes:
                changed.append({"key": key, "type": t[key]["type"],
                                "human_label": _human_label(t[key]),
                                "changes": changes})
    return {"changed": changed, "added": sum(1 for c in changed if c.get("action") == "added"),
            "removed": sum(1 for c in changed if c.get("action") == "removed"),
            "modified": sum(1 for c in changed if "changes" in c)}

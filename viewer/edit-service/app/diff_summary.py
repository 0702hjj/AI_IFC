# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Shared added/removed/changed summary for keyed item mappings.

Diff engines (ifc_fingerprint; the retired design_diff was the other user)
reduce their inputs to a ``{key: entry}`` mapping where each entry carries
at least a ``"type"`` field, then run the same three-pass comparison:

- key only in base → ``removed``
- key only in target → ``added``
- key in both with non-empty ``changes_fn`` result → modified entry

Callers supply ``label_fn`` (entry → human label) and ``changes_fn``
(old entry, new entry → field-level change list, empty = unmodified).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

LabelFn = Callable[[Dict[str, Any]], str]
ChangesFn = Callable[[Dict[str, Any], Dict[str, Any]], List[Dict[str, Any]]]


def summarize_changes(
    base_items: Dict[str, Dict[str, Any]],
    target_items: Dict[str, Dict[str, Any]],
    label_fn: LabelFn,
    changes_fn: ChangesFn,
) -> Dict[str, Any]:
    """Three-pass added/removed/changed summary over keyed item mappings."""
    changed: List[Dict[str, Any]] = []
    for key in sorted(base_items):
        if key not in target_items:
            changed.append({"key": key, "type": base_items[key]["type"],
                            "human_label": label_fn(base_items[key]), "action": "removed"})
    for key in sorted(target_items):
        if key not in base_items:
            changed.append({"key": key, "type": target_items[key]["type"],
                            "human_label": label_fn(target_items[key]), "action": "added"})
    for key in sorted(base_items):
        if key in target_items:
            changes = changes_fn(base_items[key], target_items[key])
            if changes:
                changed.append({"key": key, "type": target_items[key]["type"],
                                "human_label": label_fn(target_items[key]),
                                "changes": changes})
    return {"changed": changed,
            "added": sum(1 for c in changed if c.get("action") == "added"),
            "removed": sum(1 for c in changed if c.get("action") == "removed"),
            "modified": sum(1 for c in changed if "changes" in c)}

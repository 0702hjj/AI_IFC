# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Map diff payloads to structured user modification events.

Events use the edit-service user-edits schema: ``guid`` (IFC GlobalId or a
``dxf:<layer>/<type>/<handle>`` locator), a human-readable ``name``, ``kind``
(added/removed/modified) and field-level ``changes`` with oldValue/newValue.
The edit-service stamps ``provenance={"source": "USER", "origin": ...}``
when the events are appended to the change log.
"""

from __future__ import annotations

from typing import Any, Dict, List


def ifc_diff_to_events(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert a diff/upload (or version diff) payload to user edit events."""
    labels = payload.get("labels", {})

    def name_of(guid: str) -> str:
        return labels.get(guid, {}).get("name", "")

    events: List[Dict[str, Any]] = []
    for guid in payload.get("added", []):
        events.append({"guid": guid, "name": name_of(guid), "kind": "added", "changes": []})
    for guid in payload.get("removed", []):
        events.append({"guid": guid, "name": name_of(guid), "kind": "removed", "changes": []})
    for item in payload.get("changed", []):
        changes = [
            {"field": c["field"], "oldValue": c["old"], "newValue": c["new"]}
            for c in item["changes"]
        ]
        events.append(
            {"guid": item["guid"], "name": name_of(item["guid"]),
             "kind": "modified", "changes": changes}
        )
    return events


def dxf_diff_to_events(diff: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert a dxf_diff payload to user edit events (one per entity)."""
    events: List[Dict[str, Any]] = []
    for entry in diff.get("added", []):
        events.append(
            {"guid": entry["locator"], "name": entry["layer"],
             "kind": "added", "changes": []}
        )
    for entry in diff.get("removed", []):
        events.append(
            {"guid": entry["locator"], "name": entry["layer"],
             "kind": "removed", "changes": []}
        )
    for entry in diff.get("modified", []):
        changes = [
            {"field": c["field"], "oldValue": c["old"], "newValue": c["new"]}
            for c in entry["changes"]
        ]
        events.append(
            {"guid": entry["locator"], "name": entry["layer"],
             "kind": "modified", "changes": changes}
        )
    return events

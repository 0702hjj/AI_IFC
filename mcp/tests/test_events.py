# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""User-edit event mapping: diff payloads -> structured USER modification events."""

from __future__ import annotations

from app.events import dxf_diff_to_events, ifc_diff_to_events

IFC_DIFF = {
    "base": "current",
    "target": "upload",
    "added": ["guid-added"],
    "removed": ["guid-removed"],
    "changed": [
        {
            "guid": "guid-changed",
            "changes": [{"field": "Name", "old": "旧", "new": "新"}],
        }
    ],
    "labels": {
        "guid-added": {"name": "新墙", "type": "IfcWall"},
        "guid-removed": {"name": "旧窗", "type": "IfcWindow"},
        "guid-changed": {"name": "用户改的墙", "type": "IfcWall"},
    },
}


def test_ifc_diff_to_events_kinds_and_labels() -> None:
    events = {e["guid"]: e for e in ifc_diff_to_events(IFC_DIFF)}
    assert events["guid-added"]["kind"] == "added"
    assert events["guid-added"]["name"] == "新墙"
    assert events["guid-added"]["changes"] == []
    assert events["guid-removed"]["kind"] == "removed"
    assert events["guid-removed"]["name"] == "旧窗"
    changed = events["guid-changed"]
    assert changed["kind"] == "modified"
    assert changed["changes"] == [
        {"field": "Name", "oldValue": "旧", "newValue": "新"}
    ]


def test_ifc_diff_to_events_missing_labels_fall_back() -> None:
    payload = {**IFC_DIFF, "labels": {}}
    events = {e["guid"]: e for e in ifc_diff_to_events(payload)}
    assert events["guid-added"]["name"] == ""


def test_dxf_diff_to_events() -> None:
    diff = {
        "added": [
            {"locator": "dxf:WALLS/CIRCLE/A1", "layer": "WALLS", "type": "CIRCLE", "handle": "A1"}
        ],
        "removed": [
            {"locator": "dxf:WALLS/LINE/B2", "layer": "WALLS", "type": "LINE", "handle": "B2"}
        ],
        "modified": [
            {
                "locator": "dxf:WALLS/LINE/C3",
                "layer": "WALLS",
                "type": "LINE",
                "handle": "C3",
                "changes": [{"field": "end", "old": [10.0, 0.0], "new": [12.0, 0.0]}],
            }
        ],
        "layers": {},
        "texts": [],
    }
    events = {e["guid"]: e for e in dxf_diff_to_events(diff)}
    assert events["dxf:WALLS/CIRCLE/A1"]["kind"] == "added"
    assert events["dxf:WALLS/LINE/B2"]["kind"] == "removed"
    modified = events["dxf:WALLS/LINE/C3"]
    assert modified["kind"] == "modified"
    assert modified["name"] == "WALLS"
    assert modified["changes"] == [
        {"field": "end", "oldValue": [10.0, 0.0], "newValue": [12.0, 0.0]}
    ]

# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""DXF layer/entity-level comparison tests (fixture-driven)."""

from __future__ import annotations

from app.dxf_diff import dxf_diff


def _by_type(entries, dxftype):
    return [e for e in entries if e["type"] == dxftype]


def test_dxf_diff_detects_add_remove_modify(dxf_pair) -> None:
    base, modified = dxf_pair
    diff = dxf_diff(str(base), str(modified))

    added = _by_type(diff["added"], "CIRCLE")
    assert len(added) == 1
    assert added[0]["layer"] == "WALLS"
    assert added[0]["locator"].startswith("dxf:WALLS/CIRCLE/")

    removed = _by_type(diff["removed"], "LINE")
    assert len(removed) == 1

    changed = _by_type(diff["modified"], "LINE")
    assert len(changed) == 1
    end_change = next(c for c in changed[0]["changes"] if c["field"] == "end")
    assert end_change["old"] == [10.0, 0.0, 0.0]
    assert end_change["new"] == [12.0, 0.0, 0.0]


def test_dxf_diff_layer_stats(dxf_pair) -> None:
    base, modified = dxf_pair
    diff = dxf_diff(str(base), str(modified))
    assert diff["layers"]["WALLS"] == {"added": 1, "removed": 1, "modified": 1}
    assert diff["layers"]["TEXT"] == {"added": 0, "removed": 0, "modified": 1}


def test_dxf_diff_text_annotation_changes(dxf_pair) -> None:
    base, modified = dxf_pair
    diff = dxf_diff(str(base), str(modified))
    assert len(diff["texts"]) == 1
    text = diff["texts"][0]
    assert text["old"] == "客厅"
    assert text["new"] == "主卧"
    assert text["layer"] == "TEXT"


def test_dxf_diff_identical_files_are_empty(dxf_pair) -> None:
    base, _ = dxf_pair
    diff = dxf_diff(str(base), str(base))
    assert diff["added"] == [] and diff["removed"] == [] and diff["modified"] == []
    assert diff["texts"] == []

# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Unit tests for the shared added/removed/changed summary (diff_summary)."""

from __future__ import annotations

import pytest

from app import diff_summary


def _label(entry):
    return entry.get("label", entry["type"])


def _changes(old, new):
    return [{"field": f, "old": old.get(f), "new": new.get(f)}
            for f in sorted(set(old) | set(new)) if old.get(f) != new.get(f)]


class TestSummarizeChanges:
    @pytest.mark.parametrize("base,target,added,removed,modified", [
        ({}, {}, 0, 0, 0),
        ({"a": {"type": "T", "v": 1}}, {"a": {"type": "T", "v": 1}}, 0, 0, 0),
        ({"a": {"type": "T", "v": 1}}, {}, 0, 1, 0),
        ({}, {"a": {"type": "T", "v": 1}}, 1, 0, 0),
        ({"a": {"type": "T", "v": 1}}, {"a": {"type": "T", "v": 2}}, 0, 0, 1),
        ({"a": {"type": "T"}, "b": {"type": "T", "v": 1}},
         {"b": {"type": "T", "v": 2}, "c": {"type": "T"}}, 1, 1, 1),
    ])
    def test_counts(self, base, target, added, removed, modified):
        r = diff_summary.summarize_changes(base, target, _label, _changes)
        assert r["added"] == added
        assert r["removed"] == removed
        assert r["modified"] == modified
        assert len(r["changed"]) == added + removed + modified

    def test_entry_shapes_and_labels(self):
        base = {"r": {"type": "Wall", "label": "旧墙", "v": 1},
                "m": {"type": "Slab", "label": "旧板", "v": 1}}
        target = {"m": {"type": "Slab", "label": "新板", "v": 2},
                  "a": {"type": "Door", "label": "新门"}}
        r = diff_summary.summarize_changes(base, target, _label, _changes)
        by_key = {c["key"]: c for c in r["changed"]}
        assert by_key["r"] == {"key": "r", "type": "Wall",
                               "human_label": "旧墙", "action": "removed"}
        assert by_key["a"] == {"key": "a", "type": "Door",
                               "human_label": "新门", "action": "added"}
        mod = by_key["m"]
        assert mod["type"] == "Slab" and mod["human_label"] == "新板"
        assert mod["changes"] == [
            {"field": "label", "old": "旧板", "new": "新板"},
            {"field": "v", "old": 1, "new": 2},
        ]
        assert "action" not in mod

    def test_modified_uses_target_type_and_label(self):
        base = {"k": {"type": "OldType", "label": "old", "v": 1}}
        target = {"k": {"type": "NewType", "label": "new", "v": 1}}
        r = diff_summary.summarize_changes(base, target, _label, _changes)
        mod = r["changed"][0]
        assert mod["type"] == "NewType" and mod["human_label"] == "new"

    def test_no_field_changes_means_unmodified(self):
        # changes_fn 返回空列表的 key 不出现在结果中
        base = {"k": {"type": "T", "v": 1}}
        target = {"k": {"type": "T", "v": 1}}
        r = diff_summary.summarize_changes(base, target, _label, _changes)
        assert r["changed"] == []

    def test_sorted_output_order(self):
        base = {"z": {"type": "T"}, "b": {"type": "T"}, "m": {"type": "T"}}
        target = {"m": {"type": "T"}, "y": {"type": "T"}, "a": {"type": "T"}}
        r = diff_summary.summarize_changes(base, target, _label, _changes)
        keys = [c["key"] for c in r["changed"]]
        # removed (sorted base-only) → added (sorted target-only) → modified
        assert keys == ["b", "z", "a", "y"]

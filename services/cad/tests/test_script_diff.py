# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Script diff tests (pure helpers; HTTP endpoints land in Task 4)."""

from __future__ import annotations

from app import script_diff

SCRIPT_A = (
    'PARAMS = {"width": 12.0, "height": 3.0, "name": "a"}\n'
    "\n"
    "def build(params, out_path):\n"
    "    open(out_path, 'w').write('DXF:' + str(params['width']))\n"
    "\n"
    'if __name__ == "__main__":\n'
    "    import sys\n"
    "    build(PARAMS, sys.argv[1])\n"
)

# width 改、name 删、depth 增
SCRIPT_B = (
    'PARAMS = {"width": 14.0, "height": 3.0, "depth": 8.0}\n'
    "\n"
    "def build(params, out_path):\n"
    "    open(out_path, 'w').write('DXF:' + str(params['width']))\n"
    "\n"
    'if __name__ == "__main__":\n'
    "    import sys\n"
    "    build(PARAMS, sys.argv[1])\n"
)

NO_PARAMS_SCRIPT = "x = 1\n"


class TestTextDiff:
    def test_unified_diff_marks_changed_lines(self):
        r = script_diff.diff_scripts(SCRIPT_A, SCRIPT_B, "v1", "v2")
        text = r["text_diff"]
        assert "--- v1" in text and "+++ v2" in text
        assert '-PARAMS = {"width": 12.0, "height": 3.0, "name": "a"}' in text
        assert '+PARAMS = {"width": 14.0, "height": 3.0, "depth": 8.0}' in text
        assert r["stats"] == {"added": 1, "removed": 1}

    def test_identical_scripts_empty_diff(self):
        r = script_diff.diff_scripts(SCRIPT_A, SCRIPT_A, "v1", "v1")
        assert r["text_diff"] == ""
        assert r["stats"] == {"added": 0, "removed": 0}
        assert r["params_changes"] == []


class TestParamsChanges:
    def test_added_removed_modified_keys(self):
        changes = script_diff.params_changes(SCRIPT_A, SCRIPT_B)
        by_key = {c["key"]: c for c in changes}
        assert set(by_key) == {"width", "name", "depth"}
        assert by_key["width"] == {"key": "width", "action": "modified",
                                   "old": 12.0, "new": 14.0}
        assert by_key["name"] == {"key": "name", "action": "removed", "old": "a"}
        assert by_key["depth"] == {"key": "depth", "action": "added", "new": 8.0}

    def test_missing_params_block_treated_as_empty(self):
        assert script_diff.params_changes(NO_PARAMS_SCRIPT, SCRIPT_A) == [
            {"key": "height", "action": "added", "new": 3.0},
            {"key": "name", "action": "added", "new": "a"},
            {"key": "width", "action": "added", "new": 12.0},
        ]
        assert script_diff.params_changes(NO_PARAMS_SCRIPT, NO_PARAMS_SCRIPT) == []

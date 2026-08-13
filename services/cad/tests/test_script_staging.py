# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Script staging buffer tests (WPS-style undo/redo ring buffer).

Pure ``ScriptStaging`` semantics only; the HTTP staging endpoints
(PUT/undo/redo/discard/run/save/rollback) land in Task 4 with routes_scripts.
"""

from __future__ import annotations

from app import script_staging


class TestScriptStagingBuffer:
    def test_push_undo_redo(self):
        st = script_staging.ScriptStaging(model_id="m")
        st.push("v-a")
        st.push("v-b")
        st.push("v-c")
        assert st.current() == "v-c"
        assert st.undo() and st.current() == "v-b"
        assert st.undo() and st.current() == "v-a"
        assert st.undo() and st.current() is None  # back to (empty) base
        assert not st.undo()
        assert st.redo() and st.current() == "v-a"
        assert st.redo() and st.redo() and st.current() == "v-c"
        assert not st.redo()

    def test_new_edit_drops_redo_tail(self):
        st = script_staging.ScriptStaging(model_id="m")
        st.push("a")
        st.push("b")
        st.undo()
        st.push("z")
        assert st.current() == "z"
        assert not st.can_redo()
        assert st.staged_count() == 2

    def test_max_steps_ring_buffer(self):
        st = script_staging.ScriptStaging(model_id="m")
        for i in range(15):
            st.push(f"s{i}")
        assert len(st.history) == script_staging.MAX_STEPS
        assert st.current() == "s14"
        steps_back = 0
        while st.undo():
            steps_back += 1
        assert steps_back == script_staging.MAX_STEPS

    def test_discard_and_save(self):
        st = script_staging.ScriptStaging(model_id="m")
        st.push("a")
        st.push("b")
        assert st.discard() == 2
        assert st.current() is None
        st.push("c")
        st.save()
        assert st.base == "c"
        assert st.staged_count() == 0

    def test_base_seed(self):
        st = script_staging.ScriptStaging(model_id="m", base="seed")
        assert st.current() == "seed"
        st.push("edit")
        st.undo()
        assert st.current() == "seed"

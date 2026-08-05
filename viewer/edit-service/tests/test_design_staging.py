# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Design staging + big-version save/rollback endpoints."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from app import design_staging, design_versions
from tests.conftest import MODEL_ID


def _design(**overrides):
    d = {"meta": {"name": "t"}, "frame": {"storeys": {"1F": 0.0}}, "floors": {}}
    d.update(overrides)
    return d


class TestDesignStagingBuffer:
    def test_push_undo_redo(self):
        st = design_staging.DesignStaging(model_id="m")
        d0 = _design()
        st.push({**d0, "a": 1})
        st.push({**d0, "a": 2})
        st.push({**d0, "a": 3})
        assert st.current()["a"] == 3
        assert st.undo() and st.current()["a"] == 2
        assert st.undo() and st.current()["a"] == 1
        assert st.undo() and "a" not in st.current()   # back to base
        assert not st.undo()                            # already at base
        assert st.redo() and st.current()["a"] == 1
        assert st.redo() and st.current()["a"] == 2
        assert st.redo() and st.current()["a"] == 3
        assert not st.redo()

    def test_new_edit_drops_redo_tail(self):
        st = design_staging.DesignStaging(model_id="m")
        d0 = _design()
        st.push({**d0, "a": 1})
        st.push({**d0, "a": 2})
        st.undo()
        st.push({**d0, "a": 99})     # invalidates redo tail
        assert st.current()["a"] == 99
        assert not st.can_redo()
        assert st.staged_count() == 2

    def test_max_steps_ring_buffer(self):
        st = design_staging.DesignStaging(model_id="m")
        d0 = _design()
        for i in range(15):
            st.push({**d0, "a": i})
        assert len(st.history) == design_staging.MAX_STEPS
        assert st.current()["a"] == 14
        # oldest 5 dropped; walk back to base (9 steps) then stop
        steps_back = 0
        while st.undo():
            steps_back += 1
        assert steps_back == design_staging.MAX_STEPS

    def test_discard_and_save(self):
        st = design_staging.DesignStaging(model_id="m")
        d0 = _design()
        st.push({**d0, "a": 1})
        st.push({**d0, "a": 2})
        assert st.discard() == 2
        assert st.current() == st.base
        st.push({**d0, "a": 3})
        st.save()
        assert st.base["a"] == 3
        assert st.staged_count() == 0


class TestDesignEndpoints:
    def test_stage_undo_redo_discard(self, client: TestClient):
        r = client.get(f"/models/{MODEL_ID}/design")
        assert r.status_code == 200
        body = r.json()
        assert body["staged"] == 0 and body["canUndo"] is False

        client.put(f"/models/{MODEL_ID}/design", json={"design": _design(a=1)})
        client.put(f"/models/{MODEL_ID}/design", json={"design": _design(a=2)})
        r = client.post(f"/models/{MODEL_ID}/design/undo")
        assert r.json()["design"]["a"] == 1
        r = client.post(f"/models/{MODEL_ID}/design/redo")
        assert r.json()["design"]["a"] == 2

        r = client.post(f"/models/{MODEL_ID}/design/discard")
        assert r.json()["discarded"] == 2
        assert client.get(f"/models/{MODEL_ID}/design").json()["staged"] == 0

    def test_save_creates_big_version_pair(self, client: TestClient, data_dir: Path):
        client.put(f"/models/{MODEL_ID}/design", json={"design": _design(a=1), "note": "v1"})
        r = client.post(f"/models/{MODEL_ID}/design/save", json={"note": "first"})
        assert r.status_code == 200
        version = r.json()["version"]
        assert version == "v1"

        # both design JSON and IFC snapshots exist
        assert design_versions.design_path(str(data_dir), MODEL_ID, "v1")
        assert os.path.isfile(f"{data_dir}/models/{MODEL_ID}/versions/v1.ifc")
        payload = json.loads(
            (data_dir / "models" / MODEL_ID / "designs" / "v1.json").read_text()
        )
        assert payload["design"]["a"] == 1 and payload["note"] == "first"

        # staging cleared after save
        assert client.get(f"/models/{MODEL_ID}/design").json()["staged"] == 0

    def test_rollback_restores_design(self, client: TestClient):
        client.put(f"/models/{MODEL_ID}/design", json={"design": _design(a=1)})
        client.post(f"/models/{MODEL_ID}/design/save")
        client.put(f"/models/{MODEL_ID}/design", json={"design": _design(a=2)})
        r = client.post(f"/models/{MODEL_ID}/design/rollback", json={"version": "v1"})
        assert r.status_code == 200
        assert r.json()["design"]["a"] == 1

    def test_list_designs(self, client: TestClient):
        client.put(f"/models/{MODEL_ID}/design", json={"design": _design(a=1)})
        client.post(f"/models/{MODEL_ID}/design/save")
        r = client.get(f"/models/{MODEL_ID}/designs")
        designs = r.json()["designs"]
        assert [d["version"] for d in designs] == ["v1"]
        assert r.json()["versions"][0]["version"] == "v1"

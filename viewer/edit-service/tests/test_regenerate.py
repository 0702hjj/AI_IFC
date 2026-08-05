# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Regenerate endpoint: design JSON → derived IFC via the aiifc build pipeline."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from tests.conftest import MODEL_ID


def _design():
    return {
        "meta": {"name": "t"},
        "frame": {
            "footprint": [[0, 0], [6, 0], [6, 4], [0, 4]],
            "storeys": {"1F": 0.0},
        },
        "floors": {
            "1F": {
                "walls": [
                    {"axis": [[0, 0], [6, 0]], "t": 0.2, "kind": "ext", "key": "1F:wall:0"},
                ],
                "openings": [
                    {"wall": 0, "along": 3.0, "w": 1.0, "h": 2.0, "sill": 0.0,
                     "type": "door", "key": "1F:opening:0"},
                ],
                "slabs": [{"t": 0.15, "key": "1F:slab:0"}],
            }
        },
    }


class TestRegenerate:
    def test_regenerate_writes_ifc(self, client: TestClient, data_dir):
        client.put(f"/models/{MODEL_ID}/design", json={"design": _design()})
        r = client.post(f"/models/{MODEL_ID}/design/regenerate")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["walls"] == 1 and body["openings"] == 1 and body["slabs"] == 1
        ifc = f"{data_dir}/uploads/{MODEL_ID}.ifc"
        assert os.path.isfile(ifc)
        assert os.path.getsize(ifc) > 0

        # deterministic GlobalId written
        import ifcopenshell
        m = ifcopenshell.open(ifc)
        wall = m.by_type("IfcWall")[0]
        assert len(wall.GlobalId) == 22
        import ifcopenshell.util.element
        ps = ifcopenshell.util.element.get_psets(wall)
        assert ps["Pset_AIIFC"]["designKey"] == "1F:wall:0"

    def test_regenerate_then_save_big_version(self, client: TestClient):
        client.put(f"/models/{MODEL_ID}/design", json={"design": _design()})
        client.post(f"/models/{MODEL_ID}/design/regenerate")
        r = client.post(f"/models/{MODEL_ID}/design/save")
        assert r.status_code == 200
        assert r.json()["version"] == "v1"

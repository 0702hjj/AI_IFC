# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""L1 direct-edit chain retired: the mutation endpoints answer 410 Gone.

Script-as-source (spec 2026-08-08-script-editing-unified-design.md §9): all
editing goes through the build script, so the pending→commit true-edit
surface is permanently retired — 410, not 404, to make the retirement
explicit. The read-only views (``GET .../pending`` / ``GET .../history``)
and the pending-store reset (``DELETE .../pending``, script-run replay
bookkeeping W-0009) survive.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from conftest import MODEL_ID

RETIRED_DETAIL = "direct IFC editing retired: edit the build script (script-as-source)"


@pytest.mark.parametrize(
    "method,path",
    [
        ("PUT", "/models/{id}/entities/g1"),
        ("DELETE", "/models/{id}/entities/g1"),
        ("GET", "/models/{id}/entities/g1/editable-schema"),
        ("POST", "/models/{id}/commit"),
    ],
)
def test_direct_edit_endpoints_gone(client: TestClient, method: str, path: str) -> None:
    r = client.request(method, path.format(id=MODEL_ID), json={})
    assert r.status_code == 410
    assert r.json()["detail"] == RETIRED_DETAIL


def test_retired_even_for_missing_model(client: TestClient) -> None:
    """410 fires before any model lookup: retirement is unconditional."""
    r = client.post("/models/m_ffffffffffffffff/commit", json={})
    assert r.status_code == 410
    assert r.json()["detail"] == RETIRED_DETAIL


def test_readonly_and_pending_store_endpoints_survive(client: TestClient) -> None:
    resp = client.get(f"/models/{MODEL_ID}/pending")
    assert resp.status_code == 200
    assert resp.json() == []
    resp = client.get(f"/models/{MODEL_ID}/history")
    assert resp.status_code == 200
    assert resp.json() == []
    resp = client.delete(f"/models/{MODEL_ID}/pending")
    assert resp.status_code == 200
    assert resp.json() == {"discarded": 0}

# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""EditServiceClient tests against a fake transport."""

from __future__ import annotations

import pytest

from app.client import EditServiceClient, EditServiceError
from conftest import MODEL_ID, FakeEditService


def _client(fake: FakeEditService) -> EditServiceClient:
    return EditServiceClient("http://fake", transport=fake.transport)


def test_diff_upload_posts_multipart(fake: FakeEditService, tmp_path) -> None:
    fake.add("POST", f"/models/{MODEL_ID}/diff/upload", {"added": [], "removed": [], "changed": [], "labels": {}})
    path = tmp_path / "m.ifc"
    path.write_bytes(b"ISO-10303-21;")
    payload = _client(fake).diff_upload(MODEL_ID, str(path))
    assert payload["added"] == []
    assert fake.requests[0]["path"] == f"/models/{MODEL_ID}/diff/upload"


def test_post_user_edits_sends_origin_and_events(fake: FakeEditService) -> None:
    fake.add("POST", f"/models/{MODEL_ID}/user-edits", {"appended": 1, "entries": []})
    events = [{"guid": "g", "name": "", "kind": "modified", "changes": []}]
    _client(fake).post_user_edits(MODEL_ID, "ifc-upload", events, author="designer-1")
    sent = fake.requests[0]["json"]
    assert sent["origin"] == "ifc-upload"
    assert sent["author"] == "designer-1"
    assert sent["events"] == events


def test_error_status_raises_with_detail(fake: FakeEditService) -> None:
    fake.add("GET", f"/models/{MODEL_ID}/versions", {"detail": "model not found"}, status=404)
    with pytest.raises(EditServiceError) as excinfo:
        _client(fake).versions(MODEL_ID)
    assert excinfo.value.status == 404
    assert "model not found" in str(excinfo.value)


def test_allow_404_returns_none(fake: FakeEditService) -> None:
    client = _client(fake)
    assert client.script_diff(MODEL_ID, "v1", "v2") is None
    assert client.get_script(MODEL_ID) is None

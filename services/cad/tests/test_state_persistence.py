# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Staging persistence: the WPS-style staging buffer is written to
``models/{id}/script_staging.json`` on every mutation and restored by a fresh
app instance (restart recovery).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app

from tests.conftest import MODEL_ID
from tests.test_routes_scripts import GOOD_SCRIPT, GOOD_SCRIPT_V2

BASE = f"/models/{MODEL_ID}"


def _staging_file(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "script_staging.json"


def test_staging_persisted_to_disk(client, data_dir):
    client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
    payload = json.loads(_staging_file(data_dir).read_text(encoding="utf-8"))
    assert payload["modelId"] == MODEL_ID
    assert payload["history"] == [GOOD_SCRIPT]
    assert payload["cursor"] == 0


def test_staging_restored_after_restart(client, data_dir):
    client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
    client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT_V2})
    client.post(f"{BASE}/script/undo")

    # 新 app 实例（新 StagingRegistry，内存为空）从磁盘恢复 staging。
    restarted = TestClient(create_app())
    got = restarted.get(f"{BASE}/script")
    assert got.status_code == 200
    body = got.json()
    assert body["script"] == GOOD_SCRIPT  # undo 后的游标位置
    assert body["staged"] == 1
    assert body["canRedo"] is True

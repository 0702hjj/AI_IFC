# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""bootstrap.dxf preservation: the original upload is snapshotted on the first
script stage and survives later runs/saves.

Unlike services/ifc, the save response carries no ``alignment`` field (chunk A
decision — bootstrap-vs-generated diff counts are not computed here); this
file only asserts the bootstrap artifact itself is preserved.
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import MODEL_ID
from tests.test_routes_scripts import GOOD_SCRIPT

BASE = f"/models/{MODEL_ID}"


def _bootstrap(data_dir: Path) -> Path:
    return data_dir / "models" / MODEL_ID / "bootstrap.dxf"


def _upload(data_dir: Path) -> Path:
    return data_dir / "uploads" / f"{MODEL_ID}.dxf"


def test_bootstrap_dxf_preserved_on_first_stage(client, data_dir):
    original = _upload(data_dir).read_bytes()
    assert not _bootstrap(data_dir).exists()
    resp = client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
    assert resp.status_code == 200
    assert _bootstrap(data_dir).read_bytes() == original


def test_bootstrap_not_overwritten_by_later_stages(client, data_dir):
    client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
    first = _bootstrap(data_dir).read_bytes()
    client.put(f"{BASE}/script", json={"params": {"length": 42}})
    assert _bootstrap(data_dir).read_bytes() == first


def test_bootstrap_dxf_survives_run_and_save(client, data_dir):
    original = _upload(data_dir).read_bytes()
    client.put(f"{BASE}/script", json={"script": GOOD_SCRIPT})
    client.post(f"{BASE}/script/run")
    resp = client.post(f"{BASE}/script/save")
    assert resp.status_code == 200
    assert "alignment" not in resp.json()
    # run/save 覆盖了 uploads，但 bootstrap 仍是上传原件
    assert _upload(data_dir).read_bytes() != original
    assert _bootstrap(data_dir).read_bytes() == original

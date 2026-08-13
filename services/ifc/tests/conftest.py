# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Shared fixtures: copy the sample IFC into tmp_path so tests never touch the repo fixture."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

FIXTURE_IFC = (
    Path(__file__).resolve().parents[3]
    / "converter"
    / "test"
    / "fixtures"
    / "wall-with-opening-and-window.ifc"
)

MODEL_ID = "m_0123456789abcdef"


@pytest.fixture()
def ifc_path(tmp_path: Path) -> Path:
    """Copy the sample IFC fixture into a tmp dir and return its path."""
    dst = tmp_path / "model.ifc"
    shutil.copy(FIXTURE_IFC, dst)
    return dst


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    """Viewer data dir with the fixture IFC registered under MODEL_ID."""
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    dst = uploads / f"{MODEL_ID}.ifc"
    dst.write_bytes(FIXTURE_IFC.read_bytes())
    return tmp_path


@pytest.fixture()
def client(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("VIEWER_DATA_DIR", str(data_dir))
    return TestClient(create_app())

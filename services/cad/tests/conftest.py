# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Shared fixtures: build a sample DXF (LINE + CIRCLE with XDATA keys) in tmp_path."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import ezdxf
import pytest
from fastapi.testclient import TestClient

FLOWS_DIR = Path(__file__).resolve().parents[1] / "flows"
sys.path.insert(0, str(FLOWS_DIR))

import cad_script_lib  # noqa: E402

from app.main import create_app  # noqa: E402

# W-0047 fail-closed：CI/本地无 bwrap 时测试仍走 rlimit 降级路径（显式放行）。
# TestRlimitFailClosed 用 monkeypatch 覆盖该开关的两态。
os.environ.setdefault("ALLOW_RLIMIT_FALLBACK", "1")

MODEL_ID = "m_0123456789abcdef"


@pytest.fixture()
def dxf_path(tmp_path: Path) -> Path:
    """Create a sample DXF (one LINE + one CIRCLE, XDATA keys via cad_script_lib)."""
    cad_script_lib.reset_state()
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    cad_script_lib.add_entity(msp, "LINE", start=(0, 0), end=(10, 0))
    cad_script_lib.add_entity(msp, "CIRCLE", center=(5, 5), radius=2)
    dst = tmp_path / "model.dxf"
    doc.saveas(dst)
    return dst


@pytest.fixture()
def data_dir(tmp_path: Path, dxf_path: Path) -> Path:
    """Viewer data dir with models/ and the fixture DXF uploaded under MODEL_ID."""
    (tmp_path / "models").mkdir()
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    shutil.copy(dxf_path, uploads / f"{MODEL_ID}.dxf")
    return tmp_path


@pytest.fixture()
def client(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("VIEWER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("AIDXF_FLOWS_DIR", str(FLOWS_DIR))
    return TestClient(create_app())

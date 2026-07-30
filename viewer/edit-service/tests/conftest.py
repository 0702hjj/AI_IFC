"""Shared fixtures: copy the sample IFC into tmp_path so tests never touch the repo fixture."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURE_IFC = (
    Path(__file__).resolve().parents[2]
    / "converter"
    / "test"
    / "fixtures"
    / "wall-with-opening-and-window.ifc"
)


@pytest.fixture()
def ifc_path(tmp_path: Path) -> Path:
    """Copy the sample IFC fixture into a tmp dir and return its path."""
    dst = tmp_path / "model.ifc"
    shutil.copy(FIXTURE_IFC, dst)
    return dst

# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Environment-based configuration for the CAD edit service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Runtime settings resolved from environment variables."""

    port: int = 8200
    data_dir: str = "../data"
    flows_dir: str = "../../skills/aidxfv/v1/scripts/flows"
    max_models: int = 8
    diff_timeout_s: int = 60


def _resolve_path(value: str, anchor: Path) -> str:
    """Resolve a possibly-relative path against the app package location (not cwd)."""
    p = Path(value)
    return str(p.resolve()) if p.is_absolute() else str((anchor / p).resolve())


def load_settings() -> Settings:
    """Build Settings from env (CAD_SERVICE_PORT, VIEWER_DATA_DIR, AIDXF_FLOWS_DIR, CAD_SERVICE_MAX_MODELS, CAD_SERVICE_DIFF_TIMEOUT_S)."""
    anchor = Path(__file__).resolve().parent.parent  # edit-service root
    data_dir = os.environ.get("VIEWER_DATA_DIR", "../data")
    flows_dir = os.environ.get(
        "AIDXF_FLOWS_DIR", "../../skills/aidxfv/v1/scripts/flows"
    )
    return Settings(
        port=int(os.environ.get("CAD_SERVICE_PORT", "8200")),
        data_dir=data_dir,
        flows_dir=_resolve_path(flows_dir, anchor),
        max_models=int(os.environ.get("CAD_SERVICE_MAX_MODELS", "8")),
        diff_timeout_s=int(os.environ.get("CAD_SERVICE_DIFF_TIMEOUT_S", "60")),
    )

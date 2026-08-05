# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Environment-based configuration for the edit service."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime settings resolved from environment variables."""

    port: int = 8100
    data_dir: str = "../data"
    flows_dir: str = "../../skills/aiifc/references/docs/flows"


def load_settings() -> Settings:
    """Build Settings from env (EDIT_SERVICE_PORT, VIEWER_DATA_DIR, AIIFC_FLOWS_DIR)."""
    return Settings(
        port=int(os.environ.get("EDIT_SERVICE_PORT", "8100")),
        data_dir=os.environ.get("VIEWER_DATA_DIR", "../data"),
        flows_dir=os.environ.get("AIIFC_FLOWS_DIR", "../../skills/aiifc/references/docs/flows"),
    )

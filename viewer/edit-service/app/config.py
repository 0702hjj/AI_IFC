"""Environment-based configuration for the edit service."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime settings resolved from environment variables."""

    port: int = 8100
    data_dir: str = "../data"


def load_settings() -> Settings:
    """Build Settings from env (EDIT_SERVICE_PORT, VIEWER_DATA_DIR)."""
    return Settings(
        port=int(os.environ.get("EDIT_SERVICE_PORT", "8100")),
        data_dir=os.environ.get("VIEWER_DATA_DIR", "../data"),
    )

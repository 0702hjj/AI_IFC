# SPDX-License-Identifier: Apache-2.0
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
    flows_dir: str = "flows"
    drawlib_dir: str = ""  # 共享画法层（archdxf + dxfkit 的 src 目录，冒号分隔多路径）；空=不注入
    max_models: int = 8
    diff_timeout_s: int = 60


def _resolve_path(value: str, anchor: Path) -> str:
    """Resolve a possibly-relative path against the app package location (not cwd)."""
    p = Path(value)
    return str(p.resolve()) if p.is_absolute() else str((anchor / p).resolve())


def load_settings() -> Settings:
    """Build Settings from env (CAD_SERVICE_PORT, VIEWER_DATA_DIR, AIDXF_FLOWS_DIR, AIDXF_DRAWLIB_DIR, CAD_SERVICE_MAX_MODELS, CAD_SERVICE_DIFF_TIMEOUT_S)."""
    anchor = Path(__file__).resolve().parent.parent  # edit-service root
    data_dir = os.environ.get("VIEWER_DATA_DIR", "../data")
    flows_dir = os.environ.get("AIDXF_FLOWS_DIR", "flows")
    # 共享画法层：archdxf + dxfkit 的 src 目录（冒号分隔，缺省推导 skill **源**目录的 packages src）。
    # 单一事实源——skill editable install 与本沙箱 PYTHONPATH 引用同一份源码。
    # 注意：缺省从 skills/aidxf/（git 跟踪）推导，不从 skills/dist/（打包产物，gitignored，
    # CI 干净克隆无 dist）。CI/宿主未生成 dist 也能跑。
    drawlib_dir = os.environ.get("AIDXF_DRAWLIB_DIR", "")
    if not drawlib_dir:
        repo = anchor.parent.parent  # services/cad -> services -> repo root
        default_drawlib = [
            repo / "skills" / "aidxf" / "scripts" / "packages" / "archdxf" / "src",
            repo / "skills" / "aidxf" / "scripts" / "packages" / "dxfkit" / "src",
        ]
        drawlib_dir = ":".join(str(p) for p in default_drawlib if p.is_dir())
    return Settings(
        port=int(os.environ.get("CAD_SERVICE_PORT", "8200")),
        data_dir=data_dir,
        flows_dir=_resolve_path(flows_dir, anchor),
        drawlib_dir=drawlib_dir,
        max_models=int(os.environ.get("CAD_SERVICE_MAX_MODELS", "8")),
        diff_timeout_s=int(os.environ.get("CAD_SERVICE_DIFF_TIMEOUT_S", "60")),
    )

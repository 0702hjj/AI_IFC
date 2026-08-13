# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Cross-route request helpers: single-point definitions.

AGENTS.md「校验与业务隔离」§3: request-shape helpers shared by route
modules are defined here exactly once — route files import, never redefine.
"""

from __future__ import annotations

import os

from fastapi import HTTPException, Request

MODEL_ID_PATTERN = r"^m_[0-9a-f]{16}$"


def model_upload_path(request: Request, model_id: str) -> str:
    """uploads/{id}.ifc path; 404 when the model upload does not exist."""
    path = os.path.join(
        request.app.state.settings.data_dir, "uploads", f"{model_id}.ifc"
    )
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="model not found")
    return path


def model_lock(request: Request, model_id: str):
    """Per-model lock keyed by the uploads path (shared across edit surfaces)."""
    path = os.path.join(
        request.app.state.settings.data_dir, "uploads", f"{model_id}.ifc"
    )
    return request.app.state.registry.lock(path)

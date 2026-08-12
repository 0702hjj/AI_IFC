# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Cross-route request helpers: single-point definitions.

AGENTS.md「校验与业务隔离」§3: request-shape helpers shared by route
modules are defined here exactly once — route files import, never redefine.
"""

from __future__ import annotations

import os
import threading

from fastapi import HTTPException, Request

MODEL_ID_PATTERN = r"^m_[0-9a-f]{16}$"

_locks: "dict[str, threading.RLock]" = {}
_locks_guard = threading.Lock()


def model_upload_path(request: Request, model_id: str) -> str:
    """uploads/{id}.dxf path; 404 when the model upload does not exist."""
    path = os.path.join(
        request.app.state.settings.data_dir, "uploads", f"{model_id}.dxf"
    )
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="model not found")
    return path


def model_lock(model_id: str) -> threading.RLock:
    """Per-model reentrant lock keyed by model_id (shared across edit surfaces).

    Unlike services/ifc there is no ModelRegistry, so locks live in a
    module-level map handed out under a guard lock.
    """
    with _locks_guard:
        return _locks.setdefault(model_id, threading.RLock())

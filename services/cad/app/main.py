# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""FastAPI application factory for the CAD (DXF) edit service.

Chunk A foundation: settings + script staging state + /health only. The
scripts router (routes_scripts) lands in Task 4; locate/edit-call/semantic
diff are chunk B. Unlike services/ifc there is no ModelRegistry/PendingStore
(no in-memory entity cache, no L1 legacy).
"""

from __future__ import annotations

from fastapi import FastAPI

from .config import load_settings
from .script_staging import StagingRegistry


def create_app() -> FastAPI:
    """Create the FastAPI app with settings and the script staging registry."""
    app = FastAPI(title="cad-edit-service")
    settings = load_settings()
    app.state.settings = settings
    app.state.script_staging = StagingRegistry(settings.data_dir)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

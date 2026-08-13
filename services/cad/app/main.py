# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""FastAPI application factory for the CAD (DXF) edit service.

Chunk A: settings + script staging state + the full script-as-source router
(routes_scripts: staging/run/save/rollback + script text diffs). Chunk B adds
routes_diff (POST /diff semantic entity diff + lazy materialize); locate /
edit-call remain. Unlike services/ifc there is no
ModelRegistry/PendingStore (no in-memory entity cache, no L1 legacy).
"""

from __future__ import annotations

from fastapi import FastAPI

from . import routes_diff, routes_scripts
from .config import load_settings
from .script_staging import StagingRegistry


def create_app() -> FastAPI:
    """Create the FastAPI app with settings and the script staging registry."""
    app = FastAPI(title="cad-edit-service")
    settings = load_settings()
    app.state.settings = settings
    app.state.script_staging = StagingRegistry(settings.data_dir)
    app.include_router(routes_scripts.router)
    app.include_router(routes_diff.router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""FastAPI application factory for the IFC edit service."""

from __future__ import annotations

from fastapi import FastAPI

from .config import load_settings
from .pending import PendingStore
from .registry import ModelRegistry
from .routes_diff import router as diff_router
from .routes_edits import router as edits_router
from .routes_scripts import router as scripts_router
from .routes_user_edits import router as user_edits_router
from .script_staging import StagingRegistry


def create_app() -> FastAPI:
    """Create the FastAPI app with a shared ModelRegistry."""
    app = FastAPI(title="ifc-edit-service")
    settings = load_settings()
    app.state.settings = settings
    app.state.registry = ModelRegistry(max_models=settings.max_models)
    app.state.pending = PendingStore(settings.data_dir)
    app.state.script_staging = StagingRegistry(settings.data_dir)
    app.include_router(edits_router)
    app.include_router(diff_router)
    app.include_router(scripts_router)
    app.include_router(user_edits_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

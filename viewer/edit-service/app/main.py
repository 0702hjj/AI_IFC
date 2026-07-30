"""FastAPI application factory for the IFC edit service."""

from __future__ import annotations

from fastapi import FastAPI

from .config import load_settings
from .registry import ModelRegistry
from .routes_edits import router as edits_router


def create_app() -> FastAPI:
    """Create the FastAPI app with a shared ModelRegistry."""
    app = FastAPI(title="ifc-edit-service")
    app.state.settings = load_settings()
    app.state.registry = ModelRegistry()
    app.state.pending = {}
    app.include_router(edits_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

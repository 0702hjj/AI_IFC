"""FastAPI application factory for the IFC edit service."""

from __future__ import annotations

from fastapi import FastAPI

from .config import load_settings
from .registry import ModelRegistry


def create_app() -> FastAPI:
    """Create the FastAPI app with a shared ModelRegistry."""
    app = FastAPI(title="ifc-edit-service")
    app.state.settings = load_settings()
    app.state.registry = ModelRegistry()

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

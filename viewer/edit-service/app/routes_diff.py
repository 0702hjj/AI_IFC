"""Version listing and model diff endpoints.

``GET .../versions`` lists the immutable commit snapshots; ``POST .../diff``
compares two snapshots (or a snapshot against the current upload state) and
returns the flat GlobalId-keyed schema consumed by the web Diff Viewer.

Diff results between two immutable snapshots are cached next to them at
``versions/diff-{base}-{target}.json``. Diffs against ``target="current"``
are never cached: the uploads file is mutable, so there is no stable cache
key.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import BaseModel

from . import diffing, versions
from .routes_edits import MODEL_ID_PATTERN, _model_path

router = APIRouter()


class DiffBody(BaseModel):
    """Body of POST /models/{id}/diff. target also accepts "current"."""

    base: str
    target: str


def _version_or_404(data_dir: str, model_id: str, version: str) -> str:
    path = versions.version_path(data_dir, model_id, version)
    if path is None:
        raise HTTPException(status_code=404, detail=f"version not found: {version}")
    return path


@router.get("/models/{id}/versions")
def get_versions(
    request: Request, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """List version snapshots for a model (empty + current=null before any commit)."""
    _model_path(request, id)
    data_dir = request.app.state.settings.data_dir
    listed = versions.list_versions(data_dir, id)
    return {
        "versions": listed,
        "current": listed[-1]["version"] if listed else None,
    }


@router.post("/models/{id}/diff")
def post_diff(
    request: Request, body: DiffBody, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Diff two model versions (or base version vs the current upload state)."""
    current_path = _model_path(request, id)
    data_dir = request.app.state.settings.data_dir
    base_path = _version_or_404(data_dir, id, body.base)

    cache_path = None
    if body.target == "current":
        target_path = current_path
    else:
        target_path = _version_or_404(data_dir, id, body.target)
        cache_path = os.path.join(
            versions.versions_dir(data_dir, id), f"diff-{body.base}-{body.target}.json"
        )
        if os.path.isfile(cache_path):
            with open(cache_path, "r", encoding="utf-8") as fh:
                return json.load(fh)

    payload = {"base": body.base, "target": body.target, **diffing.compute_diff(base_path, target_path)}

    if cache_path is not None:
        tmp = cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, cache_path)
    return payload

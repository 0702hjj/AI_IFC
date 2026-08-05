# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

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

from . import design_diff, design_versions, diffing, ifc_fingerprint, versions
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


@router.post("/models/{id}/design/diff")
def post_design_diff(
    request: Request, body: DiffBody, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Big-version diff between two design JSON snapshots (semantic, keyed by design key).

    This is the primary diff path for generated models. It is lightweight:
    only big versions are ever compared (no per-step chain), and the result
    is element-level semantic changes (added / removed / modified), not a
    per-field audit log.
    """
    data_dir = request.app.state.settings.data_dir
    try:
        base_design = design_versions.load_design(data_dir, id, body.base)
        target_design = design_versions.load_design(data_dir, id, body.target)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"base": body.base, "target": body.target,
            "engine": "design-json", **design_diff.design_diff(base_design, target_design)}


@router.post("/models/{id}/design/diff-ifc")
def post_design_diff_ifc(
    request: Request, body: DiffBody, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Fallback big-version diff on IFC semantic fingerprints (external models).

    Used when a big version has no design JSON (externally uploaded IFC):
    compares element fingerprints (type/name/psets, keyed by designKey or
    GlobalId) instead of raw STEP.
    """
    data_dir = request.app.state.settings.data_dir
    base_path = _version_or_404(data_dir, id, body.base)
    target_path = _version_or_404(data_dir, id, body.target)
    return {"base": body.base, "target": body.target,
            "engine": "ifc-fingerprint", **ifc_fingerprint.ifc_fingerprint_diff(base_path, target_path)}

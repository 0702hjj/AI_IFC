# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""User-edit parsing: diff an externally modified IFC upload, and append
USER-annotated modification events to the model's change log.

These endpoints back the platform MCP server (W-0018): a user edits an IFC
(or DXF) outside the platform, and the platform needs a structured,
provenance-annotated record of what the user changed.

``POST .../diff/upload`` diffs the uploaded IFC against the current model
state with the same flat GlobalId-keyed schema as ``POST .../diff`` plus a
``labels`` map (human-readable name/type per guid; labels for removed
elements come from the base file). Nothing is persisted and nothing is
cached (the uploads file is mutable).

``POST .../user-edits`` appends structured user modification events to the
edit history, stamped ``provenance={"source": "USER", "origin": ...}`` and
``operation="upload"`` so AI-generated and UI edits stay distinguishable
from external user edits.
"""

from __future__ import annotations

import os
import secrets
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Path, Request, UploadFile
from pydantic import BaseModel, Field

from . import diffing, history
from .route_common import MODEL_ID_PATTERN, model_upload_path

router = APIRouter()


class UserFieldChange(BaseModel):
    """One field-level change inside a user modification event."""

    field: str
    oldValue: Any = None
    newValue: Any = None


class UserEditEvent(BaseModel):
    """One located user modification (IFC element or DXF entity/layer)."""

    guid: str
    name: str = ""
    kind: Literal["added", "removed", "modified"]
    changes: List[UserFieldChange] = Field(default_factory=list)


class UserEditsBody(BaseModel):
    """Body of POST /models/{id}/user-edits."""

    origin: Literal["ifc-upload", "dxf-upload"]
    author: str = "user-upload"
    events: List[UserEditEvent]


@router.post("/models/{id}/diff/upload")
def post_diff_upload(
    request: Request, file: UploadFile, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Diff an uploaded (user-modified) IFC against the current model state."""
    current_path = model_upload_path(request, id)
    fd, tmp_path = tempfile.mkstemp(suffix=".ifc")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(file.file.read())
        try:
            result = diffing.compute_diff(current_path, tmp_path)
        except Exception:
            raise HTTPException(status_code=422, detail="invalid IFC file")
        labels = diffing.element_labels(
            tmp_path, result["added"] + [c["guid"] for c in result["changed"]]
        )
        labels.update(diffing.element_labels(current_path, result["removed"]))
    finally:
        os.unlink(tmp_path)
    return {"base": "current", "target": "upload", **result, "labels": labels}


@router.post("/models/{id}/user-edits")
def post_user_edits(
    request: Request, body: UserEditsBody, id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Append USER-annotated modification events to the model's edit history."""
    model_upload_path(request, id)
    if not body.events:
        raise HTTPException(status_code=422, detail="events required")
    timestamp = datetime.now(timezone.utc).isoformat()
    entries = [
        {
            "id": "e_" + secrets.token_hex(6),
            "guid": event.guid,
            "name": event.name,
            "kind": event.kind,
            "changes": [change.model_dump() for change in event.changes],
            "author": body.author,
            "provenance": {"source": "USER", "origin": body.origin},
            "operation": "upload",
            "timestamp": timestamp,
        }
        for event in body.events
    ]
    history.append_history(request.app.state.settings.data_dir, id, entries)
    return {"appended": len(entries), "entries": entries}

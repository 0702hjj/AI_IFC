# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Platform MCP server (stdio): parse user-modified files and annotate them.

Thin wrapper over the edit-service REST API plus platform-only capabilities
(versions / staging / diff / provenance). The headline tools parse a
user-modified IFC or DXF upload into structured "user modification events"
stamped ``provenance=USER`` and appended to the model's change log, so the
orchestrator can tell external user edits apart from AI/UI edits.

Config: ``EDIT_SERVICE_URL`` (default http://127.0.0.1:8100),
``VIEWER_DATA_DIR`` (DXF baseline lookup at models/{id}/source.dxf).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from mcp.server.mcpserver import MCPServer

from .client import EditServiceClient
from .dxf_diff import dxf_diff
from .events import dxf_diff_to_events, ifc_diff_to_events

DEFAULT_BASE_URL = "http://127.0.0.1:8100"

HISTORY_LIMIT = 20


def build_server(
    base_url: Optional[str] = None,
    data_dir: Optional[str] = None,
    client: Optional[EditServiceClient] = None,
) -> MCPServer:
    if client is None:
        client = EditServiceClient(
            base_url or os.environ.get("EDIT_SERVICE_URL", DEFAULT_BASE_URL)
        )
    if data_dir is None:
        data_dir = os.environ.get("VIEWER_DATA_DIR", "")

    server = MCPServer(
        name="aiifc-platform",
        instructions=(
            "AI_IFC platform tools. Parse user-modified IFC/DXF uploads into "
            "USER-annotated modification events (ifc_upload_modified / "
            "dxf_upload_modified), and inspect current model context "
            "(model_current_context). Version/diff queries are served by the "
            "in-process agent tools (get_versions / get_diff combined views)."
        ),
    )

    @server.tool()
    def ifc_upload_modified(
        model_id: str, ifc_path: str, author: str = "user-upload"
    ) -> Dict[str, Any]:
        """Parse a user-modified IFC upload against the current model state.

        Runs the platform semantic diff (attribute/pset level, keyed by
        GlobalId), converts it to user modification events annotated
        provenance=USER (origin=ifc-upload) and appends them to the model's
        change log. Returns the recorded events (with human-readable element
        labels) plus a change summary.
        """
        payload = client.diff_upload(model_id, ifc_path)
        events = ifc_diff_to_events(payload)
        recorded = (
            client.post_user_edits(model_id, "ifc-upload", events, author=author)
            if events
            else {"appended": 0, "entries": []}
        )
        return {
            "modelId": model_id,
            "events": recorded["entries"],
            "summary": {
                "added": len(payload["added"]),
                "removed": len(payload["removed"]),
                "modified": len(payload["changed"]),
            },
        }

    @server.tool()
    def dxf_upload_modified(
        model_id: str,
        dxf_path: str,
        base_dxf_path: str = "",
        author: str = "user-upload",
    ) -> Dict[str, Any]:
        """Parse a user-modified DXF upload at layer/entity granularity.

        Compares against base_dxf_path, or the model's stored
        models/{id}/source.dxf when omitted. Generic layer/entity diff only
        (added/removed/modified per layer + text annotation changes) — no
        layout reconstruction. Events are annotated provenance=USER
        (origin=dxf-upload) and appended to the change log.
        """
        base = base_dxf_path or os.path.join(
            data_dir, "models", model_id, "source.dxf"
        )
        if not os.path.isfile(base):
            raise FileNotFoundError(
                f"no baseline DXF for model {model_id}: pass base_dxf_path "
                f"or store one at {base}"
            )
        diff = dxf_diff(base, dxf_path)
        events = dxf_diff_to_events(diff)
        recorded = (
            client.post_user_edits(model_id, "dxf-upload", events, author=author)
            if events
            else {"appended": 0, "entries": []}
        )
        return {
            "modelId": model_id,
            "events": recorded["entries"],
            "summary": diff["layers"],
            "texts": diff["texts"],
        }

    @server.tool()
    def model_current_context(model_id: str) -> Dict[str, Any]:
        """Quick agent context: current version, staging status, recent modification events."""
        versions = client.versions(model_id)
        script = client.get_script(model_id)
        staging = None
        if script is not None:
            staging = {
                "staged": script["staged"],
                "canUndo": script["canUndo"],
                "canRedo": script["canRedo"],
            }
        recent: List[Dict[str, Any]] = client.history(model_id)[-HISTORY_LIMIT:]
        return {
            "modelId": model_id,
            "currentVersion": versions["current"],
            "staging": staging,
            "recentEvents": recent,
        }

    return server


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()

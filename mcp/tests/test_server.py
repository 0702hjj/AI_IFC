# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""MCP protocol-layer tests: tool registration + calls over an in-memory session."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from mcp.client import Client

from app.client import EditServiceClient
from app.server import build_server
from conftest import MODEL_ID, FakeEditService

EXPECTED_TOOLS = [
    "ifc_upload_modified",
    "dxf_upload_modified",
    "model_versions",
    "model_diff",
    "model_current_context",
]


def _server(fake: FakeEditService, data_dir: str = ""):
    client = EditServiceClient("http://fake", transport=fake.transport)
    return build_server(client=client, data_dir=data_dir)


def _payload(result) -> dict:
    if result.content:
        return json.loads(result.content[0].text)
    structured = result.structured_content or {}
    return structured.get("result", structured)


def _call(server, tool: str, args: dict) -> dict:
    async def run() -> dict:
        async with Client(server) as client:
            return _payload(await client.call_tool(tool, args))

    return asyncio.run(run())


def test_all_tools_registered(fake: FakeEditService) -> None:
    server = _server(fake)

    async def run() -> list:
        async with Client(server) as client:
            return (await client.list_tools()).tools

    tools = [t.name for t in asyncio.run(run())]
    for name in EXPECTED_TOOLS:
        assert name in tools, f"tool {name} not registered"


def _stamp_user_edits(request, body):
    payload = json.loads(body)
    entries = [
        {
            "id": f"e_{i:06x}",
            "guid": e["guid"],
            "name": e.get("name", ""),
            "kind": e["kind"],
            "changes": e.get("changes", []),
            "author": payload.get("author", "user-upload"),
            "provenance": {"source": "USER", "origin": payload["origin"]},
            "operation": "upload",
            "timestamp": "2026-08-07T00:00:00+00:00",
        }
        for i, e in enumerate(payload["events"])
    ]
    import httpx

    return httpx.Response(200, json={"appended": len(entries), "entries": entries})


def test_ifc_upload_modified_marks_user_provenance(
    fake: FakeEditService, tmp_path: Path
) -> None:
    ifc = tmp_path / "modified.ifc"
    ifc.write_bytes(b"ISO-10303-21;")
    fake.add(
        "POST",
        f"/models/{MODEL_ID}/diff/upload",
        {
            "base": "current",
            "target": "upload",
            "added": [],
            "removed": [],
            "changed": [
                {"guid": "g1", "changes": [{"field": "Name", "old": "旧", "new": "新"}]}
            ],
            "labels": {"g1": {"name": "用户改的墙", "type": "IfcWall"}},
        },
    )
    fake.add("POST", f"/models/{MODEL_ID}/user-edits", _stamp_user_edits)

    result = _call(
        _server(fake), "ifc_upload_modified", {"model_id": MODEL_ID, "ifc_path": str(ifc)}
    )
    assert result["modelId"] == MODEL_ID
    assert result["summary"] == {"added": 0, "removed": 0, "modified": 1}
    event = result["events"][0]
    assert event["guid"] == "g1"
    assert event["name"] == "用户改的墙"
    assert event["provenance"] == {"source": "USER", "origin": "ifc-upload"}
    sent = fake.requests[1]["json"]
    assert sent["origin"] == "ifc-upload"
    assert sent["events"][0]["changes"] == [
        {"field": "Name", "oldValue": "旧", "newValue": "新"}
    ]


def test_dxf_upload_modified_against_stored_source(
    fake: FakeEditService, dxf_pair, tmp_path: Path
) -> None:
    base, modified = dxf_pair
    data_dir = tmp_path / "data"
    source = data_dir / "models" / MODEL_ID / "source.dxf"
    source.parent.mkdir(parents=True)
    source.write_bytes(base.read_bytes())
    fake.add("POST", f"/models/{MODEL_ID}/user-edits", _stamp_user_edits)

    result = _call(
        _server(fake, data_dir=str(data_dir)),
        "dxf_upload_modified",
        {"model_id": MODEL_ID, "dxf_path": str(modified)},
    )
    assert result["summary"]["WALLS"] == {"added": 1, "removed": 1, "modified": 1}
    assert result["texts"][0]["new"] == "主卧"
    assert all(
        e["provenance"] == {"source": "USER", "origin": "dxf-upload"}
        for e in result["events"]
    )
    kinds = {e["kind"] for e in result["events"]}
    assert kinds == {"added", "removed", "modified"}


def test_dxf_upload_modified_missing_baseline_errors(fake: FakeEditService) -> None:
    result_error = None

    async def run():
        nonlocal result_error
        async with Client(_server(fake)) as client:
            result_error = await client.call_tool(
                "dxf_upload_modified",
                {"model_id": MODEL_ID, "dxf_path": "/nonexistent.dxf"},
            )

    asyncio.run(run())
    assert result_error.is_error


def test_model_versions_merges_ifc_and_script_versions(fake: FakeEditService) -> None:
    fake.add(
        "GET",
        f"/models/{MODEL_ID}/versions",
        {"versions": [{"version": "v1", "createdAt": "t1"},
                      {"version": "v2", "createdAt": "t2"}],
         "current": "v2"},
    )
    fake.add(
        "GET",
        f"/models/{MODEL_ID}/scripts",
        {"modelId": MODEL_ID,
         "scripts": [{"version": "v1", "createdAt": "t1"},
                     {"version": "v2", "createdAt": "t2"}],
         "versions": [{"version": "v1", "createdAt": "t1"},
                      {"version": "v2", "createdAt": "t2"}]},
    )
    result = _call(_server(fake), "model_versions", {"model_id": MODEL_ID})
    assert result["current"] == "v2"
    assert [v["version"] for v in result["versions"]] == ["v1", "v2"]
    assert [s["version"] for s in result["scripts"]] == ["v1", "v2"]


def test_model_diff_passthrough_ifc_and_script(fake: FakeEditService) -> None:
    fake.add(
        "POST",
        f"/models/{MODEL_ID}/diff",
        {"base": "v1", "target": "v2", "added": [], "removed": [], "changed": []},
    )
    fake.add(
        "POST",
        f"/models/{MODEL_ID}/script/diff",
        {"base": "v1", "target": "v2", "engine": "script", "diff": "@@ ..."},
    )
    result = _call(
        _server(fake), "model_diff", {"model_id": MODEL_ID, "base": "v1", "target": "v2"}
    )
    assert result["ifc"]["base"] == "v1"
    assert result["script"]["engine"] == "script"


def test_model_diff_without_scripts_returns_null_script(fake: FakeEditService) -> None:
    fake.add(
        "POST",
        f"/models/{MODEL_ID}/diff",
        {"base": "v1", "target": "v2", "added": [], "removed": [], "changed": []},
    )
    result = _call(
        _server(fake), "model_diff", {"model_id": MODEL_ID, "base": "v1", "target": "v2"}
    )
    assert result["script"] is None


def test_model_current_context_composes_state(fake: FakeEditService) -> None:
    fake.add(
        "GET",
        f"/models/{MODEL_ID}/versions",
        {"versions": [{"version": "v1", "createdAt": "t1"}], "current": "v1"},
    )
    fake.add(
        "GET",
        f"/models/{MODEL_ID}/script",
        {"modelId": MODEL_ID, "script": "PARAMS = {}", "staged": 2,
         "canUndo": True, "canRedo": False, "maxSteps": 10},
    )
    fake.add(
        "GET",
        f"/models/{MODEL_ID}/history",
        [
            {"id": "e_1", "guid": "g1", "provenance": {"source": "AI"}},
            {"id": "e_2", "guid": "g2",
             "provenance": {"source": "USER", "origin": "ifc-upload"},
             "operation": "upload"},
        ],
    )
    result = _call(_server(fake), "model_current_context", {"model_id": MODEL_ID})
    assert result["currentVersion"] == "v1"
    assert result["staging"] == {"staged": 2, "canUndo": True, "canRedo": False}
    assert [e["id"] for e in result["recentEvents"]] == ["e_1", "e_2"]
    assert result["recentEvents"][1]["provenance"]["source"] == "USER"


def test_model_current_context_without_script(fake: FakeEditService) -> None:
    fake.add(
        "GET",
        f"/models/{MODEL_ID}/versions",
        {"versions": [], "current": None},
    )
    fake.add("GET", f"/models/{MODEL_ID}/history", [])
    result = _call(_server(fake), "model_current_context", {"model_id": MODEL_ID})
    assert result["currentVersion"] is None
    assert result["staging"] is None
    assert result["recentEvents"] == []

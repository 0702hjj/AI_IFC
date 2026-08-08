# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Shared fixtures: minimal ezdxf base/modified pair, fake edit-service transport."""

from __future__ import annotations

import json
from pathlib import Path

import ezdxf
import httpx
import pytest

MODEL_ID = "m_0123456789abcdef"


@pytest.fixture()
def dxf_pair(tmp_path: Path):
    """Minimal DXF pair: user moved a line end, deleted a line, edited a text, added a circle."""
    base = tmp_path / "base.dxf"
    doc = ezdxf.new()
    doc.layers.add("WALLS")
    doc.layers.add("TEXT")
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "WALLS"})
    msp.add_line((0, 1), (10, 1), dxfattribs={"layer": "WALLS"})
    msp.add_text("客厅", dxfattribs={"layer": "TEXT", "height": 2.5}).set_placement((1, 1))
    doc.saveas(base)

    modified = tmp_path / "modified.dxf"
    doc2 = ezdxf.readfile(str(base))
    msp2 = doc2.modelspace()
    lines = list(msp2.query("LINE"))
    lines[0].dxf.end = (12, 0)
    msp2.delete_entity(lines[1])
    msp2.query("TEXT").first.dxf.text = "主卧"
    msp2.add_circle((5, 5), 1.5, dxfattribs={"layer": "WALLS"})
    doc2.saveas(modified)
    return base, modified


class FakeEditService:
    """Scriptable fake of the edit-service REST API (httpx.MockTransport)."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.routes: dict[tuple[str, str], object] = {}
        self.transport = httpx.MockTransport(self._handle)

    def add(self, method: str, path: str, payload, status: int = 200) -> None:
        self.routes[(method, path)] = (status, payload)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        body = request.read()
        try:
            parsed = json.loads(body) if body else None
        except ValueError:
            parsed = None
        self.requests.append(
            {"method": request.method, "path": request.url.path, "json": parsed}
        )
        key = (request.method, request.url.path)
        if key not in self.routes:
            return httpx.Response(404, json={"detail": "not found"})
        status, payload = self.routes[key]
        if callable(payload):
            return payload(request, body)
        return httpx.Response(status, json=payload)


@pytest.fixture()
def fake() -> FakeEditService:
    return FakeEditService()

# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Regenerate the derived IFC from a design JSON (design_builder → build_script_template).

Bridges the design-JSON edit flow to the IFC product: given the staged
design JSON, run the aiifc build pipeline and write the IFC into
``uploads/{id}.ifc`` (atomically). The regenerated file is then promoted to
a big version by ``POST /models/{id}/design/save``.

The aiifc flows live in the repo (``AIIFC_FLOWS_DIR``, default relative
path); they are pure ifcopenshell code and reusable from this service.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException

from .config import Settings


def _load_flows(flows_dir: str):
    """Import design_builder + build_script_template from the aiifc flows dir."""
    flows = Path(flows_dir).resolve()
    if not flows.is_dir():
        raise HTTPException(status_code=500, detail=f"aiifc flows dir not found: {flows}")
    if str(flows) not in sys.path:
        sys.path.insert(0, str(flows))
    try:
        import design_builder
        import build_script_template
    except Exception as exc:  # pragma: no cover - env problem
        raise HTTPException(status_code=500, detail=f"load aiifc flows: {exc}")
    return design_builder, build_script_template


def regenerate(settings: Settings, design: Dict[str, Any], out_path: str) -> Dict[str, Any]:
    """Run design JSON → features.json → IFC; write IFC atomically to out_path."""
    design_builder, build_script_template = _load_flows(settings.flows_dir)

    try:
        features = design_builder.normalize(design)
    except design_builder.SchemaError as exc:
        raise HTTPException(status_code=422, detail=f"design schema error: {exc}")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump(features, fh, ensure_ascii=False)
        features_path = fh.name
    try:
        tmp_out = out_path + ".tmp"
        ok = build_script_template.build(features_path, tmp_out)
        if not ok:
            raise HTTPException(status_code=422, detail="IFC validation failed during build")
        os.replace(tmp_out, out_path)
    finally:
        try:
            os.unlink(features_path)
        except OSError:
            pass

    return {"ok": True, "ifc": out_path,
            "walls": len(features.get("walls", [])),
            "openings": len(features.get("openings", [])),
            "slabs": len(features.get("slabs", []))}

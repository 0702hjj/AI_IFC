# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Big-version snapshots for design JSON models.

A big version is a designer-approved checkpoint. It stores the design JSON
(``{data_dir}/models/{id}/designs/v{n}.json``) alongside the derived IFC
snapshot (``versions/v{n}.ifc``, reused from versions.py). Only explicit
"save" points create big versions; in-between staging edits do not persist
and produce no diff.

Rollback = restore a saved design JSON (regenerate IFC downstream), never a
per-step revert.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import versions

DESIGN_FILE_RE = re.compile(r"^v(\d+)\.json$")


def designs_dir(data_dir: str, model_id: str) -> str:
    return os.path.join(data_dir, "models", model_id, "designs")


def design_path(data_dir: str, model_id: str, version: str) -> Optional[str]:
    if not versions.VERSION_NAME_RE.match(version):
        return None
    path = os.path.join(designs_dir(data_dir, model_id), f"{version}.json")
    return path if os.path.isfile(path) else None


def list_designs(data_dir: str, model_id: str) -> List[Dict[str, Any]]:
    """List design big versions as {"version": "v1", "createdAt": ...}, oldest first."""
    directory = designs_dir(data_dir, model_id)
    entries = []
    if os.path.isdir(directory):
        for name in os.listdir(directory):
            match = DESIGN_FILE_RE.match(name)
            if match:
                path = os.path.join(directory, name)
                created = datetime.fromtimestamp(
                    os.path.getmtime(path), timezone.utc
                ).isoformat()
                entries.append((int(match.group(1)), f"v{match.group(1)}", created))
    entries.sort()
    return [{"version": name, "createdAt": created} for _, name, created in entries]


def load_design(data_dir: str, model_id: str, version: str) -> Dict[str, Any]:
    """Load a saved design JSON by version name (raise KeyError if missing)."""
    path = design_path(data_dir, model_id, version)
    if path is None:
        raise KeyError(f"design version not found: {version}")
    payload = json.loads(open(path, encoding="utf-8").read())
    return payload.get("design", payload)


def save(
    data_dir: str,
    model_id: str,
    design: Dict[str, Any],
    ifc_src_path: str,
    note: str = "",
) -> str:
    """Save a big version: design JSON snapshot + IFC snapshot; return version name.

    Reuses versions.snapshot for the IFC, keeping both numbering in lockstep.
    """
    directory = designs_dir(data_dir, model_id)
    os.makedirs(directory, exist_ok=True)
    existing = list_designs(data_dir, model_id)
    next_n = int(existing[-1]["version"][1:]) + 1 if existing else 1
    dest = os.path.join(directory, f"v{next_n}.json")
    payload = {
        "version": f"v{next_n}",
        "note": note,
        "savedAt": datetime.now(timezone.utc).isoformat(),
        "design": design,
    }
    tmp = dest + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, dest)
    versions.snapshot(data_dir, model_id, ifc_src_path)
    return f"v{next_n}"


def rollback(data_dir: str, model_id: str, version: str) -> Dict[str, Any]:
    """Restore a saved design JSON (regeneration is downstream). Return it."""
    design = load_design(data_dir, model_id, version)
    return design


def copy_ifc_to_uploads(data_dir: str, model_id: str, version: str) -> None:
    """Copy a version's IFC snapshot back to uploads (for rollback regeneration)."""
    src = versions.version_path(data_dir, model_id, version)
    if src is None:
        raise KeyError(f"ifc version not found: {version}")
    dest = os.path.join(data_dir, "uploads", f"{model_id}.ifc")
    shutil.copyfile(src, dest)

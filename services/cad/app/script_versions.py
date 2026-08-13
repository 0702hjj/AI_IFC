# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Big-version snapshots for script-as-source models.

A big version is a designer-approved checkpoint. It stores the build script
(``{data_dir}/models/{id}/scripts/v{n}.py`` — the single source of truth).
Only the latest big version keeps its derived DXF snapshot
(``versions/v{n}.dxf``); older snapshots with a rebuildable script are
deleted on save and regenerated on demand (lazy materialize is chunk B;
this chunk's versions listing only covers materialized snapshots + scripts).
Only explicit "save" points create big versions; in-between staging edits
do not persist and produce no version.

Script and DXF numbering stay in lockstep: ``n = max(next script n, next DXF
n)``, so a script version never collides with a plain snapshot
(``versions.snapshot`` shares ``versions/``). Snapshots without a script are
never pruned. A sidecar ``v{n}.meta.json`` holds the note/timestamp;
listings read the ``*.py`` files only.

Rollback = restore a saved script (re-run is downstream), never a per-step
revert.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import versions

SCRIPT_FILE_RE = re.compile(r"^v(\d+)\.py$")


def scripts_dir(data_dir: str, model_id: str) -> str:
    return os.path.join(data_dir, "models", model_id, "scripts")


def script_path(data_dir: str, model_id: str, version: str) -> Optional[str]:
    if not versions.VERSION_NAME_RE.match(version):
        return None
    path = os.path.join(scripts_dir(data_dir, model_id), f"{version}.py")
    return path if os.path.isfile(path) else None


def _load_meta(data_dir: str, model_id: str, version: str) -> Dict[str, Any]:
    path = os.path.join(scripts_dir(data_dir, model_id), f"{version}.meta.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def list_scripts(data_dir: str, model_id: str) -> List[Dict[str, Any]]:
    """List script big versions as {"version", "createdAt", "note"}, oldest first."""
    entries = versions.list_snapshots(scripts_dir(data_dir, model_id), SCRIPT_FILE_RE)
    for entry in entries:
        entry["note"] = _load_meta(data_dir, model_id, entry["version"]).get("note", "")
    return entries


def load_script(data_dir: str, model_id: str, version: str) -> str:
    """Load a saved build script by version name (raise KeyError if missing)."""
    path = script_path(data_dir, model_id, version)
    if path is None:
        raise KeyError(f"script version not found: {version}")
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _write_atomic(path: str, content: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(content)
    os.replace(tmp, path)


def _prune_rebuildable_snapshots(data_dir: str, model_id: str, keep_version: str) -> None:
    """Delete older ``versions/v{m}.dxf`` snapshots that have a script.

    Only the latest big version stays materialized; versions with
    ``scripts/v{m}.py`` are rebuildable on demand (lazy materialize is
    chunk B). Snapshots without a script are preserved.
    """
    keep_n = int(keep_version[1:])
    for m in range(1, keep_n):
        version = f"v{m}"
        if script_path(data_dir, model_id, version) is None:
            continue
        snapshot = versions.version_path(data_dir, model_id, version)
        if snapshot is not None:
            os.remove(snapshot)


def save(
    data_dir: str,
    model_id: str,
    script_text: str,
    dxf_src_path: str,
    note: str = "",
    map_text: Optional[str] = None,
) -> str:
    """Save a big version: script snapshot + DXF snapshot; return version name.

    Both snapshots use the same ``n`` (max of either side's next number), so
    ``scripts/v{n}.py`` and ``versions/v{n}.dxf`` always pair up. ``map_text``
    (the run's ScriptMap JSON) is snapshotted as ``scripts/v{n}.map.json`` in
    the same lockstep; scripts that produced no map get no map sidecar.
    After the new snapshot lands, older rebuildable DXF snapshots are pruned
    (only the latest stays materialized).
    """
    directory = scripts_dir(data_dir, model_id)
    os.makedirs(directory, exist_ok=True)
    script_list = list_scripts(data_dir, model_id)
    dxf_list = versions.list_versions(data_dir, model_id)
    next_script = int(script_list[-1]["version"][1:]) + 1 if script_list else 1
    next_dxf = int(dxf_list[-1]["version"][1:]) + 1 if dxf_list else 1
    n = max(next_script, next_dxf)
    version = f"v{n}"

    _write_atomic(os.path.join(directory, f"{version}.py"), script_text)
    meta = {
        "version": version,
        "note": note,
        "savedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write_atomic(
        os.path.join(directory, f"{version}.meta.json"),
        json.dumps(meta, ensure_ascii=False, indent=2),
    )
    if map_text is not None:
        _write_atomic(os.path.join(directory, f"{version}.map.json"), map_text)
    versions.snapshot_as(data_dir, model_id, dxf_src_path, version)
    _prune_rebuildable_snapshots(data_dir, model_id, version)
    return version

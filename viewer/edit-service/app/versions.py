"""Immutable IFC version snapshots, stored per model under the viewer data dir.

Snapshots live at ``{VIEWER_DATA_DIR}/models/{id}/versions/v{n}.ifc`` (n
starts at 1). The first commit snapshots the original upload as ``v1``
before saving; every successful commit snapshots the newly saved file as
``v{n+1}``. Snapshot files are append-only and written atomically
(write ``dest + ".tmp"`` then ``os.replace``), the same pattern as
``ModelRegistry.save``.
"""

from __future__ import annotations

import os
import re
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

VERSION_FILE_RE = re.compile(r"^v(\d+)\.ifc$")
VERSION_NAME_RE = re.compile(r"^v\d+$")


def versions_dir(data_dir: str, model_id: str) -> str:
    """Return the versions directory path for a model id."""
    return os.path.join(data_dir, "models", model_id, "versions")


def version_path(data_dir: str, model_id: str, version: str) -> Optional[str]:
    """Return the snapshot path for a version name, or None if invalid/missing."""
    if not VERSION_NAME_RE.match(version):
        return None
    path = os.path.join(versions_dir(data_dir, model_id), f"{version}.ifc")
    return path if os.path.isfile(path) else None


def list_versions(data_dir: str, model_id: str) -> List[Dict[str, Any]]:
    """List snapshots as {"version": "v1", "createdAt": ...}, oldest first."""
    directory = versions_dir(data_dir, model_id)
    entries = []
    if os.path.isdir(directory):
        for name in os.listdir(directory):
            match = VERSION_FILE_RE.match(name)
            if match:
                path = os.path.join(directory, name)
                created = datetime.fromtimestamp(
                    os.path.getmtime(path), timezone.utc
                ).isoformat()
                entries.append((int(match.group(1)), f"v{match.group(1)}", created))
    entries.sort()
    return [{"version": name, "createdAt": created} for _, name, created in entries]


def snapshot(data_dir: str, model_id: str, src_path: str) -> str:
    """Atomically copy src_path to the next version snapshot; return its name."""
    directory = versions_dir(data_dir, model_id)
    os.makedirs(directory, exist_ok=True)
    existing = list_versions(data_dir, model_id)
    next_n = int(existing[-1]["version"][1:]) + 1 if existing else 1
    dest = os.path.join(directory, f"v{next_n}.ifc")
    tmp = dest + ".tmp"
    shutil.copyfile(src_path, tmp)
    os.replace(tmp, dest)
    return f"v{next_n}"

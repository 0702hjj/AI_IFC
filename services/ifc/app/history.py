# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Persistent edit history, stored per model under the viewer data dir.

History lives at ``{VIEWER_DATA_DIR}/models/{id}/edit-history.json``.
Writes are atomic (write ``path + ".tmp"`` then ``os.replace``), the same
pattern as ``ModelRegistry.save``.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


def history_path(data_dir: str, model_id: str) -> str:
    """Return the history file path for a model id."""
    return os.path.join(data_dir, "models", model_id, "edit-history.json")


def load_history(data_dir: str, model_id: str) -> List[Dict[str, Any]]:
    """Read the history entries for a model (empty list if none)."""
    path = history_path(data_dir, model_id)
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def append_history(
    data_dir: str, model_id: str, entries: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Atomically append entries to the history file; return the full history."""
    entries_all = load_history(data_dir, model_id) + entries
    path = history_path(data_dir, model_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(entries_all, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return entries_all

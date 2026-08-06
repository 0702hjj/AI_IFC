# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Persistent pending-edit queue, stored per model under the viewer data dir.

Pending entries live at ``{VIEWER_DATA_DIR}/models/{id}/pending.json``.
Every mutation is written atomically (write ``path + ".tmp"`` then
``os.replace``), the same pattern as ``history.append_history``; an empty
queue removes the file. State is restored lazily from disk on first access,
so a service restart no longer loses uncommitted edits.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


class PendingStore:
    """Map of model_id -> pending edit entries, backed by per-model JSON files."""

    def __init__(self, data_dir: Optional[str] = None) -> None:
        self._data_dir = data_dir
        self._pending: Dict[str, List[Dict[str, Any]]] = {}

    def _path(self, model_id: str) -> str:
        return os.path.join(self._data_dir, "models", model_id, "pending.json")

    def _load(self, model_id: str) -> List[Dict[str, Any]]:
        path = self._path(model_id)
        if not os.path.isfile(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return []

    def _save(self, model_id: str) -> None:
        if self._data_dir is None:
            return
        path = self._path(model_id)
        entries = self._pending.get(model_id, [])
        if not entries:
            if os.path.isfile(path):
                os.remove(path)
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(entries, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def get(self, model_id: str) -> List[Dict[str, Any]]:
        """Pending entries for a model, restored from disk on first access."""
        if model_id not in self._pending:
            entries = self._load(model_id) if self._data_dir is not None else []
            self._pending[model_id] = entries
        return self._pending[model_id]

    def append(self, model_id: str, entry: Dict[str, Any]) -> None:
        """Append an entry and persist."""
        self.get(model_id).append(entry)
        self._save(model_id)

    def set(self, model_id: str, entries: List[Dict[str, Any]]) -> None:
        """Replace the queue and persist (empty list removes the file)."""
        self._pending[model_id] = list(entries)
        self._save(model_id)

# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Persistent pending-edit queue, stored per model under the viewer data dir.

Pending entries live at ``{VIEWER_DATA_DIR}/models/{id}/pending.json``.
Every mutation is written atomically (write ``path + ".tmp"`` then
``os.replace``), the same pattern as ``history.append_history``; an empty
queue removes the file. State is restored lazily from disk on first access,
so a service restart no longer loses uncommitted edits.

Entries restored from disk (or whose in-memory model was LRU-evicted) are
flagged via ``needs_replay``: their IFC modifications only ever existed in
memory, so a model re-opened from disk no longer reflects them. The replay
consumer (pending→commit true edit) is retired (410, script-as-source);
the flagging itself stays as script-run/LRU bookkeeping (W-0009, see
``routes_scripts._run_into_uploads``).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class PendingStore:
    """Map of model_id -> pending edit entries, backed by per-model JSON files."""

    def __init__(self, data_dir: Optional[str] = None) -> None:
        self._data_dir = data_dir
        self._pending: Dict[str, List[Dict[str, Any]]] = {}
        self._needs_replay: Set[str] = set()

    def _path(self, model_id: str) -> str:
        return os.path.join(self._data_dir, "models", model_id, "pending.json")

    def _load(self, model_id: str) -> List[Dict[str, Any]]:
        path = self._path(model_id)
        if not os.path.isfile(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return []
        if not isinstance(data, list):
            logger.warning(
                "pending file for %s is not a list (%s); treating as empty",
                model_id,
                type(data).__name__,
            )
            return []
        return data

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
        """Pending entries for a model (pure read: never mutates memory state)."""
        if model_id in self._pending:
            return self._pending[model_id]
        if self._data_dir is None:
            return []
        return self._load(model_id)

    def _ensure(self, model_id: str) -> List[Dict[str, Any]]:
        """Return the cached entries, restoring from disk on first mutation.

        A non-empty restore is flagged ``needs_replay``: the entries were
        applied to a long-gone in-memory model, not to one freshly opened
        from disk.
        """
        if model_id not in self._pending:
            entries = self._load(model_id) if self._data_dir is not None else []
            self._pending[model_id] = entries
            if entries:
                self._needs_replay.add(model_id)
        return self._pending[model_id]

    def needs_replay(self, model_id: str) -> bool:
        """Whether cached entries predate the current in-memory model."""
        return model_id in self._needs_replay

    def mark_needs_replay(self, model_id: str) -> None:
        """Flag entries as not applied to the in-memory model (LRU eviction)."""
        if self._pending.get(model_id):
            self._needs_replay.add(model_id)

    def mark_replayed(self, model_id: str) -> None:
        """Clear the replay flag after entries were re-applied to the model."""
        self._needs_replay.discard(model_id)

    def append(self, model_id: str, entry: Dict[str, Any]) -> None:
        """Append an entry and persist."""
        self._ensure(model_id).append(entry)
        self._save(model_id)

    def set(self, model_id: str, entries: List[Dict[str, Any]]) -> None:
        """Replace the queue and persist (empty list removes the file)."""
        self._pending[model_id] = list(entries)
        self._needs_replay.discard(model_id)
        self._save(model_id)

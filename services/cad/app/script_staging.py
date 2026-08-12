# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Script staging: WPS-style edit history (undo/redo ring buffer) for build scripts.

The build script is the single source of truth (script-as-source). Edits to
it go through a per-model staging buffer instead of a persistent per-step
commit chain:

- ``push`` records a new script state; the buffer keeps at most
  ``MAX_STEPS`` (10) states, dropping the oldest (WPS-style <- ->).
- ``undo``/``redo`` move a cursor back/forward through the buffer.
- ``discard`` throws the staging away; nothing is persisted, no diff exists.
- Only an explicit ``save`` (promote) turns the current staged script into a
  big version (see script_versions.py) and clears the buffer.

When constructed with a ``data_dir``, ``StagingRegistry`` persists every
mutation to ``{data_dir}/models/{id}/script_staging.json`` (atomic tmp +
replace) and restores it lazily on first access, so staging survives a
restart. (The retired design-JSON staging lived at ``staging.json``; the
payloads are incompatible, so script staging uses a fresh file name.)
"""

from __future__ import annotations

import json
import os
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

MAX_STEPS = 10


@dataclass
class ScriptStaging:
    """Per-model build-script edit history."""

    model_id: str
    base: Optional[str] = None  # last saved big version's script
    history: List[str] = field(default_factory=list)  # staged states, oldest first
    cursor: int = -1  # index into history of the current staged state; -1 = at base
    on_change: Optional[Callable[["ScriptStaging"], None]] = field(
        default=None, repr=False, compare=False
    )

    def _notify(self) -> None:
        if self.on_change is not None:
            self.on_change(self)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modelId": self.model_id,
            "base": self.base,
            "history": self.history,
            "cursor": self.cursor,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ScriptStaging":
        return cls(
            model_id=payload["modelId"],
            base=payload.get("base"),
            history=list(payload.get("history") or []),
            cursor=payload.get("cursor", -1),
        )

    def current(self) -> Optional[str]:
        """Current effective script (staged state, or base if none staged)."""
        if self.cursor >= 0 and self.cursor < len(self.history):
            return self.history[self.cursor]
        return self.base

    def push(self, script: str) -> None:
        """Record a new staged state, dropping redo tail and oldest beyond MAX_STEPS."""
        if self.cursor >= 0 and self.cursor < len(self.history) - 1:
            # New edit invalidates the redo tail.
            self.history = self.history[: self.cursor + 1]
        self.history.append(script)
        if len(self.history) > MAX_STEPS:
            self.history = self.history[-MAX_STEPS:]
        self.cursor = len(self.history) - 1
        self._notify()

    def undo(self) -> bool:
        """Move one step back; returns False when already at the oldest."""
        if self.cursor < 0:
            return False
        self.cursor -= 1
        self._notify()
        return True

    def redo(self) -> bool:
        """Move one step forward; returns False when already at the newest."""
        if self.cursor >= len(self.history) - 1:
            return False
        self.cursor += 1
        self._notify()
        return True

    def can_undo(self) -> bool:
        return self.cursor >= 0

    def can_redo(self) -> bool:
        return self.cursor < len(self.history) - 1

    def staged_count(self) -> int:
        """Number of staged states since the last save."""
        return self.cursor + 1

    def discard(self) -> int:
        """Throw staging away (back to base). Returns the number dropped."""
        dropped = self.cursor + 1
        self.history = []
        self.cursor = -1
        self._notify()
        return dropped

    def save(self) -> None:
        """Promote the current staged state to the new base (called after big-version save)."""
        self.base = self.current()
        self.history = []
        self.cursor = -1
        self._notify()

    def seed_base(self, base: str) -> None:
        """Seed base from a saved big version; no-op when a script already exists.

        Chat-archived models only have ``scripts/v{n}.py`` on disk and no
        staging buffer — seeding lets the read endpoints serve the latest big
        version instead of 404 (idempotent).
        """
        if self.current() is not None:
            return
        self.base = base
        self._notify()


class StagingRegistry:
    """App-wide map of model_id -> ScriptStaging, optionally persisted to disk.

    The in-memory map is bounded (``max_staging``, LRU): evicted stagings are
    restored from disk on next access, so eviction only drops the cache.
    """

    def __init__(self, data_dir: Optional[str] = None, max_staging: int = 32) -> None:
        self._staging: "OrderedDict[str, ScriptStaging]" = OrderedDict()
        self._data_dir = data_dir
        self._max_staging = max(1, max_staging)

    def _path(self, model_id: str) -> str:
        return os.path.join(self._data_dir, "models", model_id, "script_staging.json")

    def _load(self, model_id: str) -> Optional[ScriptStaging]:
        path = self._path(model_id)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return ScriptStaging.from_dict(json.load(fh))
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _persist(self, staging: ScriptStaging) -> None:
        if self._data_dir is None:
            return
        path = self._path(staging.model_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(staging.to_dict(), fh, ensure_ascii=False)
        os.replace(tmp, path)

    def _attach(self, staging: ScriptStaging) -> ScriptStaging:
        if self._data_dir is not None:
            staging.on_change = self._persist
        return staging

    def get(self, model_id: str) -> ScriptStaging:
        """Return the staging for a model, restoring it from disk on first access."""
        staging = self._staging.get(model_id)
        if staging is None:
            if self._data_dir is not None:
                staging = self._load(model_id)
            if staging is None:
                staging = ScriptStaging(model_id=model_id)
            self._staging[model_id] = self._attach(staging)
        else:
            self._staging.move_to_end(model_id)
        self._evict_lru()
        return staging

    def _evict_lru(self) -> None:
        while len(self._staging) > self._max_staging:
            self._staging.popitem(last=False)

    def reset(self, model_id: str, base: Optional[str] = None) -> ScriptStaging:
        """Recreate staging for a model (e.g. after rollback to a big version)."""
        st = ScriptStaging(model_id=model_id)
        if base is not None:
            st.base = base
        self._staging[model_id] = self._attach(st)
        self._staging.move_to_end(model_id)
        self._evict_lru()
        self._persist(st)
        return st

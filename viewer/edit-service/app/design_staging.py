# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Design-JSON staging: WPS-style in-memory edit history (undo/redo ring buffer).

The design JSON is the single source of truth for generated models. Edits to
it go through a per-model staging buffer instead of a persistent per-step
commit chain:

- ``push`` records a new design state; the buffer keeps at most
  ``MAX_STEPS`` (10) states, dropping the oldest (WPS-style <- ->).
- ``undo``/``redo`` move a cursor back/forward through the buffer.
- ``discard`` throws the staging away; nothing is persisted, no diff exists.
- Only an explicit ``save`` (promote) turns the current staged design into a
  big version (see design_versions.py) and clears the buffer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

MAX_STEPS = 10


@dataclass
class DesignStaging:
    """Per-model in-memory design JSON edit history."""

    model_id: str
    base: Dict[str, Any] = field(default_factory=dict)  # last saved big version's design
    history: List[Dict[str, Any]] = field(default_factory=list)  # staged states, oldest first
    cursor: int = -1  # index into history of the current staged state; -1 = at base

    def current(self) -> Dict[str, Any]:
        """Current effective design JSON (staged state, or base if none staged)."""
        if self.cursor >= 0 and self.cursor < len(self.history):
            return self.history[self.cursor]
        return self.base

    def push(self, design: Dict[str, Any]) -> None:
        """Record a new staged state, dropping redo tail and oldest beyond MAX_STEPS."""
        if self.cursor >= 0 and self.cursor < len(self.history) - 1:
            # New edit invalidates the redo tail.
            self.history = self.history[: self.cursor + 1]
        self.history.append(design)
        if len(self.history) > MAX_STEPS:
            self.history = self.history[-MAX_STEPS:]
        self.cursor = len(self.history) - 1

    def undo(self) -> bool:
        """Move one step back; returns False when already at the oldest."""
        if self.cursor < 0:
            return False
        self.cursor -= 1
        return True

    def redo(self) -> bool:
        """Move one step forward; returns False when already at the newest."""
        if self.cursor >= len(self.history) - 1:
            return False
        self.cursor += 1
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
        return dropped

    def save(self) -> None:
        """Promote the current staged state to the new base (called after big-version save)."""
        self.base = self.current()
        self.history = []
        self.cursor = -1


class StagingRegistry:
    """App-wide map of model_id -> DesignStaging."""

    def __init__(self) -> None:
        self._staging: Dict[str, DesignStaging] = {}

    def get(self, model_id: str) -> DesignStaging:
        return self._staging.setdefault(model_id, DesignStaging(model_id=model_id))

    def reset(self, model_id: str, base: Optional[Dict[str, Any]] = None) -> DesignStaging:
        """Recreate staging for a model (e.g. after external IFC upload)."""
        st = DesignStaging(model_id=model_id)
        if base is not None:
            st.base = base
        self._staging[model_id] = st
        return st

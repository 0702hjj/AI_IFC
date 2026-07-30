"""IFC model registry: load/save with per-path file locks.

Models are cached by absolute path so repeated loads return the same
``ifcopenshell.file`` object. Saves are atomic (write ``path + ".tmp"``
then ``os.replace``) and serialized per path via ``threading.Lock``.
"""

from __future__ import annotations

import os
import threading
from typing import Dict

import ifcopenshell


class ModelRegistry:
    """In-memory cache of opened IFC models with atomic save."""

    def __init__(self) -> None:
        self._models: Dict[str, ifcopenshell.file] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def load(self, path: str) -> ifcopenshell.file:
        """Open (or return cached) model for an absolute path."""
        key = os.path.abspath(path)
        with self._guard:
            if key not in self._models:
                self._models[key] = ifcopenshell.open(key)
            return self._models[key]

    def save(self, path: str) -> None:
        """Atomically write the loaded model back to disk (holds the path lock)."""
        key = os.path.abspath(path)
        if key not in self._models:
            raise KeyError(f"model not loaded: {key}")
        tmp = key + ".tmp"
        with self.lock(key):
            self._models[key].write(tmp)
            os.replace(tmp, key)

    def lock(self, path: str) -> threading.Lock:
        """Return the per-path lock (same lock for the same path)."""
        key = os.path.abspath(path)
        with self._guard:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            return self._locks[key]

    def unload(self, path: str) -> None:
        """Drop a model from the cache (no-op if not loaded)."""
        key = os.path.abspath(path)
        with self._guard:
            self._models.pop(key, None)

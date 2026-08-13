# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""IFC model registry: load/save with per-path file locks and LRU eviction.

Models are cached by absolute path so repeated loads return the same
``ifcopenshell.file`` object. Saves are atomic (write ``path + ".tmp"``
then ``os.replace``) and serialized per path via ``threading.Lock``.

The cache is bounded: at most ``max_models`` models stay loaded. ``load``
refreshes recency; once the cap is exceeded the least-recently-used model is
evicted (disk writes already go through the atomic ``save``, so eviction
only drops the cache entry). An evicted model is transparently re-opened
from disk on its next ``load``.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
from typing import Callable, Dict, List

import ifcopenshell


class ModelRegistry:
    """Bounded in-memory cache of opened IFC models with atomic save."""

    def __init__(self, max_models: int = 8) -> None:
        self._max_models = max(1, max_models)
        self._models: "OrderedDict[str, ifcopenshell.file]" = OrderedDict()
        self._locks: Dict[str, threading.RLock] = {}
        self._guard = threading.Lock()
        self._evict_callbacks: List[Callable[[str], None]] = []

    def on_evict(self, callback: Callable[[str], None]) -> None:
        """Register a hook called with the path of each LRU-evicted model.

        Used to flag pending entries as needing replay: eviction drops the
        in-memory edits those entries describe.
        """
        self._evict_callbacks.append(callback)

    def load(self, path: str) -> ifcopenshell.file:
        """Open (or return cached) model for an absolute path.

        The cache check-and-get runs under the per-path lock so a
        concurrent ``unload`` cannot drop the entry between check and get.
        Loading marks the model most-recently-used and evicts the oldest
        entry once ``max_models`` is exceeded.
        """
        key = os.path.abspath(path)
        with self.lock(key):
            model = self._models.get(key)
            if model is None:
                model = ifcopenshell.open(key)
                self._models[key] = model
            else:
                self._models.move_to_end(key)
            self._evict_lru(protect=key)
            return self._models[key]

    def _evict_lru(self, protect: str) -> None:
        """Drop oldest entries beyond capacity (never the ``protect``ed key).

        The victim's per-path lock is taken non-blocking to avoid lock-order
        deadlock with a concurrent ``load``/``save`` on that path; under
        contention eviction is simply deferred to a later ``load``.
        """
        while len(self._models) > self._max_models:
            victim = next((k for k in self._models if k != protect), None)
            if victim is None:
                return
            victim_lock = self.lock(victim)
            if not victim_lock.acquire(blocking=False):
                return
            try:
                self._models.pop(victim, None)
            finally:
                victim_lock.release()
            for callback in self._evict_callbacks:
                callback(victim)

    def save(self, path: str) -> None:
        """Atomically write the loaded model back to disk (holds the path lock)."""
        key = os.path.abspath(path)
        with self.lock(key):
            if key not in self._models:
                raise KeyError(f"model not loaded: {key}")
            tmp = key + ".tmp"
            self._models[key].write(tmp)
            os.replace(tmp, key)

    def lock(self, path: str) -> threading.RLock:
        """Return the per-path reentrant lock (same lock for the same path)."""
        key = os.path.abspath(path)
        with self._guard:
            if key not in self._locks:
                self._locks[key] = threading.RLock()
            return self._locks[key]

    def unload(self, path: str) -> None:
        """Drop a model from the cache (no-op if not loaded)."""
        key = os.path.abspath(path)
        with self.lock(key):
            self._models.pop(key, None)

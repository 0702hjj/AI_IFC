# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Script text diff between two build scripts (big versions or staging steps).

The build script is the single source of truth (script-as-source), so the
primary AI-facing diff is a plain ``difflib.unified_diff`` over the two
script texts, plus two cheap summaries:

- ``params_changes`` — ast-extracted PARAMS dict comparison (keys
  added/removed/modified), so the AI can locate knob changes without
  reading the whole diff. A missing/unparseable PARAMS block is treated
  as an empty dict.
- ``stats`` — +/- line counts of the unified diff.

This replaces the retired design-JSON diff engine (design_diff.py, W-0012).
"""

from __future__ import annotations

import difflib
from typing import Any, Dict, List

from . import script_params


def text_diff(
    base_text: str,
    target_text: str,
    base_label: str = "base",
    target_label: str = "target",
) -> str:
    """Unified diff of two script texts (empty string when identical)."""
    return "".join(
        difflib.unified_diff(
            base_text.splitlines(keepends=True),
            target_text.splitlines(keepends=True),
            fromfile=base_label,
            tofile=target_label,
        )
    )


def _extract_or_empty(script_text: str) -> Dict[str, Any]:
    try:
        return script_params.extract_params(script_text)
    except ValueError:
        return {}


def params_changes(base_text: str, target_text: str) -> List[Dict[str, Any]]:
    """PARAMS dict key-level changes (added/removed/modified), sorted by key."""
    base = _extract_or_empty(base_text)
    target = _extract_or_empty(target_text)
    changes: List[Dict[str, Any]] = []
    for key in sorted(set(base) | set(target)):
        in_base, in_target = key in base, key in target
        if in_base and not in_target:
            changes.append({"key": key, "action": "removed", "old": base[key]})
        elif in_target and not in_base:
            changes.append({"key": key, "action": "added", "new": target[key]})
        elif base[key] != target[key]:
            changes.append({"key": key, "action": "modified",
                            "old": base[key], "new": target[key]})
    return changes


def _stats(diff_text: str) -> Dict[str, int]:
    added = removed = 0
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return {"added": added, "removed": removed}


def diff_scripts(
    base_text: str,
    target_text: str,
    base_label: str = "base",
    target_label: str = "target",
) -> Dict[str, Any]:
    """Full script diff payload: unified text diff + PARAMS changes + stats."""
    text = text_diff(base_text, target_text, base_label, target_label)
    return {
        "text_diff": text,
        "params_changes": params_changes(base_text, target_text),
        "stats": _stats(text),
    }

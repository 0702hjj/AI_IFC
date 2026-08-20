# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""building.json 交付索引的字段级 diff（C1+diff，交付对齐）。

与 server/internal/store/jsondiff.go 同语义：对象按 key、数组按索引、
标量不等 = modify；输出 [{op: add|remove|modify, path, before?, after?}]。
building.json 是交付索引（plan 形态整栋楼 + 逐 zone DXF 指针）——版本间
字段级差异即交付变化视图（DXF 几何变 + 索引变）。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def diff_building(base_text: str, target_text: str) -> List[Dict[str, Any]]:
    """比较两个 building.json 文本，返回字段级差异列表（缺失/非法 JSON → None 语义由调用方定）。"""
    try:
        base = json.loads(base_text)
        target = json.loads(target_text)
    except (ValueError, TypeError):
        return []
    out: List[Dict[str, Any]] = []
    _diff_value("", base, target, out)
    return out


def _diff_value(path: str, base: Any, target: Any, out: List[Dict[str, Any]]) -> None:
    if isinstance(base, dict):
        if not isinstance(target, dict):
            _diff_scalar(path, base, target, out)
            return
        for k, bv in base.items():
            if k not in target:
                out.append({"op": "remove", "path": _join(path, k), "before": bv})
            else:
                _diff_value(_join(path, k), bv, target[k], out)
        for k, tv in target.items():
            if k not in base:
                out.append({"op": "add", "path": _join(path, k), "after": tv})
    elif isinstance(base, list):
        if not isinstance(target, list):
            _diff_scalar(path, base, target, out)
            return
        n = min(len(base), len(target))
        for i in range(n):
            _diff_value(f"{path}[{i}]", base[i], target[i], out)
        for i in range(n, len(base)):
            out.append({"op": "remove", "path": f"{path}[{i}]", "before": base[i]})
        for i in range(n, len(target)):
            out.append({"op": "add", "path": f"{path}[{i}]", "after": target[i]})
    else:
        _diff_scalar(path, base, target, out)


def _diff_scalar(path: str, base: Any, target: Any, out: List[Dict[str, Any]]) -> None:
    if base != target:
        out.append({"op": "modify", "path": path, "before": base, "after": target})


def _join(path: str, key: str) -> str:
    return key if not path else f"{path}.{key}"


def load_building_sidecar(data_dir: str, model_id: str, version: str) -> Optional[str]:
    """读 scripts/v{version}.building.json（C1 sidecar）；不存在返回 None。"""
    import os

    path = os.path.join(data_dir, "models", model_id, "scripts", f"{version}.building.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None

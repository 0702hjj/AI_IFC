# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Semantic DXF diff engine (pure functions, ezdxf).

演进自 ``mcp/app/dxf_diff.py``（handle 对齐旧实现）：

- **对齐键迁移 handle → XDATA key**：DXF handle 由 CAD 软件分配、重存全变，
  不能当身份用；稳定身份是 cad_script_lib 写入的 AIDXF XDATA key
  （``{layer}:{kind}:{n}``）。同 key 不同 handle 不产生增删——这是 mcp 版
  的已知踩坑点。
- **bulge 补齐**：LWPOLYLINE 签名用 ``get_points("xyseb")``，含
  start/end width 与 bulge（mcp 版只取 xy，漏 bulge）。
- **公共三字段**：每种已知实体的签名都附加 layer/color/linetype。
- **无 key 降级**：无 XDATA 的实体按 ``(dxftype, signature)`` 多重集合
  计数对齐，只参与 added/removed（entry key ``nokey:{type}:{i}``，按
  ``(type, repr(signature))`` 排序后编号，确定性），**永不进 changed**。

输出 schema 与 IFC 侧 diffing 同形：
``{"added": [key], "removed": [key], "changed": [{"key", "changes": [{"field", "old", "new"}]}]}``，
added/removed 为排序后的 key 列表。与 IFC 的本质差异：CAD 里几何就是
数据，坐标参与 diff。
"""

from __future__ import annotations

import logging
import sys
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import ezdxf

logger = logging.getLogger(__name__)

_PRECISION = 6

_cad_script_lib: Any = None


def _load_cad_script_lib() -> Any:
    """单点 lazy loader：经 flows_dir sys.path 导入 cad_script_lib。

    与 script_runner._load_cad_script_lib 同模式，但 compute_diff 只收路径、
    不收 settings，故这里自行经 app.config.load_settings() 解析 flows_dir。
    """
    global _cad_script_lib
    if _cad_script_lib is None:
        from .config import load_settings

        flows_dir = load_settings().flows_dir
        if flows_dir not in sys.path:
            sys.path.insert(0, flows_dir)
        import cad_script_lib

        _cad_script_lib = cad_script_lib
    return _cad_script_lib


def _point(value: Any) -> Tuple[float, ...]:
    """坐标 → round 6 的 tuple（须可哈希：无 key 降级走 Counter 计数）。"""
    return tuple(round(float(v), _PRECISION) for v in value)


def _entity_key(entity: Any) -> Optional[str]:
    """实体的 XDATA 确定性 key；无 XDATA / 异常 → None。"""
    return _load_cad_script_lib().get_entity_key(entity)


def _signature(entity: Any) -> Optional[Tuple[Tuple[str, Any], ...]]:
    """按 dxftype 的关键属性集 + 公共三字段；未知类型 → None（仅计数）。"""
    dxftype = entity.dxftype()
    dxf = entity.dxf
    if dxftype == "LINE":
        sig: Tuple[Tuple[str, Any], ...] = (
            ("start", _point(dxf.start)), ("end", _point(dxf.end)))
    elif dxftype == "LWPOLYLINE":
        points = tuple(
            tuple(round(float(v), _PRECISION) for v in p)
            for p in entity.get_points("xyseb")
        )
        sig = (("points", points),)
    elif dxftype == "CIRCLE":
        sig = (("center", _point(dxf.center)),
               ("radius", round(dxf.radius, _PRECISION)))
    elif dxftype == "ARC":
        sig = (
            ("center", _point(dxf.center)),
            ("radius", round(dxf.radius, _PRECISION)),
            ("start_angle", round(dxf.start_angle, _PRECISION)),
            ("end_angle", round(dxf.end_angle, _PRECISION)),
        )
    elif dxftype == "TEXT":
        sig = (("text", dxf.text), ("insert", _point(dxf.insert)))
    elif dxftype == "MTEXT":
        sig = (("text", entity.text), ("insert", _point(dxf.insert)))
    elif dxftype == "INSERT":
        sig = (("name", dxf.name), ("insert", _point(dxf.insert)))
    else:
        return None
    return sig + (
        ("layer", dxf.layer),
        ("color", dxf.color),
        ("linetype", dxf.linetype),
    )


def _entities_by_key(
    doc: Any,
) -> Tuple[Dict[str, Any], List[Tuple[str, Any]]]:
    """modelspace 遍历：有 key → key 对齐；无 key → (dxftype, signature) 计数。"""
    keyed: Dict[str, Any] = {}
    keyless: List[Tuple[str, Any]] = []
    for entity in doc.modelspace():
        key = _entity_key(entity)
        if key is not None:
            if key in keyed:
                # 同 key 多实体：身份对齐歧义，后者覆盖前者但必须明面化，
                # 不得静默（Task 2 review 遗留）。
                logger.warning("duplicate XDATA key %r in DXF; later entity wins", key)
            keyed[key] = entity
        else:
            keyless.append((entity.dxftype(), _signature(entity)))
    return keyed, keyless


def _nokey_entries(entries: List[Tuple[str, Any]]) -> List[str]:
    """无 key 失配项 → 确定性 entry key（按 (type, repr(sig)) 排序后编号）。"""
    ordered = sorted(entries, key=lambda item: (item[0], repr(item[1])))
    return [f"nokey:{dxftype}:{i}" for i, (dxftype, _) in enumerate(ordered)]


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def compute_diff(base_path: str, target_path: str) -> Dict[str, Any]:
    """两个 DXF 文件的实体级语义 diff（XDATA key 对齐 + 无 key 计数降级）。"""
    base_keyed, base_keyless = _entities_by_key(ezdxf.readfile(base_path))
    target_keyed, target_keyless = _entities_by_key(ezdxf.readfile(target_path))

    added = sorted(k for k in target_keyed if k not in base_keyed)
    removed = sorted(k for k in base_keyed if k not in target_keyed)

    base_counts = Counter(base_keyless)
    target_counts = Counter(target_keyless)
    unmatched_base = list((base_counts - target_counts).elements())
    unmatched_target = list((target_counts - base_counts).elements())
    added = sorted(added + _nokey_entries(unmatched_target))
    removed = sorted(removed + _nokey_entries(unmatched_base))

    changed: List[Dict[str, Any]] = []
    for key in sorted(set(base_keyed) & set(target_keyed)):
        old_entity, new_entity = base_keyed[key], target_keyed[key]
        if old_entity.dxftype() != new_entity.dxftype():
            changes = [{
                "field": "type",
                "old": old_entity.dxftype(),
                "new": new_entity.dxftype(),
            }]
        else:
            old_sig = dict(_signature(old_entity) or ())
            new_sig = dict(_signature(new_entity) or ())
            changes = [
                {"field": field, "old": _jsonable(old_sig.get(field)),
                 "new": _jsonable(new_sig.get(field))}
                for field in sorted(set(old_sig) | set(new_sig))
                if old_sig.get(field) != new_sig.get(field)
            ]
        if changes:
            changed.append({"key": key, "changes": changes})

    return {"added": added, "removed": removed, "changed": changed}

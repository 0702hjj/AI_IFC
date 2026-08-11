# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""PARAMS extraction/replacement on build scripts (ast, no execution).

The script contract puts all tunables in a top-level ``PARAMS = {...}``
literal dict. ``extract_params`` feeds the params form; ``replace_params``
rewrites just the PARAMS block (params-only PUT mode) so form submissions
never touch the rest of the script.
"""

from __future__ import annotations

import ast
import json
from typing import Any, Dict


def _find_params_assign(tree: ast.Module) -> ast.Assign:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "PARAMS":
                    return node
    raise ValueError("脚本缺少顶层 PARAMS 赋值")


def _parse(script_text: str) -> ast.Module:
    try:
        return ast.parse(script_text)
    except SyntaxError as exc:
        raise ValueError(f"语法错误: {exc}") from exc


def extract_params(script_text: str) -> Dict[str, Any]:
    """Return the literal value of the top-level PARAMS dict."""
    node = _find_params_assign(_parse(script_text))
    if not isinstance(node.value, ast.Dict):
        raise ValueError("PARAMS 必须是顶层字面量 dict")
    try:
        value = ast.literal_eval(node.value)
    except (ValueError, TypeError) as exc:
        raise ValueError("PARAMS 必须是字面量(不得含表达式/调用)") from exc
    if not isinstance(value, dict):
        raise ValueError("PARAMS 必须是 dict")
    return value


def _render_literal(value: Any) -> str:
    """Render a JSON-compatible value as a Python literal (json.dumps emits true/null)."""
    if value is None:
        return "None"
    if value is True:
        return "True"
    if value is False:
        return "False"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_render_literal(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(
            f"{_render_literal(k)}: {_render_literal(v)}" for k, v in value.items()
        ) + "}"
    raise ValueError(f"params 必须 JSON-compatible: {type(value).__name__}")


def replace_params(script_text: str, params: Dict[str, Any]) -> str:
    """Splice a new PARAMS literal into the script, preserving everything else."""
    try:
        json.dumps(params, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"params 必须 JSON-compatible: {exc}") from exc
    rendered = _render_literal(params)

    lines = script_text.splitlines(keepends=True)
    node = _find_params_assign(_parse(script_text))
    if node.lineno < 1 or node.end_lineno is None:  # pragma: no cover - ast guarantee
        raise ValueError("无法定位 PARAMS 块")
    start = node.lineno - 1
    end = node.end_lineno
    indent = lines[start][: node.col_offset]
    return "".join(lines[:start]) + f"{indent}PARAMS = {rendered}\n" + "".join(lines[end:])

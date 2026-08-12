# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""校验隔离契约测试（机器强制），镜像 services/ifc 同款（W-0024）。

AGENTS.md「校验与业务隔离」硬规则：业务规则校验必须住在 ``verify*``/``validate*``
函数里；handler 内禁止内联 ``raise HTTPException``。本测试用 ast 解析
``app/routes_*.py``，断言 ``raise HTTPException`` 只出现在：

- 名为 ``verify*``/``validate*`` 的函数体内，或
- 模块 ``route_common.py`` 内（单点 helper）。

services/cad 是新服务：ALLOWLIST 从空集起步——任何 handler 内联 raise 即变红，
不存在「存量违规」概念。别名 import（``HTTPException as H``）按同一判定。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROUTES_DIR = Path(__file__).resolve().parents[1] / "app"

VERIFY_RE = re.compile(r"^(verify|validate)")

# 白名单从空集重建：services/cad 无存量违规，新违规直接变红。
ALLOWLIST: dict[str, set[str]] = {}


def violations_in_module(tree: ast.AST, module_name: str) -> list[tuple[str, int]]:
    """返回违规点：(最小函数名, 行号)。

    判定：``raise HTTPException`` 所在的最小函数名既非 verify*/validate*、
    模块又非 route_common.py，即违规。别名 import 的异常名纳入判定集合。
    """
    if module_name == "route_common.py":
        return []
    found: list[tuple[str, int]] = []
    exception_names = {"HTTPException"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "fastapi":
            for alias in node.names:
                if alias.name == "HTTPException":
                    exception_names.add(alias.asname or "HTTPException")

    class _V(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_Raise(self, node: ast.Raise) -> None:
            if (
                isinstance(node.exc, ast.Call)
                and isinstance(node.exc.func, ast.Name)
                and node.exc.func.id in exception_names
            ):
                func = self.stack[-1] if self.stack else "<module>"
                if not VERIFY_RE.match(func):
                    found.append((func, node.lineno))
            self.generic_visit(node)

    _V().visit(tree)
    return found


def route_modules() -> list[Path]:
    return sorted(ROUTES_DIR.glob("routes_*.py"))


def test_current_route_files_raise_only_in_verify_or_allowlisted():
    """当前代码库：所有违规点必须显式登记在 ALLOWLIST（新违规 → 红）。"""
    unlisted = []
    for path in route_modules():
        for func, line in violations_in_module(
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path)), path.name
        ):
            if func not in ALLOWLIST.get(path.name, set()):
                unlisted.append(f"{path.name}:{line} {func}")
    assert not unlisted, "以下 handler/helper 内联 raise HTTPException 未登记白名单（新违规）:\n" + "\n".join(unlisted)


def test_allowlist_entries_are_real_violations():
    """白名单只登记真实违规（无 stale 项）——收拢后必须同步删除。"""
    real = {
        path.name: {
            func
            for func, _ in violations_in_module(
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path)), path.name
            )
        }
        for path in route_modules()
    }
    stale = []
    for module, funcs in ALLOWLIST.items():
        if module not in real:
            stale.append(f"{module}（模块已不存在）")
        for func in funcs:
            if func not in real.get(module, set()):
                stale.append(f"{module}:{func}（已无违规）")
    assert not stale, "ALLOWLIST 存在失效项，收拢后请同步删除:\n" + "\n".join(stale)


# --- 自证：检查逻辑有区分力（对违规样例断言会变红）---

VIOLATING_SAMPLE = """\
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/models/{id}/script")
def get_script(id: str) -> str:
    if not id:
        raise HTTPException(status_code=404, detail="no script for model")
    return id
"""

VERIFY_SAMPLE = """\
from fastapi import HTTPException


def verify_script_body(body):
    if body is None:
        raise HTTPException(status_code=422, detail="body required")
"""

COMMON_SAMPLE = """\
from fastapi import HTTPException


def model_upload_path(request, model_id):
    raise HTTPException(status_code=404, detail="model not found")
"""

ALIAS_VIOLATING_SAMPLE = """\
from fastapi import APIRouter, HTTPException as H

router = APIRouter()


@router.get("/models/{id}/script")
def get_script_alias(id: str) -> str:
    if not id:
        raise H(status_code=404, detail="no script for model")
    return id
"""

ALIAS_VERIFY_SAMPLE = """\
from fastapi import HTTPException as H


def verify_script_body_alias(body):
    if body is None:
        raise H(status_code=422, detail="body required")
"""


def test_checker_detects_handler_inline_raise():
    """自证：handler 内联 raise HTTPException 必须被检出（变红）。"""
    tree = ast.parse(VIOLATING_SAMPLE)
    viol = violations_in_module(tree, "routes_x.py")
    assert ("get_script", 9) in viol, f"检查逻辑未检出违规 handler: {viol}"


def test_checker_accepts_verify_function_raise():
    """自证：verify*/validate* 函数内 raise 合法，不得误报。"""
    tree = ast.parse(VERIFY_SAMPLE)
    assert violations_in_module(tree, "routes_x.py") == []


def test_checker_accepts_route_common_module():
    """自证：route_common.py 模块整体豁免，不得误报。"""
    tree = ast.parse(COMMON_SAMPLE)
    assert violations_in_module(tree, "route_common.py") == []
    assert ("model_upload_path", 5) in violations_in_module(tree, "routes_x.py")


def test_checker_detects_alias_import_raise():
    """自证：别名 import（``HTTPException as H``）的 ``raise H(...)`` 必须被检出。"""
    tree = ast.parse(ALIAS_VIOLATING_SAMPLE)
    viol = violations_in_module(tree, "routes_x.py")
    assert ("get_script_alias", 9) in viol, f"检查逻辑未检出别名 raise: {viol}"


def test_checker_accepts_verify_function_alias_raise():
    """自证：别名 raise 落在 verify* 函数内仍合法，不得误报。"""
    tree = ast.parse(ALIAS_VERIFY_SAMPLE)
    assert violations_in_module(tree, "routes_x.py") == []

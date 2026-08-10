#!/usr/bin/env python3
"""validate_script.py — aiifc「校验即事件」hooks 的公共实现（单点定义）。

被两种 hook 形态复用：
- opencode-plugin.ts（tool.execute.after）spawn 本脚本
- validate_script.sh（Claude Code PostToolUse）spawn 本脚本 --claude-hook

原则（与 AGENTS.md「纪律事件化」同构）：
- 只依赖标准库；ifcopenshell 仅在沙箱试跑时惰性使用，缺失自动降级为纯静态校验。
- 结果以 JSON 事件输出（aiifc:// URI，见 hooks/README.md 事件 URI 表）：
  失败即事件，不把完整错误塞进主上下文。

CLI:
    validate_script.py <path> [--model-id X] [--static-only] [--sandbox-timeout S]
        [--claude-hook]

stdout 输出 JSON。--claude-hook 时读取 stdin 的 Claude Code PostToolUse 载荷
（tool_name/tool_input），对非构建脚本返回 {"decision": "approve"} 空载荷。
"""
import argparse
import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

MODEL_ID_RE = re.compile(r"^m_[0-9a-f]{16}$")
CONTRACT_MARKERS = ("def build(params", "PARAMS =")
SANDBOX_TIMEOUT = 60

FLOWS_DIR = Path(__file__).resolve().parents[1] / "references" / "docs" / "flows"


def looks_like_build_script(path: Path) -> bool:
    """是否 aiifc 构建脚本：*.py 且内容含契约特征（PARAMS = / def build(params）。"""
    if path.suffix != ".py":
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return any(marker in text for marker in CONTRACT_MARKERS)


def extract_model_id(path: Path) -> str | None:
    """从路径启发式提取 modelId：文件 stem 或任一祖先目录名匹配 ^m_[0-9a-f]{16}$。

    demo 布局：viewer/data/staging/{modelId}.py、viewer/data/models/{modelId}/scripts/v{n}.py。
    """
    candidates = [path.stem, *(p.name for p in reversed(path.parents))]
    for c in candidates:
        if MODEL_ID_RE.match(c):
            return c
    return None


def has_build_entry(src: str) -> bool:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    return any(
        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "build"
        for n in tree.body
    )


def _is_json_compatible(value) -> bool:
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return False
    return True


def static_validate(src: str) -> list[str]:
    """纯 ast 静态校验（与 script_lib.validate_script_contract 同构，stdlib-only）。

    仅在 script_lib 不可 import（无 ifcopenshell）时作为降级实现使用；
    tests/skill/test_skill_hooks.py 有漂移防护测试保证两者结论一致。
    """
    errors: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return [f"语法错误: {exc}"]

    params_node = None
    has_build = False
    has_main = False
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "PARAMS":
                    params_node = node.value
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "build":
            has_build = True
            if len(node.args.args) < 2:
                errors.append("build 入口签名应为 build(params, out_path)")
        elif isinstance(node, ast.If):
            test = node.test
            if (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
                    and test.left.id == "__name__"):
                has_main = True

    if params_node is None:
        errors.append("缺少顶层 PARAMS = {...} 字面量 dict")
    else:
        if not isinstance(params_node, ast.Dict):
            errors.append("PARAMS 必须是顶层字面量 dict")
        else:
            try:
                value = ast.literal_eval(params_node)
            except (ValueError, TypeError):
                errors.append("PARAMS 必须是字面量(不得含表达式/调用)")
            else:
                if not _is_json_compatible(value):
                    errors.append("PARAMS 必须 JSON-compatible")

    if not has_build:
        errors.append("缺少顶层 build(params, out_path) 入口函数")
    if not has_main:
        errors.append('缺少 if __name__ == "__main__": 守卫(__main__ 应用 PARAMS 调 build)')
    return errors


def static_validate_file(path: Path) -> list[str]:
    """静态校验：优先 script_lib.validate_script_contract（有 ifcopenshell 时保真）。

    script_lib 模块顶部 import ifcopenshell——无该库时 import 失败，降级为嵌入逻辑
    static_validate（同样只依赖 ast/标准库，结论一致，见漂移防护测试）。
    """
    try:
        sys.path.insert(0, str(FLOWS_DIR))
        import script_lib
    except ImportError:
        return static_validate(path.read_text(encoding="utf-8"))
    return script_lib.validate_script_contract(str(path))


def _have_ifcopenshell() -> bool:
    return importlib.util.find_spec("ifcopenshell") is not None


def _sandbox_python() -> str:
    return os.environ.get("AIIFC_PYTHON") or sys.executable


def run_sandbox(path: Path, out_dir: Path, timeout: int = SANDBOX_TIMEOUT) -> dict:
    """沙箱试跑：临时目录 + subprocess + timeout，不污染工作区。

    试跑 = 执行构建脚本（__main__ 应用 PARAMS 调 build，产物落到 out_path）。
    PYTHONPATH 注入 flows 目录（脚本经 script_lib 出口时能 import）。
    """
    out_path = out_dir / "model.ifc"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(FLOWS_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        proc = subprocess.run(
            [_sandbox_python(), str(path), str(out_path)],
            cwd=str(out_dir), env=env, capture_output=True,
            text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ran": True, "timed_out": True, "exit_code": None,
                "stderr_tail": f"试跑超时({timeout}s)"}
    except OSError as exc:
        return {"ran": False, "error": str(exc)}
    return {
        "ran": True,
        "exit_code": proc.returncode,
        "out_exists": out_path.exists(),
        "stderr_tail": (proc.stderr or "")[-500:],
    }


def build_event(path: Path, errors: list[str], mode: str,
                sandbox: dict | None = None, model_id: str | None = None) -> dict:
    """组装事件载荷（aiifc:// URI 形态，见 hooks/README.md）。"""
    ok = not errors
    mid = f"model/{model_id}/" if model_id else ""
    verb = "validated" if ok else "validation-failed"
    uri = f"aiifc://{mid}script/{verb}"
    event: dict = {"uri": uri, "ok": ok, "path": str(path), "mode": mode,
                   "errors": errors}
    if model_id:
        event["modelId"] = model_id
    if sandbox is not None:
        event["sandbox"] = sandbox
    return event


def _to_claude_hook(event: dict) -> dict:
    """把事件翻译成 Claude Code PostToolUse hook 输出（stdout JSON）。

    非构建脚本 → 空载荷（不影响主上下文）；构建脚本 → 简短 additionalContext
    （事件 URI + 最多 3 条错误摘要，截断 120 字符），不把完整错误塞进对话。
    """
    if event.get("uri") is None:
        return {"decision": "approve"}
    ctx = event["uri"]
    if not event["ok"]:
        detail = "；".join(event["errors"][:3])
        if len(detail) > 120:
            detail = detail[:117] + "..."
        ctx = f"{ctx} — {detail}"
    return {"decision": "approve",
            "description": "aiifc 构建脚本契约校验",
            "additionalContext": ctx}


def _run_claude_hook(path: Path, args: argparse.Namespace) -> dict:
    """Claude Code 入口：stdin 载荷 → 过滤 → 事件 → hook 输出 JSON。

    stdin 载荷（tool_name/tool_input.file_path）优先；stdin 缺失/非法时
    回退 argv 传入的 path（便于调试与单测）。
    """
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = None
    if payload:
        tool_input = payload.get("tool_input") or {}
        file_path = tool_input.get("file_path")
        if file_path:
            path = Path(file_path)
    if path is None:
        return {"decision": "approve"}
    if not looks_like_build_script(path):
        return {"decision": "approve"}
    event = _validate(path, args)
    return _to_claude_hook(event)


def _validate(path: Path, args: argparse.Namespace) -> dict:
    """执行校验流水线：静态（必做）→ 沙箱试跑（可选，ifcopenshell 可用时）。

    读取失败（文件被移走/权限）也产事件（validation-failed），不把 traceback 漏给宿主。
    """
    try:
        model_id = args.model_id or extract_model_id(path)
        errors = list(static_validate_file(path))
        mode = "static"
        sandbox = None
        src = path.read_text(encoding="utf-8")
        if (not args.static_only and not errors and has_build_entry(src)
                and _have_ifcopenshell()):
            mode = "sandbox"
            with tempfile.TemporaryDirectory(prefix="aiifc-sandbox-") as tmp:
                sandbox = run_sandbox(path, Path(tmp), args.sandbox_timeout)
            if sandbox.get("ran") and sandbox.get("exit_code") != 0:
                errors.append("沙箱试跑失败（脚本可运行性检查未通过）")
        return build_event(path, errors, mode, sandbox, model_id)
    except OSError as exc:
        return build_event(path, [f"读取脚本失败: {exc}"], "static")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="aiifc 构建脚本「校验即事件」：静态契约校验 + 可选沙箱试跑")
    parser.add_argument("path", type=Path, nargs="?", default=None,
                        help="构建脚本路径（*.py）；--claude-hook 时从 stdin 载荷取，可省")
    parser.add_argument("--model-id", default=None,
                        help="显式 modelId（覆盖路径启发式）")
    parser.add_argument("--static-only", action="store_true",
                        help="只做静态校验，跳过沙箱试跑")
    parser.add_argument("--sandbox-timeout", type=int, default=SANDBOX_TIMEOUT,
                        help="沙箱试跑超时秒数")
    parser.add_argument("--claude-hook", action="store_true",
                        help="Claude Code PostToolUse 模式：读 stdin 载荷、输出 hook JSON")
    args = parser.parse_args(argv)

    path = args.path
    if args.claude_hook:
        event = _run_claude_hook(path, args)
        print(json.dumps(event, ensure_ascii=False))
        return 0

    if path is None:
        print("error: 缺少构建脚本路径", file=sys.stderr)
        return 2
    if not looks_like_build_script(path):
        print(json.dumps({"uri": None, "ok": True, "path": str(path), "mode": "skip",
                          "reason": "不是 aiifc 构建脚本（无 PARAMS = / def build(params 契约特征）"},
                         ensure_ascii=False))
        return 0

    event = _validate(path, args)
    print(json.dumps(event, ensure_ascii=False))
    return 0 if event["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

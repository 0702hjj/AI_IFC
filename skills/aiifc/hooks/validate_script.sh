#!/usr/bin/env sh
# validate_script.sh — aiifc Claude Code PostToolUse hook 的薄 shell 包装。
#
# 由 hooks/claude-settings.json 的 PostToolUse command 调用（stdin 收 Claude Code
# 载荷 JSON，stdout 回 hook 输出 JSON），实际逻辑全在 validate_script.py：
#     exec python validate_script.py --claude-hook
#
# Python 解释器探测（降级链）：
#   1. 环境变量 AIIFC_PYTHON
#   2. 仓库内 services/ifc/.venv/bin/python（有 ifcopenshell）
#   3. python3（无 ifcopenshell 时 validate_script.py 自动降级为纯静态校验）
# 注意：静态校验只用标准库；沙箱试跑才需要 ifcopenshell。

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

PYTHON_BIN=${AIIFC_PYTHON:-}
if [ -z "$PYTHON_BIN" ]; then
  GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
  if [ -n "$GIT_ROOT" ] && [ -x "$GIT_ROOT/services/ifc/.venv/bin/python" ]; then
    PYTHON_BIN="$GIT_ROOT/services/ifc/.venv/bin/python"
  fi
fi
if [ -z "$PYTHON_BIN" ]; then
  PYTHON_BIN=python3
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/validate_script.py" --claude-hook

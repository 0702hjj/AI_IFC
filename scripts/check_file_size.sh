#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# 文件行数门控（AGENTS.md「代码门控」节）：源码/文档文件 ≤500 行。
# 存量超限登记在 scripts/file_size_whitelist.txt（白名单只减不增，新增超限变红）。
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

MAX=500
WHITELIST=scripts/file_size_whitelist.txt
violations=0

while IFS= read -r f; do
  case "$f" in
    # 自动生成物 / golden 参考物 / wasm 二进制 / 调研镜像文档 / 已执行完毕的历史 plan 归档：不计入门控
    # edit-api-reference.md 由 docs/scripts/gen-edit-api-reference.mjs 从 ai-tools.openapi.json 自动生成（gen:api 产物，与 docs/site/public/* 同类）
    docs/site/public/*|docs/site/reference/edit-api-reference.md|*/references/golden/*|*/tests/golden/*|web/public/wasm/*|research/*|docs/superpowers/plans/*) continue ;;
  esac
  case "$f" in
    *.py|*.go|*.ts|*.tsx|*.js|*.mjs|*.css|*.sh|*.md|*.toml|*.yaml|*.yml|*.html) ;;
    *) continue ;;
  esac
  n=$(wc -l < "$f")
  if [ "$n" -gt "$MAX" ]; then
    grep -qxF "$f" "$WHITELIST" 2>/dev/null && continue
    echo "FAIL: $f 共 $n 行（上限 $MAX）——按领域/职责拆分；存量超限登记进 $WHITELIST"
    violations=$((violations + 1))
  fi
done < <(git ls-files)

[ "$violations" -eq 0 ] && { echo "file-size gate OK（上限 $MAX 行）"; exit 0; }
echo "共 $violations 个未登记超限文件" >&2
exit 1

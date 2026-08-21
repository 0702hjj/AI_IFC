#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj
#
# install_skill_venv.sh —— 独立 skill venv（第二层：CLI 环境落地）
#
# 目的：dist 正式 skill 的 CLI（aiplan / aidxfv3）装进独立 venv（skills/.venv），
# 与 services/ifc、services/cad 的 venv 隔离。agent 的 execute 工具通过 PATH 调用。
#
# 用法：bash tools/install_skill_venv.sh
# 产物：skills/.venv/bin/{aiplan,aidxfv3,...}（console_scripts）
#
# 说明：
#   - aiplan：editable 安装 aiplan_tools（requirements.txt 自包含）
#   - aidxf ：5 个包（archdxf/dxfkit/floorgeom/flowops/goldlib）+ ezdxf/shapely/Pillow
#   - 本脚本幂等（重跑 = 重新安装到同一 venv）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${SKILL_VENV_DIR:-$ROOT/skills/.venv}"
DIST_DIR="$ROOT/skills/dist"

if [[ ! -d "$DIST_DIR" ]]; then
  echo "ERROR: dist skill 目录不存在: $DIST_DIR" >&2
  exit 1
fi

echo "==> 创建独立 skill venv: $VENV_DIR"
python3 -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "==> 安装 aiplan CLI（aiplan_tools editable）"
pip install --quiet --upgrade pip
pip install --quiet jsonschema shapely
pip install --quiet --editable "$DIST_DIR/aiplan/scripts/packages/aiplan_tools"

echo "==> 安装 aidxf CLI（5 本地包 + aidxfv3 主包，--no-deps 避免 PyPI 解析本地依赖失败）"
# 本地包之间互相依赖（dxfkit→floorgeom 等），PyPI 没有这些包——
# 先 --no-deps 全部装到位，再统一装运行时依赖（ezdxf/shapely/Pillow）
for pkg in archdxf floorgeom goldlib dxfkit flowops; do
  pip install --quiet --no-deps --editable "$DIST_DIR/aidxf/scripts/packages/$pkg"
done
# aidxfv3 主包已原生声明 [project.scripts]（cli.py:main → bin/aidxfv3），无需 shim
pip install --quiet --no-deps --editable "$DIST_DIR/aidxf/scripts/aidxfv3"
pip install --quiet ezdxf shapely Pillow

echo "==> 安装 aiifc CLI（aiifc 主包 + flows 脚本运行时依赖 ifcopenshell/ifcquery）"
# aiifc CLI（console_scripts aiifc=aiifc.cli:main）——flows 脚本（design_builder/
# build_script_template/dxf_from_design）的通用 shell 入口 + consume_upstream 新库。
# flows 脚本运行时需要 ifcopenshell/ifcquery（build_script_template 产 IFC）。
pip install --quiet --no-deps --editable "$DIST_DIR/aiifc/scripts/aiifc"
pip install --quiet "ifcopenshell>=0.8" "ifcquery>=0.8" numpy ezdxf

echo "==> 验证"
"$VENV_DIR/bin/aiplan" gate --help >/dev/null 2>&1 && echo "  aiplan OK" || echo "  aiplan 不可用（检查安装）"
"$VENV_DIR/bin/aidxfv3" --help >/dev/null 2>&1 && echo "  aidxfv3 OK" || echo "  aidxfv3 不可用（检查安装）"
"$VENV_DIR/bin/aiifc" --help >/dev/null 2>&1 && echo "  aiifc OK" || echo "  aiifc 不可用（检查安装）"

echo "==> 完成。server 装配时配置："
echo "    server_config.json: \"skillVenv\": \"$VENV_DIR\""
echo "    env: VIEWER_SKILLS_VENV=$VENV_DIR"

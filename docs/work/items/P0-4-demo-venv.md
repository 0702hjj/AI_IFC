# P0-4: demo 环境文档与实际 venv 不符

- **状态：** done
- **关闭于：** 59a74b3（文档命令实测通过）
- **优先级：** P0
- **Milestone：** M1（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** opencode / fix/post-v2-audit

## 背景

SKILL.md 与 ifc-demo.md 声称 demo 使用根 `.venv`（已装 ifcopenshell）；实测根 `.venv` 中没有 ifcopenshell/ezdxf/ifcquery——这些依赖装在 `viewer/edit-service/.venv`（edit-service 的 uv 项目自包含环境）。按文档逐条执行直接 ImportError，demo 流程第一步就走不通。

## 涉及位置

- `skills/aiifc/SKILL.md:133` — 声称 demo 用根 `.venv`
- `.opencode/agent/ifc-demo.md:14` — 同上
- `viewer/edit-service/.venv` — 实际装有 ifcopenshell/ezdxf/ifcquery 的环境（uv sync 自包含）
- `examples/README.md` — 已按 edit-service venv 写法，可作为参照

## 方案

把 SKILL.md:133 与 .opencode/agent/ifc-demo.md:14 的环境指引改为 `viewer/edit-service/.venv`（由 edit-service 的 uv 项目 `uv sync` 自包含生成）；同时核实 ifc-demo.md 其余命令均在 edit-service 根目录下可跑，路径/工作目录假设一并修正。

## 验收标准

在一个全新 shell 中按修复后的文档逐条执行，全部命令成功，无 ImportError。

## 测试要求

CI skill-pack 的 flows 冒烟已覆盖环境正确性，文档修复本身无新增测试；但验收必须人工或脚本实际走一遍文档中的命令，确认全部可执行。

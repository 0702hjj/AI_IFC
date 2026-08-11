# P2-5: examples/ 两时代混合

- **状态：** done
- **优先级：** P2
- **Milestone：** 本轮（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** docs/work-board-and-cleanup
- **关闭于：** 本分支（2026-08-05 清理）

## 背景

examples/ 目录中 SCAD 时代与 IFC 时代的示例混杂，SCAD 示例对当前产品（IFC 编辑/查看）已无意义，且会误导使用者以为 SCAD 仍是支持的功能面。

## 涉及位置

- `examples/` — SCAD 示例与现行示例混合
- `examples/README.md` — 目录说明

## 方案

删除 examples/ 中的 SCAD 示例，重写 examples/README.md 以反映现行内容（含 demo 环境指向 `services/ifc/.venv` 的写法，与 P0-4 一致）。

## 验收标准

examples/ 中无 SCAD 示例残留，README 与目录实际内容一致。

## 测试要求

删除/文档类变更无新增测试；以 CI 全绿作为回归保障。

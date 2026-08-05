# P2-4: README 多处过时

- **状态：** done
- **优先级：** P2
- **Milestone：** M1（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** docs/work-board-and-cleanup
- **关闭于：** 本分支 commit 22ac75e（布局块）与 3f8fd51（archive 引用语境）

## 背景

README 的仓库布局块曾引用已删除的 `docs/archive/` 目录，且缺少新增的 `docs/work/`（工作项看板）与 `AGENTS.md`（人机协同契约）条目。中英文两版已同步修正。

## 涉及位置

- `README.md` 与 `README.zh-CN.md` — 布局块曾含 `docs/archive/` 行、缺 `docs/work/` 与 `AGENTS.md` 行（已修复，保留此行作历史记录）

## 方案

README 布局块删除 `docs/archive/` 行，补加 `docs/work/` 与 `AGENTS.md` 行；中英文两版同步修改。

已按此方案于本分支实施。

## 验收标准

全仓 grep 无 `docs/archive` 引用残留，README 布局与实际目录一致。（已满足）

## 测试要求

无（纯文档变更）。

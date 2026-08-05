# P2-4: README 多处过时

- **状态：** open
- **优先级：** P2
- **Milestone：** M1（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** （领取时填）

## 背景

README 的仓库布局块仍引用已删除的 `docs/archive/` 目录，且缺少新增的 `docs/work/`（工作项看板）与 `AGENTS.md`（人机协同契约）条目。中英文两版需同步修正。

## 涉及位置

- `README.md` / `README.zh-CN.md`（或等价中英两版文件）— 布局块含 `docs/archive/` 行，缺 `docs/work/` 与 `AGENTS.md` 行

## 方案

README 布局块删除 `docs/archive/` 行，补加 `docs/work/` 与 `AGENTS.md` 行；中英文两版同步修改。

## 验收标准

全仓 grep 无 `docs/archive` 引用残留，README 布局与实际目录一致。

## 测试要求

无（纯文档变更）。

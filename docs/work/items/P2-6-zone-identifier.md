# P2-6: research/ :Zone.Identifier 脏文件

- **状态：** done
- **优先级：** P2
- **Milestone：** 本轮（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** docs/work-board-and-cleanup
- **关闭于：** 本分支（2026-08-05 清理）

## 背景

research/ 目录下约有 20 个 `:Zone.Identifier` 文件——这是 Windows/WSL 下载文件时产生的 NTFS 备用数据流元数据残留，不属于仓库内容，污染目录并被 git 追踪。

## 涉及位置

- `research/` — 约 20 个 `:Zone.Identifier` 文件

## 方案

全部删除；可视情况在 .gitignore 中补 `*:Zone.Identifier` 防止再次入库。

## 验收标准

research/ 下无 `:Zone.Identifier` 文件残留，git 追踪中亦不存在。

## 测试要求

无（纯清理）。

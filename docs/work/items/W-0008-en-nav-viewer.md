# W-0008: 英文 nav 补 Viewer Usage 入口

- **状态：** open
- **优先级：** P2
- **Milestone：** 待排（随下次 site 变更顺带）
- **来源：** P2-7 审查发现（2026-08-06）
- **执行者/分支：** （领取时填）

## 背景

P2-7 补齐了英文 sidebar 的 Viewer Usage 组，但顶部 nav 仍不对等：中文 nav 有「Viewer 使用」（`docs/site/.vitepress/config.mts:24` 附近），英文 nav 无对应入口。

## 方案

config.mts 英文 locale nav 加 `Viewer Usage` → `/en/viewer/library`（与中文 nav 目标 `/viewer/library` 对应）。

## 验收标准

- 英文站顶部 nav 可见 Viewer Usage 且链接有效；`npm run docs:build` 通过

## 测试要求

- vitepress build 即验证（死链 fail）

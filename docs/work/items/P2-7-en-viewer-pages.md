# P2-7: 文档站英文缺 Viewer 使用 6 页

- **状态：** done
- **关闭于：** ebd39b4 + 99fbb11
- **优先级：** P2
- **Milestone：** M3（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** opencode / feat/m3-release

## 背景

文档站英文区缺少 viewer/ 目录，英文 sidebar 因此缺「Viewer 使用」整组 6 页，中英文档站内容不对等——英文用户看不到 Viewer 的使用文档。

## 涉及位置

- `docs/site/en/` — 无 viewer/ 目录
- `docs/site/viewer/` — 中文版 6 页（翻译来源）
- `docs/site/.vitepress/config.mts:130-167` — 英文 sidebar 缺 Viewer 使用组

## 方案

把 docs/site/viewer/ 的 6 页翻译到 docs/site/en/viewer/，并在 config.mts 的英文 sidebar 中补上对应分组。

## 验收标准

英文站 sidebar 与中文站对等（含 Viewer 使用 6 页）；`docs:build` 通过。

## 测试要求

CI docs job 的 vitepress build 即验证手段（死链会导致 build fail）。

# W-0028: skill 版本化 + Release 分发

- **状态：** in-progress
- **优先级：** P1
- **Milestone：** v0.5（可移植复用）
- **来源：** spec 2026-08-12-portability-reuse-design.md §3
- **执行者/分支：** opencode / feat/v0.5-portability-reuse

## 背景

skill 目前只能从源码仓打包，无版本号、无分发渠道，第三方无法「下载安装即用」。本轮给 skill 加版本化（frontmatter `version` + CHANGELOG）、打包产物带版本号、打 tag 后走文档化手工流程 `gh release create` 挂产物发布（CI 自动化本轮不做，后置可选）。

## 涉及位置

- `skills/aiifc/`、`skills/aidxfv/`（v1/v2）、`skills/aiblueprint-mcp/`：SKILL.md frontmatter + 各自 CHANGELOG
- `tools/skill_pack.py`：archive 命名读 frontmatter 版本号
- `tests/skill/`：命名/frontmatter 契约测试
- `docs/site/`：新增《skill 获取与安装》文档

## 方案

1. 5 个 SKILL.md（aiifc、aidxfv v1、aidxfv v2、aiblueprint-mcp 等实际入口）frontmatter 补 `version` 字段，各自加 CHANGELOG（从本次版本起记）。
2. `tools/skill_pack.py`：archive 产物命名 `<name>-<version>.tar.gz`（读 frontmatter）；缺 `version` 时报错退出。
3. 发布流程文档化：打 tag → `gh release create` 挂打包产物；至少走通一次（可预发 tag 验证）。
4. 新增《skill 获取与安装》文档：Release 下载 → 解压到 `~/.agents/skills/`（及各 agent 运行时等价目录）→ 即用。

## 验收标准

- 5 个 SKILL.md 带 `version`，各有 CHANGELOG。
- archive 命名 `<name>-<version>.tar.gz`；缺 version 打包报错。
- 安装/发布文档入站，`npm run docs:build` 绿。
- Release 流程至少走通一次。

## 测试要求

- packer 变更 TDD（先失败测试后实现）：archive 命名断言、缺 version 报错断言入 `tests/skill/`。
- `tests/skill` 全绿；新增测试量 ≥ 新增实现量。

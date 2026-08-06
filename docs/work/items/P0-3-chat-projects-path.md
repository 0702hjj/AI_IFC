# P0-3: createChatProject 路径与 Go 注册不符

- **状态：** done
- **关闭于：** f5ded74 + b7c79bb（真实联调验证通过）
- **优先级：** P0
- **Milestone：** M1（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** opencode / fix/post-v2-audit

## 背景

前端调 `POST /api/v1/chat/projects` 创建 AI 项目，但 Go 只注册了 `POST /api/v1/projects`。请求经 `/api/v1/chat/` 前缀 mux 落到 chat mux 后返回 404，前端「新建 AI 项目」按钮实际不可用。**修复前需实测验证**确认现状。

## 涉及位置

- `viewer/web/src/api/client.ts:35` — 前端调 `POST /api/v1/chat/projects`
- `viewer/server/internal/api/chat.go:96` — Go 侧 chat 路由注册
- `viewer/server/cmd/server/main.go:129` — 只注册了 `POST /api/v1/projects`

## 方案

推荐方案：Go 侧注册改为 `POST /api/v1/chat/projects`，与 chat 模块其余端点的前缀保持一致。可保留 `/api/v1/projects` 兼容一个版本，也可直接替换——本产品是单机部署，直接替换即可，无需兼容期。README/文档中的端点说明同步更新。

## 验收标准

前端「新建 AI 项目」按钮真实可用：实测点击后成功创建项目，不再 404。

## 测试要求

1. Go chat 路由测试断言 `POST /api/v1/chat/projects` 返回 201/200。
2. 前端 `client.createChatProject` 测试断言请求路径为 `/api/v1/chat/projects`。

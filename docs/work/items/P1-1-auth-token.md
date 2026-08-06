# P1-1: 零鉴权 + CORS *

- **状态：** in-progress
- **优先级：** P1
- **Milestone：** M4（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** opencode / feat/m4-hardening

## 背景

Go server 的 CORS 配置为 `Access-Control-Allow-Origin: *`，且全部端点（含删除模型、edit commit、AI 聊天等破坏性操作）无任何认证。默认绑定 127.0.0.1 时风险尚可接受，一旦改 host 对外暴露即完全裸奔。

## 涉及位置

- `viewer/server/internal/api/api.go:74` — `Access-Control-Allow-Origin: *`
- 全部 API 端点 — 无认证中间件
- `viewer/edit-service` — 同样无鉴权，依赖网络隔离

## 方案

1. Go server 加最小 token 中间件：读取 `VIEWER_API_TOKEN` 环境变量；未设置 = 关闭鉴权，保持单机零配置体验；设置后除 `/health` 外全部端点要求 `Authorization: Bearer <token>`。
2. CORS 从 `*` 改为可配置白名单（默认 `localhost:5173`），通过环境变量追加来源。
3. edit-service 侧 token 由 Go 代理注入，或同样通过环境变量配置，与 Go 侧对齐。

## 验收标准

1. 设置 token 后：无 `Authorization` 头的请求返回 401，带正确 token 的请求正常通过。
2. 未设置 token 时行为与现状完全一致（鉴权关闭，单机体验不变）。

## 测试要求

1. 中间件单元测试覆盖四种情况：未设置 token（关闭）、无 token 请求、错误 token、正确 token。
2. 现有全部 API 测试在 token 关闭配置下不回归（全绿）。

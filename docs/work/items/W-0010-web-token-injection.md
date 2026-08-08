# W-0010: web 端 API token 注入

- **状态：** done
- **关闭于：** 57a14c5 + 93876ce
- **优先级：** P2
- **Milestone：** 待排（v0.2，对外暴露场景的前置）
- **来源：** P1-1 审查裁决（2026-08-06）
- **执行者/分支：** opencode / docs-site-redesign

## 背景

P1-1 交付了 Go server 的 token 中间件（`VIEWER_API_TOKEN`，默认关闭）。但 web 前端不发 `Authorization` 头——token 开启后浏览器 UI 的 `/api/v1/*` 全部 401，「对外暴露 + 浏览器 UI」场景不可用。

## 涉及位置

- `viewer/web/src/api/client.ts`（request() 统一注入点）
- 可能的 UI：设置页/localStorage token 输入

## 方案

1. client.ts 的 request() 从 `localStorage["aiifc_token"]` 读 token 注入 `Authorization: Bearer`
2. 401 响应时显示 token 输入 UI（模态或设置页），保存后重试
3. SSE（EventSource 不支持自定义头）：token 作为 query 参数传递需 server 侧支持（auth.go 加 `?token=` 回退）——或评估 `fetch-event-source` 替换原生 EventSource（W-0007 重构时可一并）

## 验收标准

- token 开启的栈：浏览器输入 token 后 UI 全部功能可用（含 chat SSE）
- token 关闭时零行为变化

## 测试要求

- client.ts 注入逻辑测试（有/无 token、401 触发输入 UI）
- server 侧若加 query token 回退：对应测试 + 文档（configuration 中英）

## 附带（同源小项）

- auth.go 强制 `Bearer ` scheme（当前裸 token 也放行）
- 豁免前缀改路由白名单或加 guard 测试（防未来新增 GET /v1/models/ 路由被静默豁免）

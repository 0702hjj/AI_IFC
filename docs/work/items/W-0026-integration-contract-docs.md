# W-0026: 对接契约文档（存储 + 前端）

- **状态：** open
- **优先级：** P1
- **Milestone：** v0.5（可移植复用）
- **来源：** spec 2026-08-12-portability-reuse-design.md §2
- **执行者/分支：** opencode / feat/v0.5-portability-reuse

## 背景

框架 spec 的「可复用性优先」已结构落地，但第三方无法对外消费：想对接存储层或自研前端时，契约只散在代码与内部文档里。本轮把 core 可移植做成轻量的契约文档化——公开站新增《平台对接契约》文档集（中英文按站点惯例），不改 web 代码，明确 `web/` 只是参考实现、可整体替换。

## 涉及位置

- `docs/site/`（新增两页文档，中英文；nav 更新）
- 依据：`docs/site/public/go-rest-api.routes.json`（已有生成物，只引用不手改）

## 方案

1. **存储接口契约**页：
   - Go `server` store 抽象：文件存储（默认零依赖）/ PG（可选）的接口面与切换方式。
   - `VIEWER_DATA_DIR` 数据目录布局（models / scripts / versions / maps 等），edit-service 与 server 共享约束。
   - PG schema 说明：第三方「整合进已有数据库」的两条路径——实现 store 接口，或直接复用本仓 PG schema。
2. **前端对接契约**页：
   - 基于 Go OpenAPI 说明自研/第三方前端对接方式：envelope `{code,message,data}`、SSE 事件、script-as-source 编辑流程（PUT /script → run → save → locate）。
   - 注明 `web/` 为参考实现，可整体替换。

## 验收标准

- 两页文档（中英文）入站，站点 nav 更新。
- `cd docs && npm run docs:build` 绿。

## 测试要求

文档任务无单测；`npm run docs:build` 为门禁。

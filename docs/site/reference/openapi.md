# OpenAPI 文件

## edit-service（机器可消费）

完整 OpenAPI schema 见 [ai-tools.openapi.json](/ai-tools.openapi.json)，由实现直接导出（`create_app().openapi()`），与运行中服务的 `GET /openapi.json` 天然一致。

编辑 API 变更后重新生成：

```bash
cd viewer/edit-service
uv run python scripts/export_openapi.py
```

脚本输出到 `docs/site/public/ai-tools.openapi.json`（站点构建时随 public 目录发布）。

## Go server

Go server（`:8090`）的完整请求/响应 schema 见 **[go-server.openapi.json](/go-server.openapi.json)**（OpenAPI 3.0，机器可消费，可直接喂给 LLM/工具/代码生成器）。

生成与漂移检测（诚实边界）：Go 用 stdlib `net/http` mux，无 schema 反射——请求/响应 schema 无法从代码自动导出。因此采用「路由清单自动 + schema 手工维护 + 覆盖漂移检测」：

- 路由清单由 `docs/scripts/gen-go-routes.mjs` 从 mux 注册自动提取（`go-rest-api.routes.json`，method/path/handler/源文件）；
- 请求/响应 schema 由 `docs/scripts/go-openapi-schema.mjs` 手工维护（内容源是 [Viewer REST API](/reference/rest-api) 契约）；
- 生成器 `docs/scripts/gen-go-openapi.mjs` 对两者做**双向覆盖断言**：schema 端点集 ⊆ routes 端点集 且 routes 端点集 ⊆ schema 端点集——新增路由未配 schema、或 schema 有死路由，都会令生成失败（CI 红）。这是能达到的最强自动一致性。

端点或 schema 变更后重新生成并校验：

```bash
cd docs
npm run gen:api    # 三件生成物：edit-api-reference.md + go-rest-api.routes.json + go-server.openapi.json
npm run check:api  # 自证测试 + 生成 + git 漂移检测（无 diff 才绿）
```

> 自动生成与漂移检测已部分落地：edit-service 的字段/端点参考页由 OpenAPI schema 生成（见 [编辑 API 参考（自动生成）](/reference/edit-api-reference)）；edit-service 的"代码 vs schema"漂移检测已具备前提（依赖已 PyPI 自包含），接入见 [Roadmap](/project/roadmap)。

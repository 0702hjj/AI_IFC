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

Go server 的 REST 契约当前以本文档站 [Viewer REST API](/reference/rest-api) 为人工维护的公开契约。另提供从 Go mux 注册扫描生成的**机器可读端点清单**：[go-rest-api.routes.json](/go-rest-api.routes.json)（method / path / handler / 源文件），由 `docs/scripts/gen-go-routes.mjs` 生成，`npm run check:api` 检测漂移；Go 侧请求/响应 schema 的完整自动生成仍属后续迭代。

> 自动生成与漂移检测已部分落地：edit-service 的字段/端点参考页由 OpenAPI schema 生成（见 [编辑 API 参考（自动生成）](/reference/edit-api-reference)）；edit-service 的"代码 vs schema"漂移检测需待 ifcdiff 依赖自包含后才能接入（见 [Roadmap](/project/roadmap)）。

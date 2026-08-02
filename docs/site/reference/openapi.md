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

Go server 的 REST 契约当前以本文档站 [Viewer REST API](/reference/rest-api) 为人工维护的公开契约，没有自动生成的 schema。

> 自动生成与漂移检测（从 schema 生成页面、CI 检测 schema 与已提交产物是否一致）属于后续迭代，见 [Roadmap](/project/roadmap)。

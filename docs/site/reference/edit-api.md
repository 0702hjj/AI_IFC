# IFC 编辑 API

edit-service（Python FastAPI，默认 `:8100`）是 IFC 编辑端点**唯一参考**。路径参数：`id` 匹配 `^m_[0-9a-f]{16}$`；`guid` 为 IFC GlobalId。除标注外，错误响应为 FastAPI 形态 `{"detail": ...}`。

## 端点目录

### GET /health

健康检查，响应 `{"status": "ok"}`。

### PUT /models/{id}/entities/{guid}

把编辑应用到内存模型并记为一条 pending change（**不落盘**）。先全量校验再应用（单请求原子）：任一校验失败则不产生任何修改。

body（`EditBody`）：

```json
{
  "type": "object",
  "properties": {
    "fields": {"type": "object", "additionalProperties": true, "description": "实体直接属性（Name/Description 等）"},
    "psets": {"type": "object", "additionalProperties": {"type": "object", "additionalProperties": true}, "description": "pset 名 → {属性名: 新值}；pset 不存在则创建"},
    "author": {"type": "string", "default": "local-user"},
    "provenance": {"type": "object", "properties": {"source": {"type": "string", "enum": ["UI", "AI"], "default": "UI"}}}
  }
}
```

响应 200（pending entry，同时出现在 pending 与 commit 后 history 中）：

```json
{
  "id": "e_<12位hex>",
  "guid": "...",
  "changes": [{"field": "Name", "oldValue": "...", "newValue": "..."}],
  "author": "ai-agent",
  "provenance": {"source": "AI"},
  "timestamp": "<ISO8601 UTC>"
}
```

`changes[].field`：直接属性用属性名，pset 属性用 `Pset名.属性名`；`oldValue` 取自 IFC 真实值（pset 属性原本不存在时为 `null`）。

错误码：404 模型或 guid 不存在；422 `fields`/`psets` 均为空、未知属性名、值类型不受支持或与 IFC 属性类型不符。

### GET /models/{id}/pending

列出当前 pending（无 pending 返回 `[]`）。注意：pending 与 history 的 GET **不校验模型是否存在**；写路径与 versions/diff 才校验。

### DELETE /models/{id}/pending

丢弃全部 pending：卸载并从磁盘重载内存模型。响应 `{"discarded": <条数>}`；模型不存在 → 404。

### POST /models/{id}/commit

全部 pending 原子落盘（持文件锁）→ 版本快照 → 追加 history（每条补 `operation`）→ 清空 pending。

可选 body：`{"operation": "update" | "migrate"}`，缺省 `"update"`；`migrate` 由 Go 侧 override 迁移传入。响应 200 `{"committed": <条数>, "entries": [...]}`；无 pending → 409；模型不存在 → 404。

### GET /models/{id}/history

持久化编辑历史（含 `operation` 字段），存储于 `{VIEWER_DATA_DIR}/models/{id}/edit-history.json`；无历史返回 `[]`。

### GET /models/{id}/versions

```json
{"versions": [{"version": "v1", "createdAt": "<ISO8601 UTC>"}, ...], "current": "v2"}
```

从未 commit 过时 `versions` 为 `[]`、`current` 为 `null`。

### POST /models/{id}/diff

body：`{"base": "v1", "target": "v2"}`（target 可为 `"current"` 表示 uploads 现态）。响应：

```json
{
  "base": "v1",
  "target": "v2",
  "added": ["<guid>", ...],
  "removed": ["<guid>", ...],
  "changed": [{"guid": "...", "changes": [{"field": "...", "old": ..., "new": ...}]}]
}
```

版本不存在 → 404；缺 `base`/`target` → 422。diff 为属性级（无几何 diff），详见 [版本与 Diff Viewer](/viewer/versions-diff)。

## 经 Go 代理

Go server（默认 `:8090`）把同一套端点暴露在 `/api/models/{id}/edit/...` 前缀下，端点一一对应：

| Go 代理端点 | Python 端点 |
| --- | --- |
| `PUT /api/models/{id}/edit/entities/{guid}` | `PUT /models/{id}/entities/{guid}` |
| `GET /api/models/{id}/edit/pending` | `GET /models/{id}/pending` |
| `DELETE /api/models/{id}/edit/pending` | `DELETE /models/{id}/pending` |
| `GET /api/models/{id}/edit/history` | `GET /models/{id}/history` |
| `GET /api/models/{id}/edit/versions` | `GET /models/{id}/versions` |
| `POST /api/models/{id}/edit/diff` | `POST /models/{id}/diff` |
| `POST /api/models/{id}/edit/commit` | `POST /models/{id}/commit` |

与直连的差异：

- 响应统一包 `{code, message, data}`；错误码映射：404 → 40400、409 → 40900、422 → 40001、其余（含不可达）→ 50200。
- PUT/commit body 若含 `provenance.source`，Go 先校验枚举（UI|AI），非法 → 40001。
- Go 代理 commit 成功后：entries 展开写入 change log、IfcDiff 补充 diff 字段、模型置 `converting` 并排队重转；响应 data 额外含 `"reconverting": true`。
- change log 写失败不返回 500：记日志，响应仍 200，data 含 `"warning"` 字符串（IFC 已落盘、重转已排队，仅 change log 可能缺条）。

# IFC 编辑 API

edit-service（Python FastAPI，默认 `:8100`）是 IFC 编辑端点**唯一参考**。路径参数：`id` 匹配 `^m_[0-9a-f]{16}$`；`guid` 为 IFC GlobalId。除标注外，错误响应为 FastAPI 形态 `{"detail": ...}`。

> **直改链路已退役（2026-08-08）**：script-as-source 统一编辑后，一切修改落在构建脚本上。原 L1 直改端点（`PUT/DELETE /models/{id}/entities/...`、`GET .../editable-schema`、`POST /models/{id}/commit`）**返回 410 Gone**（永久退役，非 404），历史实现可从 git 历史回捞（锚点 `fb55a8a`）。现役编辑面见 [Script 编辑与版本对比](/reference/design-edit)。

## 端点目录

### GET /health

健康检查，响应 `{"status": "ok"}`。

### 直改端点（410 Gone）

| 端点 | 退役说明 |
| --- | --- |
| `PUT /models/{id}/entities/{guid}` | 改构建脚本（`PUT /script` 或 `POST /script/edit-call`），不再直接改 IFC |
| `GET /models/{id}/entities/{guid}/editable-schema` | 无直改即无类型化编辑表单 |
| `DELETE /models/{id}/entities/{guid}` | 删除构件走脚本改写 |
| `POST /models/{id}/commit` | `script/save` 是唯一版本检查点 |

均返回 `410 {"detail": "direct IFC editing retired: edit the build script (script-as-source)"}`。

### GET /models/{id}/pending

列出当前 pending（无 pending 返回 `[]`）。直改退役后 pending 仅作 script-run 回放簿记（内部用），不再承载用户编辑。注意：pending 与 history 的 GET **不校验模型是否存在**；写路径与 versions/diff 才校验。

### DELETE /models/{id}/pending

丢弃全部 pending：卸载并从磁盘重载内存模型。响应 `{"discarded": <条数>}`；模型不存在 → 404。

### GET /models/{id}/history

持久化编辑历史（含 `operation` 字段），存储于 `{VIEWER_DATA_DIR}/models/{id}/edit-history.json`；无历史返回 `[]`。直改退役后 history 只读保留历史数据，新增记录来自 `POST /models/{id}/user-edits`（外部改后 IFC/DXF 解析登记）。

### GET /models/{id}/versions

```json
{"versions": [{"version": "v1", "createdAt": "<ISO8601 UTC>"}, ...], "current": "v2"}
```

script-backed 模型只有最新大版本的 IFC 物化在盘上；历史版本在 diff/下载时按需从脚本重建（见 [版本与 Diff Viewer](/viewer/versions-diff)）。

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

版本不存在 → 404；缺 `base`/`target` → 422。diff 为属性级语义（不提供几何 diff——IFC 是脚本产物，改几何 = 改脚本），详见 [版本与 Diff Viewer](/viewer/versions-diff)。

### POST /models/{id}/diff/upload

上传对比：`multipart/form-data` 字段 `file`（待对比 IFC），与当前模型现态做属性级语义 diff（by GlobalId）。响应在 `POST /diff` 形态上多一个 `labels`（guid → 可读 name/type）；`base` 固定 `"current"`、`target` 固定 `"upload"`。不落盘、不缓存。非法 IFC → 422。

### 脚本编辑端点

`GET/PUT /models/{id}/script`、`script/params`、`script/undo|redo|discard`、`script/run`、`script/save`、`script/rollback`、`script/diff`、`script/staging/diff`、`script/locate`、`script/edit-call`、`GET /models/{id}/scripts`——语义与契约见 [Script 编辑与版本对比](/reference/design-edit)，机器可读 schema 见 [编辑 API 参考（自动生成）](/reference/edit-api-reference)。

## 经 Go 代理

Go server（默认 `:8090`）把端点暴露在 `/api/v1` 前缀下：

- 脚本编辑端点一一对应代理：`/api/v1/models/{id}/script[/...]`（含 `script/locate`，query 透传）；run/save/rollback 成功后 Go 侧排队重转 XKT。`script/edit-call` 不经 Go 代理，仅 edit-service 直连。
- 只读/对比端点保留在 `/api/v1/models/{id}/edit/...` 前缀下：`POST .../edit/diff`（对应 `POST /models/{id}/diff`）、`GET .../edit/pending|history|versions`、`DELETE .../edit/pending`。
- 直改代理路由（`PUT/DELETE .../edit/entities/{guid}`、`POST .../edit/commit`、`GET .../editable-schema`）已随退役删除。

与直连的差异：响应统一包 `{code, message, data}`；错误码映射：404 → 40400、409 → 40900、422 → 40001、其余（含不可达）→ 50200。

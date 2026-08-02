# 编辑 API 参考（自动生成）

> 本页由 `docs/scripts/gen-edit-api-reference.mjs` 从 `docs/site/public/ai-tools.openapi.json` 自动生成，**请勿手工编辑**。
> 源 schema 由 edit-service 导出（`viewer/edit-service/scripts/export_openapi.py`）；工作流与语义解释见 [IFC 编辑 API](/reference/edit-api)。

- 服务：ifc-edit-service 0.1.0
- OpenAPI 版本：3.1.0

## 端点

### GET /health

Health

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |

### POST /models/{id}/commit

Commit Pending

Atomically save all pending changes to disk and append them to history.

The first commit snapshots the original upload as ``v1`` before saving;
every commit snapshots the newly saved file as the next version. The
optional body stamps ``operation`` onto the committed entries (default
``update``; Go's override migration passes ``migrate``).

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

请求体（application/json）：

```json
{
  "anyOf": [
    {
      "$ref": "#/components/schemas/CommitBody"
    },
    {
      "type": "null"
    }
  ],
  "title": "Body"
}
```

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### POST /models/{id}/diff

Post Diff

Diff two model versions (or base version vs the current upload state).

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

请求体（application/json）：

```json
{
  "$ref": "#/components/schemas/DiffBody"
}
```

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### PUT /models/{id}/entities/{guid}

Put Entity

Apply edits to the in-memory model and record a pending change.

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |
| `guid` | path | 是 | string |  |

请求体（application/json）：

```json
{
  "$ref": "#/components/schemas/EditBody"
}
```

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### GET /models/{id}/history

Get History

List the persisted edit history for a model.

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### DELETE /models/{id}/pending

Discard Pending

Discard pending changes: reload the in-memory model from disk.

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### GET /models/{id}/pending

Get Pending

List the current pending changes for a model.

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### GET /models/{id}/versions

Get Versions

List version snapshots for a model (empty + current=null before any commit).

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

## 组件 Schema

### CommitBody

```json
{
  "properties": {
    "operation": {
      "type": "string",
      "enum": [
        "update",
        "migrate"
      ],
      "title": "Operation",
      "default": "update"
    }
  },
  "type": "object",
  "title": "CommitBody",
  "description": "Optional body of POST /models/{id}/commit."
}
```

### DiffBody

```json
{
  "properties": {
    "base": {
      "type": "string",
      "title": "Base"
    },
    "target": {
      "type": "string",
      "title": "Target"
    }
  },
  "type": "object",
  "required": [
    "base",
    "target"
  ],
  "title": "DiffBody",
  "description": "Body of POST /models/{id}/diff. target also accepts \"current\"."
}
```

### EditBody

```json
{
  "properties": {
    "fields": {
      "additionalProperties": true,
      "type": "object",
      "title": "Fields"
    },
    "psets": {
      "additionalProperties": {
        "additionalProperties": true,
        "type": "object"
      },
      "type": "object",
      "title": "Psets"
    },
    "author": {
      "type": "string",
      "title": "Author",
      "default": "local-user"
    },
    "provenance": {
      "$ref": "#/components/schemas/Provenance"
    }
  },
  "type": "object",
  "title": "EditBody",
  "description": "Body of PUT /models/{id}/entities/{guid}."
}
```

### HTTPValidationError

```json
{
  "properties": {
    "detail": {
      "items": {
        "$ref": "#/components/schemas/ValidationError"
      },
      "type": "array",
      "title": "Detail"
    }
  },
  "type": "object",
  "title": "HTTPValidationError"
}
```

### Provenance

```json
{
  "properties": {
    "source": {
      "type": "string",
      "enum": [
        "UI",
        "AI"
      ],
      "title": "Source",
      "default": "UI"
    }
  },
  "type": "object",
  "title": "Provenance",
  "description": "Who performed an edit: the web UI or an AI agent."
}
```

### ValidationError

```json
{
  "properties": {
    "loc": {
      "items": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "integer"
          }
        ]
      },
      "type": "array",
      "title": "Location"
    },
    "msg": {
      "type": "string",
      "title": "Message"
    },
    "type": {
      "type": "string",
      "title": "Error Type"
    },
    "input": {
      "title": "Input"
    },
    "ctx": {
      "type": "object",
      "title": "Context"
    }
  },
  "type": "object",
  "required": [
    "loc",
    "msg",
    "type"
  ],
  "title": "ValidationError"
}
```


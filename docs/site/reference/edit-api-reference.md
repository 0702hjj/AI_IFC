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

Retired: script save (script/save) is the only version checkpoint.

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

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

### POST /models/{id}/diff/upload

Post Diff Upload

Diff an uploaded (user-modified) IFC against the current model state.

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### DELETE /models/{id}/entities/{guid}

Delete Entity

Retired: edit the build script instead of deleting entities directly.

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |
| `guid` | path | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### PUT /models/{id}/entities/{guid}

Put Entity

Retired: edit the build script instead of mutating the IFC directly.

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |
| `guid` | path | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### GET /models/{id}/entities/{guid}/editable-schema

Get Editable Schema

Retired: no typed edit form without direct editing.

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |
| `guid` | path | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### GET /models/{id}/history

Get History

List the persisted edit history for a model (read-only).

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

List the current pending changes for a model (read-only).

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### GET /models/{id}/script

Get Script

Return the current script (staged state, or last saved base).

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### PUT /models/{id}/script

Stage Script

Stage a script edit: full replace, or params-only PARAMS-block rewrite.

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

请求体（application/json）：

```json
{
  "$ref": "#/components/schemas/ScriptBody"
}
```

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### POST /models/{id}/script/diff

Diff Script Versions

Big-version script diff: unified text diff + PARAMS changes + stats.

This is the primary AI-facing diff (the retired design-JSON diff's
replacement); the IFC semantic diff stays at POST /models/{id}/diff.

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

请求体（application/json）：

```json
{
  "$ref": "#/components/schemas/ScriptDiffBody"
}
```

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### POST /models/{id}/script/discard

Discard Script

Throw staged edits away; back to the last saved big version. No version.

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### POST /models/{id}/script/edit-call

Edit Call

Rewrite one scalar argument at a located callsite, then sandbox-run.

顺序：定位 → 重写 → 契约校验+沙箱 run → staging.push；任何失败 422 零副作用。
origin=traced 的调用点不可自动改写 → 422。

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

请求体（application/json）：

```json
{
  "$ref": "#/components/schemas/EditCallBody"
}
```

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### GET /models/{id}/script/locate

Locate Callsite

Locate the script callsite for an IFC element (guid → designKey → CallSite).

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |
| `guid` | query | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### GET /models/{id}/script/params

Get Script Params

Return the current script's PARAMS dict (ast extraction, no execution).

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### POST /models/{id}/script/redo

Redo Script

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### POST /models/{id}/script/rollback

Rollback Script

Restore a big version's script into staging and re-run it into uploads.

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

请求体（application/json）：

```json
{
  "$ref": "#/components/schemas/RollbackBody"
}
```

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### POST /models/{id}/script/run

Run Script Endpoint

Sandbox-run the current staged script into uploads (preview; no version).

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### POST /models/{id}/script/save

Save Script

Promote the staged script to a big version (run → snapshot script+IFC).

A failed sandbox run → 422 and no version; staging is preserved so the
script can be fixed and saved again.

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

请求体（application/json）：

```json
{
  "anyOf": [
    {
      "$ref": "#/components/schemas/SaveBody"
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

### GET /models/{id}/script/staging/diff

Diff Staging Steps

Small-version diff between two staging steps (default: the last two).

Step indices address the staged states ``history[0..cursor]`` (0-based).
Lightweight inline text diff + PARAMS changes; visible to both AI and user.

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |
| `from` | query | 否 |  |  |
| `to` | query | 否 |  |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### POST /models/{id}/script/undo

Undo Script

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### GET /models/{id}/scripts

List Scripts

List script big versions (empty for legacy IFC-only models).

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

响应：

| 状态码 | 说明 |
| --- | --- |
| 200 | Successful Response |
| 422 | Validation Error |

### POST /models/{id}/user-edits

Post User Edits

Append USER-annotated modification events to the model's edit history.

参数：

| 名称 | 位置 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | 是 | string |  |

请求体（application/json）：

```json
{
  "$ref": "#/components/schemas/UserEditsBody"
}
```

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

### Body_post_diff_upload_models__id__diff_upload_post

```json
{
  "properties": {
    "file": {
      "type": "string",
      "contentMediaType": "application/octet-stream",
      "title": "File"
    }
  },
  "type": "object",
  "required": [
    "file"
  ],
  "title": "Body_post_diff_upload_models__id__diff_upload_post"
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

### EditCallBody

```json
{
  "properties": {
    "designKey": {
      "type": "string",
      "title": "Designkey"
    },
    "argument": {
      "type": "string",
      "title": "Argument"
    },
    "value": {
      "title": "Value"
    }
  },
  "type": "object",
  "required": [
    "designKey",
    "argument",
    "value"
  ],
  "title": "EditCallBody",
  "description": "Body of POST /models/{id}/script/edit-call: scalar argument rewrite."
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

### RollbackBody

```json
{
  "properties": {
    "version": {
      "type": "string",
      "pattern": "^v\\d+$",
      "title": "Version"
    }
  },
  "type": "object",
  "required": [
    "version"
  ],
  "title": "RollbackBody",
  "description": "Body of POST /models/{id}/script/rollback."
}
```

### SaveBody

```json
{
  "properties": {
    "note": {
      "type": "string",
      "title": "Note",
      "default": ""
    }
  },
  "type": "object",
  "title": "SaveBody",
  "description": "Optional body of POST /models/{id}/script/save."
}
```

### ScriptBody

```json
{
  "properties": {
    "script": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Script"
    },
    "params": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "title": "Params"
    },
    "note": {
      "type": "string",
      "title": "Note",
      "default": ""
    }
  },
  "type": "object",
  "title": "ScriptBody",
  "description": "Body of PUT /models/{id}/script: exactly one of script / params."
}
```

### ScriptDiffBody

```json
{
  "properties": {
    "base": {
      "type": "string",
      "pattern": "^v\\d+$",
      "title": "Base"
    },
    "target": {
      "type": "string",
      "pattern": "^v\\d+$",
      "title": "Target"
    }
  },
  "type": "object",
  "required": [
    "base",
    "target"
  ],
  "title": "ScriptDiffBody",
  "description": "Body of POST /models/{id}/script/diff: two big versions."
}
```

### UserEditEvent

```json
{
  "properties": {
    "guid": {
      "type": "string",
      "title": "Guid"
    },
    "name": {
      "type": "string",
      "title": "Name",
      "default": ""
    },
    "kind": {
      "type": "string",
      "enum": [
        "added",
        "removed",
        "modified"
      ],
      "title": "Kind"
    },
    "changes": {
      "items": {
        "$ref": "#/components/schemas/UserFieldChange"
      },
      "type": "array",
      "title": "Changes"
    }
  },
  "type": "object",
  "required": [
    "guid",
    "kind"
  ],
  "title": "UserEditEvent",
  "description": "One located user modification (IFC element or DXF entity/layer)."
}
```

### UserEditsBody

```json
{
  "properties": {
    "origin": {
      "type": "string",
      "enum": [
        "ifc-upload",
        "dxf-upload"
      ],
      "title": "Origin"
    },
    "author": {
      "type": "string",
      "title": "Author",
      "default": "user-upload"
    },
    "events": {
      "items": {
        "$ref": "#/components/schemas/UserEditEvent"
      },
      "type": "array",
      "title": "Events"
    }
  },
  "type": "object",
  "required": [
    "origin",
    "events"
  ],
  "title": "UserEditsBody",
  "description": "Body of POST /models/{id}/user-edits."
}
```

### UserFieldChange

```json
{
  "properties": {
    "field": {
      "type": "string",
      "title": "Field"
    },
    "oldValue": {
      "title": "Oldvalue"
    },
    "newValue": {
      "title": "Newvalue"
    }
  },
  "type": "object",
  "required": [
    "field"
  ],
  "title": "UserFieldChange",
  "description": "One field-level change inside a user modification event."
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


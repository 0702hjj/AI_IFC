# Viewer REST API

后端 base：`http://localhost:8090`；JSON 信封统一为 `{code, message, data}`，`code=0` 表示成功。模型 id 格式 `m_` + 16 位小写 hex。

## 模型

### POST /api/v1/models

上传 IFC 文件并触发异步转换。请求：`multipart/form-data`，字段 `file`（仅 `.ifc`，≤200MB）。

响应：

```json
{"code":0,"message":"ok","data":{"id":"m_01J...","name":"Building-Architecture.ifc","status":"converting"}}
```

错误：`40001` 非法文件类型；`40002` 超出大小上限。

### GET /api/v1/models

模型列表（前端 2s 轮询直至所有模型脱离 `converting`）：

```json
{"code":0,"message":"ok","data":[
  {"id":"m_01J...","name":"a.ifc","size":1832140,"status":"ready","createdAt":"2026-07-27T10:00:00Z","error":""}
]}
```

`status` ∈ `converting | ready | failed`。

### GET /api/v1/models/{id} {#model-detail}

单模型详情，结构同上。

### POST /api/v1/models/{id}/retry

对 `failed` 模型重新入队转换；返回更新后的模型对象（`status:"converting"`）。

### DELETE /api/v1/models/{id} {#delete-model}

删除该模型的 IFC、XKT、metadata、状态文件及 issues/changes/overrides。响应 `data: null`。

### GET /api/v1/models/{id}/download

下载原始 IFC，带 `Content-Disposition: attachment; filename="<name>"`。

## Issues

issue id 格式 `i_` + 12 位小写 hex；status ∈ `open | checking | resolved`；`author` 默认 `local-user`；`provenance.source` 默认 `UI`（创建时可显式覆盖）。

### GET /api/v1/models/{id}/issues

返回 `data: Issue[]`，按 createdAt 降序。

### POST /api/v1/models/{id}/issues

`multipart/form-data`：

- `issue`（必填）：JSON 字符串 `{"entityId","entityName","entityType","title","comment","author"?,"provenance"?,"camera":{"eye":[...],"look":[...],"up":[...]}}`，title 必填。
- `screenshot`（可选）：PNG 文件，≤5MB。

返回 `data: Issue`（含生成的 id、`status:"open"`、默认 author/provenance、`screenshot` 相对路径、createdAt/updatedAt）。

### PATCH /api/v1/models/{id}/issues/{issueId} {#patch-issue}

JSON body：`{"title"?, "comment"?, "status"?}`，仅更新传入字段。

### DELETE /api/v1/models/{id}/issues/{issueId} {#delete-issue}

删除 Issue 及其截图。

### GET /v1/models/{id}/issues/{file}

Issue 截图静态服务，`file` 必须匹配 `i_[0-9a-f]{12}\.png`。

## 属性 Override 与修改记录

属性修改走 metadata override（不改 IFC 本体）：白名单字段仅 `Name / Description / Classification / FireRating / Comments`；每次修改逐字段写一条 change log。

### GET /api/v1/models/{id}/overrides

返回 `data: { [entityId]: { [field]: value } }`（无 override 时为 `{}`）。

### PUT /api/v1/models/{id}/entities/{entityId}/properties

JSON body：`{"entityName":"Wall","fields":{"FireRating":"F60","Comments":"备注"}}`。

- `fields` 必填且非空；字段名不在白名单返回 `40001 field not in whitelist`。
- 空字符串值 = 清除该字段 override。
- 每个字段写一条 change log（oldValue 为被覆盖前的值；author `local-user`；provenance `UI`）。
- 返回 `data: { [field]: value }`，即该实体当前生效的 override 集合。

### GET /api/v1/models/{id}/changes

返回 `data: ChangeEntry[]`，按 createdAt 降序（无记录时为 `[]`）：

```json
{"code":0,"message":"ok","data":[
  {"id":"c_1a2b3c4d5e6f","entityId":"3a82-xxxx","entityName":"Wall","field":"FireRating","oldValue":"","newValue":"F60","author":"local-user","provenance":{"source":"UI"},"operation":"update","createdAt":"2026-07-29T10:00:00Z"}
]}
```

## 编辑代理端点

Go server 把 edit-service 的脚本编辑端点暴露在 `/api/v1/models/{id}/script/...` 前缀下（编排：run/save/rollback 成功后排队重转 XKT）；只读/对比端点保留在 `/api/v1/models/{id}/edit/...` 前缀下（`edit/diff`、`edit/pending`、`edit/history`、`edit/versions`）。直改代理路由（`edit/entities/{guid}`、`edit/commit`）已随 L1 直改退役删除。完整契约见 [IFC 编辑 API](/reference/edit-api)。

## 静态资源（直挂，不走 JSON 信封）

| 路径 | 说明 |
| --- | --- |
| `GET /v1/models/{id}/model.xkt` | XKT 几何数据（支持 Range） |
| `GET /v1/models/{id}/metadata.json` | 元数据（见下） |
| `GET /v1/models/{id}/issues/{file}` | Issue 截图 |

## metadata.json Schema（xeokit 元模型格式）

由 converter 用 web-ifc 从原 IFC 提取（空间结构树 + 属性集），可直接作为 `XKTLoaderPlugin.load({metaModelSrc})` 的输入：

```json
{
  "projectId": "3xFoo",
  "metaObjects": [
    {"id": "1AbC...", "type": "IfcBuildingStorey", "name": "Level 1", "parent": "0Root"},
    {"id": "2XdE...", "type": "IfcWall", "name": "Wall-001", "parent": "1AbC...", "propertySetIds": ["pset_2XdE_0"]}
  ],
  "propertySets": [
    {
      "id": "pset_2XdE_0",
      "name": "Pset_WallCommon",
      "type": "Pset",
      "properties": [
        {"name": "FireRating", "value": "120min", "type": "IfcLabel"},
        {"name": "LoadBearing", "value": true, "type": "IfcBoolean"}
      ]
    }
  ]
}
```

约定：`metaObjects[].id` 为 IFC GlobalId（与 XKT entity id 一致）；层级为 Site → Building → Storey → 构件；无 pset 的构件省略 `propertySetIds`。

## 通用错误码

`40001` 参数/校验错误、`40002` 超限、`40400` 模型或 Issue 不存在、`50000` 服务器内部错误。

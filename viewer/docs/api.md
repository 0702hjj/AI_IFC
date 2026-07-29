# IFC Viewer 接口契约

> 后端 base：`http://localhost:8090`；JSON 信封统一为 `{code, message, data}`，`code=0` 表示成功。

## 1. REST API

### POST /api/models
上传 IFC 文件并触发异步转换。

- 请求：`multipart/form-data`，字段 `file`（仅 `.ifc`，≤200MB）
- 响应：
```json
{"code":0,"message":"ok","data":{"id":"m_01J...","name":"Building-Architecture.ifc","status":"converting"}}
```
- 错误：`40001` 非法文件类型；`40002` 超出大小上限

通用错误码：`40400` 模型不存在；`50000` 服务器内部错误

### GET /api/models
模型列表（前端以 2s 间隔轮询直至所有模型脱离 `converting`）。

```json
{"code":0,"message":"ok","data":[
  {"id":"m_01J...","name":"a.ifc","size":1832140,"status":"ready","createdAt":"2026-07-27T10:00:00Z","error":""}
]}
```
`status` ∈ `converting | ready | failed`

### GET /api/models/{id}
单模型详情，结构同上。

### POST /api/models/{id}/retry
对 `failed` 模型重新入队转换；响应返回更新后的模型对象（`status:"converting"`）。

### DELETE /api/models/{id}
删除该模型的 IFC、XKT、metadata 与状态文件。响应 `data: null`。

### GET /api/models/{id}/download
下载原始 IFC，带 `Content-Disposition: attachment; filename="<name>"`。

## 2. Issues（审查标记）

所有路由沿用 `{code,message,data}` 信封。issue id 格式 `i_` + 12 位小写 hex；status ∈ `open | checking | resolved`。

### GET /api/models/{id}/issues
返回 `data: Issue[]`，按 createdAt 降序。

### POST /api/models/{id}/issues
multipart/form-data：
- `issue`（必填）：JSON 字符串 `{"entityId","entityName","entityType","title","comment","camera":{"eye":[x,y,z],"look":[x,y,z],"up":[x,y,z]}}`，title 必填
- `screenshot`（可选）：PNG 文件，≤5MB

返回 `data: Issue`（含生成的 `id`、`status:"open"`、`screenshot` 相对路径如 `issues/{id}.png`、`createdAt/updatedAt`）。

### PATCH /api/models/{id}/issues/{issueId}
JSON body：`{"title"?, "comment"?, "status"?}`，仅更新传入字段。返回 `data: Issue`。

### DELETE /api/models/{id}/issues/{issueId}
删除 Issue 及其截图。返回 `data: null`。

### GET /models/{id}/issues/{file}
Issue 截图静态服务，`file` 必须匹配 `i_[0-9a-f]{12}\.png`。

错误码：40001（参数/校验错误）、40002（超限）、40400（模型或 Issue 不存在）、50000（内部错误）。

## 3. 静态资源（直挂，不走 JSON 信封）

| 路径 | 说明 |
|---|---|
| `GET /models/{id}/model.xkt` | XKT 几何数据（支持 Range） |
| `GET /models/{id}/metadata.json` | 元数据（见 §4） |
| `GET /models/{id}/issues/{file}` | Issue 截图（见 §2） |

## 4. metadata.json Schema（xeokit 元模型格式）

由 converter 用 web-ifc 从原 IFC 提取（空间结构树 + 属性集），输出 **xeokit 标准元模型 JSON**。
该格式可直接作为 `XKTLoaderPlugin.load({metaModelSrc})` 的输入，前端 TreeViewPlugin/属性面板
全部基于 `viewer.metaScene` 工作，无需自研树格式。

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

约定：
- `metaObjects[].id` 为 IFC GlobalId，与 converter 写入 XKT 的 entity id 一致（转换器内保证），用于拾取联动
- 层级按 Site → Building → Storey → 构件，通过 `parent` 字段表达
- 无 pset 的构件省略 `propertySetIds`

## 5. 前后端协作约定

1. 前端不解析 IFC；几何走 XKT，语义走 metadata.json
2. 上传成功后跳转/停留列表页并轮询状态
3. 所有 id 由后端生成（`m_` + 16 位随机 hex），前端不猜测存储路径以外的任何规则

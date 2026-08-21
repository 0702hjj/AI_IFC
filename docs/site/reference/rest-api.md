# Viewer REST API

> **机器可消费 OpenAPI：** 完整请求/响应 schema（OpenAPI 3.0）见 [go-server.openapi.json](/go-server.openapi.json)，由 `docs/scripts/gen-go-openapi.mjs` 生成，并对 mux 路由做覆盖漂移检测（见 [OpenAPI 文件](/reference/openapi)）。

后端 base：`http://localhost:8090`；JSON 信封统一为 `{code, message, data}`，`code=0` 表示成功。模型 id 格式 `m_` + 16 位小写 hex。

## 模型

### POST /api/v1/models {#upload-model}

上传 IFC 文件并触发异步转换。请求：`multipart/form-data`，字段 `file`（仅 `.ifc`，≤200MB）。

> **用户视角已隐藏**（2026-08-21）：前端不再暴露上传入口——模型由 agent 在项目会话内生成（
> 用户走项目流程：`POST /chat/projects` → 会话 → agent 建模型）。本端点保留为
> **agent 建模型的内部链路**（agent 初始化模型 → 沙箱构建 → 转化 → 显示），用户勿直调。

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

## Chat（项目 + 会话 + AI 对话）

进程内 chat agent 的 REST/SSE 接口（主 agent 编排：项目级会话，按项目类型选择性装配子 agent）。**历史项目 = 会话列表**（前端「历史项目（会话）」即 `GET /api/v1/chat/sessions`）。

### 项目

#### POST /api/v1/chat/projects

创建项目。body `{"title", "kind"}`；`kind` 必选 ∈ `ifc | cad | cad->ifc`（强制预选，决定 Agent 派发方向与装配：cad→只派 cad-agent+aiplan，ifc→只派 ifc-agent，cad->ifc→全装）。

> **项目路径组织**：项目创建/删除在 `/api/v1/chat/projects`（chat 子树），项目方案/交付在
> `/api/v1/projects/{id}/...`（非 chat 前缀）——同一 projectID 两种前缀，历史原因（chat 模块独立挂载）。
> **项目绑定唯一会话**（1 项目 = 1 会话）：模型由 agent 在项目内产生，不用户上传。

```json
{"code":0,"message":"ok","data":{"projectId":"p_xxxx","title":"我的项目","kind":"cad","createdAt":"2026-08-21T06:00:00Z","models":[]}}
```

错误：`40001` kind 缺失/非法。

### 会话

#### GET /api/v1/chat/sessions

会话列表（历史项目入口）：

```json
{"code":0,"message":"ok","data":[
  {"chatSessionId":"c_xxxx","opencodeSessionId":"s_xxxx","modelId":"","projectId":"p_xxxx","title":"我的项目","createdAt":"2026-08-21T06:00:00Z"}
]}
```

#### DELETE /api/v1/chat/projects/{id} {#delete-project}

删除项目并**级联清理绑定产物**：项目 + 会话（chat-sessions）+ 事件日志（chat/{agentID}.jsonl）+
方案（plans/{projectID}）+ 项目下模型（issues/changes/overrides + store 目录）。
与 `DELETE /api/v1/models/{id}`（单模型删除，不级联）区分——**删除项目即删全套**。

#### POST /api/v1/chat/sessions

创建/复用会话。body `{"title", "projectId"}`（项目级，**projectId 幂等：1 项目 = 1 会话，历史项目进入即命中现有会话**）或 `{"title", "modelId"}`（单模型，旧语义）。

会话绑定项目后，对话按 `Project.Kind` 路由主 agent（选择性装配：AgentAsTool 子 agent + persona + aiplan skill 按 kind 分化）；历史项目会话恢复（重启后）同样命中对应 kind agent。

错误：`40001` project 不存在。

#### POST /api/v1/chat/sessions/{cid}/messages

发消息（异步）。body `{"text"}`；响应 `{"code":0,"data":{"accepted":true}}`，事件经 SSE 推送。

#### GET /api/v1/chat/sessions/{cid}/messages

会话历史（事件投影回填 `{info, parts}`，重新打开会话时前端按 id 去重合并）。

#### GET /api/v1/chat/sessions/{cid}/events

SSE 事件流（`text/event-stream`）。帧类型：

| event | data | 说明 |
| --- | --- | --- |
| `session.status` | `{"status":{"type":"busy\|idle"}}` | run 边界 |
| `message.updated` | `{"info":{"id","role","sessionID"}}` | 消息骨架 |
| `message.part.updated` | `{"part":{...}}` | part 定型（text/reasoning/tool 卡片） |
| `message.part.delta` | `{"delta","field":"text","partID",...}` | 流式增量（reasoning partID 含 `_reasoning`） |
| `subagent.status` | `{"subagentId","parentSessionId","persona","status","task"}` | 子 agent 边界 |
| `question.ask` | `{"interruptId","question"}` | HITL 提问（ask_user 中断） |
| `session.error` | `{"error"}` | 错误 |
| `session.idle` | `{}` | turn 结束 |

支持 `Last-Event-ID` 断线重同步（缓冲最近 64 条）。

#### POST /api/v1/chat/sessions/{cid}/answer

HITL 回答（ask_user 中断续跑）。body `{"interruptId", "answer"}`；响应 `{"code":0,"data":{"accepted":true}}`。

#### POST /api/v1/chat/sessions/{cid}/abort

中止当前 run。

### 项目级方案产物

#### GET / PUT /api/v1/projects/{projectID}/{name} {#plan-file}

方案文件读存。`name` ∈ `plan | bim_supplement`。PUT 全量替换并版本化（`plan_history/v{n}.json`）。

#### GET /api/v1/projects/{projectID}/plan_history

方案版本历史：`data: {"versions":[...]}`。

#### GET /api/v1/projects/{projectID}/plan_history/{base}/{target}/diff

方案版本 diff（JSONDiff）：`data: {"changes":[...]}`；`base/target` 可为 `v{n}` 或 `current`。

#### POST /api/v1/projects/{projectID}/deliver

plan 交付（aiplan land → 方案级目录版本化）。body `{"plan", "bimSupplement"}`（对象 JSON 文本）。

## 编辑代理端点

Go server 把 edit-service 的脚本编辑端点暴露在 `/api/v1/models/{id}/script/...` 前缀下（编排：run/save/rollback 成功后排队重转 XKT）；只读/对比端点保留在 `/api/v1/models/{id}/edit/...` 前缀下（`edit/diff`、`edit/pending`、`edit/history`、`edit/versions`）。直改代理路由（`edit/entities/{guid}`、`edit/commit`）已随 L1 直改退役删除。完整契约见 [IFC 编辑 API](/reference/edit-api)。

## 静态资源（直挂，不走 JSON 信封）

| 路径 | 说明 |
| --- | --- |
| `GET /v1/models/{id}/model.xkt` | XKT 几何数据（支持 Range） |
| `GET /v1/models/{id}/metadata.json` | 元数据（见下） |
| `GET /v1/models/{id}/render.json` | CAD 渲染数据（仅 kind=dxf 模型，见下） |
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

## render.json Schema（render payload v2）

由 services/cad 在 `script/run`、`script/save` 成功后原子发布（仅 kind=dxf 模型存在该文件），供前端 Canvas 2D 只读预览；坐标保留原始 DXF 坐标系（不归一化）：

```json
{
  "schemaVersion": 2,
  "bounds": {"min": [0, 0], "max": [100, 80]},
  "layers": [{"name": "WALL", "color": 7, "linetype": "CONTINUOUS"}],
  "entities": [
    {"key": "e_1a2b3c", "type": "LINE", "layer": "WALL", "start": [0, 0], "end": [10, 0]}
  ],
  "unsupported": [{"type": "HATCH", "handle": "1F", "coords": [5, 5]}]
}
```

约定：`bounds` 可空——`entities` 为空（或无可用坐标）时为 `null`；`entities[].key` 为 XDATA 稳定 key（APPID `AIDXF`，与 ScriptMap 同源），前端选中即得 key；LWPOLYLINE 炸开为 LINE/ARC 条目（同 key 多条目）；INSERT 仅展开一层（子实体 `key=null` 且带 `block` 标记）；白名单外实体明面列入 `unsupported`，不静默丢弃。

## 通用错误码

`40001` 参数/校验错误、`40002` 超限、`40400` 模型或 Issue 不存在、`50000` 服务器内部错误。

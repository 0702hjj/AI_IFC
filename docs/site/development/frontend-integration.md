# 前端对接契约（自研/第三方前端接入）

本文面向自研或第三方前端的集成方。一切 envelope、错误码与鉴权行为以 `server/internal/api/api.go` 与 `server/internal/api/auth.go` 为准。

## web/ 是参考实现

平台本体是 API；`web/`（React + xeokit + zustand）只是参考实现，**可整体替换**。对接面 = Go 网关（默认 `:8090`）的 `/api/v1/*` 与 `/v1/models/*` 只读文件端点。机器可读契约：

- OpenAPI 3.0：[go-server.openapi.json](/go-server.openapi.json)（生成物，含 mux 路由覆盖漂移检测）；
- 路由清单：[go-rest-api.routes.json](/go-rest-api.routes.json)（生成物，只引用不改）；
- 叙述性文档：[Viewer REST API](/reference/rest-api)、[IFC 编辑 API](/reference/edit-api)、[OpenAPI 文件](/reference/openapi)。

## 协议基线

### Envelope 与错误码

除 `/v1/models/...` 静态文件端点外，所有响应统一 envelope：

```json
{"code": 0, "message": "ok", "data": {...}}
```

`code=0` 表示成功。错误码段（列自 `api.go` / `auth.go` / `edit.go`）：

| code | 含义 |
| --- | --- |
| `40001` | 参数/校验错误（edit-service 的 422 经 Go 代理也映射为此） |
| `40002` | 超限（上传大小、截图大小） |
| `40100` | 鉴权失败 |
| `40400` | 模型或资源不存在 |
| `40900` | 冲突（edit-service 409 透传） |
| `50000` | 服务器内部错误 |
| `50200` | edit-service 不可达或其余代理错误 |
| `50400` | edit-service 超时（如 diff 超时） |

### 鉴权与 CORS

- **鉴权默认关闭**：`VIEWER_API_TOKEN` 为空时所有端点匿名可用（单机零配置默认）。
- 设置后：除 OPTIONS 预检与豁免白名单外，全部端点要求 `Authorization: Bearer <token>`（强制 Bearer scheme，裸 token 拒绝，401 envelope 码 `40100`）。
- **豁免白名单（精确匹配，非前缀）**：`GET /v1/models/{id}/model.xkt`、`GET /v1/models/{id}/metadata.json`、`GET /v1/models/{id}/issues/{file}`——xeokit 与 `<img>` 无法携带 Authorization 头，故只读模型文件匿名可读。
- **SSE 特例**：`GET /api/v1/chat/sessions/{cid}/events` 是唯一允许 `?token=` query 回退的路径（EventSource 不支持自定义头）。
- **CORS 白名单**：`VIEWER_CORS_ORIGINS`（逗号分隔，默认 `http://localhost:5173,http://localhost:8080`），预检由网关统一应答。

### SSE 事件流

chat 子树提供会话事件流：`GET /api/v1/chat/sessions/{cid}/events`。帧格式为标准 SSE：

```
event: <事件类型>
data: <JSON 载荷>

```

服务端为每个会话维护编号重同步缓冲（断线重连可回放已编号帧）。事件类型与载荷随 opencode 上游透传，连接管理参考 `web/` 参考实现的用法。

## 编辑流程对接（script-as-source）

一切修改落在构建脚本上（原 L1 直改端点已退役返回 410）。完整契约见 [IFC 编辑 API](/reference/edit-api) 与 [Script 编辑与版本](/reference/design-edit)；典型链路（curl 风格同 [AI 接入](/reference/ai)）：

```bash
BASE=http://127.0.0.1:8090/api/v1
MID=m_0123456789abcdef

# 1. 暂存脚本（整脚本或 params 增量）
curl -X PUT "$BASE/models/$MID/script" \
  -H 'Content-Type: application/json' \
  -d '{"script": "PARAMS = {...}\n\ndef build(params, out_path):\n    ...\n"}'

# 2. 沙箱试运行（预览，无版本；成功后 Go 侧排队重转 XKT）
curl -X POST "$BASE/models/$MID/script/run"

# 3. 保存大版本 v{n}（脚本 + map 成对快照；成功后重转 XKT）
curl -X POST "$BASE/models/$MID/script/save" \
  -H 'Content-Type: application/json' -d '{"note": "v1"}'

# 4. 按 guid 定位脚本调用点（行/列/snippet/origin）
curl "$BASE/models/$MID/script/locate?guid=2O2Fr\$t4X7ZfFPoeewFlqU"

# 5. 版本与 diff
curl "$BASE/models/$MID/edit/versions"
curl -X POST "$BASE/models/$MID/script/diff" \
  -H 'Content-Type: application/json' -d '{"base": "v1", "target": "v2"}'
curl -X POST "$BASE/models/$MID/edit/diff" \
  -H 'Content-Type: application/json' -d '{"base": "v1", "target": "current"}'
```

配套端点：`script/undo|redo|discard`（暂存链）、`script/rollback`（回滚，成功后同样重转 XKT）、`script/staging/diff`（暂存步间小版本 diff）、`GET .../scripts`（历史脚本列表）。模型侧轮询 `GET /api/v1/models` 直至 `status` 从 `converting` 变为 `ready`，即新 XKT 可取。

## 显示对接

XKT 产物经只读文件端点获取（鉴权豁免白名单，见上）：

| 端点 | 说明 |
| --- | --- |
| `GET /v1/models/{id}/model.xkt` | XKT 几何数据（支持 Range） |
| `GET /v1/models/{id}/metadata.json` | xeokit 元模型（空间结构树 + 属性集，schema 见 [Viewer REST API](/reference/rest-api)） |

自研前端可用任意 XKT/IFC 渲染器；用 xeokit 时 `metadata.json` 可直接作为 `XKTLoaderPlugin.load({metaModelSrc})` 的输入，实体 id 即 IFC GlobalId，与编辑 API 的 `guid` 对齐。

# 配置说明

## Go server（`server/server_config.json`）

路径相对于进程工作目录解析（非可执行文件目录）。

| key | 默认 | env 覆盖 | 说明 |
| --- | --- | --- | --- |
| `host` / `port` | `127.0.0.1` / `8090` | — | 监听地址 |
| `dataDir` | `../data` | — | 数据目录（**与 edit-service 的 VIEWER_DATA_DIR 同目录**） |
| `nodeBin` / `converterScript` | `node` / `../converter/convert.js` | — | 转换器调用 |
| `maxUploadMB` | `200` | — | 上传上限 |
| `webDist` | `../web/dist` | `VIEWER_WEB_DIST` | web 构建产物目录；存在即由 server 托管（SPA fallback + 指纹资源长缓存），缺失时静态路径 503、API 照常 |
| `pgDSN` | `""` | `VIEWER_PG_DSN` | 配置即启用 PostgreSQL（自动建表），空则文件存储 |
| `editServiceURL` | `http://127.0.0.1:8100` | `VIEWER_EDIT_SERVICE_URL` | edit-service 地址 |
| `cadServiceURL` | `http://127.0.0.1:8200` | `VIEWER_CAD_SERVICE_URL` | cad-edit-service 地址（DXF 模型按 kind 分流） |
| `llmAPIKey` | `""` | `VIEWER_LLM_API_KEY` | chat agent 的 LLM API key；**空 = scriptedModel 离线模式**（确定性 mock，测试/离线 demo 不依赖真模型） |
| `llmBaseURL` | `""` | `VIEWER_LLM_BASE_URL` | LLM OpenAI 兼容端点（如 `https://api.openai.com/v1`） |
| `llmModel` | `""` | `VIEWER_LLM_MODEL` | 模型名（如 `gpt-4o`、`deepseek-chat`） |
| `apiToken` | `""` | `VIEWER_API_TOKEN` | Bearer token 鉴权；**空 = 关闭**（仅限本机开发），**生产/多用户环境必填**；设置后除豁免路径外全部端点要求 `Authorization: Bearer <token>` |
| `corsOrigins` | `http://localhost:5173,http://localhost:8080` | `VIEWER_CORS_ORIGINS` | CORS 允许来源白名单，逗号分隔；不在白名单的 Origin 不反射 `Access-Control-Allow-Origin` |

```json
{
  "host": "127.0.0.1",
  "port": 8090,
  "dataDir": "../data",
  "nodeBin": "node",
  "converterScript": "../converter/convert.js",
  "maxUploadMB": 200,
  "webDist": "../web/dist",
  "pgDSN": "",
  "editServiceURL": "http://127.0.0.1:8100"
}
```

## 鉴权与 CORS

- 默认不开启鉴权（`apiToken` 为空），仅适用于本机单机开发。**生产/多用户环境必须设置 `apiToken`（或 env `VIEWER_API_TOKEN`）**——编辑 API 会在服务端沙箱执行构建脚本（脚本执行 = 代码执行），无鉴权对外开放等价于开放远程代码执行入口。
- 开启后所有端点要求 `Authorization: Bearer <token>`（强制 Bearer scheme，裸 token 拒绝），仅豁免：OPTIONS 预检、`GET /v1/models/{id}/model.xkt`、`GET /v1/models/{id}/metadata.json`、`GET /v1/models/{id}/issues/{file}`（前端 xeokit 与 `<img>` 标签无法携带请求头，需匿名可读）。401 响应为统一 envelope，错误码 `40100`。
- **浏览器 UI 使用**：web 端所有 API 请求自动带上 localStorage（键 `aiifc_token`）中的 token。未存 token 或 token 失效时，任一请求 401 会弹出 token 输入框，保存后自动重试原请求；chat 的 SSE 事件流（EventSource 无法携带自定义头）经 `?token=` query 传递（server 仅对 events 路径放行该回退）。
- 生产部署通过环境变量传 `VIEWER_API_TOKEN` 给 server 进程（如 systemd unit 的 `Environment=`，见 [快速开始](/guide/quickstart)）。
- edit-service（:8100）与 cad-edit-service（:8200）本身**无鉴权**，依赖网络隔离：务必保持绑定 `127.0.0.1`，不要对外暴露；AI agent 直连 :8100/:8200 会绕过 Go server 的 token 校验。
- CORS 从通配 `*` 收敛为白名单（默认本地开发两个端口），新增部署来源用 `corsOrigins` / `VIEWER_CORS_ORIGINS` 追加。

## chat agent（LLM）

- chat 侧的 AI 对话由 **进程内 Eino agent**（`server/internal/agent/`，react loop）驱动，经领域工具集读写 edit-service / cad-edit-service，不再依赖外部 opencode serve。
- 三参配置见上表（`llmAPIKey` / `llmBaseURL` / `llmModel`）；`llmAPIKey` 为空时自动回退 **scriptedModel**（确定性脚本模型）：离线 demo 与测试零依赖可跑，但不会产生真实智能回复。
- 主子编排：主 agent 可派 `ifc-agent` / `cad-agent` 子 agent（深度预算 1），子 agent 事件经同一 SSE 流下发（`subagentId` 标签），前端右侧边栏分组展示。
- 历史配置 `VIEWER_OPENCODE_URL` 已退役（W-0043）：opencode serve 退役，设置后无效果，可从部署环境删除。

## edit-service

| 环境变量 | 默认 | 说明 |
| --- | --- | --- |
| `VIEWER_DATA_DIR` | `../data` | 数据目录（相对进程工作目录）；**必须与 server `dataDir` 指向同一目录**，否则编辑请求 404 |
| `EDIT_SERVICE_PORT` | `8100` | 监听端口 |

## cad-edit-service（DXF 编辑，与 edit-service 同构）

| 环境变量 | 默认 | 说明 |
| --- | --- | --- |
| `VIEWER_DATA_DIR` | `../data` | 数据目录；**与 server `dataDir`、edit-service `VIEWER_DATA_DIR` 同目录** |
| `AIDXF_FLOWS_DIR` | `flows`（相对服务根） | DXF 沙箱契约层目录（`services/cad/flows`） |
| `CAD_SERVICE_PORT` | `8200` | 监听端口 |

cad-edit-service 与 edit-service 同为宿主进程（默认绑 `127.0.0.1:8200`），server 经 `cadServiceURL` / `VIEWER_CAD_SERVICE_URL` 访问。

## PostgreSQL（可选）

- 不配置 `pgDSN` / `VIEWER_PG_DSN` 时，issues / overrides / change log 全部使用文件存储，零外部依赖可跑。
- 配置后 server 启动时自动创建 `issues` / `changes` / `overrides` 表；模型文件（uploads / models / 版本快照）始终在文件系统。
- 测试时需 `VIEWER_TEST_PG_DSN` 指向**专用测试库**（测试会 DROP 表）。

## 端口

默认端口：server `8090`、edit-service `8100`、cad-edit-service `8200`、web 开发服务器 `5173`。

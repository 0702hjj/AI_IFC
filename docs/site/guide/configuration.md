# 配置说明

## Go server（`server/server_config.json`）

路径相对于进程工作目录解析（非可执行文件目录）。

| key | 默认 | env 覆盖 | 说明 |
| --- | --- | --- | --- |
| `host` / `port` | `127.0.0.1` / `8090` | — | 监听地址 |
| `dataDir` | `../data` | — | 数据目录（**与 edit-service 的 VIEWER_DATA_DIR 同目录**） |
| `nodeBin` / `converterScript` | `node` / `../converter/convert.js` | — | 转换器调用 |
| `maxUploadMB` | `200` | — | 上传上限 |
| `pgDSN` | `""` | `VIEWER_PG_DSN` | 配置即启用 PostgreSQL（自动建表），空则文件存储 |
| `editServiceURL` | `http://127.0.0.1:8100` | `VIEWER_EDIT_SERVICE_URL` | edit-service 地址 |
| `apiToken` | `""` | `VIEWER_API_TOKEN` | Bearer token 鉴权；**空 = 关闭**（单机零配置默认），设置后除豁免路径外全部端点要求 `Authorization: Bearer <token>` |
| `corsOrigins` | `http://localhost:5173,http://localhost:8080` | `VIEWER_CORS_ORIGINS` | CORS 允许来源白名单，逗号分隔；不在白名单的 Origin 不反射 `Access-Control-Allow-Origin` |

```json
{
  "host": "127.0.0.1",
  "port": 8090,
  "dataDir": "../data",
  "nodeBin": "node",
  "converterScript": "../converter/convert.js",
  "maxUploadMB": 200,
  "pgDSN": "",
  "editServiceURL": "http://127.0.0.1:8100"
}
```

## 鉴权与 CORS

- 默认不开启鉴权（`apiToken` 为空），面向单机 localhost 使用。**一旦把 `host` 改成对外地址，务必设置 `apiToken`（或 env `VIEWER_API_TOKEN`）**。
- 开启后所有端点要求 `Authorization: Bearer <token>`（强制 Bearer scheme，裸 token 拒绝），仅豁免：OPTIONS 预检、`GET /v1/models/{id}/model.xkt`、`GET /v1/models/{id}/metadata.json`、`GET /v1/models/{id}/issues/{file}`（前端 xeokit 与 `<img>` 标签无法携带请求头，需匿名可读）。401 响应为统一 envelope，错误码 `40100`。
- **浏览器 UI 使用**：web 端所有 API 请求自动带上 localStorage（键 `aiifc_token`）中的 token。未存 token 或 token 失效时，任一请求 401 会弹出 token 输入框，保存后自动重试原请求；chat 的 SSE 事件流（EventSource 无法携带自定义头）经 `?token=` query 传递（server 仅对 events 路径放行该回退）。
- docker compose 部署时在 `.env` 设 `VIEWER_API_TOKEN`（见 `.env.example`），compose 会透传给 server 容器。
- edit-service（:8100）本身**无鉴权**，依赖网络隔离：务必保持绑定 `127.0.0.1`，不要对外暴露；AI agent 直连 :8100 会绕过 Go server 的 token 校验。
- CORS 从通配 `*` 收敛为白名单（默认本地开发两个端口），新增部署来源用 `corsOrigins` / `VIEWER_CORS_ORIGINS` 追加。

## edit-service

| 环境变量 | 默认 | 说明 |
| --- | --- | --- |
| `VIEWER_DATA_DIR` | `../data` | 数据目录（相对进程工作目录）；**必须与 server `dataDir` 指向同一目录**，否则编辑请求 404 |
| `EDIT_SERVICE_PORT` | `8100` | 监听端口 |

## PostgreSQL（可选）

- 不配置 `pgDSN` / `VIEWER_PG_DSN` 时，issues / overrides / change log 全部使用文件存储，零外部依赖可跑。
- 配置后 server 启动时自动创建 `issues` / `changes` / `overrides` 表；模型文件（uploads / models / 版本快照）始终在文件系统。
- 测试时需 `VIEWER_TEST_PG_DSN` 指向**专用测试库**（测试会 DROP 表）。

## 端口

默认端口：server `8090`、edit-service `8100`、web 开发服务器 `5173`。

# 配置说明

## Go server（`viewer/server/server_config.json`）

路径相对于进程工作目录解析（非可执行文件目录）。

| key | 默认 | env 覆盖 | 说明 |
| --- | --- | --- | --- |
| `host` / `port` | `127.0.0.1` / `8090` | — | 监听地址 |
| `dataDir` | `../data` | — | 数据目录（**与 edit-service 的 VIEWER_DATA_DIR 同目录**） |
| `nodeBin` / `converterScript` | `node` / `../converter/convert.js` | — | 转换器调用 |
| `maxUploadMB` | `200` | — | 上传上限 |
| `pgDSN` | `""` | `VIEWER_PG_DSN` | 配置即启用 PostgreSQL（自动建表），空则文件存储 |
| `editServiceURL` | `http://127.0.0.1:8100` | `VIEWER_EDIT_SERVICE_URL` | edit-service 地址 |

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

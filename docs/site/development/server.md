# Go Server

`viewer/server/`：Go 1.26（stdlib net/http + pgx/v5 唯一第三方依赖），默认 `:8090`。

## 命令

```bash
cd viewer/server
go run ./cmd/server          # 默认读取 ./server_config.json
go test ./...                # 单元 + httptest + 并发（-race 下通过）
go vet ./...
```

## 包结构

```
cmd/server/main.go        config（json + VIEWER_PG_DSN / VIEWER_EDIT_SERVICE_URL env）+ 依赖装配
internal/
├── api/                  全部 handler（api.go 核心 + edit.go 编辑编排），envelope {code,message,data}
├── store/                模型元数据/文件存储：Create/Get/List/SetStatus/Delete/Recover
├── convert/              转换队列：Runner 接口、Queue（2 worker、dedup、dirty 重跑、重启 Recover）
├── issue/ change/ override/   各 Store 接口 + FileStore + PgStore（构造时自动建表）
└── editsvc/              edit-service HTTP 客户端（简单调用 10s / commit·diff 120s）
```

## 端点全表

| 路由 | 说明 |
| --- | --- |
| `POST /api/models` | 上传（multipart `file`，.ifc，限大小）→ 入转换队列 |
| `GET /api/models` / `GET /api/models/{id}` | 列表（createdAt 倒序）/ 详情 |
| `POST /api/models/{id}/retry` | failed 重转 |
| `DELETE /api/models/{id}` | 级联删 issues/changes/overrides + 文件 |
| `GET /api/models/{id}/download` | 下载原 IFC |
| `GET /models/{id}/model.xkt` · `/metadata.json` | 静态产物（无 envelope） |
| `GET/POST /api/models/{id}/issues` · `PATCH/DELETE .../issues/{issueId}` | Issue CRUD（截图 ≤5MB） |
| `GET /models/{id}/issues/{file}` | Issue 截图（文件名白名单正则） |
| `GET /api/models/{id}/changes` | 修改记录（change log） |
| `GET /api/models/{id}/overrides` | `map[entityId]map[field]value` |
| `PUT /api/models/{id}/entities/{entityId}/properties` | override 写入（白名单五字段；每字段一条 change） |
| `POST /api/models/{id}/overrides/migrate` | override → 真改迁移 |
| `PUT /api/models/{id}/edit/entities/{guid}` | 代理至 edit-service（provenance 先校验） |
| `GET/DELETE /api/models/{id}/edit/pending` · `GET .../edit/history` · `GET .../edit/versions` · `POST .../edit/diff` | 代理透传 |
| `POST /api/models/{id}/edit/commit` | 编排：Python commit → change log 展开 → 重转；change log 失败降级 `warning` |

错误映射（代理）：Python 404 → 404 / 409 → 409 / 422 → 400 / 其他 → 502。模型 id 校验 `^m_[0-9a-f]{16}$`（路径穿越防护，与 Python 侧同规则）。

## 存储双实现

- 三个领域 store（issue/change/override）各有 `Store` 接口 + FileStore（`models/{id}/*.json`，tmp+rename 原子写）+ PgStore（pgx/v5，构造时建表）。
- 切换：`server_config.json` 的 `pgDSN` 或 env `VIEWER_PG_DSN`；不配置即 File 模式。
- 模型文件本身始终文件存储。

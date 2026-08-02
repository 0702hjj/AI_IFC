# 使用文档（2026-07-30）

> 面向使用者：从零启动平台、浏览器操作、AI 直连、故障排查。
> 架构见 `docs/internal/architecture/ai-bim.md`；AI 接入契约详见 `docs/internal/ai-integration.md`。

## 一、环境依赖

| 依赖 | 版本 | 用途 | 必需性 |
| --- | --- | --- | --- |
| Go | 1.26+ | server | 必需 |
| Node.js | 18+ | converter（npm install 一次即可，无需常驻） | 必需 |
| Python + [uv](https://docs.astral.sh/uv/) | 3.10+ | edit-service | 编辑/diff 功能必需；纯浏览可不要 |
| PostgreSQL | 14+ | issues/changes/overrides 持久化 | 可选（默认文件存储） |
| IfcOpenShell 源码 checkout | v0.8 | ifcdiff editable 依赖（`../IfcOpenShell`，与仓库同级） | 暂必需（N+3 前改为自包含） |

## 二、启动（四个终端）

```bash
# 0. 一次性：装依赖
cd viewer/converter && npm install
cd ../web && npm install
cd ../edit-service && uv sync

# 1. edit-service（:8100）—— VIEWER_DATA_DIR 必须指向 viewer/data 的绝对路径
cd viewer/edit-service
VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100

# 2. Go server（:8090）
cd viewer/server && go run ./cmd/server

# 3. web（:5173）
cd viewer/web && npm run dev
```

打开 `http://localhost:5173`。

### 配置项

**server**（`viewer/server/server_config.json`）：

| key | 默认 | env 覆盖 | 说明 |
| --- | --- | --- | --- |
| `host` / `port` | `127.0.0.1` / `8090` | — | 监听地址 |
| `dataDir` | `../data` | — | 数据目录（**与 edit-service 的 VIEWER_DATA_DIR 同目录**） |
| `nodeBin` / `converterScript` | `node` / `../converter/convert.js` | — | 转换器调用 |
| `maxUploadMB` | `200` | — | 上传上限 |
| `pgDSN` | `""` | `VIEWER_PG_DSN` | 配置即启用 PG（自动建表），空则文件存储 |
| `editServiceURL` | `http://127.0.0.1:8100` | `VIEWER_EDIT_SERVICE_URL` | edit-service 地址 |

**edit-service**：`VIEWER_DATA_DIR`（必需，同上）、`EDIT_SERVICE_PORT`（默认 8100）。

## 三、浏览器操作

1. **上传**：模型库页拖入 `.ifc`（≤200MB）→ 状态 converting → ready（轮询自动更新）
2. **审查**：进入模型 → 模型树（搜索/类型过滤/显隐）、点选构件看属性（pset 搜索/折叠/复制）、剖切、测量、隐藏/隔离/X-Ray
3. **Issue**：选中构件 → Issue 面板「新建 Issue」（自动带相机视角 + 截图）→ 3D 钉出现在构件上，点击钉定位；状态流转 open/checking/resolved
4. **改属性（override）**：属性面板白名单字段（Name/Description/Classification/FireRating/Comments）行内编辑 → 显示层覆盖（不改 IFC），修改历史 tab 可查
5. **override 迁移真改**（API）：`POST /api/models/{id}/overrides/migrate` → 回放为真实 IFC 修改，失败条目保留 override 并带原因
6. **版本对比**：工具栏「Diff」→ 选 base（v1/v2/…）与 target（版本或 current）→「对比」→ 绿=新增、黄=修改（点击条目定位构件、展开看 old→new）、红=删除（仅列表）；「清除」复位着色

## 四、AI 直连（curl 全流程）

```bash
MID=m_xxxxxxxxxxxxxxxx   # 模型 id（上传响应或 GET /api/models 获得）
GUID=...                 # 构件 GlobalId（metadata.json 的 metaObject id）

# 1. 改属性（进 pending，不落盘）
curl -X PUT http://127.0.0.1:8100/models/$MID/entities/$GUID \
  -H 'Content-Type: application/json' \
  -d '{"fields":{"Name":"新名字"},"psets":{"Pset_WallCommon":{"FireRating":"F60"}},
       "author":"ai-agent","provenance":{"source":"AI"}}'

# 2. 看 pending / 放弃 pending
curl http://127.0.0.1:8100/models/$MID/pending
curl -X DELETE http://127.0.0.1:8100/models/$MID/pending

# 3. commit（落盘 + 版本快照 + history）
curl -X POST http://127.0.0.1:8100/models/$MID/commit

# 4. 版本与 diff
curl http://127.0.0.1:8100/models/$MID/versions
curl -X POST http://127.0.0.1:8100/models/$MID/diff \
  -H 'Content-Type: application/json' -d '{"base":"v1","target":"current"}'
```

> 直连的 commit **不触发** Go 侧 change log 与 XKT 重转。需要完整链路（前端自动刷新可见）时，改走 Go 代理：把 `http://127.0.0.1:8100/models/$MID/...` 换成 `http://127.0.0.1:8090/api/models/$MID/edit/...`。

完整契约（端点目录、JSON Schema、错误码）：`docs/internal/ai-integration.md` + `docs/site/public/ai-tools.openapi.json`。

## 五、验证

```bash
# 端到端（需 server + edit-service 运行中；edit-flow 段服务不可达会自动 skip）
cd viewer && ./scripts/smoke.sh

# 各层测试
cd viewer/server && go test ./...
cd viewer/edit-service && uv run pytest
cd viewer/web && npm test
cd viewer/converter && npm test
```

## 六、故障排查

| 现象 | 排查 |
| --- | --- |
| 上传后一直 converting | 看 server 日志的 converter stderr（截断 500B）；手动跑 `node viewer/converter/convert.js <ifc> <outDir>` 复现；确认 `nodeBin`/`converterScript` 路径 |
| 转换 failed | `POST /api/models/{id}/retry` 重试 |
| 编辑报 404 model not found | edit-service 的 `VIEWER_DATA_DIR` 与 Go `dataDir` 不是同一目录 |
| 编辑报 422 | 属性名不存在或值类型不符——该请求零副作用，修正后重发即可 |
| commit 报 409 | 没有 pending（可能已被他人/上次 commit 消费；pending 存内存，edit-service 重启会丢） |
| 改了属性前端没刷新 | 经 Go 代理 commit 才会触发重转；直连 Python 后需手动刷新或经代理重放 |
| PG 连不上 | 清空 `pgDSN`/`VIEWER_PG_DSN` 回退文件存储；PG 测试需 `VIEWER_TEST_PG_DSN` 指向**专用测试库**（测试会 DROP 表） |
| 端口冲突 | server 8090 / edit-service 8100 / web 5173；改配置或 `ss -tlnp` 找占用 |

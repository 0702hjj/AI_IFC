# AI 接入口：编辑 API 集成指南

面向 AI 生成线的接入文档：如何用 REST 调用本仓库的 IFC 编辑服务，完成「改属性 → pending → commit → diff」全流程。文档中的端点、字段、枚举、默认值均与 `viewer/edit-service/app/`（Python FastAPI）和 `viewer/server/internal/api/`（Go 代理）实现逐一核对；机器可消费的完整 schema 见 [`docs/ai-tools.openapi.json`](ai-tools.openapi.json)（由实现导出，重新生成方式见文末）。

## 概述：双角色同一 API

人（浏览器）与 AI agent 使用**同一套编辑端点**，仅入口与 `provenance.source` 不同：

```
浏览器（人）──► Go server :8090 ──代理──► Python 编辑服务 :8100
                  /api/models/{id}/edit/...        │  /models/{id}/...
AI agent ────────► REST 直连 ──────────────────────┘  （或经 Go 代理，端点一一对应）
                                                   │
                                    {VIEWER_DATA_DIR}/uploads/{id}.ifc
```

- 人：浏览器 → Go server 代理（`/api/models/{id}/edit/...`），commit 后 Go 侧负责写 change log、触发 XKT 重转。
- AI：**REST 直连** Python 编辑服务（默认 `http://127.0.0.1:8100`），调用时传 `provenance.source="AI"`；也可以走 Go 代理，端点一一对应（见「经 Go 代理」一节）。
- Python 服务自带 Swagger UI（`/docs`）与原始 schema（`/openapi.json`）。

## 快速开始

### 起服务

```bash
# 1) Python 编辑服务（默认端口 8100）
cd viewer/edit-service
uv sync
uv run uvicorn app.main:app --port 8100

# 2) Go server（默认 127.0.0.1:8090，配置见 viewer/server/server_config.json）
cd viewer/server
go run ./cmd/server
```

**dataDir 一致性**：Python 的数据目录由 `VIEWER_DATA_DIR` 决定（默认 `../data`，相对进程工作目录），必须与 Go `server_config.json` 的 `dataDir` 指向**同一目录**——两边都按 `{dataDir}/uploads/{id}.ifc` 定位模型文件。Go 侧可用 `VIEWER_EDIT_SERVICE_URL` 覆盖 Python 地址（默认 `http://127.0.0.1:8100`）。

### AI 直连全流程（curl）

前提：已有一个模型，id 形如 `m_` + 16 位小写十六进制（正则 `^m_[0-9a-f]{16}$`），文件在 `{VIEWER_DATA_DIR}/uploads/{id}.ifc`。

```bash
BASE=http://127.0.0.1:8100
MID=m_0123456789abcdef
GUID='2O2Fr$t4X7ZfFPoeewFlqU'   # IFC GlobalId（22 位 base64 风格）

# 1. 改属性 → 记入 pending（只改内存，不落盘）
curl -X PUT "$BASE/models/$MID/entities/$GUID" \
  -H 'Content-Type: application/json' \
  -d '{
        "fields": {"Name": "Basic Wall:AI"},
        "psets":  {"Pset_WallCommon": {"FireRating": "2h"}},
        "author": "ai-agent",
        "provenance": {"source": "AI"}
      }'

# 2. 查看 pending
curl "$BASE/models/$MID/pending"

# 3. commit：原子落盘 + 版本快照 + 追加 history（可选 body 见 commit 模型脚注）
curl -X POST "$BASE/models/$MID/commit"

# 4. 查看版本与 diff
curl "$BASE/models/$MID/versions"
curl -X POST "$BASE/models/$MID/diff" \
  -H 'Content-Type: application/json' \
  -d '{"base": "v1", "target": "current"}'
```

## 端点目录（tool catalog）

路径参数：`id` 匹配 `^m_[0-9a-f]{16}$`；`guid` 为 IFC GlobalId。除标注外，错误响应为 FastAPI 形态 `{"detail": ...}`。

### `GET /health`

健康检查。响应 `{"status": "ok"}`。

### `PUT /models/{id}/entities/{guid}`

把编辑应用到内存模型并记为一条 pending change（**不落盘**）。先全量校验再应用（单请求原子）：任一校验失败则不产生任何修改。

body（JSON Schema，`EditBody`）：

```json
{
  "type": "object",
  "properties": {
    "fields": {
      "type": "object",
      "additionalProperties": true,
      "description": "实体直接属性（Name/Description 等 IFC 属性名 → 新值）；缺省为 {}"
    },
    "psets": {
      "type": "object",
      "additionalProperties": {"type": "object", "additionalProperties": true},
      "description": "pset 名 → {属性名: 新值}；pset 不存在则创建；值限 string/number/boolean/null；缺省为 {}"
    },
    "author": {"type": "string", "default": "local-user"},
    "provenance": {
      "type": "object",
      "properties": {
        "source": {"type": "string", "enum": ["UI", "AI"], "default": "UI"}
      }
    }
  }
}
```

响应 200（pending entry，同时出现在 `GET .../pending` 与 commit 后的 history 中）：

```json
{
  "id": "e_<12位hex>",
  "guid": "...",
  "changes": [{"field": "Name", "oldValue": "...", "newValue": "..."}],
  "author": "ai-agent",
  "provenance": {"source": "AI"},
  "timestamp": "<ISO8601 UTC>"
}
```

`changes[].field`：直接属性用属性名，pset 属性用 `Pset名.属性名`；`oldValue` 取自 IFC 真实值（pset 属性原本不存在时为 `null`；非 JSON 标量的值转为字符串）。

错误码：

| 状态码 | 条件 |
| --- | --- |
| 404 | 模型不存在（`model not found`）或 guid 不存在（`entity not found`） |
| 422 | `fields`/`psets` 均为空；`fields` 含未知属性名；pset 值类型不受支持；字段值与 IFC 属性类型不符（回滚本次 fields 修改） |

### `GET /models/{id}/pending`

列出当前 pending changes（entry 数组，形状同上；无 pending 返回 `[]`）。

> 注意：`GET .../pending` 与 `GET .../history` **不校验模型是否存在**——模型 id 不存在时同样返回 200 `[]`（pending 为内存字典按 id 查询，history 为读文件、文件不存在即空）。写路径（PUT/commit/DELETE pending）与 versions/diff 才会对不存在的模型返回 404。经 Go 代理时 Go 侧会先校验模型，不存在 → 404 / code 40400。

### `DELETE /models/{id}/pending`

丢弃全部 pending：卸载并从磁盘重新加载内存模型。响应 `{"discarded": <丢弃条数>}`。模型不存在 → 404。

### `POST /models/{id}/commit`

把全部 pending 原子落盘（持文件锁）→ 版本快照 → 追加 history（每条 entry 补 `"operation"` 字段）→ 清空 pending。

可选 body（JSON Schema，`CommitBody`）：`{"operation": "update" | "migrate"}`，缺省（或无 body）为 `"update"`，其他值 → 422。`operation` 会被打到本次 commit 的全部 entries 与 history 上；`migrate` 由 Go 侧 override → 真改迁移传入，AI 常规编辑无需传。

响应 200：`{"committed": <条数>, "entries": [...]}`（entries 即持久化的 history 条目）。无 pending → 409（`no pending changes`）；模型不存在 → 404。

> **脚注（commit body）**：Python 的 `POST /models/{id}/commit` 只消费可选的 `operation` 字段。`author`/`provenance` 在每次 PUT 的 body 中流动，先落进 pending entry，再由 commit 原样持久化到 history。经 Go 代理时，Go 会校验 commit body 里的 `provenance.source`（若提供），但转发给 Python 时不带 body（`operation` 取默认 `update`）；Go 的 migrate 端点则显式传 `{"operation": "migrate"}`。

### `GET /models/{id}/history`

列出持久化编辑历史（entry 数组，含 `operation` 字段），存储于 `{VIEWER_DATA_DIR}/models/{id}/edit-history.json`（原子写）。无历史返回 `[]`。

### `GET /models/{id}/versions`

列出版本快照：

```json
{"versions": [{"version": "v1", "createdAt": "<ISO8601 UTC>"}, ...], "current": "v2"}
```

从未 commit 过时 `versions` 为 `[]`、`current` 为 `null`。模型不存在 → 404。

### `POST /models/{id}/diff`

body（JSON Schema，`DiffBody`）：

```json
{
  "type": "object",
  "required": ["base", "target"],
  "properties": {
    "base":   {"type": "string", "description": "版本名，如 v1"},
    "target": {"type": "string", "description": "版本名，或 \"current\" 表示 uploads 现态"}
  }
}
```

响应 200：

```json
{
  "base": "v1",
  "target": "v2",
  "added":   ["<guid>", ...],
  "removed": ["<guid>", ...],
  "changed": [{"guid": "...", "changes": [{"field": "...", "old": ..., "new": ...}]}]
}
```

错误码：base/target 版本不存在 → 404（`version not found: vX`）；缺 `base`/`target` → 422。

### 经 Go 代理（可选入口）

Go server（默认 `127.0.0.1:8090`）把同一套端点暴露在 `/api/models/{id}/edit/...` 前缀下：

| Go 代理端点 | Python 端点 |
| --- | --- |
| `PUT /api/models/{id}/edit/entities/{guid}` | `PUT /models/{id}/entities/{guid}` |
| `GET /api/models/{id}/edit/pending` | `GET /models/{id}/pending` |
| `DELETE /api/models/{id}/edit/pending` | `DELETE /models/{id}/pending` |
| `GET /api/models/{id}/edit/history` | `GET /models/{id}/history` |
| `GET /api/models/{id}/edit/versions` | `GET /models/{id}/versions` |
| `POST /api/models/{id}/edit/diff` | `POST /models/{id}/diff` |
| `POST /api/models/{id}/edit/commit` | `POST /models/{id}/commit` |

与直连的差异：

- **响应包络**：所有响应包一层 `{"code": 0, "message": "ok", "data": <Python 响应>}`；错误为 `{"code": <业务码>, "message": <detail>, "data": null}`。
- **错误映射**：Python 404 → HTTP 404 / code 40400；409 → HTTP 409 / code 40900；422 → HTTP 400 / code 40001；其余（含 Python 不可达）→ HTTP 502 / code 50200。
- **provenance 校验**：PUT 与 commit 的 body 若含 `provenance.source`，Go 侧先校验枚举（UI|AI），非法 → HTTP 400 / code 40001。
- **commit 编排**：Go 代理的 commit 在 Python commit 成功后追加：把 entries 展开写入 change log（`{dataDir}/models/{id}/changes.json`）、用 IfcDiff 结果补充 change log 的 `diff` 字段、把模型状态置为 `converting` 并排入 XKT 重转队列；响应 data 额外含 `"reconverting": true`。
- **commit 后的非致命错误语义**：Python commit 一旦成功，重转**一定**会被排入队列（运行中的转换会被标记重跑，新内容不会丢）。此阶段 change log 写失败（`edit/commit` 与 `overrides/migrate` 同一策略）不再返回 500：记服务端日志，响应仍为 HTTP 200，data 额外含 `"warning"` 字符串（如 `"commit applied but change log write failed: ..."`）；调用方应把 warning 视为降级提示而非失败——IFC 已落盘、重转已排队，仅 change log 可能缺条。

## provenance 与 commit 模型

- `provenance.source`：枚举 `UI | AI`，默认 `UI`。**AI 调用必须传 `"AI"`**。
- `author`：自由文本，默认 `local-user`。
- **两阶段语义**：PUT 只改内存模型并记 pending；commit 才落盘 + 版本快照 + 写 history。pending 在内存中按模型 id 存放，可用 `DELETE .../pending` 整体丢弃（从磁盘重载）。
- **commit 模型**（Go 侧 change log，对齐报告 §1.1）：每条 entry 含 `author` / `createdAt`(timestamp) / `operation`（`update | migrate`）/ `diff`（该 guid 本次 commit 的字段级 changes，JSON）/ `provenance`。`update` 来自常规编辑 commit；`migrate` 来自 override → 真改迁移（`POST /api/models/{id}/overrides/migrate`，把旧属性 override 回放为真实 IFC 修改）。
- Python 侧 history 与 Go 侧 change log 是两份记录：history 按「一次 PUT = 一条 entry（含 changes 数组）」；change log 按「一个字段变更 = 一条 entry」展开。

## 版本与 diff 语义

- 快照存放于 `{VIEWER_DATA_DIR}/models/{id}/versions/v{n}.ifc`（n 从 1 开始，只增不改、原子写）。
- 首次 commit：先把原始上传文件快照为 `v1`，落盘后再快照新文件为 `v2`；之后每次 commit 成功产生 `v{n+1}`。
- diff 以 **GlobalId** 为实体标识：`added`/`removed` 为 guid 列表；`changed` 归约为实体直接属性与 pset 属性的字段级 old→new（基于 ifcdiff 的 `IfcDiff`，仅以 `attributes`/`property` 两种 relationship 运行）。
- **几何 diff v1 不做**：entity 引用属性（ObjectPlacement、Representation 等几何表示层）不参与比较，天然过滤几何噪声。
- 缓存：base/target 均为不可变版本快照时，结果缓存在 `versions/diff-{base}-{target}.json`；`target="current"` 不缓存（uploads 文件可变，无稳定缓存 key）。

## 限制与 v1.1 路线

v1 已知限制（定位：单机单用户内部工具）：

- 单机单用户、**无认证**；请勿暴露到公网。
- pending 只存内存，**Python 服务重启即丢失**未 commit 的修改（history/版本快照不受影响）。
- `VIEWER_DATA_DIR` 必须与 Go `dataDir` 同目录，否则 Python 报 404 `model not found`。
- diff 仅属性级，无几何 diff。

v1.1 候选路线：

- **MCP 化**：报告 §4.1 建议 REST+MCP 双暴露；v1 先 REST（本文档 + `ai-tools.openapi.json` 即 tool catalog 的 REST 形态），MCP 薄包装参考 ifcmcp 31 工具模式。本文档只写路线，不实现。
- **沙箱 / 代码执行**：属 AI 生成侧（另一同学）范围；本架构不阻塞（Python 服务进程隔离，后续可加 execute 端点）。

## 附：OpenAPI schema 的生成与再生成

`docs/ai-tools.openapi.json` 由实现直接导出（`create_app().openapi()`），与运行中服务的 `GET /openapi.json` 天然一致。编辑 API 变更后重新生成：

```bash
cd viewer/edit-service
uv run python scripts/export_openapi.py
```

# AI 接入

面向 AI agent 的接入指南：用 REST 调用 IFC 编辑服务完成「改属性 → pending → commit → diff」全流程。机器可消费的完整 schema 见 [OpenAPI 文件](/reference/openapi)。

## 双角色同一 API

人（浏览器）与 AI agent 使用**同一套编辑端点**，仅入口与 `provenance.source` 不同：

```
浏览器（人）──► Go server :8090 ──代理──► Python 编辑服务 :8100
                  /api/v1/models/{id}/edit/...     │  /models/{id}/...
AI agent ────────► REST 直连 ──────────────────────┘  （或经 Go 代理，端点一一对应）
```

- 人：浏览器 → Go 代理，commit 后 Go 侧写 change log、触发 XKT 重转。
- AI：REST 直连 edit-service（默认 `http://127.0.0.1:8100`），调用时传 `provenance.source="AI"`；也可走 Go 代理。
- Python 服务自带 Swagger UI（`/docs`）与原始 schema（`/openapi.json`）。

## 快速开始

```bash
# 1) Python 编辑服务（默认端口 8100）
cd viewer/edit-service
uv sync
uv run uvicorn app.main:app --port 8100

# 2) Go server（默认 127.0.0.1:8090）
cd viewer/server
go run ./cmd/server
```

**dataDir 一致性**：`VIEWER_DATA_DIR` 必须与 Go `server_config.json` 的 `dataDir` 指向同一目录（两边都按 `{dataDir}/uploads/{id}.ifc` 定位模型文件）。

## AI 直连全流程（curl）

前提：已有一个模型（id 形如 `m_` + 16 位小写 hex），文件在 `{VIEWER_DATA_DIR}/uploads/{id}.ifc`。

```bash
BASE=http://127.0.0.1:8100
MID=m_0123456789abcdef
GUID='2O2Fr$t4X7ZfFPoeewFlqU'   # IFC GlobalId

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

# 3. commit：原子落盘 + 版本快照 + 追加 history
curl -X POST "$BASE/models/$MID/commit"

# 4. 查看版本与 diff
curl "$BASE/models/$MID/versions"
curl -X POST "$BASE/models/$MID/diff" \
  -H 'Content-Type: application/json' \
  -d '{"base": "v1", "target": "current"}'
```

> 直连的 commit **不触发** Go 侧 change log 与 XKT 重转。需要完整链路（前端自动刷新可见）时改走 Go 代理：`http://127.0.0.1:8090/api/v1/models/$MID/edit/...`。

## provenance 与 commit 模型

- `provenance.source`：枚举 `UI | AI`，默认 `UI`。**AI 调用必须传 `"AI"`**。它是声明字段，无防伪语义（v1 无认证）。
- `author`：自由文本，默认 `local-user`。
- 两阶段语义：PUT 只改内存并记 pending；commit 才落盘 + 版本快照 + 写 history。
- commit 模型（Go 侧 change log）：每条 entry 含 `author` / `createdAt` / `operation`（`update | migrate`）/ `diff` / `provenance`。
- Python history 与 Go change log 是两份记录：history 按「一次 PUT = 一条 entry」；change log 按「一个字段变更 = 一条 entry」展开。

## 版本与 diff 语义

- 快照存放于 `{VIEWER_DATA_DIR}/models/{id}/versions/v{n}.ifc`（n 从 1 开始，只增不改、原子写）。
- 首次 commit：先把原始上传快照为 v1，再快照新文件为 v2；之后每次 commit 产生 v{n+1}。
- diff 以 GlobalId 为实体标识；changed 归约为实体直接属性与 pset 属性字段级 old→new；entity 引用属性（几何表示层）不参与比较。
- 快照间 diff 结果缓存在 `versions/diff-{base}-{target}.json`；`target="current"` 不缓存。

## 限制与后续路线

v1 已知限制（详见 [已知限制](/project/known-limits)）：单机单用户、无认证（勿暴露公网）；pending 只存内存（服务重启丢失）；`VIEWER_DATA_DIR` 必须与 Go `dataDir` 同目录；diff 仅属性级。

后续路线（**当前未交付**）：MCP 化（REST+MCP 双暴露，参考 ifcmcp 工具模式）与沙箱/代码执行端点——详见 [Roadmap](/project/roadmap)。

## 与 aiifc skill 的分工

REST 编辑 API 适合「改现有模型属性/pset」这类细粒度编辑；若要**从零建模型或大改几何**，用 [AI Skill（aiifc）](/reference/ai-skill)——agent 直接写 `ifcopenshell.api` 代码产出完整 IFC 文件，再交给平台做 commit/版本/重转。

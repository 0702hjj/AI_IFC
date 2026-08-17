# AI 接入

面向 AI agent 的接入指南：script-as-source 下，AI 的修改统一落在构建脚本上——暂存（`PUT /script`）→ 沙箱试运行（`script/run`）→ 保存大版本（`script/save`）。机器可消费的完整 schema 见 [OpenAPI 文件](/reference/openapi)。

> **直改链路已退役**：原「改属性 → pending → commit」端点（`PUT /entities/{guid}`、`POST /commit` 等）返回 410 Gone。细粒度参数修改改用 `POST /script/edit-call`（libcst 标量改写）或 PARAMS 暂存。

## 平台内置 chat agent（Eino）

除 REST 直连外，平台自带一个**进程内 chat agent**（`server/internal/agent/`，cloudwego/eino react loop）：web 界面的「AI 对话」侧栏即由它驱动，经下方同一套领域工具读写平台，SSE 事件流与 REST 契约公开不变。

- **LLM 配置**：`llmAPIKey` / `llmBaseURL` / `llmModel`（env `VIEWER_LLM_API_KEY` 等，OpenAI 兼容端点）；**key 为空时回退 scriptedModel**（确定性离线模式，不产生真实智能回复）。
- **领域工具面**（agent 只见这些，无 bash/任意文件写）：`list_models`、`get_model_info`、`get_script`、`stage_script`、`run_script`、`save_script`、`get_versions`、`get_diff`、`create_project`、`dispatch_ifc_agent` / `dispatch_cad_agent`（主子编排入口）。按模型 kind 自动路由 ifc→edit-service(:8100) / dxf→cad-edit-service(:8200)；工具错误以文本返回供模型自愈，结果 64KB 截断。
- **主子编排**：`dispatch_ifc_agent` / `dispatch_cad_agent` 派子 agent（独立 agent run + persona，深度预算 1 防递归）；子 agent 事件带 `subagentId` 标签经同一 SSE 下发，前端右侧边栏分组展示。
- agent 的暂存/保存改动同样走 notify 管线：run/save 成功后自动排队重转、`viewer.committed` 事件驱动前端刷新。

## 双角色同一 API

人（浏览器）与 AI agent 使用**同一套脚本编辑端点**，仅入口不同：

```
浏览器（人）──► Go server :8090 ──代理──► Python 编辑服务 :8100
                  /api/v1/models/{id}/script/...  │  /models/{id}/script/...
AI agent ────────► REST 直连 ──────────────────────┘  （或经 Go 代理，端点一一对应）
```

- 人：浏览器 → Go 代理，run/save/rollback 成功后 Go 侧排队 XKT 重转。
- AI：REST 直连 edit-service（默认 `http://127.0.0.1:8100`）；也可走 Go 代理。`script/edit-call` 不经 Go 代理，仅直连可用。
- Python 服务自带 Swagger UI（`/docs`）与原始 schema（`/openapi.json`）。

## 快速开始

```bash
# 1) Python 编辑服务（默认端口 8100）
cd services/ifc
uv sync
uv run uvicorn app.main:app --port 8100

# 2) Go server（默认 127.0.0.1:8090）
cd server
go run ./cmd/server
```

**dataDir 一致性**：`VIEWER_DATA_DIR` 必须与 Go `server_config.json` 的 `dataDir` 指向同一目录（两边都按 `{dataDir}/uploads/{id}.ifc` 定位模型文件）。

> **脱离 viewer 独立部署**：AI agent 可以不装 Go server / web / converter / PostgreSQL，只装 `services/ifc/`（`uv sync`）即可用上述同一套端点做脚本编辑、版本与 diff。独立部署、模型文件布局、端点全清单、可缺省边界与移植指南见 [services/ifc 独立部署与调用](/guide/services-ifc)。

## AI 直连全流程（curl）

前提：已有一个模型（id 形如 `m_` + 16 位小写 hex），文件在 `{VIEWER_DATA_DIR}/uploads/{id}.ifc`。

### A. 上传 IFC 的参考生成（bootstrap）

```bash
BASE=http://127.0.0.1:8100
MID=m_0123456789abcdef

# 1. 用 aiifc skill 编写复现脚本（MCP server 可读取模型），暂存
#    首次暂存时平台自动把上传原件保留为 bootstrap.ifc
curl -X PUT "$BASE/models/$MID/script" \
  -H 'Content-Type: application/json' \
  -d '{"script": "PARAMS = {...}\n\ndef build(params, out_path):\n    ...\n"}'

# 2. 沙箱试运行（预览，无版本）
curl -X POST "$BASE/models/$MID/script/run"

# 3. 保存大版本 v1（脚本 + map 成对快照）
#    响应带 alignment 计数：bootstrap 原件 vs 生成 IFC 的语义 diff 摘要
curl -X POST "$BASE/models/$MID/script/save" \
  -H 'Content-Type: application/json' -d '{"note": "bootstrap v1"}'
```

### B. 既有脚本的定向修改

```bash
# 1. 按 guid 定位脚本调用点（line/col/snippet/origin）
curl "$BASE/models/$MID/script/locate?guid=2O2Fr\$t4X7ZfFPoeewFlqU"

# 2a. origin=params：只改 PARAMS 键值，暂存一步
curl -X PUT "$BASE/models/$MID/script" \
  -H 'Content-Type: application/json' \
  -d '{"params": {"wall_height": 3.2}}'

# 2b. origin=literal：libcst 标量改写 + 沙箱验证 + 暂存（一步完成）
curl -X POST "$BASE/models/$MID/script/edit-call" \
  -H 'Content-Type: application/json' \
  -d '{"designKey": "L1:wall:1", "argument": "height", "value": 3.2}'

# 3. 保存大版本
curl -X POST "$BASE/models/$MID/script/save"

# 4. 版本对比：脚本 diff + IFC 语义 diff
curl -X POST "$BASE/models/$MID/script/diff" \
  -H 'Content-Type: application/json' -d '{"base": "v1", "target": "v2"}'
curl -X POST "$BASE/models/$MID/diff" \
  -H 'Content-Type: application/json' -d '{"base": "v1", "target": "current"}'
```

> 直连的 run/save **不触发** Go 侧 XKT 重转。需要前端自动刷新可见时改走 Go 代理：`http://127.0.0.1:8090/api/v1/models/$MID/script/...`。

## 契约要点

- **脚本契约**（aiifc skill MUST #25-31）：顶层 `PARAMS` 字面量 dict；构件经 `script_lib.create_entity` 工厂创建（确定性 GlobalId + `Pset_AIIFC.designKey` + 调用点记录，C-locate #30）；web 可编辑参数必须是标量字面量或 PARAMS 引用（C-scalar #31）；`build(params, out_path)` 入口；出口过 `ifcopenshell.validate`。
- **失败语义**：契约校验或沙箱 build 失败 → 422 零副作用；edit-call 对 `origin=traced` / 非标量 / 非法参数名 / 非有限浮点 → 422；locate miss → 200 `{"found": false}`（不 5xx）。
- **版本语义**：`scripts/v{n}.py` + `v{n}.map.json` 全量保留、lockstep 编号；`versions/v{n}.ifc` 只物化最新，历史按需从脚本重建（语义 diff 对齐，不断言字节）。
- **provenance**：登记外部用户修改用 `POST /models/{id}/user-edits`（`source="USER"`）；issue 创建仍支持 `provenance.source`。

## 限制与后续路线

v1 已知限制（详见 [已知限制](/project/known-limits)）：单机单用户、无认证（勿暴露公网）；`VIEWER_DATA_DIR` 必须与 Go `dataDir` 同目录；diff 仅属性级。

## 与 aiifc skill 的分工

REST 编辑 API 适合「在既有脚本上做定向修改 / 暂存 / 版本管理」；**从零建模型或大改几何**用 [AI Skill（aiifc）](/reference/ai-skill)——agent 直接写符合脚本契约的 `ifcopenshell.api` 构建脚本，再交给平台做沙箱执行、版本与 diff。上传 IFC 的复现（bootstrap）同样由 skill 产出脚本完成。

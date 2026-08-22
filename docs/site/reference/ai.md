# AI 接入

面向 AI agent 的接入指南：script-as-source 下，AI 的修改统一落在构建脚本上——暂存（`PUT /script`）→ 沙箱试运行（`script/run`）→ 保存大版本（`script/save`）。机器可消费的完整 schema 见 [OpenAPI 文件](/reference/openapi)。

> **直改链路已退役**：原「改属性 → pending → commit」端点（`PUT /entities/{guid}`、`POST /commit` 等）返回 410 Gone。细粒度参数修改改用 `POST /script/edit-call`（libcst 标量改写）或 PARAMS 暂存。

## 平台内置 chat agent（Eino ADK）

除 REST 直连外，平台自带一个**进程内 chat agent**（`server/internal/agent/`，cloudwego/eino **ADK**：`adk.ChatModelAgent` + `Runner`）：web 界面的「AI 对话」侧栏即由它驱动，经下方同一套领域工具读写平台，SSE 事件流与 REST 契约公开不变。

- **LLM 配置**：`llmAPIKey` / `llmBaseURL` / `llmModel`（env `VIEWER_LLM_API_KEY` 等，OpenAI 兼容端点）；**key 为空时回退 scriptedModel**（确定性离线模式，不产生真实智能回复）。
- **领域工具面**（agent 只见这些，无 bash/任意文件写）：平台级 `create_project`、`init_model`（骨架模型注册 modelId + **写 Model.ProjectID 反向归属**，成功后推 SSE `model.created`——前端刷新渲染）、`get_project_models`、`get_script`、`stage_script`、`run_script`、`save_script`、`get_versions`、`get_diff`、`get_model_info`、`list_models`；方案级 `deliver_plan`（plan.json + bim_supplement 版本化）、`deliver_building`（building.json zones 记 modelId）、`get_project_plans`、`get_skill_workdir`、桥接工具 `stage_plan_to_workdir`（aiplan→cad）/ `stage_upstream_to_workdir`（cad→ifc：building + bim + 各 zone DXF 落工作区）。按模型 kind 自动路由 ifc→edit-service(:8100) / dxf→cad-edit-service(:8200)；工具错误以文本返回供模型自愈，结果 64KB 截断。**模型↔项目双向归属**：`Project.Models` 正向 + `Model.ProjectID` 反向；删除模型联动项目摘除（无孤儿）。
- **三角色编排（AgentAsTool）**：orchestrator（对话入口 + 意图路由）经官方 `AgentAsTool` 派 `ifc-agent`（aiifc skill）/ `cad-agent`（aidxf skill）子 agent（独立 ChatModelAgent + 独立模型实例 + 深度预算 1）；子 agent 事件带 `subagentId` 标签经同一 SSE 下发，前端右侧边栏分组展示。
- **skill 接入（`skills/dist` 正式集合）**：`aiplan`（规划协调，orchestrator 内联）、`aiifc`（IFC，含 cad→ifc 消费上游链 consume-upstream）、`aidxf`（CAD）——官方 skill middleware 加载 SKILL.md，`filesystem` 收敛适配提供读 references（read_file/glob/grep）+ 白名单 CLI 执行（execute，`aiplan,aidxfv3,aiifc`），禁止任意文件写。skill 中间产物（design.json/features.json/演示 IFC）经 `--project-id` 结构性落 `{DATA}/skill-work/{projectID}/`（不版本化）。
- **会话连续性**：跨 turn 历史回填（检查阀门：≤60% context 全量喂，超预算语义压缩每轮指令+最终回复）；模型随时 get_script 读当前脚本（script-as-source 事实源）。
- **HITL 提问**：`ask_user` 工具（官方 interrupt/resume）→ SSE `question.ask` 帧，用户回答续跑。
- agent 的暂存/保存改动同样走 notify 管线：run/save 成功后自动排队重转、`viewer.committed` 事件驱动前端刷新。

### 中途预览（live preview）

`run_script` 试跑成功即推 SSE 事件 `event: viewer.staged`（`data: {"modelId","kind":"ifc"|"dxf"}`，严格 2 字段，与 `viewer.committed` 同一推送管线），**保存大版本之前**人就能看到中间结果：

- **dxf 管线**：render.json 直挂，画布自动刷新。
- **ifc + webifc 引擎**：web-ifc 直读 IFC，自动重挂查看器。
- **ifc + xeokit 引擎**：重转 XKT 慢且闪烁，不自动刷——画布左上角出现角标「AI 中间结果 · 点击预览」，点击才重载。

同时 `run_script` 的工具结果末尾会追加 staging diff 摘要，供 AI 对照预期自纠：**优先构件级计数**（`[staging diff] 构件 +N -M ~K`，取自 run 响应的 `semanticDiff`——`script/run` 成功时附旧产物 vs 新产物的构件级 `{added, removed, changed}`，diff 失败或首次 run 无旧产物时为 `null`）；构件级不可用时**回退行级摘要**（`[staging diff] added=N removed=M` + `PARAMS +/-/~ key ...` 行，复用 `GET /script/staging/diff`）；两者都不可用则不附摘要。run 失败时不推事件、不附摘要。

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

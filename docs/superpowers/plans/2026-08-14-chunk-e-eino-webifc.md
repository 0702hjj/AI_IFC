# Chunk E：Eino 替换 opencode + 主子编排 + web-ifc 查看器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox syntax.
> 用户裁决（2026-08-14）：领域收敛工具面；主子编排一起做；本 chunk 与 web-ifc 合并为一个 PR（节奏放慢）；参考 ~/projects/work/sec-agent（Eino 最小样本）、~/projects/deepseek-harness（架构）、~/projects/codex、grok-build（agent 能力范式）。

**Goal:** 用进程内 Eino agent loop 全量替换 opencode serve（SSE/REST 契约不变），落地 aibim-orchestrator 主子编排（subagent-as-tool），并交付 web-ifc IFC 查看器（与 xeokit 并存渐进）。一个 PR 收口。

**Architecture:**
- **chat 内核**：`server/internal/agent/`（新包）——eino `react.NewAgent` + `utils.InferTool` 领域工具 + `callbacks` 采集 → 事件翻译层产出**与 opencode 原生形状一致**的 SSE 事件（ChatSidebar 零改动）+ 自有事件（viewer.committed/notify_failed 与新增 subagent.*）。会话持久化改 append-only JSONL 事件日志（dsh 模式），`chat-sessions.json` 映射表保留兼容。
- **主子编排**：`subagent` 工具（dsh 模式：子=独立 agent run + parentSessionId 元数据 + 深度预算=1）；ifc/cad 子 agent persona 取自 `skills/aibim-orchestrator`；子 agent 事件打 `subagentId` 标签经同一 SSE 下发，前端右侧边栏展示。
- **notify 管线不动**（Pure Core/Shell 已事件化）：agent 经领域工具改 staging/uploads → idle 后 Go 照旧 commit。
- **web-ifc**：`web-ifc`（0.0.77，wasm 拷 public）+ `three`（0.185）手写最小 loader；**不用** web-ifc-three（2024 停更，three 版本冲突）。与 xeokit 并存：用户级开关（localStorage）+ 默认 xeokit。

**Tech Stack:** Go 1.26 + cloudwego/eino v0.9.13 + eino-ext openai 组件；React 19 + three + web-ifc。

## Global Constraints

- 分支 `feat/v0.9-eino-webifc`（自 main 新建）；**整 chunk 一个 PR**；commit 中文前缀式；TDD；测试 ≥1:1。
- **契约红线**：ChatSidebar 消费的 SSE 事件集与 data 形状（message.updated / message.part.updated / message.part.delta / message.part.removed / session.status / session.idle / session.error + viewer.committed / viewer.notify_failed）逐字段不变；7 条 REST 路由 + envelope + Last-Event-ID 重同步语义不变；`POST /chat/projects` 骨架项目不变；prompt 系统上下文注入格式不变。
- 配置：`VIEWER_LLM_API_KEY` / `VIEWER_LLM_BASE_URL` / `VIEWER_LLM_MODEL`（server_config.json 同名字段）；**API key 为空时回退 scriptedModel**（确定性 mock，sec-agent 模式——测试与离线 demo 不依赖真模型）。VIEWER_OPENCODE_URL 退役（config 删除 + 文档标注）。
- kind 感知：chat 绑定 dxf 模型时工具路由到 cad 服务（清偿 main.go:150 注释的已知缺口）。
- 工具面（领域收敛，禁止 bash/任意文件写）：`list_models / get_model_info / get_script / stage_script / run_script / save_script / get_versions / get_diff / get_render_entities(可选) / create_project`；文件访问只读 data 目录白名单路径；edit-service/cad 调用经既有 client；错误以文本返回供 LLM 自愈（sec-agent 模式），工具结果 64KB 截断。
- 主子编排：深度预算 1（主→子一层，防递归）；子 agent 复用主 agent 领域工具集（按 persona 过滤：cad 子 agent 不给 IFC 专用工具）；子 agent 事件 SSE data 带 `subagentId` + `parentSessionId`；子 agent 的 staging 改动同样走 notify 管线。
- 测试纪律：Eino 层全部经 scriptedModel 确定性测试；SSE 契约测试逐字段对拍既有 chat_sse_test.go 用例（改造成新实现的契约钉）；异步写盘条件等待。
- opencode 移除范围：`server/internal/opencode/`、`VIEWER_OPENCODE_URL`、main.go 装配、根 `opencode.json`/`.opencode/`（保留 .opencode/agent/ 下的 agent 定义文件作参考？——裁决：保留 .opencode/ 目录作为提示词资产，文档注明不再被 server 消费；根 opencode.json 删除）。
- Eino 升级面：`github.com/cloudwego/eino v0.9.13` + `github.com/cloudwego/eino-ext/components/model/openai`（sec-agent 同款版本组合）；go.mod 变更需 `go mod tidy` 后 CI 绿。

---

### Task 1: 立项 W-0043/W-0044 + PLAN 行

- [ ] W-0043「Eino 替换 opencode + 主子编排」：验收——契约红线逐条（SSE 事件形状对拍 / 7 路由 / 重同步 / projects / 注入格式）；scriptedModel 离线测试；subagent 工具 + 事件标签；kind 感知；opencode 移除；VitePress AI 接入文档更新。
- [ ] W-0044「web-ifc IFC 查看器（并存渐进）」：验收——web-ifc+three 加载/树/属性/选中；开关切换默认 xeokit；wasm 部署（vite public + nginx MIME）；测试 mock wasm。
- [ ] PLAN v0.6 加 chunk E 行。
- [ ] Commit `docs(work): W-0043/W-0044 立项 + PLAN chunk E 行`

---

### Task 2: agent 包骨架——事件日志 + react loop + scriptedModel（TDD）

**Files:**
- Create: `server/internal/agent/model.go`（NewChatModel：openai 组件装配；API key 空 → scriptedModel）
- Create: `server/internal/agent/scripted.go`（确定性 ToolCallingChatModel mock：按脚本步进产出 text/tool_call 帧）
- Create: `server/internal/agent/agent.go`（react.NewAgent 装配 + persona modifier + MaxStep）
- Create: `server/internal/agent/events.go`（append-only 事件日志：turn/step/chunk/tool_call/tool_result 词汇 + JSONL 持久化 + projection 派生消息列表）
- Test: `server/internal/agent/*_test.go`

**Interfaces（Produces——后续 Task 依赖）:**
- `agent.New(cfg LLMConfig) (*Agent, error)`；`Agent.Run(ctx, sessionID, userText) (<-chan Event, error)`（事件流）；`Event{Type, Turn, Step, Payload json.RawMessage, Ts}`；`agent.EventStore`（JSONL append + Load + projection）。

- [ ] **Step 1: 失败测试**——scriptedModel 确定性（同脚本两跑事件序列全等）；react loop 工具调用回合（scripted 产 tool_call → 工具执行 → 结果回灌 → 终答）；事件日志 append/Load round-trip + projection 派生 openai 消息史；MaxStep 截断。
- [ ] **Step 2: 实现**（照 sec-agent internal/agent/ 模式；react.Generate 先行，Stream 在 Task 3 接）
- [ ] **Step 3: `go test ./internal/agent/ && go vet` 绿 + Commit** `feat(server): agent 包骨架——eino react loop + scriptedModel + JSONL 事件日志（W-0043 上半 a）`

---

### Task 3: chat 接线——SSE 契约仿真 + REST 路由 + notify 复用（TDD）

**Files:**
- Create: `server/internal/api/chat_eino.go`（7 路由 handler，复用 chat.go 的装配/错误映射）
- Create: `server/internal/api/chat_translate.go`（agent Event → opencode 形状 SSE 帧的纯函数翻译层：message.updated/part.updated(part.type=text|reasoning|tool)/part.delta/session.status(busy|idle)/session.error）
- Modify: `server/cmd/server/main.go`（装配切换：LLM 三参 config + agent handler 替换 opencode handler；保留 notify 触发——idle 判定改为 agent loop 结束事件）
- Modify: `server/internal/api/chat_session.go`（会话映射表保留 chat-sessions.json；opencodeSessionId 字段改 agentSessionId 语义不变；历史回填改读事件日志 projection）
- Test: `chat_translate_test.go`（纯函数逐字段对拍）、`chat_sse_test.go`（既有用例改造钉新实现：递增 id/重同步/缓冲滚动）、`chat_test.go` 保留契约用例（幂等创建/projects/notify 管线）

**Interfaces:**
- Consumes: Task 2 `Agent.Run` 事件流、`EventStore`
- Produces: 与现网完全一致的 SSE/REST 契约；`translateEvent(Event) []sseFrame` 纯函数

- [ ] **Step 1: 失败测试**——翻译层：scripted 事件序列 → SSE 帧逐字段对拍既有 ChatSidebar 契约（含 tool part 的 state.status/title/input/output/error 映射；reasoning 折叠段）；重同步三用例改造后红→绿；notify 触发点：agent loop 结束（idle）+ staging dirty → planNotify 管线调用顺序不变（chat_notify_test 改造钉）。
- [ ] **Step 2: 实现**
- [ ] **Step 3: 绿 + Commit** `feat(server): chat 切 Eino——SSE 契约仿真 + REST 路由 + notify 复用（W-0043 上半 b）`

---

### Task 4: 领域工具集 + kind 感知（TDD）

**Files:**
- Create: `server/internal/agent/tools.go`（InferTool 注册：jsonschema tag + 64KB 截断 + 错误文本化）
- Create: `server/internal/agent/tools_test.go`
- Modify: 装配处按 model kind 选 editsvc/cadsvc client（main.go:150 注释清偿）

**Interfaces（Produces）:** `agent.DomainTools(deps ToolDeps) []tool.InvokableTool`；ToolDeps 含 ifc/cad client、dataDir、modelId 解析器。

- [ ] **Step 1: 失败测试**（每个工具：正常路径 + 错误文本化 + 截断 + kind 路由）
  - `list_models`（kind 字段带出）、`get_model_info`、`get_script`（staging 或基线）、`stage_script{script}`（PUT /script 代理）、`run_script`（POST run，DoSlow）、`save_script`、`get_versions`、`get_diff{base,target}`、`create_project`（复用骨架生成）
  - kind 路由：dxf modelId → cad client 被调、ifc client 零调用（双 fake 钉死）
  - 守卫：路径白名单外的文件访问拒绝；未知 modelId 错误文本化
- [ ] **Step 2: 实现**
- [ ] **Step 3: 绿 + Commit** `feat(server): 领域工具集 + kind 感知路由（W-0043 中）`

---

### Task 5: subagent 工具 + 事件标签（TDD）

**Files:**
- Create: `server/internal/agent/subagent.go`（subagent 工具：ifc-agent/cad-agent 两种 persona——system prompt 取自 skills/aibim-orchestrator/references/SUBAGENTS.md 要点内嵌常量；独立 agent run + parentSessionId + 深度预算 1；子事件打 subagentId 经同一事件流上浮）
- Modify: `server/internal/api/chat_translate.go`（子 agent 事件翻译：tool part 内嵌 subagent 标记 + `subagent.status` 事件（start/end + parentSessionId））
- Modify: `web/src/viewer/ChatSidebar.tsx`（右侧 subagent 边栏：按 subagentId 分组展示子 agent 的 text/tool 片段，折叠面板；主会话流不变）
- Test: `subagent_test.go`、`ChatSidebar.test.tsx`（subagent 事件渲染用例）

**Interfaces:** `subagentTool(persona, deps) InvokableTool`；SSE 新增事件 `subagent.status{subagentId,parentSessionId,persona,status:started|finished}`；子 agent 的 part 事件 data 附加 `subagentId` 字段（主会话事件不带——前端据此分流，旧事件形状不变）。

- [ ] **Step 1: 失败测试**——scripted 主 agent 产 subagent tool_call → 子 run 执行（scripted 子模型）→ 事件序列带 subagentId/parentSessionId；深度预算：子 agent 的 subagent 工具不可见；前端：subagent.status/part 事件进边栏分组渲染，主会话流不受影响（既有用例不回归）。
- [ ] **Step 2: 实现**
- [ ] **Step 3: 绿 + Commit** `feat: subagent 编排落地——subagent-as-tool + 事件标签 + 右侧边栏（W-0043 下半）`

---

### Task 6: opencode 移除 + 配置切换

**Files:**
- Delete: `server/internal/opencode/`、根 `opencode.json`
- Modify: `server/cmd/server/main.go`（VIEWER_OPENCODE_URL/装配删）、`server/server_config.json`（llm 三参）、`docker-compose*`（opencode 服务条目——检查）、`.opencode/`（保留，README 注明提示词资产不再被 server 消费）
- Modify: 受影响测试（chat 测试已全部改造后此处应零引用）

- [ ] **Step 1: `grep -rn opencode server/ --include="*.go" | grep -v _test` 清零 + 全量测试绿**
- [ ] **Step 2: Commit** `refactor(server): opencode serve 退役——Eino 进程内 agent 全面接管`

---

### Task 7: web-ifc IFC 查看器（并存渐进，TDD）

**Files:**
- Modify: `web/package.json`（+ three@0.185、web-ifc@0.0.77；wasm 文件拷 web/public/wasm/）
- Create: `web/src/ifcviewer/IfcLiteViewer.tsx`（three 场景 + web-ifc IfcAPI 加载 `/v1/models/{id}/download` IFC → BufferGeometry；轨道控制；模型树（IfcAPI 空间结构遍历）；属性面板（选中 → IfcAPI 属性行）；选中高亮）
- Create: `web/src/ifcviewer/ifcLoader.ts`（纯逻辑层：IfcAPI 装配/几何提取——可 mock wasm 单测）
- Modify: `web/src/pages/ViewerPage.tsx`（引擎开关：localStorage `viewerEngine=xeokit|webifc`，默认 xeokit；Toolbar 或设置入口切换）
- Modify: `web/Dockerfile`/`web/nginx.conf`（wasm MIME application/wasm——检查现状补）
- Test: `ifcLoader.test.ts`（mock web-ifc wasm 接口）、`IfcLiteViewer.test.tsx`（mock three/web-ifc）

**Interfaces:** `IfcLiteViewer({ modelId })`；wasm 路径 `WebIFC.IfcAPI.SetWasmPath("/AI_IFC/wasm/")`（base 对齐 vite base）。

- [ ] **Step 1: 失败测试**——loader：mock IfcAPI（OpenModel/GetGeometry/GetLineIDsWithType/GetName 等）→ 几何/树/属性提取断言；组件：引擎开关持久化 + 分流渲染（webifc 分支不建 xeokit Viewer）；wasm 路径拼接含 base。
- [ ] **Step 2: 实现**（web-ifc 官方 three.js 示例模式：IfcAPI.Init → OpenModel → 遍历 ExpressID → GetGeometry → BufferGeometry 合批；树取 IFCPROJECT/IFCSITE/IFCBUILDING/IFCBUILDINGSTOREY 层级；属性取 GetLine）
- [ ] **Step 3: `npm test && lint && build` 绿 + W-0044 done + Commit** `feat(web): web-ifc IFC 查看器（并存渐进，默认 xeokit）（W-0044）`

---

### Task 8: VitePress 文档还债 + 收口

**Files:**
- Modify: `docs/site/reference/ai.md`（+en：Eino 架构、LLM 三参配置、scriptedModel 离线模式、领域工具表、主子编排）
- Modify: `docs/site/development/architecture.md`（+en：架构图 opencode→Eino、web-ifc 并存说明）
- Modify: `docs/site/guide/configuration.md`（+en：VIEWER_LLM_* 三参；VIEWER_OPENCODE_URL 退役标注）
- Modify: `AGENTS.md`（组件表 opencode→agent 包；server 测试计数；架构描述；逻辑一/二状态行）
- Modify: `docs/work/PLAN-v0.1.0.md`（chunk E ✅）、W-0043 done
- [ ] `cd docs && npm run docs:build && npm run check:api`（Eino 不改 REST 形状，应无漂移；chat 文档页手工同步）
- [ ] 全量回归：server / web / services×2 / skill / mcp 全部测试
- [ ] Commit `docs: chunk E 收口——Eino/web-ifc 文档 + AGENTS 同步`

---

## Self-Review 记录

- 覆盖：Eino 替换（用户裁决）→Task 2-6；主子编排→Task 5；web-ifc→Task 7；VitePress 还债→Task 8；契约红线→Global Constraints + Task 3 对拍测试。
- 类型一致：`Agent.Run` 事件流（Task 2）→ 翻译层（Task 3）→ subagent 标签（Task 5）一条链签名一致；`DomainTools` deps（Task 4）与装配（Task 3/6）一致。
- 风险：react 包 API 版本差异（v0.9.13 以 sec-agent 编译产物为准）；SSE 仿真与 opencode 原生形状的边角（reasoning/tool 态）靠对拍测试钉；web-ifc wasm 在 jsdom 不可执行必须 mock（测试价值集中在提取逻辑）。
- 明确不做：MAS 四级表持久化（gaia 模式，过度设计）；subagent 深度>1；bash/通用文件工具；opencode 兼容层。

# agent 包结构规范

> 从 `server/internal/agent` 现状抽出的**不可轻易改**的结构契约。
> 上游讨论/部署方案重写时以本文为准；实现以源码为准，冲突先改本文再改代码。
> 包路径：`server/internal/agent/`。装配胶水在 `server/internal/api/chat_tools.go`，不属本包但受本规范约束。

## 1. 包边界

- 本包只做：**ADK ChatModelAgent 循环装配、领域工具、subagent 派发、事件账本、离线模型**。
- 不做：HTTP/SSE 翻译、会话 CRUD、notify 落盘、XKT 重转。那些在 `internal/api/chat_*.go`。
- 工具变更一律经 edit-service REST（ifc :8100 / cad :8200），本包**禁止** bash / 任意文件写。

## 2. 文件职责

| 文件 | 职责 | 禁止变成 |
|---|---|---|
| `agent.go` | `adk.NewChatModelAgent` + `adk.NewRunner` 装配（含官方 skill middleware / safeToolMiddleware）+ `Run` 事件扇出 | 业务规则 / REST / 文件 IO |
| `events.go` | 事件模型 + 存储 + ADK 翻译层：9 种事件常量、`Event`、`EventStore` JSONL、`Project` 投影、`adkTranslator`（AgentEvent→平台事件，见 §4） | 工具实现 |
| `middleware_safe.go` | 官方 SafeToolMiddleware 对齐：工具 Go error → 文本结果（`[tool error] ...`），interrupt 透传；翻译层据此恢复 error 载荷 | 业务规则 |
| `tools.go` | 9 个领域工具 + `resolve` kind 路由 + 截断/错误文本化 | 派发逻辑 |
| `fs_backend.go` | 官方 filesystem 收敛适配：`fsReadOnlyBackend`（读透传/写拒绝）+ `validateSkillCommand` 命令白名单 | 业务规则 |
| `agents.go` | persona 常量 + 三角色装配：`newRoleAgent`（ifc/cad 子 agent）、`orchestratorTools`（AgentAsTool 包装）、`newSkillMiddleware`/`newFilesystemMiddleware`（官方 skill/文件挂载） | 领域 REST |
| `model.go` | OpenAI 兼容 ChatModel；APIKey 空返回 nil | 工具 |
| `scripted.go` | 确定性 mock（测试/离线），ADK 兼容（WithTools + Stream） | 生产推理 |

新增能力按上表归位：skill 接入用官方 middleware（`agent.New` 挂 `WithSkillsDir`），不自写解析器。

## 3. 工具面规范

### 3.1 构造

- 一律 `utils.InferTool`；schema 静态，构造失败 `panic`（`mustTool`）。
- 对外类型：`tool.InvokableTool`；进 `WithTools` 前经 `AsBaseTools` 转 `[]tool.BaseTool`。
- 工具名、jsonschema description 即模型可见契约，改名/改参必须有测试。

### 3.2 错误与截断

- **禁止**用 Go `error` 中断 ReAct 循环。失败返回 `(文本, nil)`，供模型自愈。
- 统一入口：`toolErr` / `truncateToolResult`；上限 `maxToolResult = 65536`，超长后缀 `...(truncated)`。
- `resolve` 失败同样返回 errText 字符串，不触达后端。

### 3.3 modelId 与 kind 路由

- `modelId` 缺省：`SessionModel(ctx)`（会话绑定）；再缺省：提示先 `create_project` 或在绑定会话里重试。
- `store.Get` 失败 / 后端未配：文本错误，不 panic。
- kind：`KindDXF` → `ToolDeps.CAD`（:8200），其余 → `IFC`（:8100）。
- 非法 id / 路径穿越：在 `resolve` 拦截，禁止落到 REST。

### 3.4 ctx 会话

- `Run` 启动前 `WithSessionID(ctx, sessionID)`。
- 工具只经 `SessionIDFromContext` 取会话，禁止自己解析 HTTP。
- `sessionID` 必须匹配 `^[A-Za-z0-9_-]+$`（EventStore 文件名）。

### 3.5 dirty

- 变更类成功（stage/run/save）调 `MarkDirty`。
- **`create_project` 禁止 MarkDirty**：新模型 ≠ 会话绑定模型，置位会让 notify 错绑。

### 3.6 现有工具清单（领域 9 + filesystem 官方面）

领域（`DomainTools`）：`list_models` / `get_model_info` / `get_script` / `stage_script` / `run_script` / `save_script` / `get_versions` / `get_diff` / `create_project`。

**filesystem 官方面（D12/M2-0，经 `newFilesystemMiddleware` 注入，非 DomainTools）**：
- 读：`read_file` / `glob` / `grep` / `ls`——读 skill references 与工作区（`fsReadOnlyBackend` 透传）。
- 执行：`execute`——跑 skill 捆绑 CLI（`aiplan` / `aidxfv3` 白名单，`validateSkillCommand` 单点）。
- **禁止**：`write_file` / `edit_file`（官方 middleware Backend 非空即全挂，`fsReadOnlyBackend.Write/Edit` 拒绝——领域收敛：模型不持任意文件写；skill 产物由 CLI 经 execute 自身落盘）。
- 领域收敛红线不破：文件读 OK，文件写拒绝，命令执行白名单枚举。

run/save/diff 走 slow client（沙箱最长 60s）。stage 是全量替换暂存，不是定点改写。

## 4. 事件规范

### 4.1 类型（9+1 种，改名即破翻译层）

`turn/start` · `turn/end` · `step/start` · `assistant/chunk` · `assistant/message` · `tool/call` · `tool/result` · `error` · `subagent/status` · `question/ask`（HITL，2026-08-19 加法事件）

载荷约定：

| type | payload 要点 |
|---|---|
| turn/start | `{user}` |
| turn/end | `{message}` 或 `{error}` |
| step/start | `{kind: model\|tool, name}`（model 步骤 name = agent 名：主 `aiifc-main`，子经 `WithName(persona)` 覆盖；tool 步骤 name = 工具名） |
| assistant/chunk | `{content}` 或 `{reasoning}` |
| question/ask | `{interruptId, question, checkpointId}`（HITL：模型 StatefulInterrupt 提问；用户回答经 `/answer` → `Agent.Resume(ResumeParams{Targets:{interruptId: *AskUserInfo{UserAnswer}}})`） |
| assistant/message | `{content, tool_calls?}` |
| tool/call | `{id, name, arguments}` |
| tool/result | `{id, name, content}` 或 `{id, name, error}` |
| error | `{error, name?}` |
| subagent/status | `{subagentId, parentSessionId, persona, status, task}` |

### 4.2 Event 附加字段

- `SubagentID` / `ParentSessionID` 空 = 主会话（旧形状）。非空 = 子事件，翻译层打 `subagentId` 分流边栏。
- `Turn` 从 EventStore 已有 `turn/start` 且 `SubagentID==""` 恢复；子事件不打扰父计数。

### 4.3 EventStore

- 路径：`{DataDir}/chat/{sessionID}.jsonl`；首行 header，其后每行一个 Event。
- append-only，写盘同步完成。
- `ParentSessionID != "" && != sessionID` → 拒绝写入。
- Load 坏行跳过，不拖垮会话。
- 写盘失败：浮 `error` 事件，**不打断**循环。

### 4.4 Project 投影

- 折叠为 `{role, content, tool_calls, tool_call_id}`。
- **跳过 `SubagentID != ""`**（子内容经 dispatch 结果回流，再注入会重复）。
- **会话连续性（2026-08-19 接线）**：`Run` 每轮从 EventStore Load 历史，经
  `BuildHistoryMessages`（检查阀门：未超 `maxContextChars*60%` 全量喂，超预算语义压缩——
  每轮只留用户指令 + 最终无工具回复，从新到旧填充）拼历史 + 当前消息喂给模型。
  默认 `maxContextChars=1_000_000`（`WithMaxContextChars` 可配，按部署模型窗口调）。

### 4.5 Run 生命周期

- `Run` 返回 `<-chan Event`（缓冲 256），结束即关闭。调用方必须排空。
- 唯一发送路径：落盘 + 扇出（`sendRaw`）。
- 事件顺序由 `adkTranslator`（events.go §4）同步翻译保证：模型流帧先 chunk 后合流
  assistant/message → tool/call，工具完成后 step/start(tool) → tool/result。
  **注意**：dispatch 子 agent 期间，父工具的 step/start 由 ADK event sender 在工具
  完成后发出（晚于子事件上浮）——与旧 react 的「执行前发」不同，前端可接受（v1）。
- 取消：ctx cancel；ADK 迭代器以 canceled 错误收尾，翻译层只发 turn/end，不刷 error。
- 超步：ADK `ErrExceedMaxIterations` → 翻译层错误文本化（含 step 措辞）+ turn/end。
- 工具 Go error：safeToolMiddleware 转 `[tool error] ...` 文本，翻译层恢复 error 载荷
  （单卡错误态，模型可自愈）；interrupt 类错误透传。
- MaxStep 默认 20（映射 ADK `MaxIterations`）。

## 5. Subagent 规范（路线 B：官方 AgentAsTool，2026-08-19 迁移完成）

### 5.1 深度预算 1（结构性）

- 子 agent（ifc-agent / cad-agent）= 独立 `ChatModelAgent`，工具面 = 领域工具（当前
  全量 DomainTools，A2 按角色分离留后续），**绝不含 AgentAsTool**——孙代派发结构性不可能。
- orchestrator 工具面 = DomainTools + AgentAsTool(ifc/cad)。
- 禁止用运行时计数「模拟」深度限制。

### 5.2 派发

- 子 agent 在 `agent.New` 装配期创建（`newRoleAgent`），非每次派发创建。
- 子模型 = `WithChildModelFactory` 工厂独立实例（scriptedModel 有 pos 游标，主/子必须独立）。
- 入参：AgentAsTool 默认 `{"request": "..."}`（自包含任务描述，与旧 dispatch 的 task 同语义）。
- 子 agent 工具经 `SessionIDFromContext` 继承父会话绑定（AgentAsTool 传父 ctx，已验证）。
- 同步等待子完成；AgentAsTool 工具结果 = 子 agent 最终答复。

### 5.3 事件上浮（翻译层合成，见 events.go §4）

- `subagentId` 格式：`sa_{父turn}_{seq}`（seq 由 adkTranslator 维护，单 goroutine 顺序消费）。
- 父子判定 = `event.RunPath` 深度 ≥2（官方 EmitInternalEvents 透传）。
- 子事件打 `SubagentID`/`ParentSessionID` 后走同一 sendRaw（同一通道、同一 JSONL）。
- `subagent/status` 官方无此事件——翻译层在子边界合成：首个子事件 → started（persona=子 agent
  名、task=父 tool_call arguments），RunPath 回父 → finished。
- 生命周期：started 先于子事件、finished 后于子事件、先于父 AgentAsTool 的 tool/result。

### 5.4 Persona

- 主：`OrchestratorPersona`（意图路由 + 派发纪律 + 破坏性大改先文字确认；**路由纪律：CAD 必须先 aiplan 再派 cad-agent，IFC 直接派 ifc-agent（独立线），问答直接答**，D11）。
- 子：`ifcAgentPersona` / `cadAgentPersona`（技能来源一句话 + 三段式 + 报告格式）。
- **角色 skill 映射（第一层，`filteredSkillBackend` 过滤）**：orchestrator→aiplan（协调层内联）、
  ifc-agent→aiifc、cad-agent→aidxf——模型工具面只出现本角色允许的 skill，跨角色调用被拒（文本错误）。
- 装配 `WithSkillsDir` 时，官方 skill middleware 把 progressive disclosure 系统提示词
  追加在 persona 之后、并把 `skill` 工具注入模型工具面。

### 5.5 隔离边界

- 会话与会话：隔离（独立 JSONL、独立 sessionID）。
- 父子：不隔离会话 id（设计使然）。隔离的是工具面（子无 AgentAsTool）和模型上下文
  （Project 跳子事件；官方 EmitInternalEvents 子事件也不写父 runSession）。

## 6. 模型规范

- `NewChatModel`：APIKey 空返回 `(nil, nil)`，由 `New` 回退 `defaultScriptedModel`。
- `scriptedModel`：按 `Script.Steps` 逐步吐出；同脚本两跑事件序列必须全等。
- 离线/测试禁止依赖真 LLM。

## 7. 装配顺序（chat_tools.go）

1. 先 `NewChatHandler`（工具 deps 需要会话表回调）。
2. 再 `agent.New(..., WithTools(DomainTools), WithStore, WithChildModelFactory?, ...)`——
   AgentAsTool(ifc/cad) 在 `agent.New` 内部装配。
3. 最后 `SetAgent` 回填破环。
4. 子 agent 工具面 = orchestrator 的领域工具（当前共享全量）。

## 8. 翻译层对接（本包不实现，但本包不得破坏）

`internal/api/chat_translate.go` 消费本包 Event。改事件 type/载荷/SubagentID 语义必须同步翻译层测试。

确定性 id（翻译层，供对照）：`msg_{turn}_{step}`、`part_{turn}_{step}_text`、子 part `sp_{subagentId}_...`。

SSE 帧形状（opencode 兼容）不在本包，但本包事件是其唯一来源。

## 9. 测试纪律（本包）

- 新代码测试量 ≥ 实现量；TDD。
- scriptedModel：同脚本两跑事件序列全等（ADK 下已兼容）。
- 异步 JSONL：条件等待，禁止固定 sleep。
- 工具：正常路径 + 错误文本化 + 64KB 截断 + kind 路由 + modelId 守卫。
- subagent：标签 / parentSessionId / 深度预算（子工具面无 dispatch）/ 空 task 文本错误。
- skill：`WithSkillsDir` 挂载后模型工具面出现 `skill` 工具、调用返回 SKILL.md 正文；
  不挂载则无该工具（离线/测试路径不受影响）。

## 10. 明确未做（重写文档时不要写成「已有」）

- **skill 加载已用官方 middleware 接入**（`WithSkillsDir` + 官方 `skill.NewTyped`，
  模型自动获得 skill 工具 + progressive disclosure 提示词）。未做：read references /
  文件工具（模型只有 skill 工具，不能直接读 skill 包内文件——后续经 PyExecutor 或
  官方 filesystem middleware 补）。
- `locate` / `edit-call` 工具。
- **HITL 已接线（2026-08-19）**：`ask_user` 工具（官方 StatefulInterrupt 对齐）+ CheckPointStore（in-memory）+ `Agent.Resume` + 翻译层 `question/ask` 帧。未做：SSE 侧 `question.ask` 翻译与 `/answer` 端点（chat 层，下一步）。
- **跨 turn 历史已接线（2026-08-19）**：`BuildHistoryMessages` 检查阀门（≤60% 全量喂 / 超预算语义压缩）。
- EventStore 轮转/压缩。
- 深度 > 1。
- python/bash 执行。

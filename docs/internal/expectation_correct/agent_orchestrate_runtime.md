# Agent 编排：skill 资产层 + 平台运行时层

> 从 agent_orchestrate.md 拆分（历史演进文档，2026-08-20 拆分为多文件满足 ≤500 行门控）。skill 资产层（agent 大脑）+ Eino 进程内 agent 运行时。

## 二、skill 资产层：agent 的「大脑」（你负责的部分）

### 1.1 资产地图

| 包 | 阶段 | 输入 | 输出 | 机器命令 |
|---|---|---|---|---|
| `skills/aiplan/` | plan（管线入口） | 外部资料（图片/PPT/文档/对话） | `plan.json` + `bim_supplement.json` | `aiplan land/validate/gate` |
| `skills/aidxfv/v3/` | cad（管线中段，正式版基线） | `plan.json`（只读）+ 用户补充 | `building.json` + 各层 `floor.dxf` | `aidxfv3 preprocess/skeleton/rooms/details/deliver/normalize/state` |
| `skills/aiifc/` | bim（下游消费） | plan/building 派生参数 + 用户需求 | 构建脚本 `scripts/v{n}.py` + IFC | 无（agent 直接写 `ifcopenshell.api` 代码） |
| `skills/aibim-orchestrator/` | 编排提示词包 | 设计师对话 | 派发决策 + 汇总报告 | 无（纯提示词 + 数据契约） |

探索动作：`ls skills/aiifc/ skills/aiplan/ skills/aidxfv/v3/ skills/aibim-orchestrator/`，每个包先看 `SKILL.md` 前 20 行。

### 1.2 aibim-orchestrator 解剖（编排的「大脑」）

这是理解整个编排设计的入口。三件套：

**① SKILL.md —— 意图路由表 + 派发纪律**
- 意图路由：IFC 生成/修改 → ifc-agent；DXF 生成/修改 → cad-agent；设计规范/审查问答 → 直接回答不派发。
- 接力编排：**子 Agent 之间永不直接交互、互不知道对方存在**；一切产物位置（plan.json / building.json / DXF 目录 / 脚本 / IFC 版本路径）由主 Agent 维护清单，派发时显式传入「输入锚点」。
- 确认门禁只有两个：**DXF 确认、IFC 交付确认**（plan 确认只在可选 plan 范式时存在，由 cad 管线内部承载）。

**② references/SUBAGENTS.md —— 子 Agent 契约 + 派发提示词模板**
- ifc-agent：技能来源 `skills/aiifc`，script-as-source；输入 = 主 Agent 显式传入的产物路径；输出 = 构建脚本 + IFC + validate 结果；边界 = 只写脚本与派生物、不改 DXF、不与设计师对话。
- cad-agent：技能来源 `skills/aidxfv`；输出 = DXF + building.json；边界 = IFC 转换不归它。
- 报告格式统一：`{产物路径, 版本, validate 结果, 遗留问题}`。
- 每类子 Agent 配一段可直接粘贴的「派发提示词模板」。

**③ references/RELAY_CONTRACT.md —— 接力手册（锚点 + 门禁）**
- 锚点 1：plan.json（可选范式，`draft/confirmed` 状态机由 cad 管线内部流转）。
- 锚点 2：DXF + building.json（`elevation_mm` 累加规则、DXF 过 `canonicalize_dxf` 后算 sha256、DXF 承载不了的信息必须写进 building.json 不许口头传递）。
- 锚点 3：IFC（**脚本是唯一事实源**，IFC 是派生物从不直改；PARAMS 从 plan/building 派生；GlobalId 由 `script_lib.deterministic_guid(key)` 派生 + `Pset_AIIFC.designKey` 追溯）。
- 反例约定：缺硬约束字段的 plan.json 应被拒收停步，主 Agent 原样转述字段清单，不得自行编造默认值。

### 1.3 关键设计决策（skill 侧想清楚的四件事）

1. **LLM 声明 × 机器锚定**：LLM 只声明 skeleton.json/rooms.json（哪里/多大/邻着谁），**坐标交给机器**（`aidxfv3 normalize` 是唯一坐标计算点）；派生/锚定/校验/渲染/检索全机器——这就是「怎么把工作尽量封装在固定代码、减轻模型负担」的现状答案。
2. **信息传递上移主 Agent**：子 Agent 只认主 Agent 显式给出的路径，杜绝自行发现产物位置——防止多 agent 协作时上下文漂移。
3. **确认门禁只有两个**：避免每个环节都问用户造成对话疲劳；plan 确认下沉到管线内部状态机（`confirmed: true` 是落盘形式）。
4. **question 工具是断点确认的实现手段**：aiplan 四轮渐进（骨架→几何→功能→结构空间）、aidxfv3 S0-S4 断点都靠它——⚠️ 这是 opencode 形态的能力，平台侧没接（见 Q3-1 卡）。

---

## 三、平台运行时层：Eino 进程内 agent（另一位开发者的部分，你要能读懂）

### 2.1 文件地图（server/internal/agent/）

| 文件 | 职责 |
|---|---|
| `agent.go` | `react.NewAgent` 装配 + `Run()` 事件流扇出（callbacks 观测模型/工具每一步） |
| `events.go` | Event 类型 + 9 种事件常量 + `EventStore`（append-only JSONL）+ `Project`（投影为 openai 消息列表） |
| `tools.go` | 9 个领域工具（InferTool 静态 schema）+ kind 路由 + 64KB 截断 |
| `subagent.go` | 主/子 persona 常量 + `subagentHub` + `runChild` + 派发工具 |
| `model.go` | `NewChatModel`（APIKey 空返回 nil → 回退 scriptedModel） |
| `scripted.go` | 确定性 mock 模型（`Script.Steps` 逐步消费，同脚本两跑事件序列全等） |

### 2.2 一次 turn 的生命周期（agent.go:111 Run）

```
POST /messages
  → postMessage（chat_eino.go:32）：拼系统上下文 → Ag.Run(ctx, agentSessionId, text)
  → Run 内：
      turn 号从 EventStore 已有 EventTurnStart 恢复（子事件不打扰计数）
      ctx 注入 sessionID（工具经 SessionIDFromContext 解析绑定模型）
      注册 subagentHub（ctx）——子 run 事件经它打标上浮
      goroutine：emit turn/start → react.Stream（persona 注入 + callbacks）
        callbacks 观测（runEmitter.handler）：
          onStart(model/tool)     → step/start
          onEndStream(model)      → 消费流式输出：正文/思考分片逐片发 assistant/chunk
                                    EOF 后 ConcatMessages 合流 → assistant/message + tool/call
          onEnd/onError(tool)     → tool/result（成功 content / 失败 error 载荷，单卡错误态）
        MaxStep=20 截断；onError 去重（不重复刷 session 级 error）
      → emit turn/end {message} → finishRun（closed 置位 → 等合流 goroutine → 关通道）
  → consumeRun（chat_eino.go:84）：翻译层逐事件转 SSE 帧推送
  → 流关闭后 notifyIfDirty（chat_orchestrator.go:100）
```

**事件类型表**（events.go:18-28，这是平台内部契约，翻译层消费它）：

| 常量 | 载荷要点 | 谁产生 |
|---|---|---|
| `turn/start` | `{user}` | Run 启动 |
| `turn/end` | `{message}` 或 `{error}` | Run 收尾（abort 也发） |
| `step/start` | `{kind: model\|tool, name}` | callbacks onStart |
| `assistant/chunk` | `{content}` 或 `{reasoning}`（逐分片） | onEndStream 消费 goroutine |
| `assistant/message` | `{content, tool_calls:[{id,name,arguments}]}` | 模型输出合流 |
| `tool/call` | `{id, name, arguments}` | 模型输出的工具调用声明 |
| `tool/result` | `{id, name, content}` 或 `{id, name, error}` | 工具执行结束/失败 |
| `error` | `{error, name?}` | 组件 onError（取消不产） |
| `subagent/status` | `{subagentId, parentSessionId, persona, status, task}` | 子 run 开始/结束 |

**确定性设计**：模型流式输出由消费 goroutine 合流，graph 线程在下一组件 onStart 前 `waitPrevModel()`（agent.go:284）——保证 `assistant/message + tool/call` 永远先于下一步的 `step/start` 落序列；测试（scriptedModel）靠它两跑全等。

### 2.3 领域工具面（tools.go，9 个，agent 的全部「手」）

> 无 bash、无任意文件写——全部变更经 edit-service REST，按模型 kind 路由（resolve 归一 modelId 缺省取会话绑定模型）。错误一律**文本化返回**（不抛 Go error 中断循环），供 LLM 观测自愈；结果 64KB 截断防爆上下文。

| 工具 | 参数（jsonschema 即模型可见说明） | 行为 | 后端调用 |
|---|---|---|---|
| `list_models` | 无 | 列全部模型 | store.List |
| `get_model_info` | `modelId?` | 单模型信息 | store.Get |
| `get_script` | `modelId?` | 读当前脚本（暂存优先，否则最近大版本） | GET /models/{id}/script |
| `stage_script` | `script`（必填）, `note?`, `modelId?` | 暂存全量替换；**成功后 markDirty** | PUT /models/{id}/script |
| `run_script` | `modelId?` | 沙箱执行暂存脚本（重写工作区文件，不落版本）；**markDirty** | POST /models/{id}/script/run（slow） |
| `save_script` | `note?`, `modelId?` | 沙箱执行并落大版本（原子）；**markDirty** | POST /models/{id}/script/save（slow） |
| `get_versions` | `modelId?` | 版本列表 | GET /models/{id}/scripts |
| `get_diff` | `base`, `target`, `modelId?` | 脚本 diff + PARAMS 变化 + 统计 | POST /models/{id}/script/diff（slow） |
| `create_project` | `title`（必填） | 骨架 IFC + 注册 + 入队转换；**不 markDirty**（新模型≠绑定模型，防 notify 错绑） | 平台内骨架生成 |

工具执行注意：`run/save/diff` 走 slow client（沙箱最长 60s），fast 10s 会三方状态分叉（tools.go:154 注释）。

### 2.4 subagent-as-tool 封装（subagent.go，重点中的重点）

**① persona 从哪来**：不是从 skill 文件读取，而是**内嵌代码常量**——`aibim-orchestrator` 的 SKILL.md/SUBAGENTS.md 要点被人工提炼成三段常量（subagent.go:26-56）：

```
OrchestratorPersona（主 agent）：设计师对话入口与编排者，不直接建模/画图
  - 意图路由三行（IFC→dispatch_ifc_agent；DXF→dispatch_cad_agent；问答→直接回答）
  - 派发纪律：task 必须自包含（子 agent 不见本会话历史——需求要点、
    显式输入锚点、期望产物都写进 task）；一次一派发；报告即事实；
    破坏性大改前先用文字向设计师确认

ifcAgentPersona（子）：你是 IFC 建模子 Agent（技能来源：aiifc skill，script-as-source）
  - 先 get_script 读当前脚本增量修改，禁止整体重写；保持 PARAMS key 稳定
  - 三段式：stage_script → run_script（沙箱验证）→ save_script（落大版本）
  - 不改任何 DXF；不与设计师对话；不与其他子 Agent 交互；只使用主 Agent 显式给出的输入锚点
  - 报告格式：{产物路径, 版本, validate 结果, 遗留问题}

cadAgentPersona（子）：你是 CAD 绘图子 Agent（技能来源：aidxfv skill）——同上结构
```

**② 派发工具**（subagent.go:156-175）：`dispatch_ifc_agent` / `dispatch_cad_agent`，参数只有 `task`（`dispatchReq`，schema 注明「自包含任务描述，含输入锚点；子 agent 不见本会话历史」）。校验：无父会话 ctx 或空 task → 文本错误（不中断主循环）。

**③ runChild 机制**（subagent.go:94-139）：

```
主 Run 启动时创建 subagentHub{emit: 父事件发送路径, parent: 父会话id, turn: 父turn号, ctx}
派发工具被调用 → h.runChild(ctx, persona, task, cfg)
  1. 分配唯一 subagentId：sa_{父turn}_{递增seq}
  2. 发 subagent/status {started}（前端据此建边栏分组）
  3. child := New(WithModel(cfg.NewModel()), WithTools(cfg.MakeTools(persona)),
                 WithPersona(personaPersona(persona)), WithMaxStep(cfg.MaxStep))
     —— 每次派发新建模型 + 新建工具面，并行派发互不共享位置
  4. child.Run(ctx, 父会话id, task)   ← 复用父会话 id！
     —— 子工具的 kind 路由/会话绑定模型经 ctx 继承父会话（SessionIDFromContext 解析）
  5. 子事件循环：每条事件打 SubagentID/ParentSessionID 标签 → 原样走父 sendRaw
     （同一通道、同一落盘、同一 closed 守卫）
  6. 收尾：发 subagent/status {finished}；返回子 turn/end 的 message（即报告）
```

**④ 深度预算 1 怎么保证**（结构性而非运行时检查）：子工具面由 `SubagentConfig.MakeTools` 提供，主 Agent 装配时传的是 `h.DomainTools()`（chat_tools.go:110）——**只有领域工具，绝不含派发工具**，所以孙代派发「结构性不可能」（subagent.go:6 注释原文）。子 agent 的 MaxStep 同主 agent（20）。

**⑤ 事件去向**：子事件打标后与父事件同一 EventStore JSONL（`{DataDir}/chat/{sessionID}.jsonl`）落盘；但 `Project()` 投影重建模型上下文时**跳过子事件**（events.go:149——子内容经 dispatch 工具结果回流父模型，直接注入会重复计数）；前端历史回填同样跳过子事件（子内容靠右侧边栏分组承载）。

**⑥ 与 skill 侧 SUBAGENTS.md 的关系**：平台 persona 是 SUBAGENTS.md 的**要点提炼**（只保留纪律，不复制技能细节）；技能细节（aiifc MUST 条款、aidxfv3 机器命令）子 agent 不会自动加载——当前派发 task 里没指示加载 skill，这属于 Q3-3/Q3-4 的待对齐点（skill 侧模板是「加载 aiifc skill 并遵守其 MUST 条款」，平台 persona 只说「技能来源：aiifc skill」）。

### 2.5 装配顺序（main.go 侧，读懂依赖怎么注入）

1. `NewChatHandler(ChatDeps{...})` 先建 handler（领域工具 deps 需要会话表回调：`sessionBoundModel` / `markSessionDirty` / `createProjectForAgent`，见 chat_tools.go:75-89）。
2. `agent.New(LLMConfig, WithTools(SubagentAgentTools(llm, nil)), WithStore(ev))` 建主 agent——`SubagentAgentTools` = DomainTools + SubagentTools（chat_tools.go:97-114）。
3. `handler.SetAgent(ag)` 回填引用破环（chat_tools.go:118）。

LLM 配置：`VIEWER_LLM_API_KEY / VIEWER_LLM_BASE_URL / VIEWER_LLM_MODEL`；APIKey 为空 → `NewChatModel` 返回 nil → `agent.New` 回退 `defaultScriptedModel`（固定一句「未配置 LLM API Key」答复，不调工具）——离线 demo 与测试都跑这条路径。

### 2.6 会话与历史（chat_session.go + events.go）

- 两个 id：`chatSessionId`（`c_`+16hex，前端路由用）↔ `agentSessionId`（`s_`+16hex，EventStore 文件名），JSON 字段名保留 `opencodeSessionId`（web client 契约不动）。
- 映射表 `{DataDir}/chat-sessions.json`（原子写 tmp+rename）；重启恢复时同 modelId 只保留最早一条（幂等：同一模型只会有一个会话）。
- 每会话 EventStore：首行 header，其后每行一个 Event；坏行跳过（LoadReport 返回 skipped 数）。
- 历史回填：`GET /messages` → `projectChatHistory`（chat_translate.go:338）把事件折叠成 ChatSidebar 消费的 `{info, parts}` 形状——与实时流**共用同一套 id 约定**，前端按 id 去重合并（防 SSE 先到/历史后到竞态）。

---

---
intent: 由于这个项目是我和另一个开发者合作开发的，所以在开发的原则和想法上可能存在一些差异，这边特别对agent设计这一块进行探讨。本文升级为「一个下午的深度探索指南」：以可运行代码为事实源，细化到 subagent 怎么封装、网页对齐接口具体是哪些的程度，探索完能对这个项目建立直观印象。
---

# Agent 编排深度探索指南（skill 设计者 × 平台侧 × 网页对齐全景）

> ⚠️ **当前状态（2026-08-19）：已裁决迁移 ADK。**
> D1 翻转：官方 skill 接入（skill middleware）只存在于 ADK，经典侧手搓薄壳「复原拼接」效果无保证。
> **本文是历史演进记录**——大量「经典 flow/react 侧」描述是讨论当时的现状，已不构成目标设计。
> **开工看**：`agent_deployment_plan.md`（ADK 迁移主路径，M0-M4）+ `server/internal/agent/FLOW.md`（ADK 目标框架）+ `server/internal/agent/skill_adk_readme.md`（skill 源码导读）+ `server/internal/agent/hitl_adk_readme.md`（HITL 源码导读）。
> **硬标准**：`server/internal/agent/api_regulation.md`（不可破坏的结构契约）。

> 三层视角：**skill 资产层**（agent 无关的提示词/脚本包，你负责）→ **平台运行时层**（Go Eino 进程内 agent，另一位开发者负责）→ **网页对齐层**（SSE/REST 接口，双方都要懂）。每一节都标了「读哪、跑什么」的探索路径。
> 主事实源：`docs/site/reference/ai-skill.md` · `docs/site/reference/ai.md` · 编排设计演进 `docs/superpowers/specs/2026-08-11-orchestrator-design.md`（代码级 orchestrator 已退役，落地为提示词包）。本文与公开站冲突处，以公开站为准。

---

## 〇、全景速览（10 分钟建立印象）

```
浏览器 ChatSidebar（React, web/src/viewer/ChatSidebar.tsx）
   │  EventSource SSE 订阅            │ POST /chat/sessions/{cid}/messages
   ▼                                 ▼
Go server :8090 ── chat 模块（server/internal/api/chat*.go）
   │  ChatHandler：会话表/SSE 订阅/重同步缓冲/notify 触发
   ├──► agent.Agent（server/internal/agent/agent.go）
   │       Eino react.NewAgent 循环：persona + 工具面 + EventStore
   │       工具面 = 9 个领域工具（tools.go）+ 2 个派发工具（subagent.go）
   │       └── dispatch_ifc_agent / dispatch_cad_agent
   │             └──► 子 agent = 独立 run + persona + 深度预算 1
   ├──► 领域工具经 editsvc.Client REST 代理 ──► services/ifc :8100（IFC kind）
   │                                            services/cad :8200（DXF kind）
   ├──► notify 落盘闭环（chat_core.go planNotify + chat_shell.go execAction）
   │       丢弃 pending → 暂存 → 沙箱 run → save 大版本 → 归档 → 重转 → viewer.committed
   └──► converter（Node 子进程，IFC→XKT）← convert.Queue

skill 资产（agent 无关目录包，任何支持 Agent Skills 的 agent 可加载）：
   skills/aiplan（plan.json + bim_supplement.json）
   skills/aidxfv/v3（building.json + 各层 DXF，机器命令族 aidxfv3）
   skills/aiifc（构建脚本 script-as-source）
   skills/aibim-orchestrator（主 Agent 编排提示词包：意图路由 + 子 Agent 契约）
```

**分层心智模型**：

| 层 | 存在形式 | 谁写 | 关键文件 |
|---|---|---|---|
| skill 资产层 | 提示词 + 脚本 + schema（agent 无关） | skill 设计者（你） | `skills/*/SKILL.md`、`references/` |
| 平台运行时层 | Go 代码（Eino agent loop） | 平台开发者 | `server/internal/agent/*.go` |
| 网页对齐层 | SSE 帧 + REST envelope + 前端渲染 | 平台开发者 + 前端 | `server/internal/api/chat_*.go`、`web/src/viewer/ChatSidebar.tsx` |

**两个关键事实（先记住，后面都是它们的展开）**：
1. **skill 不加载进平台**——skill 是给「会自己跑命令的 agent 环境」用的；平台 agent 的工具面是固定的 9+2 个 Go 函数，skill 内容只以 **persona 提示词文本**形态内嵌在代码常量里（subagent.go:26-56）。
2. **SSE 契约保持 opencode 形状**——翻译层把 agent 内部事件翻译成浏览器熟悉的 `message.updated / part.delta / session.idle` 等帧，前端 ChatSidebar 零改动（W-0043 契约红线）。

---

## 一、参考资料库：Eino 源码与官方例子怎么用

> 两个本地资源已就位，本文后续所有「探索动作」都指向它们：
> - **Eino 源码**（版本与项目完全一致 **v0.9.13**）：`~/go/pkg/mod/github.com/cloudwego/eino@v0.9.13/`——Go module cache，**只读**，只用来读/搜索，不要改。
> - **官方 examples**（git 仓库，可改可跑）：`/home/cyvol0521/.code/gaiahub/CADapi/eino-examples/`（`research/eino-examples/` 为同内容副本）。根 go.mod 锁 eino v0.9.12，与项目 v0.9.13 同族（API 兼容）。

### 1.1 最重要的认知：项目用「经典 flow/agent/react」，examples 大量用「新一代 ADK」

| | 经典 flow API（**项目现状**） | 新一代 ADK（examples 主力） |
|---|---|---|
| agent 循环入口 | `flow/agent/react`（agent.go:89 `react.NewAgent`） | `adk/` 包（Runner / Agent / AgentTool / interrupt…） |
| HITL 断点（Q3-1 主题） | 无 | ✅ `adk.Interrupt()` / `Runner.ResumeWithParams`（interrupt.go） |
| AgentAsTool（子 agent 封装，Q3 参考） | 无（项目**自研** subagentHub，subagent.go:73） | ✅ `adk.NewAgentTool`（agent_tool.go:93） |
| skill 加载中间件（Q3-4 主题） | 无（persona 内嵌常量） | ✅ `adk/middlewares/skill`（filesystem backend） |

两者**同版本共存**（都在 v0.9.13 包里）但 API 不互通。这是 Q3-1/Q3-4 候选方案评估的关键背景：**HITL 与 skill 加载能力是现成的，但都在 ADK 侧**——接线的真实成本 = 迁移/桥接 ADK 的评估成本，不是「从零实现」。

### 1.2 源码导航（按探讨主题，v0.9.13 包内）

| 主题 | 源码位置 | 要点 |
|---|---|---|
| ReAct 循环（项目正用的） | `flow/agent/react/react.go` | `AgentConfig{ToolCallingModel, ToolsConfig, MessageModifier, MaxStep}`——agent.go:89 的装配就是它 |
| HITL 中断/恢复（Q3-1） | `adk/interrupt.go` | `Interrupt(ctx, info)` 从工具内触发；`Runner.ResumeWithParams` 恢复；中断上下文带 ID / Info / State |
| **DeepAgent 预构建**（「复杂能力」官方答案） | `adk/prebuilt/deep/` | 配置即挂载全家桶：`Backend`→文件工具组（read/write/edit_file/glob/grep）、`Shell`/`StreamingShell`→**execute 命令执行工具**、`write_todos`、TaskTool 子 agent 委派 + general-purpose 子 agent；默认 coding-agent 系统提示词 |
| **「skill 完全接入」官方堆栈**（Q3-4 关键参照） | ch09 接线（`quickstart/chatwitheino/cmd/ch09/main.go:125-175`） | `local` backend（`eino-ext/adk/backend/local`，一个对象同时实现 filesystem.Backend + StreamingShell 两接口）+ skill middleware + DeepAgent——**读文档（skill 工具 + 文件工具组）+ 跑 scripts（execute）双能力官方成套**；官方 prompt 原文即含 "Executing Skill Scripts…use absolute paths" |
| **Python 执行器**（经典 flow 可直接挂） | eino-ext `components/tool/commandline/pyexecutor.go` | `python_execute` 工具（执行 Python 代码串，print 输出可见），带 Operator/sandbox 抽象——普通 `tool.BaseTool`，不迁 ADK 也能用 |
| AgentAsTool（Q3-3 对照） | `adk/agent_tool.go` | 把 agent 包成 tool（子 agent 独立上下文、可并行、事件透传）——项目 subagentHub 的官方对应物 |
| skill 中间件（Q3-4 蓝本） | `adk/middlewares/skill/`（skill.go + filesystem_backend.go） | `NewBackendFromFilesystem` + `NewMiddleware`——**ADK 原生支持从文件系统目录加载 skill**，与咱们「skill = 目录包」的形态天然契合 |
| 取消/中止 | `adk/cancel.go` | 项目现状：ctx cancel + 深度预算 1（自研） |
| 事件流 | `adk/runner.go` | AgentEvent 流；项目现状：自研 callbacks → 事件 → 翻译层（chat_translate.go） |

### 1.3 官方例子导航（按探讨主题）

| 主题 | 例子 | 与本项目探讨的关系 |
|---|---|---|
| **HITL 批准门禁**（Q3-1 方案 A 蓝本） | `adk/human-in-the-loop/1_approval/` | 工具内 `Interrupt` → 拿 `InterruptContexts[0]` → 人批准/拒绝（`ApprovalResult`）→ `ResumeWithParams` 恢复——「question 工具化」的官方实现形态 |
| **HITL 反馈循环**（Q3-1 变体） | `adk/human-in-the-loop/3_feedback-loop/` | 中断携带 `FeedbackInfo`，恢复时注入人的反馈——aidxfv3 S0-S4 断点「用户补充需求」的形态 |
| HITL 全景（其余 6 例） | `adk/human-in-the-loop/2_review-and-edit` · `4_follow-up` · `5_supervisor` · `6_plan-execute-replan` · `7_deep-agents` · `8_supervisor-plan-execute` | 按需翻；5/6/8 是 supervisor 模式（官方 FAQ 明确不推荐全上下文共享，见 spec §3.2 结论） |
| 多 agent 协作（Q3-3 对照） | `adk/multiagent/deep/` · `adk/multiagent/plan-execute-replan/` | AgentAsTool 派生的 deep 模式（独立上下文委派）；`deep/` 即 DeepAgent 预设的完整例子（文件工具 + shell + 子 agent） |
| **skill 加载**（Q3-4 蓝本，必跑） | `adk/middlewares/skill/main.go` | filesystem skill backend + middleware 挂进 agent——我们的 aiifc/aidxfv 包目录形态可直接对照 |
| **skill 加载完整教程**（Q3-4，官方文档+代码） | `quickstart/chatwitheino/cmd/ch09` + [官方文档第九章](https://www.cloudwego.io/zh/docs/eino/quick_start/chapter_09_skill_console/) | skill middleware 完整用法：目录扫描约定 `<dir>/<name>/SKILL.md` → NewBackendFromFilesystem → 注册 Handlers → `skill` 工具按需加载（入参 `{"skill":"<name>"}`）；官方定位：**Tool=「能做什么」，Skill=「怎么做」**；eino-ext 官方自维护四个 skills 即此模式 |
| **Graph Tool**（确定性流水线 tool 化，知识储备） | `quickstart/chatwitheino/cmd/ch08` + [官方文档第八章](https://www.cloudwego.io/zh/docs/eino/quick_start/chapter_08_graph_tool/) | compose Workflow（BatchNode 并行/FieldMapping/interrupt+checkpoint）→ `graphtool.NewInvokableGraphTool` 封装为 tool。对咱们的意义：思路同 A1 白名单端点（流水线打包），载体不同；compose 原生支持断点（理论上可承载 S0-S4），但 Go 侧重写管线与 flowops 单源裁决冲突——**只作知识储备不推荐** |
| **SSE 服务化**（网页对齐参考） | `adk/intro/http-sse-service/` | ADK Runner 事件流 → HTTP SSE 的标准做法；对照项目自研翻译层的差异 |
| 完整 agent 应用 | `adk/agent/ralph-loop/` | 一个自包含 agent 应用长什么样 |
| 经典 flow 多 agent | `flow/agent/multiagent/` | 旧 API 下的多 agent（评估迁移成本用） |

### 1.4 怎么跑例子

```bash
cd /home/cyvol0521/.code/gaiahub/CADapi/eino-examples

# Q3-1 必跑：HITL 批准门禁、反馈循环
go run ./adk/human-in-the-loop/1_approval
go run ./adk/human-in-the-loop/3_feedback-loop

# Q3-4 必跑：skill 加载中间件
go run ./adk/middlewares/skill

# 网页对齐参考：ADK Runner 事件流 → SSE
go run ./adk/intro/http-sse-service
```

- LLM 配置走环境变量（`adk/common/model/chat_model.go`）：`MODEL_TYPE=openai|ark`，`OPENAI_API_KEY/OPENAI_MODEL/OPENAI_BASE_URL` 或 `ARK_API_KEY/ARK_MODEL/ARK_BASE_URL`。**咱们自己的三参可直接复用**：
  ```bash
  MODEL_TYPE=openai OPENAI_API_KEY=$VIEWER_LLM_API_KEY \
    OPENAI_BASE_URL=$VIEWER_LLM_BASE_URL OPENAI_MODEL=$VIEWER_LLM_MODEL \
    go run ./adk/human-in-the-loop/1_approval
  ```
- 首次 `go run` 自动按根 go.mod 下载依赖（v0.9.12 同族）；改例子代码随意，不影响主仓。
- ⚠️ module cache（`~/go/pkg/mod/...eino@v0.9.13/`）只读，源码搜索用 `grep -rn` / 编辑器跳转，别落改动。

### 1.5 与 Q 卡的挂钩（探索时对照填证据）

- **Q3-1（question 承载形态）**：跑 `1_approval` / `3_feedback-loop` 填「证据」——确认 ADK interrupt/resume 形态与项目翻译层（chat_translate.go）桥接的复杂度；候选 C 的调研路径 = `adk/interrupt.go` + 这两个例子。
- **Q3-3（dispatch 衔接）**：对照 `adk/agent_tool.go`（AgentAsTool 内联事件透传）评估项目自研 subagentHub（subagent.go:73）的差距。
- **Q3-4（skill 加载）**：跑 `adk/middlewares/skill`，对照 `NewBackendFromFilesystem` 评估「平台子 agent 读 skill 文件」的候选 B 可行性。

---

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

## 四、网页对齐层：接口全景（双方都要懂的契约）

### 3.1 REST 路由（chat.go:79-87，全部走 `/api/v1` 前缀，envelope `{code,message,data}`）

| 方法 | 路径 | 功能 | 响应 |
|---|---|---|---|
| POST | `/api/v1/chat/sessions` | 创建会话（幂等：同 modelId 只一个） | `{chatSessionId, opencodeSessionId, modelId, title, createdAt}` |
| GET | `/api/v1/chat/sessions` | 列会话 | 数组 |
| POST | `/api/v1/chat/sessions/{cid}/messages` | 发消息启动一轮 agent | `{"accepted": true}` |
| GET | `/api/v1/chat/sessions/{cid}/messages` | 历史回填（投影） | `[{info, parts}]` |
| GET | `/api/v1/chat/sessions/{cid}/events` | **SSE 事件流**（EventSource 直连） | text/event-stream |
| POST | `/api/v1/chat/sessions/{cid}/abort` | 中止当前 turn | `{"aborted": true}` |
| POST | `/api/v1/chat/projects` | 创建骨架项目（AI 对话从零建模入口） | 模型对象（含 modelId） |

注意：`/events` 带 `Last-Event-ID` 重连时补发 missed 帧；不带则行为与旧版一致（不补发）。鉴权开启时 `GET /chat/sessions/...` 只读端点白名单（auth.go:55）。

### 3.2 SSE 帧契约（翻译层 chat_translate.go，浏览器消费的逐事件清单）

> 传输层：每帧 `id: {会话内递增seq}\ndata: {json}\n\n`；seq 复用了 pushLocked（chat_sse.go:95），重同步缓冲 64 条环形。事件名 = opencode 形状（W-0043 契约红线：**前端零改动**）。

**主会话帧**（不带 subagentId 字段，旧形状不变）：

| event 名 | data 形状 | 触发时机 | ChatSidebar 行为（ChatSidebar.tsx） |
|---|---|---|---|
| `session.status` | `{status:{type:"busy"\|"idle"}}` | turn/start、turn/end | busy 置位/清除，禁用发送 |
| `message.updated` | `{info:{id,role,sessionID}}` | turn/start（user 消息）、每步 model step/start（assistant 消息行） | 记 role 到 rolesRef（用户输入已本地乐观插入，跳过渲染） |
| `message.part.updated` | `{part:{id,type:text\|reasoning\|tool,messageID,sessionID,text?,state?}}` | 首分片建行（text 空文本）、tool/call（running）、tool/result（completed/error） | text/reasoning 建行（增量交给 delta）；tool 建工具卡片（title/input/output/error 状态渲染） |
| `message.part.delta` | `{sessionID,messageID,partID,field:"text",delta}` | assistant/chunk 每个分片 | 按 partID 追加到 m.text（流式渲染） |
| `message.part.removed` | `{part:{id}}` | 消息重写/abort 收尾 | 删行防残留 |
| `session.idle` | `{}` | turn/end | busy 清除 |
| `session.error` | `{error}` | EventError | 红色系统消息 |
| `viewer.committed` | `{modelId,version,committed:true}` | notify 落盘成功 | ✅ 系统消息 + `flagPendingModelReload()`（轮询到 ready 重载画布） |
| `viewer.notify_failed` | `{modelId,step,reason}` | notify 任一步失败 | ⚠️ 系统消息 |

**子 agent 帧**（附加 `subagentId` 字段，前端据此分流右侧边栏，不进主消息流）：

| event 名 | data | 前端行为 |
|---|---|---|
| `subagent.status` | `{subagentId,parentSessionId,persona,status:"started"\|"finished",task}` | started 建分组（persona 徽章+task），finished 置完成 |
| `message.part.updated`（带 subagentId） | 同上 + subagentId；part.id 前缀 `sp_`（防与主会话碰撞） | 并入对应分组 |
| `message.part.delta`（带 subagentId） | 同上 + subagentId | 追加到分组 part 文本 |

**确定性 id 约定**（chat_translate.go:24-38，实时帧与历史投影共用，前端按 id 去重）：
- 用户消息 `msg_{turn}_user`、用户 part `part_{turn}_user`
- 助手消息 `msg_{turn}_{step}`、文本 part `part_{turn}_{step}_text`、思考 part `part_{turn}_{step}_reasoning`
- 工具 part `part_{turn}_{step}_tool_{callID}`（callID 空退化 `..._tool`）
- 子消息 `sub_{subagentId}_msg_{turn}_{step}`、子 part `sp_{subagentId}_{turn}_{step}_{kind}`

### 3.3 翻译层映射（agent 内部事件 → SSE 帧，chat_translate.go:91-191）

| agent 事件 | 产出的 SSE 帧 |
|---|---|
| `turn/start` | `session.status busy` + `message.updated`（user 行） |
| `step/start`（kind=model） | `message.updated`（assistant 行）；tool step 不产帧 |
| `assistant/chunk` | `message.part.updated`（首分片建行）+ `message.part.delta`（逐片） |
| `assistant/message` | 正文非空且未建行 → `message.part.updated`（text） |
| `tool/call` | `message.part.updated`（tool part, status:running）——工具卡片建行 |
| `tool/result` | 成功 → `message.part.updated`（completed+output）；失败 → `error` 载荷（status:error，前端 ✗ 态） |
| `error` | `session.error` |
| `turn/end` | `session.status idle` + `session.idle` |
| `subagent/status` | `subagent.status`；其余子事件走 translateChild（带 subagentId 的 part 帧） |

### 3.4 notify 落盘闭环（AI 改完模型后平台自动收尾，ChatSidebar 侧只看到两个系统事件）

```
turn/end → consumeRun 流关闭 → notifyIfDirty(cs)（chat_orchestrator.go:100）
  变更检测：cs.dirty（工具面 markDirty 精确信号）∨ uploads/{id}.ifc mtime > lastCheck（兜底）
  → notify(cs)（:150）：
      读 staging/{modelId}.py（有则注入 NotifyState.Script；读不出宁可中止也不丢变更）
      组装第一轮事件 aiifc://chat/{cid}/idle + NotifyState{Dirty,Bound,HasStagingScript,Script}
      → runShell（chat_shell.go:29）：循环 planNotify(Event+State)→Action 列表→逐条 execAction
```

**Core（chat_core.go planNotify，纯函数零 IO）** 的分支 → Action：

| 分支 | Action 序列 |
|---|---|
| idle + dirty + bound + 有脚本 | discard_pending → stage_script → run_script → save_script（saved 事件驱动第二轮） |
| 第二轮（saved 事件，version 已知） | archive_artifact（staging → `models/{id}/scripts/v{n}.py` 删源）→ reconvert（EnqueueIfStale）→ notify（viewer.committed） |
| idle + dirty + 无脚本 | discard_pending → reconvert → notify（空版本 viewer.committed） |
| 任一步失败（script/failed） | notify_failed（viewer.notify_failed {step,reason}），fail-fast 不跨步重试 |

**Shell（chat_shell.go execAction，唯一 IO 层）** 的动作与失败语义：
- `discard_pending` → `DeletePending`（坏文件自检：强制 edit-service 磁盘重载）
- `stage/run/save` → 对应 REST；save 版本不可解析 → `save_version` 细分 fail（防空版本静默吞掉导致 staging 滞留、下次 idle 重复 save）
- `reconvert` → `EnqueueIfStale`（IFC 不新于 XKT 时跳过冗余重放）
- dxf kind 整条管线走 cad :8200；`ModelKind=DXF` 时 Core 短路 reconvert（XKT 是 IFC 专属产物）
- 180s 整体超时（notifyTimeout）

### 3.5 前端消费对照（ChatSidebar.tsx:175-331）

EventSource 挂 `chatEventsUrl(cid)`；断线由 EventSource 原生自动重连（带 Last-Event-ID，服务端补发 missed）；`error`/`open` 事件控制「连接断开」提示。子 agent 分组渲染（:436-514 可折叠边栏）：`subagent.status started` 建组 → 带 subagentId 的 part 帧并入组内 → `finished` 置完成态。前端右侧边栏展示、主消息流不受污染。

---

## 五、数据流场景走读（带 curl / 代码路径的探索路线）

### 场景 A：网页对话「帮我新建一个项目，然后建一堵墙」（完整闭环）

1. 前端 `POST /api/v1/chat/projects {title}` → 骨架 IFC 生成 + 注册 `m_...` + 入队转换（chat_orchestrator.go:58）。
2. 前端 `POST /api/v1/chat/sessions {modelId}` → 幂等返回会话。
3. 用户发消息 → `POST /messages {text}` → postMessage 拼系统上下文（`[系统上下文] 会话绑定模型...\n\n[用户需求] ...`，≥2 版本时追加脚本 diff 上下文 W-0016）→ `Ag.Run`。
4. agent 循环：`create_project`（或直接用绑定模型）→ `stage_script` → `run_script` → `save_script`；浏览器实时看到工具卡片从 running → completed。
5. turn/end → SSE `session.idle` → notifyIfDirty（dirty 已由 save_script markDirty）→ notify 闭环 → `viewer.committed {version:"v1"}` → 前端轮询到 ready 自动重载画布。

### 场景 B：主 Agent 派子 agent 画 CAD

1. 用户在绑定 DXF 模型的会话里说「画一个两室一厅平面」。
2. 主 agent 判断意图 → 调 `dispatch_cad_agent {task:"...（自包含需求 + 输入锚点）"}`。
3. runChild：发 `subagent.status started`（前端建分组）→ 子 run（cadAgentPersona）用**父会话绑定**的 DXF 模型走工具（stage/run/save 打到 :8200）→ 子事件全部打 `sa_{turn}_{seq}` 标签上浮（前端边栏分组）→ `finished`。
4. 子报告（turn/end 的 message）作为 dispatch 工具的**结果文本**回到主 agent 上下文 → 主 agent 转述给用户。
5. 主 turn 结束 → 子 save 已 markDirty（注意：markSessionDirty 按 ctx 里的 agentSessionId 解析——子会话 id 复用父会话，所以 dirty 落在父会话上）→ notify 闭环照常。

### 场景 C：REST 直连（无网页）——你这边主要形态

agent 直连 edit-service :8100（不经 Go server）：`PUT /models/{id}/script` → `POST /models/{id}/script/run` → `POST /models/{id}/script/save`。注意：**直连的 run/save 不触发 Go 侧 XKT 重转**（ai.md 明示）；需要前端自动刷新时改走 Go 代理 `:8090/api/v1/models/{id}/script/...`。provenance 直连时传 `source="AI"`。

### 场景 D：离线模式（无 API key）

`agent.New` 回退 scriptedModel（固定一句答复，不调工具）——浏览器能正常建会话/发消息/看到 busy→idle 流转，只是没有智能内容。测试全部跑这条路径（scripted 确定性：同脚本两跑事件序列全等）。

### 场景 E：abort 中止

`POST /abort` → runs 表取消对应 ctx → agent 发 turn/end（无 error）→ 翻译层照常推 idle，前端 busy 清除。runs 表条件删除（identity 指针比对）防旧 run 误删新 run 登记（chat_eino.go:84-97 注释）。

---

## 六、核心设计决策问答（快速理解「为什么」）

| 问题 | 答案 |
|---|---|
| 为什么 skill 不用改造就能「进平台」？ | skill 是 agent 无关目录包；平台 agent 不加载 SKILL.md，只消费它的**提示词提炼**（persona 常量）。技能细节靠 agent 自己读文件——所以 skill 的设计质量（MUST 条款、机器命令）决定 agent 表现，但平台不解析它 |
| 为什么子 agent 工具面是全量领域工具而不是 persona 硬过滤？ | W-0043 Task 5 裁决：工具面本身已领域收敛（9 个函数无 bash/写盘），硬过滤的维护成本 > 收益 |
| 为什么深度预算 1 是「结构性」保证？ | 子工具面由 MakeTools 产出且不含派发工具——不是运行时计数，是类型层面不可能 |
| 为什么 SSE 保持 opencode 形状？ | 契约红线：ChatSidebar 零改动（W-0043 验收标准第一条）；翻译层把内部事件归一成浏览器熟悉的形状 |
| 为什么子事件要落 EventStore 又跳过投影？ | 落盘 = 审计/回放完整性；跳过投影 = 子内容已经 dispatch 结果回流父上下文，再注入会重复计数 |
| 为什么 notify 是 Core+Shell 而不是一把命令式函数？ | 决策可单测（planNotify 各分支纯函数断言）；Shell 副作用清单与旧行为逐条对齐（顺序即契约） |
| 为什么 skill 侧要「信息传递上移主 Agent」？ | 子 agent 不见会话历史（平台侧 task 自包含要求），产物路径显式传递防止多 agent 上下文漂移——两边是同一纪律的两种实现 |

---

## 七、问题探讨深入理解表单（自顶向下：你的原始三问 → 编排机制 → 网页对齐细节 → 开放研究点）

> 排序逻辑：从你最初文档里那三个 confusion（L0）开始——它们是最顶层的问题，已经落地但需要你亲自验证理解；然后往下挖「编排机制」层（L1，平台怎么想、子 agent 怎么跑）；再挖「网页对齐细节」层（L2，你没看过代码的部分，重点讲）；最后是共同研究的开放点（L3）。
> 用法：每张理解卡（L0-L2）的「答案要点」已由我读完代码填好——你逐张说「讲讲 Qx-x」，我就展开讲到你明白为止，确认后状态改 `done`；开放卡（L3）保持 `open`，按「证据」里的探索路径共同研究，有裁决填「结论」。

### L0 · 你的原始三问（顶层：你最初文档里的 confusion，已落地）

#### Q0-1 · skill 怎么加载到 Eino 框架上？

| 字段 | 内容 |
|---|---|
| 关联原始疑问 | confusion #1「原本适配 opencode 的 skill 怎么加载到 eino 框架上」 |
| 问题 | 你的 skill（SKILL.md + references/）是 opencode 形态的目录包，平台 Eino agent 不加载它——那它到底「怎么被用」？ |
| 答案要点 | **skill 不加载进平台运行时**，只在两个地方被消费：① 平台 agent 的 **persona 常量**（subagent.go:26-56）——从 SKILL.md/SUBAGENTS.md 人工提炼的纪律文本，随 agent 启动注入系统提示词；② **对话时由 agent 自己读**——但平台工具面无文件读，所以实际只有 persona 里的那几句话生效。skill 包本身服务的是「会自己跑命令的 agent 环境」（opencode 形态：AI 直连跑 `aiplan`/`aidxfv3` 机器命令）；平台的 script-as-source 等价路径走的是领域工具（get_script/stage_script/...）。这就是 Q3-4 的待研究点 |
| 探索路径 | `skills/aibim-orchestrator/SKILL.md` → `server/internal/agent/subagent.go:26-56` → `tools.go:155`（领域工具集） |
| 结论 | （交互后填：你是否认可这种「不加载、只提炼」的消费方式） |
| 状态 | `open`（我讲完后改 done） |

#### Q0-2 · 为迁移到这套体系，skill 要做哪些改造？

| 字段 | 内容 |
|---|---|
| 关联原始疑问 | confusion #2「为了迁移到这个体系里面应该对 skill 做什么改造」 |
| 问题 | W-0043 已把 opencode serve 换成进程内 Eino，你的 skill 资产被怎么对待？需要你动手改什么？ |
| 答案要点 | **你几乎不用改**——W-0043 的结论是「不改 skill，改平台接入面」：① 平台侧自建领域工具面（9+2 个 Go 函数）替代 skill 的工具形态；② 主/子 persona 从 aibim-orchestrator 提炼内嵌（代码常量，不是运行时读取）；③ `.opencode/` 保留为提示词资产但不再被 server 消费（AGENTS.md 已注明）；④ 你的 skill 包继续为 opencode 形态服务（aiplan/aidxfv3 机器命令、question 断点），两形态并存。**需要你动的只有提示词资产本身的维护**（Q3-2：SUBAGENTS.md 还写着 v1/v2） |
| 探索路径 | `docs/work/items/W-0043-eino-replace-opencode-orchestration.md` 方案 §2/§8 → `server/cmd/server/main.go` 装配 → `chat_tools.go:97-114` |
| 结论 | （交互后填） |
| 状态 | `open` |

#### Q0-3 · 原本 opencode 的基本能力，平台怎么赋予？

| 字段 | 内容 |
|---|---|
| 关联原始疑问 | confusion #3「怎么赋予迁移后我需要的那些原本 opencode 适用的基本能力」 |
| 问题 | 逐项对照：通用终端 / question 弹框 / subagent 派发 / 提示词模板注入 / 事件驱动，各在平台侧对应什么？ |
| 答案要点 | 映射表（完整版见第二节 2.3/2.4 与第五节）：① **通用终端+python 环境 → 没有**（设计使然，工具面领域收敛防任意代码执行），skill 机器命令以包内脚本承载；② **question 弹框 → 没接**（工具面无 question/confirm，OrchestratorPersona 用「文字向设计师确认」兜底，这是 Q3-1）；③ **subagent 派发 → dispatch_ifc_agent/dispatch_cad_agent**（subagent-as-tool，深度预算 1 结构性防递归）；④ **模板注入 → persona + prompt 注入**（全量工具 + prompt 约束，不做 persona 硬过滤）；⑤ **file.edited 事件驱动 → 事件 URI + notify 管线**（Core/Shell 闭环） |
| 探索路径 | `server/internal/agent/subagent.go` 全文 + `chat_orchestrator.go:100-177`（notifyIfDirty/notify） |
| 结论 | （交互后填） |
| 状态 | `open` |

### L1 · 编排机制（平台怎么想、子 agent 怎么跑）

#### Q1-1 · 主 Agent 怎么决定「这次派谁」？

| 字段 | 内容 |
|---|---|
| 问题 | 「意图路由」在代码里到底是什么形态？是规则引擎还是模型自己判断？ |
| 答案要点 | **纯提示词路由，没有代码级规则**——`OrchestratorPersona`（subagent.go:26-37）里三行文字：「IFC 生成/修改 → dispatch_ifc_agent；DXF 生成/修改 → dispatch_cad_agent；设计规范/审查问答 → 直接回答不派发」。模型读到这些约束后自己决定调哪个工具。派发纪律也在这段文字里（task 必须自包含、一次一派发、报告即事实、破坏性大改前先文字确认）。对比 skill 侧 SKILL.md 的意图路由表：两者是同一份设计的两个载体（提示词包 vs 内嵌常量），内容基本一致 |
| 探索路径 | `subagent.go:26-37` ↔ `skills/aibim-orchestrator/SKILL.md`（意图路由表） |
| 结论 | （交互后填） |
| 状态 | `open` |

#### Q1-2 · 子 agent 是怎么被「封装」的？（我派发一个任务，内部发生什么）

| 字段 | 内容 |
|---|---|
| 问题 | dispatch 工具被调用后，到子 agent 跑完返回报告，中间每一步是什么？ |
| 答案要点 | `runChild`（subagent.go:94-139）五步：① 分配唯一 id `sa_{父turn}_{seq}`；② 发 `subagent/status started`（前端建边栏分组）；③ **新建**一个 agent（新模型实例 + 新工具面 = 领域工具 9 个，不含派发工具——深度预算 1 的结构性保证）+ persona（ifc/cad 二选一，subagent.go:141-146）+ MaxStep 20；④ `child.Run(ctx, 父会话id, task)`——**复用父会话 id**，所以子工具里 `SessionIDFromContext` 解析到父会话、kind 路由/绑定模型直接继承；⑤ 子事件循环：每条打 `SubagentID/ParentSessionID` 标签原样走父发送通道（同一 EventStore 落盘、同一 closed 守卫）→ 收尾发 `finished` → 返回子 turn/end 的 message 作为 dispatch 工具的结果文本，**回到主 agent 上下文**。注意两次派发互不共享位置（每次 new 模型+工具面），可并行 |
| 探索路径 | `subagent.go:73-139`（subagentHub + runChild）→ `agent.go:111-192`（父 Run 如何注入 hub 与扇出） |
| 结论 | （交互后填） |
| 状态 | `open` |

#### Q1-3 · 子 agent 的事件去哪了？（落盘、投影、浏览器三路去向）

| 字段 | 内容 |
|---|---|
| 问题 | 子事件和主事件都进同一个 JSONL 日志，为什么模型上下文里不会重复计数？前端怎么分开显示？ |
| 答案要点 | 三路去向，各自处理子事件：① **落盘**：`EventStore.Append` 原样存（含 subagentId 标签，events.go:73）；② **模型上下文投影**：`Project()` 跳过子事件（events.go:146-151——子内容已经 dispatch 结果文本回流父模型，再注入就重复）；③ **浏览器**：翻译层 `translateChild`（chat_translate.go:195）把子事件转成带 `subagentId` 字段的 part 帧 + `subagent.status` 生命周期帧，前端据此分流右侧边栏（ChatSidebar.tsx:277-291），**不进主消息流**；历史回填投影同样跳过子事件（chat_translate.go:346）。结论：子 agent 的一切对外可见性 = 右侧边栏分组 + dispatch 工具的结果文本 |
| 探索路径 | `events.go:146` → `chat_translate.go:195-299` → `ChatSidebar.tsx:277-291` |
| 结论 | （交互后填） |
| 状态 | `open` |

### L2 · 网页对齐细节（你没看过代码的部分，重点讲）

#### Q2-1 · SSE 帧契约为什么是 opencode 形状？（翻译层存在的意义）

| 字段 | 内容 |
|---|---|
| 问题 | 平台内部事件叫 `turn/start`、`assistant/chunk`，浏览器收到的却是 `session.status`、`message.part.delta`——中间隔着一层什么？为什么？ |
| 答案要点 | 隔着 **eventTranslator 翻译层**（chat_translate.go:91-191）。W-0043 契约红线第一条：「ChatSidebar 消费的 SSE 事件集与 data 形状逐字段不变」——前端是 opencode 时代写好的，迁移只换后端执行器，不换浏览器协议。翻译层把 9 种 agent 内部事件映射成 11 种浏览器帧（对照表见 4.3 节）。它还是**纯函数**（无 IO、可按 turn 新建、id 确定性派生），所以有完整单测对拍（chat_translate_test.go）。agent 内部事件（`EventTurnStart` 等）是平台私有协议，SSE 帧是公共契约——这条边界划在哪、为什么划，是理解整个 chat 模块的钥匙 |
| 探索路径 | `chat_translate.go:91-191`（translate 主分支）→ `chat_translate_test.go`（契约钉） |
| 结论 | （交互后填） |
| 状态 | `open` |

#### Q2-2 · 帧的 id 怎么保证前后端不重不漏？

| 字段 | 内容 |
|---|---|
| 问题 | 实时流和历史回填是两条通道（SSE + GET messages），前端怎么知道哪些消息重复了？ |
| 答案要点 | 两层 id 约定：① **SSE 传输 id**：`pushLocked` 每会话递增 seq（chat_sse.go:95），写进帧头 `id:` 行，供断线重连补发；② **内容 id（去重键）**：确定性派生规则（chat_translate.go:24-38）——`msg_{turn}_user` / `msg_{turn}_{step}` / `part_{turn}_{step}_text` / `part_{turn}_{step}_tool_{callID}`，子消息前缀 `sub_{subagentId}_`、子 part 前缀 `sp_{subagentId}_...`。**实时翻译与历史投影共用同一套规则**（projectChatHistory 用同一批 id 函数），前端 ChatSidebar 打开时先 fetch 历史再连 SSE，按 id 去重合并（ChatSidebar.tsx:160-167：`live.filter(...)` + `history.filter(h => !liveIds.has(h.id))`）——SSE 先到、历史后到也不重不漏 |
| 探索路径 | `chat_translate.go:24-38` + `chat_translate.go:338-418`（投影共用 id）→ `ChatSidebar.tsx:160-167` |
| 结论 | （交互后填） |
| 状态 | `open` |

#### Q2-3 · 断线重连怎么补事件？

| 字段 | 内容 |
|---|---|
| 问题 | 浏览器断网/刷新，EventSource 自动重连后，错过的事件怎么补回来？ |
| 答案要点 | 三件套：① **重同步环形缓冲**：每会话最近 64 条帧（`sseReplayBufferSize`，chat_sse.go:15）——即使当时没有在线订阅者也入缓冲（pushLocked 无条件 append，:95-106）；② **Last-Event-ID 补发**：重连请求带浏览器上次收到的帧 id，服务端在注册订阅的同一临界区取出 `id > last` 的帧按序补发（chat_sse.go:47-55）——注册与取快照同临界区保证不重不漏；③ **丢帧兜底**：订阅者消费不及时直接丢帧保主循环（default 分支，:108-111），靠重连补发兜底。不做持久化重放——重启后缓冲清空，重连拿不到旧事件（文档化限制） |
| 探索路径 | `chat_sse.go` 全文（67 行，小而完整）→ `ChatSidebar.tsx:177-179`（error/open 提示） |
| 结论 | （交互后填） |
| 状态 | `open` |

#### Q2-4 · 一张工具卡片的一生（running → completed/error）

| 字段 | 内容 |
|---|---|
| 问题 | 浏览器里那个「工具卡片」是怎么从出现到定格为 ✓/✗ 的？涉及哪些帧？ |
| 答案要点 | 三帧生命周期：① `tool/call` → `message.part.updated`，part.type=tool、state.status=`running`、state.input=参数 JSON——卡片建行（chat_translate.go:144-157）；② 工具执行完 `tool/result`（content）→ 同一条 part id 的 `message.part.updated`，status=`completed`、state.output=结果（:158-179）；③ 工具执行失败（error 载荷）→ status=`error` + error 字段——前端渲染 ✗ 态（:169-173 注释：opencode 行为）。**配对机制**：`eventTranslator.tools` map 按 toolCallID（空 id 退化 `name@turn@step`）把 result 回填到 call 建的卡（toolKey，:81-86）——result 跨 step 到达也能配对；历史投影用同样机制回填（:399-416）。还有防呆：result 先于 call 到达（日志截断）时兜底建卡（:160-166）。前端收到同一 part id 的更新是**更新**不是追加（upsert，ChatSidebar.tsx:230-245） |
| 探索路径 | `chat_translate.go:144-179` → `ChatSidebar.tsx:230-245`（tool upsert） |
| 结论 | （交互后填） |
| 状态 | `open` |

#### Q2-5 · 会话与历史是怎么持久化的？（双 id 与幂等）

| 字段 | 内容 |
|---|---|
| 问题 | 刷新页面/重启服务，会话还在吗？为什么同一模型只有一个会话？ |
| 答案要点 | 三份持久化：① **会话映射** `{DataDir}/chat-sessions.json`：`chatSessionId`（`c_`，前端路由用）↔ `agentSessionId`（`s_`，JSONL 文件名，JSON 字段名保留 `opencodeSessionId` 兼容 web client）+ modelId + title + createdAt（chat_session.go:19-29）；原子写 tmp+rename（:78-97）。② **事件史** `{DataDir}/chat/{agentSessionId}.jsonl`：首行 header + 每行一个 Event（events.go:52-106），坏行跳过不拖垮会话。③ **幂等**：createSession 同 modelId 只建一个（先读锁快路径、再 per-modelId 串行锁 double-check，chat_session.go:150-177）；重启加载时同 modelId 只保留最早一条（:48-61）。重启后：会话在、历史在（GET messages 投影）、进行中的 turn 没了（runs 表是内存态） |
| 探索路径 | `chat_session.go` 全文 → `chat_eino.go:100-122`（getMessages 投影） |
| 结论 | （交互后填） |
| 状态 | `open` |

#### Q2-6 · notify 落盘闭环怎么收尾？（AI 改完模型后，平台自动做了什么）

| 字段 | 内容 |
|---|---|
| 问题 | agent 通过工具改了模型文件，turn 结束后浏览器只看到 `viewer.committed`——中间那套「暂存→沙箱→保存→归档→重转」是谁、怎么编排的？为什么叫 Core+Shell？ |
| 答案要点 | 触发点：`consumeRun` 事件流关闭 → `notifyIfDirty`（chat_orchestrator.go:100）：dirty 信号 = 工具面 markSessionDirty 精确标记（stage/run/save 成功即置，chat_tools.go:22-34）∨ 工作区文件 mtime 兜底。**为什么分 Core+Shell**：决策（要不要跑脚本管线、失败怎么办）是**纯函数** `planNotify`（chat_core.go，`Event+State→Action 列表`，可单测每个分支）；副作用（REST/文件/队列/SSE）是 Shell `execAction`（chat_shell.go:56-122）——决策与执行分离，旧命令式逻辑的分支全变单测断言点。**多轮闭环**：第一轮 idle+dirty → `discard_pending → stage → run → save`；`saved` 事件驱动第二轮 → `archive（staging→scripts/v{n}.py 删源）→ reconvert（EnqueueIfStale，IFC 不新于 XKT 跳过）→ notify（viewer.committed）`；失败 → `viewer.notify_failed {step,reason}`，fail-fast 不跨步重试；180s 整体超时。版本号只在 save 成功后已知，所以收尾必须延到第二轮——这是「不在 LLM 调用上同步等待」基调的体现 |
| 探索路径 | `chat_core.go`（planNotify 全分支）→ `chat_shell.go:29-52`（runShell 循环）+ `:56-122`（execAction 每动作） |
| 结论 | （交互后填） |
| 状态 | `open` |

### L3 · 开放研究点（原 Q1-Q4 保留重编号，状态 open）

#### Q3-1 · question 断点确认的承载形态（原 Q1）

| 字段 | 内容 |
|---|---|
| 问题 | aiplan 四轮确认、aidxfv3 S0-S4 断点依赖 `question` 弹框；平台 agent 工具面没有它 |
| 背景 | 平台工具面 = 9 领域 + 2 派发，无 question/confirm；ADK 的 HITL（`adk.Interrupt` / `Runner.ResumeWithParams`）现成但**项目在经典 flow API 侧**（见 1.1）；`OrchestratorPersona` 只要求「破坏性大改前先文字确认」——对话式，不是工具式断点 |
| 约束 | 工具面领域收敛；SSE 单向流（服务端→浏览器），工具式 question 需反向通道；REST 直连场景无对话 UI，断点会卡死 |
| 候选 | A. 工具化 question（工具 + 新端点 + 前端弹框） B. 主 Agent 文字确认（现状，零新接口） C. ADK HITL 接线（迁移/桥接成本见 1.1 结论） |
| 证据 | ✅ 已核实（2026-08-18 源码）：① 官方 question 模式 = interrupt/resume，原语在 `components/tool/interrupt.go`（`StatefulInterrupt`/`GetResumeContext`，非 ADK 专属包），参考实现 `adk/common/tool/follow_up_tool.go`（`FollowUpInfo{Questions, UserAnswer}`）+ `approval_wrapper.go`；② **但驱动需 ADK Runner**（interruptID + ResumeWithParams）——经典 react.Agent 只暴露 Generate/Stream/ExportGraph，无 Resume 入口；走官方 interrupt = ExportGraph 自编译 + CheckPointStore 自组运行时，成本逼近迁 ADK；③ **关键官方字段 `react.AgentConfig.ToolReturnDirectly`**（react.go：工具调用后 agent 直接结束本轮）——question 工具语义的经典侧官方支持点 |
| 封装方案（Q-A 细化，经典侧） | 「结构化结束本轮 + 问答通道」四件套：① `ask_user {questions[]}` 工具（InferTool + 注册 ToolReturnDirectly → 调即用本轮干净结束，不靠 prompt 约束）+ pending 问题存储（v1 内存态）② 翻译层新 SSE 事件 `question.ask {questionId, questions, subagentId?}` → 前端提问卡片 ③ 新端点 `POST /chat/sessions/{cid}/answer` → 答案作为用户消息注入新 turn ④ 子 agent 场景：ask_user 使子 run 干净结束 → 问题经 dispatch 报告/透传带出 → 答案由主 agent 下次派发注入（状态连续性靠持久工作区）。工程量 ≈ Go 150 行 + 测试 200 行 + 前端 100 行 ≈ 1-1.5 天。**核心认知：经典侧不做「挂起-恢复」语义（ADK 形态），做「结构化结束本轮 + 新 turn 带回答」——与「每条消息一个 turn」的 chat 架构同构** |
| 倾向 | v1 纯 prompt 约定（报告遗留问题字段 + 派发边界断点，零成本）→ 实测不够用时升 Q-A（约 1-1.5 天）→ Q-B（ExportGraph 自组运行时）不做，届时直接评估迁 ADK |
| 结论 | **（2026-08-19 用户裁决，D1 翻转）迁移 ADK**——官方 skill 接入（skill middleware + filesystem backend）只存在于 ADK；经典侧手搓薄壳是「复原拼接」、效果无法保证。断点确认走官方 HITL（interrupt/resume），skill 加载走官方 skill middleware。迁移工作分解见 `agent_deployment_plan.md` §8（ADK 迁移主路径）。 |
| 状态 | `done`（裁决） |

#### Q3-2 · 提示词资产引用过期（SUBAGENTS.md vs aidxfv v3）（原 Q2）

| 字段 | 内容 |
|---|---|
| 问题 | `skills/aibim-orchestrator/references/SUBAGENTS.md` 写 aidxfv v1/v2（step-routed 管线、archdxf 构造），正式版 v3 已上线。**2026-08-18 新发现：漂移已到运行时依赖层——`services/cad/app/config.py:19` 的 flows_dir 指向 `skills/aidxfv/v1/scripts/flows`（cad_script_lib 住在 v1），v3 无 script_lib 等价物** |
| 背景 | v3 = 2026-08-18 决议的迭代基线；RELAY_CONTRACT.md 锚点 1/2 也复制自 v2 的 plan_contract.md；平台 persona 文字不受影响但信息量低。**「v1/v2 待删除」决议与运行时依赖直接冲突：删 v1 前必须先把 cad_script_lib 迁走（内联进 services/cad 或移植进 v3），否则 cad 服务的契约校验门 + 沙箱（reset_state/import）直接崩** |
| 候选 | A. 同步 SUBAGENTS.md/RELAY_CONTRACT.md 到 v3 B. 顺带删 v1/v2 时一起改 C. 平台 persona 补「加载 skills/aidxfv/v3 并遵守 SKILL.md」 D. **（新增，前置依赖）cad_script_lib 迁移：内联进 services/cad 或移植 v3——删 v1 的硬前置** |
| 证据 | ✅ 已核实：services/cad flows_dir → v1（config.py:19）；v3 无 script_lib（find 无结果）。**cad_script_lib 功能面已读**（295 行，镜像 aiifc script_lib 的 DXF 契约层）：① 实体工厂 + XDATA 确定性 key（APPID AIDXF，`{layer}:{kind}:{n}`——解 DXF handle 重存全变的身份问题）② 调用点登记（origin literal/params/traced 分类 + params_keys，locate/edit-call 原料）③ write_and_validate（saveas+audit+map.json 侧车）④ validate_script_contract 静态门（ast 不执行）。**services/cad 三消费点全承重**：script_runner（静态门+沙箱 reset_state）、dxf_diffing（get_entity_key 跨版本对齐）、dxf_materialize（确定性约定）。**迁移归属判断**：它本质已是 cad 服务的契约层（skill 包只是历史存放地），正确归宿倾向**内联进 services/cad** 而非塞进 v3（v3 无 script-as-source 契约层形态）。仍待填：v3 包内 SKILL.md 的准确命令/流程名 |
| 倾向 | （待填） |
| 结论 | （待填） |
| 状态 | `open` |

#### Q3-3 · dispatch 与接力契约（RELAY_CONTRACT）的衔接（原 Q3）

| 字段 | 内容 |
|---|---|
| 问题 | 平台 dispatch 工具只有 `task` 文本参数；skill 侧「输入锚点显式传递 + 报告格式」纪律如何在平台落地 |
| 背景 | 平台侧已部分落地：OrchestratorPersona 要求 task 自包含；子 persona 要求报告格式 `{产物路径,版本,validate 结果,遗留问题}`——**但子 agent 工具面是领域工具，不是 skill 机器命令（aidxfv3 normalize 等）**：平台子 agent 只能走「script-as-source 脚本」等价路径，跑不了 aidxfv v3 管线本身 |
| 候选 | A. 平台工具面新增 skill 机器命令代理工具——细化两条工程路径：**A1 经 services/cad REST**（cad 服务新增管线端点族，复用 script_runner 沙箱骨架；aidxfv3 自包含包入 cad 环境；1 个泛化工具 + 服务端白名单校验，**推荐**）/**A2 Go 侧直接 subprocess**（converter 起 Node 子进程先例，快 MVP） B. 保持 script-as-source 等价路径（现状），v3 管线留给 opencode 形态 C. dispatch task 模板化（SUBAGENTS.md 派发模板嵌进 persona） |
| 迁移评估（2026-08-18） | **好改造，最难的部分已完成**：CLI 封装（JSON I/O + 退出码 0/1/2）是 REST 端点天然形状；`machine_contract.md` 已写好全命令 schema/边界/退出码——服务端 `verify*` 校验器几乎现成；包自包含仅依赖 ezdxf+shapely（cad 服务已有 ezdxf）。**硬点只有两个**：① 工作区模型（现沙箱=一次性临时目录单产物 vs aidxfv3=持久项目目录多产物，改造=bwrap bind 持久工作区 `models/{id}/`）② 命令面粒度（~13 命令 → 1 泛化工具 + 服务端白名单，避免模型负担）。**意外之喜**：S0-S4 断点在工具形态下 = 两次工具调用之间主 agent 对话确认，不用等 Q3-1 HITL；状态监视（`state sync/advance/reconcile`）= 普通工具调用返回状态 JSON，比 CLI 进程内监视更自然 |
| 证据 | ✅ 已核实：DeepAgent 预设 / PyExecutor 两条官方路都与「领域收敛」哲学冲突（见 1.2）；aidxfv3 命令面与 machine_contract.md 已读。仍待填：A2 半天实测（跑通一个 `aidxfv3 normalize` 验证体感）再定 A1 立项。**Operator 实现现状（已核实）**：eino-ext 官方仅 DockerSandbox 一个实现（Docker 容器，断网/限额/VolumeBindings/safeResolvePath 齐全，example 即此接法）——对咱们偏重（docker.sock + 自建镜像 + 沙箱纪律分叉）；建议自实现 bwrap Operator（约百行 Go：4 个文件方法=路径 jail+os 调用，RunCommand=bwrap 参数照抄 script_runner.py:159-172 + 宿主 venv python），保持沙箱纪律单源 |
| 状态机归属裁决（2026-08-18） | **flowops 不融合进 Go**——状态事实（九态推进/产物对账/中断恢复）是 Python 工作区产物的纯函数，属 cad 领域知识；搬 Go = 跨语言双写漂移。**沿用 script_lib 先例**：skill 包 = 领域逻辑单源 → services/cad import flowops → REST 端点（state sync/advance/reconcile）→ Go 泛化工具薄代理。三分天下：状态事实归 Python flowops / 派发运行时（派了谁、等谁回来）归 Go（subagentHub/runs 表先例）/ 派发决策归主 agent prompt（dispatch.md → persona，Q3-2 同步时带上）。反例条件：状态推进需实时驱动跨域事件时，Go Core 把 flowops 状态当事件输入消费，仍不搬状态机 |
| 三级执行模型（2026-08-18，用户分层直觉修正版） | ① **交付级**：构建脚本 run/save、deliver 封存 → 现有 script_runner 重沙箱（REST）② **管线命令级**：aidxfv3 固定命令 + flowops 状态机 → services/cad 白名单端点（A1）③ **探索级**：worker 临时 python → **PyExecutor + project-bound Operator**（自实现 Operator 接口：ctx 解析 modelId → 工作区 `{dataDir}/models/{id}/pipeline/`，路径 jail + bwrap 断网为底线）。**落盘统一解法**：三级物理写同一目录——靠两个既有硬不变量：VIEWER_DATA_DIR 三方共享（AGENTS.md 硬规则）+ ctx→modelId 解析（SessionIDFromContext 先例）。**边界修正**：flowops state 命令是固定命令+状态单源，必须走白名单（否则任意 python 改 missions/ 可绕过九态推进规则——非破防级，状态机是簿记辅助，质量门在 validate/check/readback）；PyExecutor 只承接真·ad-hoc。**权限**：PyExecutor 只挂子 agent（worker persona），主 agent 不挂——W-0043「子复用主工具集」的第一个有理例外 |
| 层级映射方案（2026-08-18，针对「skill 里有子派子」） | **Eino 框架本身不限嵌套层级**（ADK AgentAsTool 可任意嵌套；经典侧 subagentHub 是自研，「深度预算 1」是 W-0043 有意选择非框架限制）。aidxfv3 管线本身只需「编排者→worker」一层派发（dispatch.md）；二级只出现在 aibim-orchestrator + aidxfv3 组合形态（main→cad-agent→worker）。**方案 A 扁平化（推荐）**：平台主 agent 直接当管线编排者——持管线白名单工具 + 自己派 worker，深度预算 1 零改动；「cad-agent 中间层」用工具分组替代（契合 flowops「状态归机器、决策归主 agent」+「信息传递上移主 Agent」两条既有裁决）。**方案 B 真嵌套（后备）**：深度升 2，需 subagentHub 事件标签链式化（现 SubagentID 单标签，孙代上浮会被重打标覆盖）+ 前端嵌套分组 + 深度预算配置化——中等工程非框架障碍。触发条件：A2 实测发现主 agent 上下文过载（多 zone 并行 mission 状态膨胀）再升级 |
| 倾向 | （待填——我倾向 A1 正式化 + 方案 A 扁平化层级映射 + PyExecutor 探索级只给 worker） |
| 结论 | （待填） |
| 状态 | `open` |

#### Q3-4 · 子 agent 的「技能加载」语义（原 Q4）

| 字段 | 内容 |
|---|---|
| 问题 | skill 侧 SUBAGENTS.md 要求子 agent「先加载 aiifc skill 并遵守 MUST 条款」；平台 persona 只说「技能来源：aiifc skill」——平台子 agent 没有文件系统工具，读不了 `skills/aiifc/SKILL.md`。**且 skill 是厚包 + 分级加载设计（L0 描述→L1 宪法→L2 索引→L3 厚参考），分级加载怎么在平台实现？** |
| 背景 | 分级加载的真相：**不是运行时机制，是 MUST 条款编码的阅读协议**（「什么动作读什么页」）+ agent 文件工具——平台无文件工具，pull 链断。Eino 官方对应物：`adk/middlewares/skill`（系统提示词教 progressive disclosure 协议 + `skill` 工具加载 SKILL.md 全文 + 支撑文件走绝对路径依赖文件工具 + `BuildForkMessages` 可注入派生 subagent 初始消息）——但在 ADK 侧 |
| 候选（按层选载体，2026-08-18 细化） | **L1 宪法（MUST 1-31 约 60 行，总是需要）→ persona 常量内嵌全文**（零风险，现状只内嵌了几句）；**L2 索引 → 拼进 persona 或随工具返回**；**L3 厚参考（103 API 页/8 recipe，按需）→ push 为主：dispatch 时机器注入**（aidxfv3 `pack` 先例：机器预筛相关页拼进 task，「建墙→墙 recipe + create_2pt_wall API 页」，LLM 零加载负担）**+ pull 兜底：`read_skill_doc` 只读工具**（jail 到 skills/、白名单 .md/.py、64KB 截断，worker 卡顿时自救，恢复 MUST 阅读纪律的执行力）。ADK skill 中间件为第四路——同 DeepAgent 评估，为它还 ADK 不值，Q3-1 迁 ADK 则白送 |
| 证据 | ✅ 已核实：aiifc SKILL.md 阅读协议结构（MUST #1-5 阅读地图）；`adk/middlewares/skill` prompt.go/skill.go 机制（含 BuildForkMessages 官方版派发注入）；aidxfv3 pack 的 push 注入先例（dispatch.md「push 保底 + pull 精准」K1 纪律）。**平台侧分层加载现状核查（2026-08-18）**：参考文档层零载体（Go server/mcp/services/系统上下文拼接均无文档加载）——但有两个隐性知识通道部分补偿：① 既有脚本即活例子（get_script 读回的脚本可见 PARAMS/create_entity/build/write_and_validate 实际形态）② 静态门 422 错误文本经工具结果回喂 = 反馈式纪律执行（模型自愈）。**缺口精确定位**：缺的是 L3 厚参考的按需触达，尤其「动笔前必读」的前置文档（SPATIAL_QUALITY 等，MUST #4 "BEFORE framing"）——报错自愈救不了防错类纪律，这是 push 注入比 pull 兜底更重要的原因 |
| 倾向 | **官方零件组装（O2）**：`load_skill`/`read_skill_doc` 工具薄壳（InferTool，~150 行含 jail+截断）+ **100% 官方复用**：skill.Backend（`NewBackendFromFilesystem`：frontmatter 解析/目录扫描/正文提取）+ local backend（文件 IO）；persona 索引由官方 Backend.List 生成。L1 宪法由加载后的 SKILL.md 承载，L3 push（pack 模式）后续叠加 |
| 结论 | **（2026-08-19 D1 翻转后更新）采用官方 skill middleware**：`skill.NewTyped` 挂进三角色 agent Handlers，自动获得 `skill` 工具 + progressive disclosure + inline/fork 模式。经典侧 O2 薄壳方案（下方候选/倾向仍保留历史原貌）已废弃——官方未导出工具级构造函数的问题在迁 ADK 后消失。 |
| 状态 | `done` |

---

## 八、执行改造方案（2026-08-18 讨论产出汇总）

> 本节是 Q3-3/Q3-4 讨论收敛出的设计记录：把 skill 的「机器命令 + 流程编排 + 探索性 python」能力赋予平台 agent。**当前全部未写代码**（见 §8.6 清单），落地前先 A2 半天实测再立项。

### 8.1 背景与目标

skill 侧（aiplan / aidxfv v3 / aiifc）有三类执行能力：① 构建脚本执行（确定性 build → IFC/DXF）；② 管线机器命令（`aidxfv3 preprocess/normalize/check/pack/state...` + flowops 状态机）；③ 探索性 python（worker 临时脚本、调试、一次性分析）。平台现状：只有①有载体（edit-service 沙箱 REST），②③完全没有——平台子 agent 只能走「写构建脚本 → run/save」等价路径，跑不了 aidxfv3 编排命令。

目标：在**不破坏领域收敛**（W-0043 裁决：工具面无 bash/任意文件写）的前提下，把②③以受控形态赋予平台。

### 8.1.5 能力等价性矩阵（2026-08-18 核实：平台侧 aiifc ≠ skill 包）

| aiifc 完整能力（opencode 形态） | 平台现状 | 等价？ |
|---|---|---|
| 知识层 L1：MUST 1-31 宪法全文 | persona 约 5 句纪律 | ❌ |
| 知识层 L2/L3：103 API 页/8 recipe/方法论按需读 | 无载体 | ❌ |
| 执行层-契约：script_lib 工厂 + 静态门 + 沙箱 PYTHONPATH | 完整等价（机器侧） | ✅ 唯一等价层 |
| 执行层-flows：13 个可运行 flows 由 agent 按需跑 | 无 python 执行工具，一个都跑不了 | ❌ |
| 校验层三层（#20 snapshot / #21 design_review / #22 validate） | 仅第 3 层（脚本出口强制）；design_review/snapshot 平台跑不了（services/ifc 零引用，已核实） | ⚠️ 1/3 |
| 工作流层：design JSON 起草（MUST #18） | 无 | ❌ |
| 细粒度编辑：locate/edit-call 平台工具 | edit-service 有两端点（locate 按 guid 定位、edit-call libcst 标量改写），但平台 9 工具未覆盖（edit-call 仅直连暴露不经 Go 代理）——agent 改单个标量只能「读全文→改一处→全量 stage」，与 persona「增量编辑」纪律不匹配，大脚本下 token/出错风险实质差距 | ❌（2026-08-18 新发现） |

**关键设计转向——平台式等价 ≠ 复刻 opencode 形态**：检查性 flows（design_review「fixed black-box check」、validate）在 opencode 形态靠 MUST 软约束 agent 自觉跑；平台应把它们**焊进 run/save 端点做服务端强制门禁**（构建成功 → 沙箱内自动跑 design_review → 报告随响应返回供自愈；严重违规可 422 拦截，严格度待裁决）——纪律从「提示词约束」升级为「结构不可绕过」，比等价更强。创作性 flows（design_builder / design JSON 起草）才需要 agent 参与，走三级模型的探索级/管线级。**等价公式：知识层分级加载（Q3-4）+ 校验层服务端门禁化 + 创作性 flows 走三级模型**。

### 8.2 设计原则

1. **领域收敛不破**：不挂裸 bash/任意文件写；任意 python 执行只出现在带 jail 的独立工具，且只给子 agent。
2. **领域逻辑单源**（script_lib 先例）：skill 包 = 事实源，services import 它，Go 只做薄代理——不跨语言双写。
3. **沙箱纪律单源**：所有沙箱复用 script_runner 的 bwrap 参数模式（ro root + unshare-net + rlimit + 进程组杀），不引入第二种沙箱语义（Docker 除外作为官方备选）。
4. **落盘统一**：三级执行物理写同一工作区，靠两个既有硬不变量保证（VIEWER_DATA_DIR 三方共享 + ctx→modelId 解析）。

### 8.3 三级执行模型

| 级 | 内容 | 载体 | 沙箱强度 | 现状 |
|---|---|---|---|---|
| **交付级** | 构建脚本 run/save、deliver 封存 | 现有 script_runner（services/ifc :8100 / services/cad :8200 REST） | 重：bwrap + 契约静态门（ast 不执行）+ 原子发布 | ✅ 已有 |
| **管线命令级** | aidxfv3 固定命令面（~13 命令）+ flowops 状态机（state sync/advance/reconcile） | services/cad 白名单端点族（新增） | 中：bwrap + 持久工作区 | ❌ 未写 |
| **探索级** | worker 临时 python（调试几何/一次性分析） | eino-ext commandline PyExecutor + 自实现 project-bound Operator | 轻：bwrap + 路径 jail | ❌ 未写 |

边界修正（重要）：flowops state 命令**不是杂务**——是固定命令 + 状态事实单源，必须走白名单（否则任意 python 改 missions/ 可绕过九态推进规则。非破防级：状态机是簿记辅助，质量门在 validate/check/readback；但白名单化消掉一类噪音）。PyExecutor 只承接真·ad-hoc。

**层级分配衡量框架（2026-08-18）**——「什么能力放哪一级」的尺子，按序问四问：① 产物要进平台服务端管线吗（版本/diff/web 视图/notify 重转）→ 是 = 交付级（**结构必然**：全链路在服务端，agent 侧执行还得同步回去等于绕圈）② 是固定命令集吗（CLI 已封装 + machine_contract）→ 是 = 管线命令级 ③ 产物/状态要被后续步骤消费吗 → 是 = 至少管线命令级（持久工作区 + 状态机）④ 剩下临时/探索/一次性 → 探索级。三维度对照：产物去向（进管线/中间产物/只给 agent 看）× 命令形态（固定契约/固定命令集/任意代码）× 爆炸半径（版本污染/可对账恢复/jail 内无副作用）。数量经济：通用执行器一次开发覆盖长尾但带风险预算，专属工具每个可测可审计可门禁化——高频+交付相关+有契约做专属，低频+探索靠通用兜底。**能力晋升路径**：探索级临时脚本常用化 → CLI 化 → 进白名单 → 服务端门禁化（design_review 即案例：opencode 形态 MUST #21 软约束 → 应晋升焊进 run/save 端点强制跑）；定期问「这个探索用法该晋升了吗」就是体系的演进机制。

### 8.4 落盘统一方案

- 统一工作区约定：`{dataDir}/models/{id}/pipeline/`（复用 per-model 目录惯例）。
- 不变量一：**VIEWER_DATA_DIR 三方共享**（Go + :8100 + :8200 同一 data 目录，AGENTS.md 硬规则）→ Go 进程内的 PyExecutor 与 cad 服务端点物理写同一目录。
- 不变量二：**ctx→modelId 解析**（`SessionIDFromContext` → 会话绑定模型，领域工具 resolve 同款机制）→ 两条路径都从 ctx 拿工作区根，agent 不传路径。
- 自实现 **project-bound Operator**（PyExecutorConfig.Operator 接口：ReadFile/WriteFile/IsDirectory/Exists/RunCommand，约百行 Go）：4 个文件方法 = 路径 jail 到工作区 + os 调用；RunCommand = bwrap 包装（参数照抄 script_runner.py:159-172）+ cwd 强制 + 超时杀进程组 + 64KB 截断；python 解释器指向 services/cad 的 venv。
- Operator 官方实现现状（已核实）：eino-ext 仅 `DockerSandbox`（Docker 容器，断网/限额/VolumeBindings/safeResolvePath 齐全）——对咱们偏重（docker.sock + 自建镜像 + 沙箱纪律分叉），故自实现 bwrap 版。

### 8.5 状态机归属裁决

**flowops 不融合进 Go。** 状态事实（九态推进/产物对账/中断恢复）是 Python 工作区产物的纯函数，属 cad 领域知识；搬 Go = 跨语言双写漂移。沿用 script_lib 先例（已是两处先例的成熟模式：`services/ifc` import aiifc 的 script_lib + `services/cad` import aidxfv v1 的 cad_script_lib——均为 config flows_dir 指向 skill 包 + sys.path import 单源 + 沙箱 PYTHONPATH 注入）：`services/cad` import flowops → REST 端点暴露 → Go 泛化工具薄代理。

三分天下：
| 职责 | 归属 | 先例 |
|---|---|---|
| 管线状态事实（九态/对账/恢复） | Python flowops（单源）→ services/cad REST | script_lib |
| 派发运行时（派了谁、等谁回来） | Go server | subagentHub / runs 表 |
| 派发决策（何时派/重派/断点） | 主 agent prompt | dispatch.md → persona（Q3-2 同步时带上） |

反例条件：状态推进需实时驱动跨域事件时，Go Core 把 flowops 状态当事件输入消费（planNotify 同款 Event+State→Action），仍不搬状态机。

### 8.6 已有 / 未写清单（2026-08-18 代码事实）

| 已有 | 未写 |
|---|---|
| 交付级沙箱（两个 script_runner.py） | ① PyExecutor 挂工具面（依赖未进 go.mod） |
| 平台工具面 9+2（无 python 执行） | ② 自实现 bwrap Operator（约百行） |
| flowops 包（仅 CLI 形态被用） | ③ services/cad 管线白名单端点族 |
| go.mod 有 eino-ext openai 组件 | ④ 持久工作区沙箱（`models/{id}/pipeline/`，区别于一次性临时目录） |
| | ⑤ services/cad import flowops / aidxfv3 包入环境（加 shapely） |
| | ⑥ worker persona 工具面例外（子 agent 才挂 PyExecutor——W-0043「子复用主工具集」的第一个有理例外；主 agent 不挂） |

### 8.7 工程路径与工作量

| | A1：经 services/cad REST（推荐，正式路径） | A2：Go 侧直接 subprocess（快 MVP） |
|---|---|---|
| 内容 | cad 服务新增管线端点族 + 持久工作区沙箱（复用 script_runner 骨架）+ aidxfv3 包入环境 + Go 1 个泛化工具薄代理 | 自实现 bwrap Operator + 挂 PyExecutor + 跑通一个 aidxfv3 命令 |
| 校验 | 白名单 + 参数校验在服务端 `verify*` 单点（machine_contract.md 几乎现成） | Operator 路径 jail 即边界 |
| 工作量 | 中等工作项（端点族 + 工作区沙箱 + 依赖入环境 + 契约测试） | 半天 |
| 用途 | 正式立项 | 验证体感，再定 A1 |

迁移有利面（已核实）：CLI 封装（JSON I/O + 退出码 0/1/2）是 REST 天然形状；machine_contract.md 已写好全命令 schema/边界/退出码；包自包含仅依赖 ezdxf+shapely。硬点两个：① 工作区模型（一次性临时目录 → 持久项目目录，bwrap bind 持久工作区）② 命令面粒度（~13 命令 → 1 泛化工具 + 服务端白名单）。意外之喜：S0-S4 断点在工具形态下 = 两次工具调用之间主 agent 对话确认，不用等 Q3-1 HITL；状态监视 = 普通工具调用返回状态 JSON。

**DeepAgent 评估（2026-08-18，结论：现在不合适）**：① 只在 ADK 侧，用它 = 迁整个 agent 运行时（事件模型/SSE 翻译层/EventStore/确定性测试全重做，W-0043 投资重来）；② 预设形态（通用 shell + 文件工具挂给每个 agent）与领域收敛冲突，拆瘦后预设价值没了迁移成本还在；③ 不解决真问题（工作区绑定/状态单源/白名单/bwrap 纪律都得自己写），文件工具组还冗余（PyExecutor 的 python 在 jail 内本就能读写工作区文件，worker 写 rooms.json DSL 靠它即可）。可零成本借鉴：write_todos 进度 UX、filesystem.Backend 接口划分、「配置即挂载」形态。**入场触发条件：Q3-1（HITL）若裁决迁 ADK**——DeepAgent 返回 `adk.ResumableAgent`，interrupt/resume 白送，届时 worker 用 DeepAgent 预设（Backend=project-bound + Shell=bwrap 版 + 领域工具）是自然选择。

### 8.8 下一步

1. A2 半天实测：写 bwrap Operator → 挂 PyExecutor → 绑定工作区跑通一个 `aidxfv3 normalize`（或 import flowops 查状态）。
2. 拍板 Q3-3 倾向/结论（A1 立项与否）。
3. Q3-2 同步提示词资产时，把 dispatch.md 的派发决策纪律带进平台 persona。

### 8.9 裁决后工作分解（历史，2026-08-18：经典侧开发 + 官方零件 skill 加载）——**已被 ADK 迁移取代（2026-08-19）**

> ⚠️ 本节是迁 ADK 前的经典侧计划，**不构成当前执行依据**。当前执行看 `agent_deployment_plan.md` M0-M4。

| 序 | 工作项 | 内容 | 位置 | 量级 |
|---|---|---|---|---|
| ① | `get_script_locate` 工具 | 薄代理 `GET /models/{id}/script/locate?guid=`（found/line/col/snippet/origin 透传，kind 路由） | `agent/tools.go` | 小（~30 行+测试） |
| ② | `edit_script_call` 工具 | 薄代理 `POST /models/{id}/script/edit-call`（designKey/argument/value；DoSlow 含沙箱验证；成功 markDirty） | `agent/tools.go` | 小（~40 行+测试） |
| ③ | skill 加载两工具 | `load_skill`（官方 `skill.Backend.Get`）+ `read_skill_doc`（官方 local backend ReadFile + 自写 jail：Clean/前缀/symlink 求值/后缀白名单/64KB 截断） | `agent/skills.go`（新） | 中（~150 行+~250 行测试，TDD） |
| ④ | persona 索引注入 | 装配时 `skill.Backend.List` 生成「name+description 清单 + progressive disclosure 协议」拼进 persona；配置项 `skillsDir`（默认 `./skills`） | `chat_tools.go`/main 装配 | 小（~30 行） |
| ⑤ | 挂载范围 | 子 agent 挂全量两工具；主 agent 只挂 `load_skill` | `chat_tools.go SubagentAgentTools` | 小（~15 行） |
| ⑥ | design_review 门禁化 v1 | services/ifc：沙箱构建成功后同沙箱自动跑 design_review.py，报告随 run/save 响应返回（非拦截；422 严格度留 v2）；注意计入 60s 沙箱预算 | `services/ifc/script_runner.py` | 中（~80 行 Python+测试） |

**顺序**：①②（半天，验证工具面扩展体感）→ ③④⑤（约一天，核心交付）→ ⑥（半天）。同一迭代分支累积，当天一次 PR（硬规则）。**范围外**：ADK 迁移/DeepAgent/官方 middleware（触发条件见 Q3-1）、管线命令级 A1 端点族（先 A2 实测）、子派子真嵌套（方案 A 扁平化已裁决）。

### 8.10 ADK 迁移预案（历史，备用设计）——**已成主路径（2026-08-19 D1 翻转）**

> ⚠️ 本节原为「若经典侧不合适才迁」，现已成为执行主路径。迁移工作分解（M0-M4）见 `agent_deployment_plan.md` §4；以下「相似处/要重写的」仍是对迁移的准确描述。

**框架相似处（零/小改动）**：① 工具面共享——9 领域 + 2 派发工具全是 `utils.InferTool` 产物（`tool.BaseTool`），零改动挂进 ADK ToolsConfig（最大红利）；② 模型接口兼容——scriptedModel/openai 组件直接可用（`model.BaseModel[*schema.Message]`）；③ 概念 1:1：persona→Instruction/AdditionalInstruction、MaxStep→MaxIterations、react loop→ChatModelAgent、ctx 取消→TurnLoop 中止。

**要重写的**：事件采集层（runEmitter callbacks 观测 → Runner 的 `AsyncIterator[AgentEvent]` 直读）；Run 生命周期适配；EventStore 记录对象换成 AgentEvent（投影规则同步改）；删掉三个自研件换官方：subagentHub→`NewAgentTool`+`EmitInternalEvents`（chatmodel.go:143）、ask_user→`tool.StatefulInterrupt`+`ResumeWithParams`、skill 薄壳→skill middleware。

**翻译层 2.0（对接/呈现定制化的承载点，契约红线不动）**：SSE 帧形状/7 路由/envelope/前端零改动，只换源映射——`AgentEvent{AgentName, RunPath, Output.Message, Action}`：流式 Message→part.delta；ToolCall/Result→工具卡片三态；`Action.Interrupted`→新帧 question.ask（Q3-1 官方答案落地）；**子事件经 AgentName/RunPath 识别**→附加 subagentId 分流边栏（比自研打标更正规：框架管理的执行路径）；AgentAsTool 起止→subagent.status。确定性 id 约定（msg_/part_/sp_）整套保留，前端去重合并零改动。

**工作量**：1-1.5 个 chunk（3-6 天）——小于 W-0043（工具面/notify/前端/会话映射保留），大于 Q-A+O2 自写（核心事件链路重做）。

**启动触发条件**（任一满足即重评）：① Q-A 实测不够（需真挂起-恢复，如跨会话长任务断点——CheckPointStore 才给得了）② skill middleware 进阶能力成硬需求（BuildForkMessages 子 agent 注入）③ 方案 B 真嵌套成硬需求（ADK RunPath 原生任意深度）④ ADK 稳定至 1.0。

---

## 九、一个下午的探索路线（建议顺序）

| 时段 | 动作 | 目标 |
|---|---|---|
| 0:00-0:15 | 读本文件「〇」+「一」（参考资料库导航，确认本地资源可跑）；`ls skills/` 各包 SKILL.md 前 20 行 | 建立资产地图 |
| 0:15-0:30 | 细读 `skills/aibim-orchestrator/` 三件套（SKILL.md / SUBAGENTS.md / RELAY_CONTRACT.md） | 吃透编排契约 |
| 0:30-1:00 | 读 `server/internal/agent/subagent.go` + `tools.go`（对照本文件 3.3/3.4 节） | 吃透 subagent 封装 |
| 1:00-1:30 | 读 `chat_translate.go` + `chat_sse.go` + `ChatSidebar.tsx:175-331`（对照 4.2/4.3/4.5） | 吃透网页对齐接口 |
| 1:30-2:00 | 跑官方例子：`eino-examples/adk/human-in-the-loop/1_approval` + `adk/middlewares/skill`（复用 VIEWER_LLM_* 三参） | 填 Q3-1/Q3-4 卡的「证据」 |
| 1:30-2:00 | 跑一遍场景 A：起 edit-service + server（API key 留空），浏览器走 chat 建项目发消息；或跑场景 C：curl 直连 :8100 三段式 | 亲手验证 |
| 2:00-2:30 | 跑 chat 相关测试理解契约钉：`cd server && go test ./internal/api/ -run 'Chat|Subagent'`；前端 `cd web && npx vitest run src/viewer/ChatSidebar.test.tsx` | 测试即契约文档 |
| 2:30-3:00 | 回填 Q 卡（L0-L2 确认理解、L3 填证据）；有裁决就填「结论」 | 产出对齐结论 |
| 3:00-3:30 | 通读 `docs/site/reference/ai-skill.md` + `ai.md` 全文，对照本文差异 | 校准事实源 |

**起服务命令**：
```bash
# edit-service（IFC 侧，:8100）
cd services/ifc && VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100
# cad-edit-service（DXF 侧，:8200）
cd services/cad && VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8200
# Go server（:8090；API key 留空 = 离线模式，不产生真实智能回复）
cd server && go run ./cmd/server
# web（:5173）
cd web && npm run dev
```

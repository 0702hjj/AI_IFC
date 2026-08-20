# Agent 部署完整方案（2026-08-18 裁决版）

> 本文是 agent 编排改造的可执行方案，由 `agent_orchestrate.md` 的全天讨论收敛而来（Q 卡与论证过程见该文）。
> 读者：执行者（人或 subagent）。读完本文应能直接开工，无需回看讨论。

## 0. 一页速览

- **做什么**：把 agent 运行时从经典 `flow/agent/react` **迁移到 ADK**，skill 接入走官方 skill middleware + filesystem backend（ch09 直路），HITL 走官方 interrupt/resume。三级执行模型（交付/管线/探索）+ 交付工具在 ADK 上落地。
- **不做什么**：不在经典侧手工复原 skill 加载（官方方案只在 ADK）；不做子派子真嵌套（扁平化）；不动 SSE/REST 契约（前端零改动）。
- **总工作量**：Phase M0（ADK 运行时迁移）约 1-2 chunk；Phase M1（skill 官方接入）约 2 天；Phase M2-M4（交付工具/HITL/执行模型）各 1-3 天。
- **核心原则**：官方优先（能直接用 ADK 组件就不自创）· 领域逻辑单源（script_lib 先例）· 沙箱纪律单源（bwrap 参数模式）· SSE/REST 契约不破。

## 1. 背景与目标

平台 agent 当前是经典 `flow/agent/react`（W-0043 建成），skill 只有 persona 快照 + 契约机器层，厚参考文档/flows/断点确认无载体。**2026-08-19 裁决：迁移 ADK**——官方 skill 接入（`skill` middleware 挂上即有 `skill` 工具 + progressive disclosure + fork 模式）只存在于 ADK；经典侧只能自创薄壳「复原拼接」、效果无法保证。本方案以 ADK 迁移为主路径，落地完整 skill 能力。

## 2. 已裁决决策清单（2026-08-18 初版，2026-08-19 追加，不再讨论，执行依据）

| # | 裁决 | 备选/触发条件 |
|---|---|---|
| D1 | **迁移 ADK**（2026-08-19 裁决：官方 skill 接入（skill middleware）只存在于 ADK，经典侧只能自创薄壳、无法保证效果）——按 `server/internal/agent` 迁移到 ADK 运行时，skill 接入走官方 skill middleware + filesystem backend | 经典侧折中（薄壳）已验证成本高、效果无保证，放弃 |
| D2 | **skill 加载 = 官方 skill middleware（2026-08-19 更新，替代 O2 薄壳）**：`skill.NewTyped` 挂进 agent Handlers，自动获得 `skill` 工具 + progressive disclosure 系统提示词 + 工具描述渲染 + inline/fork 模式；`NewBackendFromFilesystem`（frontmatter 解析/扫描 100% 官方）+ `local` backend（真实磁盘 IO 官方）。**零自创加载逻辑** | 经典侧薄壳方案已验证成本高、效果无保证，废弃 |
| D3 | **三级执行模型**：交付级（现有 script_runner REST）/ 管线命令级（services/cad 白名单端点）/ 探索级（PyExecutor + 自实现 bwrap Operator）；层级分配按「产物去向×命令形态×爆炸半径」四问决策树 | 能力晋升路径：探索级脚本常用化 → CLI 化 → 白名单 → 门禁化 |
| D4 | **扁平化层级映射（方案 A）**：主 agent 直接当管线编排者（持管线工具 + 派 worker），深度预算 1 不动；「cad-agent 中间层」用工具分组替代 | 方案 B（真嵌套）触发条件：实测主 agent 上下文过载 |
| D5 | **flowops 留 Python 单源**：services/cad import（script_lib 先例）→ REST 暴露 → Go 薄代理；状态事实归 Python / 派发运行时归 Go / 派发决策归 prompt | 反例条件：状态推进需实时驱动跨域事件时 Go Core 消费状态事件，仍不搬状态机 |
| D6 | **断点确认 v1 = 对话确认**（报告遗留问题字段 + 派发边界断点）；结构化 question 留 Q-A 方案（`ask_user` 工具 + `ToolReturnDirectly` + `question.ask` SSE + `/answer` 端点，约 1-1.5 天） | Q-A 触发条件：实测对话确认不够用 |
| D7 | **design_review 门禁化 v1 = 报告回喂**（非拦截）；422 拦截严格度留 v2 裁决 | — |
| D8 | **PyExecutor 只挂子 agent（worker persona）**，主 agent 不挂——W-0043「子复用主工具集」的第一个有理例外 | — |
| D9 | **cad_script_lib 归宿**：倾向内联进 services/cad（它本质已是服务契约层），删 v1 的硬前置 | 删 v1/v2 前必须完成 |
| D10 | **subagent 编排：v1 保留自研 hub 过渡，M3 前迁官方 AgentAsTool**（2026-08-19 裁决）——v1 骨架 `subagent.go` 一行不动（New/Run 签名兼容，ADK 下照常工作）；全面迁移设计见 §3.3（翻译层按 RunPath 合成 subagentId 标签 + subagent/status，前端/SSE 契约不变）。自研 hub 没有官方 CompositeInterrupt，交付审批 HITL（M3）前必须迁 B | 若 M1 实测发现自研 hub 成为 skill 接入瓶颈，提前迁 B |
| D11 | **aiplan 双层分离：对话协调内联 orchestrator，工程执行走管线命令级**（2026-08-19 裁决）——aiplan 需要与用户对话交互（orchestrator 是唯一对话入口）且 orchestrator 需亲自理解 plan 产物才能对齐下游 cad/ifc，故 aiplan 的**对话协调层**由 orchestrator 内联（inline skill）；但 aiplan 工程上与 cad/ifc 等价（CLI 13 子命令 + 固定 schema plan.schema.json/bim_supplement + 固定落盘 {workspace}/plan/ + gate 门禁），其**工程执行层**走 M2 管线命令模式（白名单端点 + Go 薄代理 `run_aiplan_command`），orchestrator 不直挂 python（领域收敛） | 若 plan 阶段实测上下文过载，再评估 aiplan 脚本独立 worker |
| D12 | **skill 完整能力 = 官方 filesystem middleware（2026-08-19 调查修正）**——「读 skill 包内文件（references/）+ 执行 skill scripts」官方均有标准实现：`adk/middlewares/filesystem` 注入 `read_file/write_file/edit_file/glob/grep/ls` + 可选 `execute`（Shell/StreamingShell 配置时注册）；`local` backend 实现 Backend + StreamingShell（`/bin/sh -c`）。模型流程 = skill 工具拿 BaseDirectory → read_file/glob/grep 深读 references → execute 跑 skill CLI。**领域收敛 = local backend `Config.ValidateCommand` 白名单**（aiplan-*/aidxfv3-* 命令面枚举）；更强隔离（bwrap 路径 jail + unshare-net）挂 `filesystem.Shell` 接口后（替代自创 PyExecutor 薄壳）。DeepAgent（prebuilt/deep）是官方「标准包接入」形态（传 Backend+StreamingShell+Handlers 自动挂 filesystem middleware），我们当前 ChatModelAgent + 手动挂更可控（不引入 TaskTool） | 若实测 execute+ValidateCommand 覆盖不了，再评估 services 白名单端点族（M2-③ 保留） |

## 3. 目标架构（ADK 三角色）

```
浏览器 ChatSidebar ──SSE（契约不变）── Go server :8090
   └─ chat 模块（chat_*.go，SSE/REST 契约不动；事件源换 ADK AgentEvent）
   └─ agent 包（server/internal/agent，迁移到 ADK 运行时）
       ├─ Runner（官方）：EnableStreaming + CheckPointStore + ResumeWithParams
       │     ├─ AgentEvent 流 → 翻译层 2.0 → SSE（形状不变）
       │     ├─ interrupt/resume → HITL question（官方）
       │     └─ 事件落盘：保留 EventStore JSONL（记录 AgentEvent）
       │
       ├─ orchestrator-agent（挂 aiplan）
       │     adk.ChatModelAgent{ Instruction=OrchestratorPersona,
       │                          Handlers=[skill middleware(aiplan)] }
       │     工具 = 领域交付 + AgentAsTool(ifc/cad 子 agent) + 审批包装(save/deliver)
       │
       ├─ ifc-agent（挂 aiifc，AgentAsTool 派发）
       │     adk.ChatModelAgent{ Instruction=ifcAgentPersona,
       │                          Handlers=[skill middleware(aiifc)] }
       │     工具 = 交付 REST（get_script/stage/run/save/locate/edit-call）
       │
       └─ cad-agent（挂 aidxf，AgentAsTool 派发）
             adk.ChatModelAgent{ Instruction=cadAgentPersona,
                                  Handlers=[skill middleware(aidxf)] }
             工具 = 交付 REST + 管线命令(run_pipeline_command) + PyExecutor(worker)
services/ifc :8100 ── 交付级沙箱（现有）+ design_review 门禁化（Phase M3）
services/cad :8200 ── 交付级沙箱（现有）+ 管线白名单端点族（Phase M2）
                      + import flowops / aidxfv3 包（持久工作区 models/{id}/pipeline/）
```

挂载方案（A）：orchestrator 挂 `aiplan`、ifc-agent 挂 `aiifc`、cad-agent 挂 `aidxf`——每个角色都是**「自己的 agent 定义（Instruction + ToolsConfig）+ skill middleware」**，两者不冲突（skill middleware 只在 `BeforeAgent` 追加 progressive disclosure 提示词和 `skill` 工具，不改 agent 本体）。ifc/cad 子 agent 由 `adk.NewAgentTool` 派发（独立上下文，官方原生隔离）。

工作区约定：`{dataDir}/models/{id}/pipeline/`（三级执行物理同目录；VIEWER_DATA_DIR 三方共享 + ctx→modelId 解析两个既有不变量保证）。

## 3.0 skill 接入前置：标准化成 Eino 能扫的通用格式

**不是 npm。** 仓内已是 [Anthropic Agent Skills](https://github.com/anthropics/anthropic-sdk-python) 目录包（`SKILL.md` + frontmatter + `references/`）。Eino 官方加载器 `skill.NewBackendFromFilesystem` 扫的就是这套。

> **2026-08-19 约定：agent 只面对 `skills/dist/`（正式发布集合），不感知开发版本**
> `server/internal/agent` 的 `skillsDir` 指向 `../skills/dist`——仓库打包器（`tools/skill_pack.py`）
> 产出的正式集合（aidxf / aiplan / aiifc，frontmatter name 正确 + 第一层 SKILL.md）。
> 开发版本（`skills/aidxfv/v1|v2|v3` 等）是 skill 侧开发目录，agent 不接触。

```
skillsDir/                 <-- server_config.skillsDir = ../skills/dist
  <frontmatter.name>/
    SKILL.md               <-- 必有, 以 --- YAML --- 开头
    requirements.txt       <-- 仓内打包器基线合同
    references/            <-- 官方 skill 工具加载后按需深读（filesystem backend）
    scripts/               <-- python_execute / 管线命令
```

只扫 **BaseDir 下第一层子目录** 的 `SKILL.md`。`name` 必须等于目录名。

仓内现状（2026-08-19 已就绪）：

```
skills/aiifc/              name: aiifc   version 0.1.1   已登记 registry，已打 aiifc-0.1.1.tar.gz
skills/aiplan/             name: aiplan  version 1.0.0   已登记 registry，已打 aiplan-1.0.0.tar.gz
skills/aidxf/              name: aidxf   version 3.0.0   已登记 registry，已打 aidxf-3.0.0.tar.gz
skills/aidxfv/v1|v2        遗留（cad_script_lib 依赖，Phase 1 迁走后删）
```

三个接入包都已顶层化、frontmatter 齐备、registry 登记、tar.gz 产出（`skills/dist/`）。

前置怎么搞（不新发明格式）：

```
1. 打扁平安装树（给 Eino，不是 npm）
   python tools/skill_pack.py --skill-dir skills/aiifc --archive
   python tools/skill_pack.py --skill-dir skills/aiplan --archive
   python tools/skill_pack.py --skill-dir skills/aidxf --archive
   解压到同一 skillsDir:
     skillsDir/aiifc/SKILL.md
     skillsDir/aiplan/SKILL.md
     skillsDir/aidxf/SKILL.md      <-- 目录名 = frontmatter.name

2. 开发期可软链，不必每次打 tar
   mkdir -p skills/eino
   ln -sfn ../../skills/aiifc      skills/eino/aiifc
   ln -sfn ../../skills/aiplan     skills/eino/aiplan
   ln -sfn ../../skills/aidxf      skills/eino/aidxf
   server_config.skillsDir = skills/eino

3. ADK skill middleware 按方案 A 挂载（官方直路，无自创加载逻辑）
   skill.NewTyped(Backend=NewBackendFromFilesystem(BaseDir=skillsDir))
   挂进 agent Handlers → 自动获得 `skill` 工具 + progressive disclosure
   总控    挂 aiplan（skill middleware）
   ifc-agent 挂 aiifc
   cad-agent 挂 aidxf
```

`skill_pack.py` 已做：校验 SKILL.md / requirements.txt / frontmatter / 无噪声，复制到 `skills/dist/`，可选 tar.gz。**不要改成 npm**——Eino 和 Claude Code / opencode 消费的都是目录 + SKILL.md，不是 node_modules。

## 3.1 当前 agent 形态 vs 官方 FLOW（6/7/8）

`server/internal/agent` **已经是 Supervisor**：主 agent 不建模，经 `dispatch_*` 派子 agent（≈ 例 8 的主管 + 例 7 的 SubAgents/AgentAsTool）。缺的是例 7 的 **FollowUp：模型自己判断时机调提问工具**。

```
  官方 8 Supervisor          官方 7 DeepAgent            咱们现在
  ----------------           ----------------            ----------
  主管                       DeepAgent 主 agent          OrchestratorPersona
    |                          |                           |
    +-- research               +-- FollowUpTool  <--缺     +-- 文字确认（软）
    +-- PlanExecute            +-- ResearchAgent           +-- dispatch_ifc
         |                          (AgentAsTool)          +-- dispatch_cad
         +-- allocate_budget       +-- AnalysisAgent            |
             (审批包装,强制)            (AgentAsTool)            子 agent
                                                                  无 question
```

自主 question 应对齐 **例 7**（模型调工具），不要对齐例 8 的强制包装（那是 save/deliver 用的）。

```
 用户说话
    |
    v
 +-- 主 agent（ADK ChatModelAgent，意图路由）----------------------+
 |  工具: AgentAsTool(子) | skill 工具(官方) | locate/edit-call |  |
 |  纪律: 破坏性大改先问人；S0-S4 断点由子 agent 自己问            |
 |                                                               |
 |     合适时机 ──> skill 断点 ──> StatefulInterrupt ──> 挂起     |
 |                      |                                        |
 |                      v                                        |
 |              SSE question.ask --> 前端卡片 --> /answer         |
 |                      |                                        |
 |                      v                                        |
 |          Runner.ResumeWithParams(interruptID, 回答) → 续跑     |
 |                                                               |
 |     意图匹配 ──> AgentAsTool 派 ifc/cad 子 agent                |
 |                      |                                        |
 |                      v                                        |
 |              +-- 子 agent（ADK ChatModelAgent + skill middleware）+
 |              |  skill 工具（官方，加载 SKILL.md + references） |  |
 |              |  领域工具 / 管线命令                           |  |
 |              |  断点 interrupt（读 SKILL.md 后模型自己决定）  |  |
 |              +------------------------------------------------+  |
 +---------------------------------------------------------------+
```

**何时问**：不写死在 Go 里。persona + SKILL.md（MUST 断点）进上下文后，模型自己调 skill/提问触发 interrupt。平台提供官方中断/恢复通道。

**两套 HITL 不要混**：

```
  开放确认（四轮、S0-S4 草案）  -->  工具内 StatefulInterrupt   对齐 FLOW 7
  固定危险动作（save/deliver）  -->  工具外包「调了先问」       对齐 FLOW 6/8
```

ADK 用官方 `StatefulInterrupt` + `Runner.ResumeWithParams`（原语在 `components/tool/interrupt.go`，参考实现 `adk/common/tool/follow_up_tool.go`）。v1 可先靠报告「遗留问题」字段（零通道）；要弹框再上官方 interrupt。

## 3.2 工具清单：官方已有 vs 自己封装

迁移 ADK 后，agent 的工具分三类——**官方直接可用**、**官方参考 + 平台封装**、**纯平台封装**。

### 官方已有（直接用，零自创）

| 工具/能力 | 官方来源 | 用途 |
|---|---|---|
| `skill` 工具 | `skill.NewTyped` middleware 自动注入 | 加载 SKILL.md（progressive disclosure） |
| 文件工具组（read/write/edit/glob/grep） | `filesystem` middleware / DeepAgent Backend | 读写工作区文件、skill references 深分页（skill BaseDirectory → read_file/glob/grep） |
| `execute`（命令执行） | `filesystem` middleware Shell/StreamingShell + `local` backend | 执行 skill 捆绑 CLI（aiplan-*/aidxfv3-*）；领域收敛 = local `ValidateCommand` 白名单（D12） |
| `AgentAsTool` | `adk.NewAgentTool` | 子 agent 当工具派发（独立上下文） |
| interrupt/resume | `tool.StatefulInterrupt` + `Runner.ResumeWithParams` | HITL 断点 |
| python 探索执行 | `filesystem.Shell` 接口 + bwrap Operator（D12 修正，替代自创 PyExecutor 薄壳） | 探索级 python 执行（M4） |
| 会话/CheckPoint | `adk.Runner` + CheckPointStore | 中断持久化 |

### 官方参考 + 平台封装（examples 有实现，套到我们工具上）

| 工具 | 官方参考 | 平台要做的 |
|---|---|---|
| question 断点 | `follow_up_tool.go`（问开放问题） | 用它触发 S0-S4 断点；SSE `question.ask` + `/answer` 端点 |
| 交付审批 | `approval_wrapper.go`（Y/N）+ ch09 `approvalMiddleware` | 包 `save_script`/`deliver`：调了先问 |
| 审阅改参 | `review_edit_wrapper.go`（改 JSON） | 交付前允许用户改参数再执行 |

### 纯平台封装（官方无对应，必须自写）

| 工具 | 内容 | 为什么自写 |
|---|---|---|
| 领域交付工具 | get_script / stage / run / save / versions / diff / locate / edit-call / create_project | 调 services REST（:8100/:8200），平台业务 |
| `run_pipeline_command` | cad 管线白名单命令（preprocess/normalize/...） | 平台业务（services/cad） |
| bwrap Operator | PyExecutor 的 Operator 实现（路径 jail + bwrap） | 官方只有 DockerSandbox，bwrap 自写（沙箱纪律单源） |
| 持久工作区绑定 | Operator 里 cwd→`models/{id}/pipeline/` | 平台数据目录约定 |

### 交付 tool 能否在流程中定义——能，两种官方形态

**问题**：最终交付（save_script / deliver）要「先用户确认 → 执行 → design_review → 报告」，这能不能作为流程定义而不是散在 persona 里？

**答案：能。官方两种方式，推荐 ①。**

**① middleware 拦截（推荐，ch09 就是它）**：

```go
// 定义一个交付审批 middleware：拦指定的交付工具，先 interrupt 等用户确认
func (m *deliveryMiddleware) WrapInvokableToolCall(_ context.Context, endpoint adk.InvokableToolCallEndpoint, tCtx *adk.ToolContext) (adk.InvokableToolCallEndpoint, error) {
    if !isDeliveryTool(tCtx.Name) { return endpoint, nil }   // 只拦 save/deliver
    return func(ctx context.Context, args string, opts ...tool.Option) (string, error) {
        wasInterrupted, _, stored := tool.GetInterruptState[string](ctx)
        if !wasInterrupted {
            return "", tool.StatefulInterrupt(ctx, &ApprovalInfo{ToolName: tCtx.Name, ArgumentsInJSON: args}, args)
        }
        // resume 后：approved → 真正执行 → design_review → 返回报告
        ...
    }, nil
}
```

**流程固化在 middleware**（不是 persona）：交付 = 确认 → 执行 → review → 报告，作为一条确定的工具拦截链。模型无法绕过（指定工具名拦死）。

**② Graph Tool（确定性流程 tool 化）**：把「确认→执行→review→报告」用 `compose.Graph` 定义成 workflow，`graphtool.NewInvokableGraphTool` 包成单个 tool。适合交付流程固定、多步并行时。

**选型**：单工具审批用 ①（轻、与 ch09 同构）；跨多工具的交付流水线（save + review + 归档）用 ②。我们交付级单工具（save/deliver）先 ①。

### subagent 编排：路线 A（保留自研 hub）vs 路线 B（官方 AgentAsTool）

> 2026-08-19 裁决：v1 骨架已落地（引擎 ADK 化 + skill 官方接入），**subagent 编排保留自研 hub 过渡**。
> 本小节记录两条路线的权衡与路线 B 的完整设计（M0-④ 的细化），供 D 系列执行时直接照做。

**背景**：v1 骨架把 `react.NewAgent` 换成 `adk.ChatModelAgent + Runner`，`subagent.go` 一行未动——因为 `New()/Run()` 签名不变，自研 hub 在 ADK 下照常工作（子 agent 底层也是 ADK）。但自研 hub 不是终态：**没有官方 CompositeInterrupt 跨边界中断传播**，走到 M3（交付审批 HITL）必须迁 B。

**官方 AgentAsTool 能力（源码：`eino@v0.9.13/adk/agent_tool.go`）**：

| 能力 | 说明 | 源码 |
|---|---|---|
| 子 agent 包装为工具 | `adk.NewAgentTool(ctx, agent)` → `tool.BaseTool`，工具名/描述 = 子 agent Name/Description | `agent_tool.go:93` |
| 输入 schema | 默认 `{"request": "..."}`；`WithAgentInputSchema` 自定义；`WithFullChatHistoryAsInput` 传全历史 | `:47-61` |
| 事件实时上浮 | 主 agent `ToolsConfig.EmitInternalEvents=true` → 子 AgentEvent 转发父 Runner 流 | `chatmodel.go:145` / `agent_tool.go:234` |
| RunPath 层级 | 转发时拼接父+子 RunPath（根→子路径，事件来源可追溯） | `agent_tool.go:236-241` |
| 子事件不进父 runSession | 仅发给用户，不写父状态/checkpoint（天然 Project 隔离） | `agent_tool.go:80-82` |
| Action 边界隔离 | 子 agent 的 Exit/TransferToAgent/BreakLoop 出不了工具边界；Interrupted 经 CompositeInterrupt 传播 | `agent_tool.go:84-92` |
| 跨边界 HITL | 子 agent interrupt → CompositeInterrupt → 父 Runner 捕获 → Resume 恢复 | `:251-262` |
| 独立 checkpoint | bridgeStore（工具内独立 CheckPointStore）+ `withSharedParentSession`（共享会话值） | `:164-198` |

**装配形状（路线 B 目标态，替换 `SubagentTools`）**：

```
orchestrator-agent（Instruction=OrchestratorPersona，Handlers=[skillMW(aiplan) + skillMW(aibim-orchestrator), safeToolMW]）
  ToolsConfig:
    Tools = DomainTools
          + run_aiplan_command（aiplan CLI 管线薄代理，见下「aiplan 双层分离」）
          + AgentAsTool(ifc-agent) + AgentAsTool(cad-agent)
    EmitInternalEvents = true
        │                       │
        v                       v
  ifc-agent（aiifc skillMW）  cad-agent（aidxf skillMW）
  独立 ChatModelAgent          独立 ChatModelAgent
  Tools = IFC 领域工具          Tools = CAD 领域工具（+ 管线/PyExecutor，M2/M4）
  无 AgentAsTool（深度 1）      无 AgentAsTool（深度 1）
```

**aiplan 双层分离（D11）**——aiplan 不是纯软流程，工程上与 cad/ifc 等价（CLI 13 子命令 + 固定 schema + 固定落盘 + gate 门禁），但它的对话协调必须由 orchestrator 亲自做：

| 层 | 归谁 | 为什么 |
|---|---|---|
| 层 1 对话协调 | orchestrator **内联** aiplan skill（inline） | aiplan 核心是「与用户自然语言交互确认设计意图」；orchestrator 是唯一对话入口，且亲自做 plan 才懂 plan.json 字段、派发 cad 时才能对齐产物 |
| 层 2 工程执行 | `run_aiplan_command` 工具 → services 白名单端点 → aiplan CLI | aiplan 有固定脚本/产物（`derive/normalize/gate/land` → `{workspace}/plan/plan.json`），与 cad 管线命令同构（M2 模式复用）；orchestrator 不直挂 python（领域收敛） |

```
orchestrator 内联对话（框定 design_intent）
  → run_aiplan_command: derive（派生事实）→ normalize（语义→坐标）
  → run_aiplan_command: gate（落盘前质量门禁，强制）
  → run_aiplan_command: land（成对落盘 {workspace}/plan/plan.json + bim_supplement.json）
  → AgentAsTool(cad-agent)：读 plan.json + 用户描述对齐（orchestrator 亲自做过 plan，天然懂字段）
```

aiplan 命令集（白名单枚举，与 cad 管线命令族并列）：`derive / normalize / gate / land / validate(plan|bim|intent) / route / canon / geom / area`。

**层次感三保证（路线 B，前端/契约不变）**：

| 原本的层次感来源 | 路线 B 的对应设计 | 不变点 |
|---|---|---|
| 子事件打 subagentId/parentSessionId 标签，前端分流边栏 | 翻译层按 `event.RunPath` 深度合成：深度 1=父（无标签）、≥2=子（分配 `sa_{turn}_{seq}` + parentSessionId） | 平台 Event 的 SubagentID/ParentSessionID 字段语义不变 |
| 父模型上下文不含子内容（dispatch 结果回流） | 官方 EmitInternalEvents 子事件不写父 runSession；我们落盘后 `Project` 跳过 SubagentID 非空（现有逻辑） | `Project` 行为不变 |
| 深度预算 1（结构性） | 子 agent ToolsConfig 不含 AgentAsTool（嵌套=嵌套深度，结构性） | 结构性限制不变 |
| `subagent/status`（started/finished） | 官方无此事件——翻译层维护子边界状态：首个子事件 → 合成 started；RunPath 回父 → 合成 finished | 事件类型不变，翻译层合成 |

**翻译层升级要点（events.go §4 adkTranslator）**：

```go
// 伪代码：RunPath 深度判定父子 + subagentId 分配
func (t *adkTranslator) run(ctx, iter) {
    var curSub *subagentCtx   // 当前子边界（id、seq）
    for ev := range iter {
        if isChildEvent(ev.RunPath) {        // len(RunPath) >= 2
            if curSub == nil { curSub = t.beginSub(ev.RunPath) }  // 合成 subagent/status started
            ev.SubagentID = curSub.id        // sa_{turn}_{seq}
            ev.ParentSessionID = sessionID
        } else if curSub != nil {
            t.endSub(curSub)                 // 合成 subagent/status finished
            curSub = nil
        }
        // 其余映射逻辑不变（assistant/tool/chunk/error）
    }
    if curSub != nil { t.endSub(curSub) }    // 收尾兜底
}
```

**两条路线决策表**：

| 维度 | A：保留自研（现状+增强） | B：AgentAsTool 全面迁移 |
|---|---|---|
| 子 agent 挂 skill | 可加（runChild 传 WithSkillsDir） | 天然（子 agent 自己配 Handlers） |
| HITL 跨边界（M3 前置） | ❌ 无 CompositeInterrupt | ✅ 原生 |
| RunPath 层级追踪 | ❌ 手动标签 | ✅ 官方 |
| 前端/SSE 契约 | 不变（已绿） | 不变（翻译层合成标签，chat_translate.go 零改动） |
| 改动量 | 小（subagent.go 不动） | 大（subagent.go 重写 + 翻译层升级 + 测试重写） |
| 风险 | 低 | 中（行为变化集中在翻译层） |

**结论**：
- **现在（v1→M1 阶段）走 A**：先做 A1/A2 增强（见下），不动契约、低风险。
- **M3 之前必须迁 B**：交付审批（HITL）需要官方中断传播，自研 hub 到不了那里。迁移时按本小节设计执行，翻译层 RunPath 标签化 + subagent/status 合成为主要改动面。

**路线 A 增强清单（D 系列前可做）**：
- A1：`SubagentConfig` 加 skill 目录（按 persona 派生：ifc→aiifc / cad→aidxf），runChild 的 `New` 补 `WithSkillsDir`。
- A2：`MakeTools(persona)` 按 persona 分离工具面（ifc-agent 只挂 IFC 工具 / cad-agent 只挂 CAD 工具，当前全量 DomainTools）。
- A3：验证项已绿：`TestSubagentChildInheritsParentSessionBinding`（ADK 子 run 的 SessionIDFromContext 继承父绑定）。

## 4. 工作分解（ADK 迁移主路径）

### Phase M0：agent 运行时迁移到 ADK（核心，约 1-2 chunk）

把 `server/internal/agent` 从经典 `flow/agent/react` 迁移到 ADK 运行时，**SSE/REST 契约逐字段不变**（W-0043 红线，前端零改动）。

| # | 工作项 | 内容 | 位置 |
|---|---|---|---|
| M0-① | 运行时替换 | `react.NewAgent` → `adk.NewChatModelAgent`（Instruction/ToolsConfig/MaxIterations）；`Agent.Run(chan Event)` → `Runner.Run(AsyncIterator[AgentEvent])` | `agent/agent.go` 重写 |
| M0-② | 事件采集层 | 自研 runEmitter（callbacks 观测）→ Runner 的 AgentEvent 流直读；事件类型映射到现有 9 种或直接 AgentEvent | `agent/agent.go` |
| M0-③ | 翻译层 2.0 | `chat_translate.go` 源映射：callbacks 事件 → ADK AgentEvent（流式 Message → part.delta；ToolCall/Result → 工具卡片；interrupt → question 帧）；**SSE 帧形状/id 约定不变** | `api/chat_translate.go` 重写 |
| M0-④ | 子 agent 派发 | ✅ **2026-08-19 完成（路线 B）**：自研 subagentHub → 官方 `adk.NewAgentTool`（三角色：orchestrator 领域工具 + AgentAsTool(ifc/cad) + EmitInternalEvents；子事件经 RunPath 合成 subagentId + subagent/status，见 §3.3 路线 B）；深度预算 1 = 子 agent 无 AgentAsTool | `agent/agents.go` + `events.go` §4 |
| M0-⑤ | 会话/事件落盘 | 保留 EventStore JSONL（记录 AgentEvent）或切换 CheckPointStore；投影规则同步改 | `agent/events.go` |
| M0-⑥ | HITL 接线 | ✅ **2026-08-19 agent 侧完成**：`ask_user` 工具（官方 StatefulInterrupt 对齐）+ in-memory CheckPointStore（Runner 已配）+ `Agent.Resume`（升级 zrefResumeWith）+ 翻译层 `question/ask` 帧（`onInterrupt`）；剩余：SSE `question.ask` 翻译 + `/answer` 端点 | `agent/ask_user.go` + `agent/hitl.go` + `events.go` §4 |
| M0-⑦ | scriptedModel 确定性 | 验证 ADK ChatModelAgent 兼容 scriptedModel（同脚本两跑事件序列全等）；测试基座重钉 | `agent/scripted.go` |

**顺序**：M0-①②③（运行时 + 事件 + 翻译，一次 PR）→ M0-④⑤（子 agent + 落盘）→ M0-⑥⑦（HITL + 测试基座）。
**契约红线**：SSE 帧形状 / 7 路由 / envelope / 前端零改动；每步跑既有 chat 契约测试对拍。

### Phase M1：skill 官方接入（约 2 天）

官方 skill middleware 挂载（ch09 直路），零自创加载逻辑。

| # | 工作项 | 内容 | 位置 |
|---|---|---|---|
| M1-① | skill middleware | `skill.NewTyped`（Backend=local filesystem）挂进三个角色 agent 的 Handlers；自动获得 `skill` 工具 + progressive disclosure 系统提示词 + 工具描述渲染 | `agent` 装配 |
| M1-② | 挂载方案 A | ✅ **2026-08-19 落地（第一层角色映射）**：orchestrator 挂 `aiplan`；ifc-agent 挂 `aiifc`；cad-agent 挂 `aidxf`——`filteredSkillBackend` 过滤（跨角色调用被拒）；路由纪律进 OrchestratorPersona（CAD 必须先 aiplan、IFC 直接 ifc-agent、问答直接答） | `agent/agents.go` |
| M1-③ | 配置 | `skillsDir`（env `VIEWER_SKILLS_DIR`，默认 `./skills/dist`——agent 只面对正式发布集合，不感知开发版本） | `cmd/server/main.go` |
| M1-④ | 依赖 | `eino-ext/adk/backend/local`（官方真实磁盘 backend）进 go.mod | `go.mod` |

### Phase M2：skill 完整能力 + 管线命令级（约 2-4 天）

前置：A2 半天实测（`aidxfv3 normalize` 跑通）验证体感。

| # | 工作项 | 内容 | 位置 |
|---|---|---|---|
| M2-0 | **官方 filesystem middleware 挂载（D12）** | ✅ **2026-08-19 落地**：orchestrator/子 agent 的 Handlers 挂 `newFilesystemMiddleware`（Backend=fsReadOnlyBackend 读透传/写拒绝 + StreamingShell=local with `validateSkillCommand` 白名单 aiplan/aidxfv3）→ 模型获得 read_file/glob/grep（读 skill references）+ execute（跑 skill CLI）；契约测试 5 个（`fs_backend_test.go`） | `agent/fs_backend.go` + `agents.go` |
| M2-① | cad_script_lib 内联 | 从 `skills/aidxfv/v1/scripts/flows/` 迁入 `services/cad`（D9，删 v1 硬前置） | `services/cad/app/` |
| M2-② | 持久工作区沙箱 | bwrap bind `models/{id}/pipeline/`（plan 产物 `{workspace}/plan/` 同区） | `services/cad` |
| M2-③ | 管线白名单端点族（保留备选） | `POST /models/{id}/pipeline/{cmd}`（白名单枚举，verify* 单点，退出码 0/1/2）；命令集覆盖 **cad 管线**（preprocess/normalize/...）+ **aiplan 命令**（derive/normalize/gate/land/validate/route/canon/geom/area，D11）。**与 M2-0 的 execute+ValidateCommand 二选一或并存**：交付级强隔离走端点，普通 skill scripts 走官方 execute | `services/cad/app/routes_pipeline.py`（新） |
| M2-④ | flowops/aiplan_tools 包入环境 | ✅ **2026-08-19 落地（独立 skill venv）**：`tools/install_skill_venv.sh` → `skills/.venv`（aiplan_tools + aidxf 5 包 + aidxfv3 主包，--no-deps 规避 PyPI 本地依赖解析）；`skillVenv` 注入 PATH（main 装配）+ `skillCLI` 白名单配置化（`SetSkillCommandAllowlist`）；集成测试 `TestExecuteRunsSkillCLI`。**aidxfv3 入口原生修复**：源 + dist 的 pyproject.toml 补 `[project.scripts] aidxfv3 = "aidxfv3.cli:main"`（pip 生成 console_scripts，无 shim） | `tools/install_skill_venv.sh` + `cmd/server/main.go` + `agent/fs_backend.go` + `skills/{aidxf,dist/aidxf}/scripts/aidxfv3/pyproject.toml` |
| M2-⑤ | Go 泛化工具（按 M2-0/M2-③ 选型后） | 若走端点：`run_pipeline_command` + `run_aiplan_command`；若走 execute 白名单：无需 Go 工具（execute 直跑 CLI） | `agent` 工具面 |

### Phase M3：交付工具补齐 + HITL 断点（约 1-2 天）

| # | 工作项 | 内容 | 位置 |
|---|---|---|---|
| M3-① | `get_script_locate` / `edit_script_call` | 薄代理 locate / edit-call（定点标量改写） | `agent` 工具面 |
| M3-② | design_review 门禁化 v1 | 沙箱内自动跑 design_review，报告随 run/save 响应返回（非拦截） | `services/ifc/script_runner.py` |
| M3-③ | HITL question | 官方 interrupt/resume → `question.ask` SSE + `/answer`；交付工具（save/deliver）外包审批（例 6/8 形态） | `api/chat_*` |

### Phase M4：探索级执行（约 1-2 天）

> 2026-08-19 修正（D12）：不再自创 PyExecutor 薄壳——官方 `filesystem.Shell` 接口 + bwrap Operator 实现。

| # | 工作项 | 内容 | 位置 |
|---|---|---|---|
| M4-① | bwrap Operator | 自实现 `filesystem.Shell`/`StreamingShell` 接口（路径 jail + bwrap，参数照抄 script_runner.py:159-172）——替代 local 裸 `/bin/sh -c`，作为 filesystem middleware 的 StreamingShell | `server/internal/agent/`（新 `shell_bwrap.go`） |
| M4-② | python_execute 挂载 | 探索级 python 执行挂 bwrap Shell（worker persona，D8）；`python_execute {code}` 命令进 ValidateCommand 白名单 | `agent` 装配 |

### 条件触发项（不主动做）

- 方案 B 真嵌套：ADK RunPath 原生支持，需要时配置化（D4 触发：主 agent 上下文过载）。
- 跨 turn 记忆：ADK SessionValues / CheckPointStore 原生，迁移后评估是否需额外截断策略。

## 5. 测试要求（仓内硬规则，逐条对应）

1. **新增测试量 ≥ 新增实现量**；TDD：先失败测试后实现。
2. M0-①-③：SSE 帧形状/7 路由/envelope 对拍（既有 chat 契约测试改造成 ADK 契约钉）；翻译层 2.0 逐字段（Message→part.delta、ToolCall→工具卡片、interrupt→question 帧）。
3. M0-④：AgentAsTool 子 agent 事件透传（AgentName/RunPath → subagentId 映射）；深度预算 1（子工具面无 agent tool）；独立上下文断言。
4. M0-⑥：interrupt/resume 全流程（中断事件带 interruptID → 回答注入 → ResumeWithParams 续跑）；取消语义。
5. M0-⑦：scriptedModel 确定性（同脚本两跑事件序列全等）；测试基座重钉。
6. M1：skill 官方接入——`skill` 工具加载 SKILL.md、frontmatter 渲染、progressive disclosure 系统提示词；挂载方案 A（主 aiplan / ifc aiifc / cad aidxf）断言；真实 `skills/` 目录集成。
7. M2：管线端点契约测试（每命令入参 schema/退出码映射/工作区隔离）；白名单拒绝非枚举 cmd。
8. M3-①②：locate/edit-call 薄代理（kind 路由/错误文本化/守卫）；design_review 报告随响应返回（非拦截）。
9. 全部走 scriptedModel 确定性测试；异步写盘用条件等待，禁止固定 sleep。

## 6. 配置与部署变更

| 配置 | 默认 | 说明 |
|---|---|---|
| `skillsDir`（server_config.json / env `VIEWER_SKILLS_DIR`） | `./skills/dist` | **正式发布集合**（agent 只面对 dist，不感知 aidxfv/v1/v2/v3 等开发版本）；skill middleware 的 BaseDir |
| go.mod | — | M1 新增 `eino-ext/adk/backend/local`；M4 新增 `eino-ext/components/tool/commandline` |
| services/cad 依赖 | — | M2 新增 shapely + aidxfv3 包路径 |
| services/ifc | — | M3 design_review 在沙箱内运行，无新依赖（flows_dir 已有） |

无 SSE/REST 契约变更（M0 契约红线：前端零改动，SSE 帧形状逐字段不变）。`docs` 漂移检测：新增工具不进 OpenAPI（agent 工具非 REST 端点），M3 若改 run/save 响应形状需跑 `cd docs && npm run gen:api && npm run check:api`。

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| ADK pre-1.0 版本跟随（v0.3/v0.8 有 breaking） | 迁移时锁版本（go.mod 固定）；契约测试兜底；ADK 是官方主推、迁移后获得官方维护 |
| SSE 契约破坏（迁移最大风险） | M0 契约红线：翻译层 2.0 逐字段对拍，前端零改动；既有 chat 契约测试改造成对拍钉 |
| scriptedModel 确定性在 ADK 下不成立 | M0-⑦ 先实测（同脚本两跑事件序列全等），不成立则测试基座改用 ADK 官方 mock/离线模式 |
| skill middleware 语义与预期差异 | 参考 ch09 官方演示逐项对拍（skill 工具入参、progressive disclosure、工具描述渲染） |
| design_review 拖慢 run/save | 计入 60s 预算；v1 非拦截，失败仅报告 |
| EventStore 无界增长 | 长会话 JSONL 无限增长 + Load 全量读内存；M0 迁移时评估 CheckPointStore 或压缩策略 |
| A2 实测发现扁平化不够用（主 agent 上下文过载） | 触发 D4 方案 B：ADK RunPath 原生支持嵌套，配置化启用 |

## 8. 回退策略

- **M0 迁移前**：git 分支保留完整经典侧实现，`server/internal/agent` 可在任何阶段 checkout 回退。
- **M0 逐阶段**：每阶段独立 PR + 契约对拍通过才合入；任一阶段失败即回退该阶段，不继续。
- M3 端点族独立路由文件，可整体下线；cad_script_lib 内联是移动不是删除，v1 保留至 M2 验收后再删。
- 任何阶段出问题：回退 = 切回经典侧分支，平台回到 W-0043 现状。

## 附：关键代码位置索引

| 用途 | 位置 |
|---|---|
| 领域工具面（规范范例） | `server/internal/agent/tools.go`（mustTool/错误文本化/64KB/kind 路由 resolve） |
| 装配 | `server/internal/api/chat_tools.go`（DomainTools/SubagentAgentTools/AgentToolDeps） |
| 官方 skill middleware | `eino@v0.9.13/adk/middlewares/skill/`（skill.go:192 NewTyped / :360 typedSkillTool / filesystem_backend.go:49） |
| 官方 filesystem middleware（D12） | `eino@v0.9.13/adk/middlewares/filesystem/filesystem.go`（read_file:611 / execute:1009 / MiddlewareConfig:222）；`local@v0.2.1/local.go`（Backend+StreamingShell，ValidateCommand:42） |
| 官方 skill 完整 demo | `eino-examples/quickstart/chatwitheino/cmd/ch09/main.go`（装配 + handleInterrupt） |
| 官方 local backend | `eino-ext/adk/backend/local@v0.2.1` |
| HITL 参考实现 | `eino-examples/adk/common/tool/follow_up_tool.go`（question）/ `approval_wrapper.go`（审批）/ `review_edit_wrapper.go`（改参）；`eino@v0.9.13/components/tool/interrupt.go`（原语） |
| Graph Tool（交付流程 ②） | `eino-examples/quickstart/chatwitheino/cmd/ch08` + `graphtool.NewInvokableGraphTool` |
| 沙箱参数照抄点 | `services/ifc/app/script_runner.py:159-172`（bwrap 调用） |
| 静态门/契约校验范例 | `services/ifc/app/script_runner.py:121-139`（sys.path import script_lib 先例） |
| edit-call/locate 端点 | `services/ifc/app/routes_scripts.py:514+`（EditCallBody: designKey/argument/value 标量强校验） |
| 管线命令契约事实源 | `skills/aidxfv/v3/references/machine_contract.md` |
| flowops 状态机 | `skills/aidxfv/v3/scripts/packages/flowops/src/flowops/orchestrate.py` |
| 讨论与论证全过程 | `docs/internal/expectation_correct/agent_orchestrate.md`（Q 卡 + 第八节） |

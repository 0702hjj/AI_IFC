# agent 目标框架（ADK）

对照官方 HITL 例 6/7/8 与 ch09 skill 演示。迁移决策见 `agent_deployment_plan.md`（D1 翻转：迁 ADK）。
本文是**目标形态**——ADK 运行时 + 官方 skill middleware + 官方 HITL。现状规范见 `api_regulation.md`。

取舍：例 7 的「模型自己问」（官方 interrupt）+ 例 7/8 的「子 agent 当工具」（官方 AgentAsTool）
+ 例 6/8 的「危险工具外包审批」（官方 middleware 拦截）。**全部走官方组件，不自创。**

```
  取 7 FollowUp            取 7/8 AgentAsTool         取 6/8 审批包装
  模型 StatefulInterrupt   AgentAsTool 派子 agent     WrapInvokableToolCall
        \                     |                        /
         +--------------------+-----------------------+
                              |
                   咱们目标：ADK 三角色
                   orchestrator(aiplan) / ifc(aiifc) / cad(aidxf)
                   + 官方 skill middleware
                   + 通用 python 沙箱
                   + 标准交付工具（流程可固化）
```

## 1. 总图

```
 用户
   |
   v
 ChatSidebar SSE (形状不变)
   |
   v
 +==================== Runner (adk) ======================+
 |  EnableStreaming + CheckPointStore + ResumeWithParams  |
 |     AgentEvent 流 --> 翻译层 2.0 --> SSE (形状不变)     |
 |     interrupt/resume --> HITL question (官方)          |
 |     事件落盘：EventStore JSONL (记录 AgentEvent)        |
 +==========================+============================+
                            |
                            v
  +============= orchestrator-agent (aiplan 内联) ============+
  |  adk.ChatModelAgent                                        |
  |  Instruction = OrchestratorPersona (意图路由+派发纪律)      |
  |  Handlers    = [skill middleware(aiplan) +                  |
  |                 skill middleware(aibim-orchestrator)]      |
  |  工具 = 领域交付 + run_aiplan_command (D11 工程层)          |
  |       + AgentAsTool(ifc/cad) + 交付审批 middleware          |
  +==========================+============================+
                |                          |
    AgentAsTool |                          | AgentAsTool
                v                          v
 +============ ifc-agent (aiifc) =====+ +======== cad-agent (aidxf) =====+
 |  ChatModelAgent                    | |  ChatModelAgent                |
 |  Instruction = ifcAgentPersona     | |  Instruction = cadAgentPersona |
 |  Handlers = [skill middleware]     | |  Handlers = [skill middleware] |
 |  工具 = 交付 REST (get_script/      | |  工具 = 交付 REST +             |
 |        stage/run/save/locate/      | |        run_pipeline_command +  |
 |        edit-call)                  | |        PyExecutor (worker)     |
 +============+============+==========+ +========+============+==========+
              |            |                       |            |
              v            v                       v            v
       交付 REST 沙箱    python 沙箱          交付 REST 沙箱   skill 包只读
      services :8100   bwrap Operator       services :8200   skills/{name}/
      /:8200 沙箱      PyExecutor+Operator                   SKILL.md + refs
```

## 2. skill 官方接入（ch09 直路，零自创加载逻辑）

挂载方案 A：**每个角色 = 自己的 agent 定义 + 对应 skill 的 middleware**，两者不冲突。

```
 装配（一个角色一份）
   backend    = local.NewBackend(...)                    // 官方：真实磁盘
   skillBack  = skill.NewBackendFromFilesystem(backend, skillsDir)  // 官方：扫描+frontmatter
   skillMW    = skill.NewTyped(Backend: skillBack)       // 官方 middleware

   agent := adk.NewChatModelAgent(adk.ChatModelAgentConfig{
       Instruction: <角色 persona>,            // orchestrator / ifc / cad
       Handlers:    [skillMW, 交付审批MW, ...],  // skill middleware 自动注入 skill 工具
       ToolsConfig: <领域工具 + AgentAsTool>,
   })

 三角色绑定（角色 skill 映射，第一层 filteredSkillBackend 过滤）
   orchestrator --> "aiplan"（对话协调内联，D11；编排纪律在 OrchestratorPersona）
   ifc-agent    --> "aiifc"
   cad-agent    --> "aidxf"
```

> **aiplan 双层分离（D11）**：aiplan 的**对话协调**由 orchestrator 内联（它是唯一对话入口，
> 且 orchestrator 亲自做 plan 才懂 plan.json 字段、派发 cad 才能对齐产物）；aiplan 的
> **工程执行**（CLI 13 子命令 + 固定 schema + 固定落盘 + gate 门禁）与 cad 管线等价，
> 走 M2 管线命令模式（白名单端点 + Go 薄代理 `run_aiplan_command`），orchestrator 不直挂 python。

> **skill 来源约定（2026-08-19）**：agent 只面对 `skills/dist`（正式发布集合：aidxf/aiplan/aiifc），
> 不感知开发版本（`aidxfv/v1|v2|v3` 等）。`skillsDir` 默认 `../skills/dist`。

> **2026-08-19 M2-0 已落地（D12）**：filesystem middleware 已挂（`newFilesystemMiddleware`，
> Backend=只读包装 + StreamingShell=local 白名单）——模型已能 read_file/glob/grep 读 skill
> references、execute 跑 aiplan/aidxfv3 白名单 CLI；write/edit 被拒绝（领域收敛）。

skill middleware 只做两件事（`BeforeAgent`）：
1. `runCtx.Instruction += progressive disclosure 系统提示词`
2. `runCtx.Tools = append(..., skill 工具)`

模型侧自动获得：`skill` 工具（入参 `{"skill": name}`，返回 SKILL.md 正文 + BaseDirectory）+ 全部 skill 清单渲染在工具描述里 + inline/fork 两种模式。**不写解析器、不写扫描器、不写加载工具。**

**skill 完整能力 = skill middleware + filesystem middleware（D12）**——skill 工具只给「说明书 + BaseDirectory 路径」，要「按需加载其他文件 + 执行捆绑代码」靠 filesystem middleware：

```
skill 工具 → SKILL.md 正文 + BaseDirectory（/path/to/skills/aiplan）
    │
    ├─ 读 references/  →  filesystem middleware: read_file / glob / grep
    └─ 跑 scripts CLI  →  filesystem middleware: execute（local backend /bin/sh -c，
                          领域收敛 = local Config.ValidateCommand 命令白名单 aiplan-*/aidxfv3-*）
```

装配：orchestrator/子 agent 的 Handlers 追加 `filesystem.NewTyped(Backend: local, StreamingShell: local)`（M2-0）。

## 3. 执行层（skill scripts / python 探索，D12 修正）

和交付沙箱分开。交付走 REST（版本/diff/notify）；skill scripts / python 探索走**官方 filesystem middleware 的 execute + bwrap Shell**（不再自创 PyExecutor 薄壳）。

```
  execute {command}            官方 filesystem middleware（ValidateCommand 白名单）
        |
        v
  filesystem.Shell 接口
        |
        +-- local backend（默认）：/bin/sh -c + ValidateCommand 白名单（M2-0）
        +-- bwrap Shell（M4）：路径 jail + bwrap 参数照抄 script_runner.py:159-172
             +-- cwd 强制 {dataDir}/models/{id}/pipeline/
             +-- 路径 jail (逃出工作区即拒)
             +-- bwrap: ro root + 工作区可写 + unshare-net
             +-- RLIMIT + 超时 killpg
             +-- 输出 64KB 截断
             +-- python = services/cad 或 ifc 的 venv

  能跑:  skill 包 scripts/ (flows, aiplan/aidxfv CLI 探索)
  不能:  直接改 uploads/ 当交付; 那必须走 §4
```

衡量（产物去向）：

```
  要进版本/diff/web  -->  交付 REST 沙箱       专属 tool
  skill references   -->  filesystem read_file/glob/grep（D12/M2-0）
  skill CLI / python -->  filesystem execute + ValidateCommand（M2-0）；
                          更强隔离走 bwrap Shell（M4）
  固定交付管线命令    -->  services 白名单端点（M2-③ 备选，与 execute 白名单二选一/并存）
```

## 4. 标准交付工具 + 流程固化

### 交付工具面（script-as-source 唯一交付面）

```
  读
    get_script
    get_script_locate {guid}      新增  薄代理 locate
    get_versions / get_diff / get_model_info / list_models

  改 (仍不进版本)
    stage_script                  全量暂存
    edit_script_call              新增  薄代理 edit-call 定点标量
         {designKey, argument, value}  服务端校验标量

  跑 / 落盘
    run_script                    沙箱预览, 不落版本
    save_script                   沙箱 + 大版本
         成功后同沙箱跑 design_review, 报告随结果回喂 (v1 不 422)

  创建
    create_project                不 MarkDirty
```

### 交付流程固化（官方 middleware 拦截，ch09 同构）

交付 = 「确认 → 执行 → review → 报告」作为**确定的工具拦截链**，固化成 middleware，模型无法绕过：

```go
func (m *deliveryMW) WrapInvokableToolCall(_ context.Context, endpoint adk.InvokableToolCallEndpoint, tCtx *adk.ToolContext) (adk.InvokableToolCallEndpoint, error) {
    if !isDeliveryTool(tCtx.Name) { return endpoint, nil }   // 只拦 save_script / deliver
    return func(ctx context.Context, args string, opts ...tool.Option) (string, error) {
        wasInterrupted, _, stored := tool.GetInterruptState[string](ctx)
        if !wasInterrupted {
            return "", tool.StatefulInterrupt(ctx, &ApprovalInfo{ToolName: tCtx.Name, ArgumentsInJSON: args}, args)
        }
        // resume 后：approved → 真执行 → design_review → 返回报告
        ...
    }, nil
}
```

> 备选：跨多工具的交付流水线（save + review + 归档）用 Graph Tool（`compose.Graph` → `graphtool.NewInvokableGraphTool`）。单工具审批先 middleware。

### 开放断点（对齐例 7，官方 interrupt/resume）

```
  读完 SKILL.md MUST 断点
        |
        v
  模型自己调 skill / 提问触发 interrupt
        |
        v
  StatefulInterrupt --> Runner 捕获 (InterruptContexts[].ID + Info)
        |
        v
  SSE question.ask --> 前端 --> POST .../answer
        |
        v
  Runner.ResumeWithParams(checkPointID, {interruptID: 回答}) --> 续跑
```

参考实现：`eino-examples/adk/common/tool/follow_up_tool.go`。v1 可先靠报告「遗留问题」字段（零通道）；要弹框再上官方 interrupt。

## 5. 一次完整路径（CAD 管线示例）

```
 用户: 从模糊想法开始，帮我做一个标准层方案
    |
    v
 orchestrator: 意图路由 → 判定需先规划（plan→cad 链）
    内联 aiplan skill（对话协调，D11）：与用户对话框定 design_intent
    调 run_aiplan_command: derive → normalize → gate → land
    产物: {workspace}/plan/plan.json + bim_supplement.json（固定 schema/位置）
    |
    v
 orchestrator: AgentAsTool 派 cad-agent（对齐 plan.json + 用户描述）
    断点 interrupt <-- 需要用户确认时挂起
    |
    v
 用户回答 --> ResumeWithParams 续跑
    |
    v
 cad-agent: skill 工具加载 aidxf SKILL.md
    文件工具读 references / 管线命令 preprocess / normalize
    产物落 pipeline/
    交付 --> save_script (delivery middleware 先问) --> design_review 报告
    |
    v
 orchestrator: notify 闭环 --> viewer.committed
```

## 6. 现状 --> 目标（要动的）

```
 现在 (经典 flow/react)            目标 (ADK)
 ----                              ----
 ✅ react.NewAgent + runEmitter    ✅ adk.ChatModelAgent + Runner（2026-08-19 v1 骨架）
 ✅ persona 快照几句话              ✅ 官方 skill middleware（WithSkillsDir 挂载；6 skill 可扫）
 ✅ 自研 subagentHub               ✅ 官方 adk.NewAgentTool（2026-08-19 路线 B 迁移完成；翻译层 RunPath 合成 subagentId + subagent/status）
 ✅ skill 只有 SKILL.md            ✅ skill + filesystem middleware（M2-0 落地：read_file/glob/grep + execute 白名单；write/edit 拒绝）
 无 python 执行                    ⏳ PyExecutor + bwrap Operator（仅 worker）
 无 locate/edit-call               ⏳ 标准交付工具补齐
 文字确认 (软)                     ⏳ 官方 interrupt/resume + 交付 middleware 审批
 ✅ 事件 9 种 (callbacks 观测)     ✅ ADK AgentEvent 流 → 翻译层 2.0（events.go §4，形状不变）
 ✅ EventStore JSONL                ✅ 保留（记录平台 Event）
 ✅ scriptedModel 确定性            ✅ ADK 兼容（已验证）
```

改动：SSE 帧形状 / 7 路由 / envelope / 前端零改动 / kind 路由 / 64KB / 错误文本化 / EventStore 思路。
新增（2026-08-19）：`events.go` §4 `adkTranslator`（AgentEvent→Event 翻译）、`middleware_safe.go`（工具错误兜底）、
`WithSkillsDir`（官方 skill middleware）。差异：工具 step/start 在 ADK 下晚于子事件发出（见 api_regulation §4.5）。

## 7. 对照 6/7/8 一句话

```
 6  ReviewEdit 包装     -->  交付工具 WrapInvokableToolCall 拦截, 可改参数再执行
 7  FollowUp + SubAgents -->  StatefulInterrupt 自主时机 + AgentAsTool 派子 agent
 8  Supervisor 嵌套审批  -->  只要三角色扁平; 审批留交付 middleware
                             不要把 PER 三 LLM 搬过来, flowops 已是机器规划
```

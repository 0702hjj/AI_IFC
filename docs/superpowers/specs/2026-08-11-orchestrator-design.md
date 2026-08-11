# Orchestrator 设计（Eino 评估 + 事件总线规约）

> 日期：2026-08-11 · 状态：待评审（spec 先行，notify 事件化由同日迭代 Task 2 实施）
> 前置：W-0017（docs/work/items/W-0017-orchestrator-agent.md）、W-0025（事件 URI 化，skills/aiifc/hooks/README.md）
> 架构基调：help.md 架构精要 **Pure Core + Imperative Shell**；AGENTS.md「纪律事件化」（controller 不轮询、子代理报告即事件载荷）
> 关联代码：`viewer/server/internal/api/chat_orchestrator.go`（现状 notify 命令式编排）、`chat.go/chat_sse.go/chat_session.go`（SSE 地基）、`internal/opencode/opencode.go`（opencode serve 客户端）

---

## 1. 背景与目标

### 1.1 为什么需要 orchestrator

现状：`chat` 模块是**单 agent 形态**——Go server 薄客户端代理 `opencode serve`（:4096，demo 工作目录承载 `ifc-demo` agent + aiifc skill），浏览器对话透传、agent 直接改 `uploads/{id}.ifc`，AI 大改后由 Go 内命令式 `notify` 固定流程落盘（chat_orchestrator.go:171）。

单 agent 形态的局限（W-0017 背景）：

| 能力 | 现状 | 编排层缺口 |
|---|---|---|
| 意图路由 | 无：单一 `ifc-demo` agent 承接全部对话 | 需按任务分派 IFCagent / CADAgent / designerAgent |
| 子 Agent 提示词封装 | 无（单一 `.opencode/agent/ifc-demo.md`） | 需每个子 Agent 独立提示词 + orchestrator 统一封装 |
| 事件驱动闭环 | notify 是「idle 后同步跑完的命令式流程」 | 需 Pure Core（Event+State→Action 纯函数）+ Shell 副作用回填闭环 |
| 结果汇总呈现 | 单 agent 直接流式返回 | 多子 agent 结果需 orchestrator 汇总 |
| 多 agent 协同 | 无事件总线 | 需 `aiifc://` 事件 URI 规约（W-0025 已打底） |

### 1.2 本 spec 的目标

1. **框架裁决准备**：调研 Go Eino（CloudWeGo），与现状裸 opencode-serve 编排做对比矩阵，给出明确倾向与建议，**最终裁决留用户**。
2. **事件总线规约**：定义事件 URI 表（与 W-0025 对齐）、Event+State→Action 纯函数签名、Shell 执行模型、in-flight 取消、幂等/重放。
3. **notify 事件化细则**：把现状命令式 `notify` 拆为 Core 纯函数 + Shell 副作用清单——这是 Task 2 的直接实施蓝本。
4. **子 Agent 划分**：IFCagent / CADAgent / designerAgent 职责边界与提示词封装位置。

**本 spec 不写实现代码**（除 Go 伪代码签名）。

---

## 2. 已定决策回顾

### 2.1 叙事：orchestrator 内向，A2A 是出口（2026-08-07 用户裁决）

平台自持 **orchestrator 为内向用户对话面**；A2A 协议仅作为子 agent 的**对外暴露形态**（与同事的外部主 agent 对接，见 docs/internal/architecture/ai-bim-agent-page.md §4.5）。两者不冲突：orchestrator 是内部枢纽，A2A 是出口。本 spec 只定 orchestrator 内部结构；A2A 出口边界在 §7 简述，不实现。

### 2.2 架构基调：Pure Core + Imperative Shell（2026-08-08，help.md 入约）

- **Core** 是纯函数：`Event + State → Action 列表`，零 IO，可单测。
- **Shell** 执行全部副作用（LLM 调用、edit-service REST、converter 子进程、文件归档、SSE 推送），并把每步结果转为**新 Event 回填 Core**，驱动多轮闭环。
- 不在 LLM 调用上同步等待（异步 + 事件回填）。
- in-flight 任务必须可取消（子进程用进程组物理 kill，沙箱已有先例）。
- 事件 URI 化（`aiifc://model/{id}/script/saved` 形态）为多 agent 协同打底。

### 2.3 事件 URI 化：W-0025 已落地

`skills/aiifc/hooks/`（2026-08-10 交付，W-0025，PR #28）已定义校验即事件 URI 表：

| 事件 URI | 含义 |
|---|---|
| `aiifc://script/validated` | 契约校验通过（无 modelId 上下文） |
| `aiifc://script/validation-failed` | 契约校验失败（无 modelId 上下文） |
| `aiifc://model/{id}/script/validated` | 契约校验通过（路径含 modelId） |
| `aiifc://model/{id}/script/validation-failed` | 契约校验失败（路径含 modelId） |

本 spec 的事件总线必须与其保持一致（同 scheme、同路径段语义、modelId 嵌入同一位置）。

---

## 3. Eino 调研结论（2026-08-11，webfetch 官方资料）

> 证据等级：**【A1】一手**——官方 GitHub README / CloudWeGo 官网文档直接阅读；**【B2】推断**——基于一手材料的分析，未逐一验证。

### 3.1 调研范围

- 官方仓库：github.com/cloudwego/eino（README + 仓库元数据）
- 官方文档：www.cloudwego.io/docs/eino/（User Manual 目录、Agent Collaboration、FAQ）
- 未获取到：eino-ext 的完整 provider 列表逐一核对（zhipuai/GLM 适配属【B2】）；未实际跑通 Hello World。

### 3.2 能力画像【A1】

- **定位**：Go 的 LLM 应用框架，借鉴 LangChain + Google ADK，Apache-2.0，Go 1.18+。
- **组件抽象**：`ChatModel / Tool / Retriever / Embedding / ChatTemplate`；官方实现（eino-ext）覆盖 OpenAI、Claude、Gemini、Ollama、Ark、DeepSeek 等。
- **编排（compose）**：Chain/Graph/Workflow——`graph.AddLambdaNode / AddChatModelNode / AddEdge(START→…→END) / Compile / Invoke`；graph 可包装为 Tool（graphtool.NewInvokableGraphTool）。
- **ADK（Agent Development Kit）**：
  - `ChatModelAgent`：内置 ReAct 循环，`ToolsConfig` 挂工具。
  - `DeepAgents`：主 agent 用 TaskTool + WriteTodos 委派子 agent、跟踪进度。
  - Workflow Agents：Sequential / Parallel / Loop（固定流程确定性编排）。
- **多 agent 协作**：**AgentAsTool**（推荐）——子 agent 包成 Tool，父 agent 自主调用，子 agent **独立上下文**（不继承父对话历史）、可并行；`EmitInternalEvents=true` 时子 agent 事件流实时透传给用户展示。**Supervisor/AgentTransfer 模式官方明确不推荐**（全上下文共享 → token 成本高、注意力稀释、上下文污染、强制注入工具）【A1，FAQ】。
- **流式**：框架自动处理编排全程的流（合并/盒装/拷贝）。
- **回调（callback aspects）**：OnStart / OnEnd / OnError 等固定点注入日志/追踪/指标。
- **HITL**：interrupt/resume + checkpoint（人与机器循环）。
- **取消**：TurnLoop 支持抢占/中止多轮生命周期。
- **Tool 防御机制**：ToolArgumentsHandler（JSON 修复）、UnknownToolsHandler（幻觉工具自纠正）、ToolAliases（改名兼容）、middleware 把 tool 错误转 result 让模型自愈【A1，FAQ】。
- **SessionValues**：agent 执行内全局 KV，跨 agent 共享。

### 3.3 局限与风险

- **pre-1.0 快速迭代**【A1】：v0.1→v0.9 多次发布，v0.3（tiny break change）、v0.8（breaking changes）有破坏性变更，v0.9 有迁移指南。跟版本是持续负担。
- **自带 agent 运行时需自建**【B2】：会话持久化、历史回填、权限系统、技能（skill）加载、MCP 集成、`file.edited` 语义——这些 opencode 已免费提供，Eino 只给抽象，落地全要自写。
- **provider 适配需核对**【B2】：现用模型为 zhipuai-coding-plan/glm-5.2（demo_connect.md §3.4）；eino-ext 对 zhipu/GLM 的适配未逐一验证。FAQ 亦披露 **DeepSeek V4 在 tool call 场景有已知 reason content 问题**【A1】——虽非现用 provider，但说明 eino-ext 的 provider 包装存在版本敏感的已知坑，zhipu 适配同样需实测。
- **框架有已知版本坑**【A1】：kin-openapi 依赖在 v0.6 移除、sonic 与 go1.24 不兼容（旧版）、无内置 batch 节点等。
- **Skill 与 MCP 生态围绕 opencode 构建**【B2】：aiifc skill、mcp-server、W-0025 hooks（opencode-plugin.ts / claude-settings.json 双形态）都挂在 opencode 的工具/事件模型上；迁移 Eino 意味着重写这些接入面，而非平移。

### 3.4 对「LLM 调用编排 + 事件驱动回填」的适配度评估【B2】

| 需求 | Eino 适配度 | 说明 |
|---|---|---|
| LLM 调用编排（Chain/Graph/多 agent 委派） | **高** | compose + ADK + AgentAsTool 是成熟抽象，与子 agent 愿景契合 |
| 事件驱动回填（领域事件总线） | **中** | Eino 提供的是「执行期事件」（回调/AgentEvent 流）；**领域事件总线（aiifc:// URI、Event+State→Action）仍须自建**——Eino 可当 Shell 内的执行器，不天然是总线 |
| 与现有 SSE 地基衔接 | **中** | Go 侧 pushLocked/evLog 复用；需自写 Runner 事件流 → SSE 的适配层 |
| HITL 设计师确认 | **高** | interrupt/resume 现成 |
| 取消 | **中高** | TurnLoop 现成；但 subprocess（converter）物理 kill 仍自建 |

结论：**Eino 解决「执行编排」，不解决「领域事件总线」**。后者（本 spec §5）是运行时无关的，今天就能做。

---

## 4. Eino vs 现状 opencode-serve 对比矩阵

### 4.1 矩阵

| 维度 | 现状：裸 opencode-serve 编排（A 轨） | 候选：Eino（Go 库内嵌，B 轨） | 判分 |
|---|---|---|---|
| **会话管理** | opencode 原生：CreateSession / PromptAsync / GetMessages / Abort + 服务侧持久会话 + 历史回填（已实测） | 自建：ADK Runner + memory/session 持久化、历史、重开回填全要写 | A 省一个存储与协议层 |
| **成本（部署/运维）** | 多一个 Node 进程（:4096），独立版本/配置，需随 opencode 演进核对契约 | 无额外进程（Go 库内嵌）；但 provider 配置、代理层、超时策略自建 | 持平（迁移抵消进程数） |
| **失败语义** | opencode 非 2xx → 502 透传；notify 命令式 fail 推 `viewer.notify_failed` | 库内错误（NodeRunError / context deadline）；失败语义由我们 Shell 定义，更可控 | 平分：B 语义更细，A 已够用 |
| **与现有 SSE 地基衔接** | 现成：opencode `/event` 全局订阅 → 过滤 → 透传 + 重连退避 + 重同步缓冲（chat_sse.go） | 需自写：Runner 事件流 → SSE + 会话重连缓冲（可复用 pushLocked/evLog） | A 领先（地基已建且踩过坑） |
| **对 notify 事件化的承载** | 事件源：opencode `file.edited` / `session.idle`（机器可读）；我们自行归一 | 事件源：Tool 结果 / 回调；领域事件总线仍自建，与 A 轨相同 | 平分（框架不解决领域事件） |
| **子 agent / 多 agent 编排** | 单 agent；`prompt_async` 可带 `agent` 名切 agent，但**无「agent 调 agent + 独立上下文」委派** | AgentAsTool / DeepAgents 原生支持独立上下文、并行、事件透传（官方推荐形态） | **B 强项**（但 M7+ 才需要） |
| **技能 / 工具生态** | aiifc skill、mcp-server、W-0025 hooks、权限、`.opencode/agent/` 提示词全部就绪 | 需重写 skill 接入形态（Eino skill = prompt/middleware）、MCP 工具化、hooks 事件回填 | **A 大幅领先**（存量资产） |
| **团队维护成本** | opencode 演进由社区维护，我们只管薄客户端；契约风险在服务升级时一次性核对 | 跟进 pre-1.0 breaking change（v0.3/v0.8 已两次）+ 自建运行时积木持续维护 | A 更省 |
| **事件 URI 一致性** | 不受影响（URI 是约定，与运行时无关） | 不受影响 | 平分 |
| **License** | opencode 许可与自托管前提需核对 | Apache-2.0，AGPL 项目内嵌库无传染冲突（库级 Apache） | 持平 |

### 4.2 建议结论

**倾向：保持现状演进（A 轨）为主轨，Eino 评估留到 M7+ 作为备轨。理由：**

1. **存量资产最大**：aiifc skill、MCP、hooks、`.opencode/agent/`、SSE 地基、会话持久化已全部围绕 opencode 建成并踩过坑（W-0002/W-0006/W-0021）；迁移 Eino 是「为了换执行器而重写整个 agent 接入面」。
2. **本 spec 的核心（事件总线 + Core/Shell）与运行时无关**：notify 事件化（Task 2）、orchestrator 骨架、意图路由都可以在 A 轨上落地，不阻塞，也不浪费——将来若迁移 B 轨，Go 编排层原样保留，只替换 Shell 内的 LLM 调用端。
3. **Eino 当前不需要**：M6 阶段是「多 agent 名 + 意图路由」，opencode 的 `prompt_async(agent=...)` 已能承载；真正需要「agent 调 agent + 独立上下文」的 DeepAgents 场景在 M7+。
4. **Eino 尚 pre-1.0**：v0.3/v0.8 已两次 breaking change；此刻迁移等于绑一个仍在变形的桩，团队维护成本高。

**迁移触发条件（M7+ 重评）**：
- 子 agent 需要独立上下文委派（agent 调 agent）且 opencode 多 agent 名方案承载不住；
- 或 Eino 稳定至 1.0、zhipu/GLM provider 实测可用。

届时建议：**开 PoC 对比**（Eino AgentAsTool vs opencode 多 agent 名），带指标（实现量、token 成本、失败语义）再裁决。迁移路径是「**替换执行器**」：Go 编排 + 事件总线保留，把 Shell 的 LLM 调用从 opencode REST 换成 Eino 库调用——边界清晰。

> **待用户裁决**：① A 轨为主轨是否认可；② 迁移触发条件是否合适。

---

## 5. 事件总线规约

### 5.0 诚实声明：总线是进程内逻辑总线，不是跨进程基础设施

- **单进程事实**：Go server 是唯一编排进程；edit-service 无事件流（REST 拉模式）、converter 是子进程、hooks 事件经对话上下文回填（半结构化）。
- 因此「事件总线」= Go 进程内的**适配器 + 分发循环**：外部事件（opencode `/event`、REST 结果、hooks 消息）由 Shell 适配器归一为总线 Event，喂给 Core；不引入独立事件存储（v1 不做持久化总线，见 §9 开放问题 2）。
- 跨进程的事件语义（如 `aiifc://model/{id}/script/validated`）由 hooks 侧保持 URI 一致，作为约定而非总线传输——两条腿：URI 规约统一命名（本表），传输由各适配器负责。

### 5.1 事件 URI 表

统一命名：`aiifc://{域}/{id?}/{动作}`，`{id}` = modelId（`^m_[0-9a-f]{16}$`）。

| 事件 URI | 含义 | 来源 | 载荷（JSON） |
|---|---|---|---|
| `aiifc://model/{id}/edited` | 模型文件被修改（write/edit 工具或 bash 跑脚本） | opencode `file.edited` ∪ mtime 兜底 | `{path}` |
| `aiifc://chat/{cid}/idle` | agent turn 结束（会话空闲，`{cid}` = chatSessionId） | opencode `session.idle` 归一 | `{}` |
| `aiifc://script/validated` | 契约校验通过（无 modelId） | W-0025 hooks（已落地） | `{path, mode, ok:true}` |
| `aiifc://script/validation-failed` | 契约校验失败（无 modelId） | W-0025 hooks（已落地） | `{path, mode, ok:false, errors:[...]}` |
| `aiifc://model/{id}/script/validated` | 契约校验通过（含 modelId） | W-0025 hooks（已落地） | `{path, mode, ok:true}` |
| `aiifc://model/{id}/script/validation-failed` | 契约校验失败（含 modelId） | W-0025 hooks（已落地） | `{path, mode, ok:false, errors:[...]}` |
| `aiifc://model/{id}/pending/discarded` | DELETE pending 成功（坏文件自检通过） | Shell 执行 `discard_pending` 结果 | `{discarded}` |
| `aiifc://model/{id}/script/staged` | PUT /script 成功（已暂存） | Shell 执行 `stage_script` 结果 | `{staged, canUndo}` |
| `aiifc://model/{id}/script/run` | 沙箱试跑成功 | Shell 执行 `run_script` 结果 | `{ok:true}` |
| `aiifc://model/{id}/script/saved` | save 落大版本成功（版本已产生） | Shell 执行 `save_script` 结果 | `{version}` |
| `aiifc://model/{id}/script/failed` | script 管线任一步失败 | Shell 执行错误 | `{step, reason}` |
| `aiifc://model/{id}/converted` | 重转完成 | convert.Queue | `{status}` |

对齐 W-0025：scheme 与路径段语义一致（`aiifc://model/{id}/script/{动词}`）；新增的 staged/run/saved/failed 是同一命名空间的自然延伸。浏览器 SSE 侧保持现有 `viewer.committed` / `viewer.notify_failed` 契约不变（总线事件 ≠ 浏览器事件，前者喂 Core，后者出 Shell）。

### 5.2 Event + State → Action 纯函数签名（Go 伪代码）

```go
// Event 是总线最小契约（Shell 适配器归一后的统一形态）。
type Event struct {
    URI       string          // "aiifc://model/{id}/script/saved"
    ModelID   string          // 归一提取（空则无 modelId 上下文）
    SessionID string          // chatSessionId（chat 域事件）
    Seq       uint64          // 每会话递增（幂等去重用，复用 pushLocked 的 seq）
    Payload   json.RawMessage
}

// Action 是 Shell 要执行的副作用原子操作（纯声明，零 IO）。
type Action struct {
    Type    ActionType
    Step    string         // notify_failed 的 step 名（现状语义保留）
    Script  string         // stage_script：脚本全文（Shell 注入，来自 staging 读取）
    Version string         // archive/reconvert/notify：save 回填的版本号
    Reason  string         // notify_failed 的原因
}

type ActionType string

const (
    ActionDiscardPending   ActionType = "discard_pending"
    ActionStageScript      ActionType = "stage_script"
    ActionRunScript        ActionType = "run_script"
    ActionSaveScript       ActionType = "save_script"
    ActionArchiveArtifact  ActionType = "archive_artifact"
    ActionReconvert        ActionType = "reconvert"
    ActionNotify           ActionType = "notify"         // → 推 viewer.committed
    ActionNotifyFailed     ActionType = "notify_failed"  // → 推 viewer.notify_failed
)

// NotifyState 是决策所需的最小状态快照（纯数据，无 IO 句柄）。
type NotifyState struct {
    Dirty            bool   // file.edited 或 mtime 兜底置位
    HasStagingScript bool
    Script           string // staging/{modelId}.py 全文（Shell 读好注入）
    Bound            bool   // 会话已绑定 modelId
}

// planNotify 是 notify 流程的 Core：Event + State → Action 列表。
// 纯函数：不 IO（不读 staging、不调 edit-service、不写状态）；返回的 Action 顺序即
// Shell 必须遵守的执行顺序（顺序即契约）。
//
// 关键决策：版本号只在 save 成功后已知，因此「收尾动作（归档/重转/推送）」不能
// 在第一轮一次性决定——由 saved 事件驱动第二轮回填（多轮闭环，符合「不在 LLM
// 调用上同步等待」的基调）。
func planNotify(ev Event, st NotifyState) []Action {
    switch {
    case ev.URI == "aiifc://chat/"+ev.SessionID+"/idle" && st.Dirty && st.Bound:
        // 第一轮：丢 pending（坏文件自检）；有脚本则追加 script 管线（PUT→run→save）。
        // 版本不可知 → 收尾延后到 saved 事件。
        acts := []Action{{Type: ActionDiscardPending, Step: "discard_pending"}}
        if st.HasStagingScript {
            acts = append(acts,
                Action{Type: ActionStageScript, Step: "stage_script", Script: st.Script},
                Action{Type: ActionRunScript, Step: "run_script"},
                Action{Type: ActionSaveScript, Step: "save_script"},
            )
        }
        return acts

    case ev.URI == "aiifc://model/"+ev.ModelID+"/script/saved":
        // 第二轮（有脚本）：save 成功，version 已知 → 归档 + 重转 + 推送。
        return []Action{
            {Type: ActionArchiveArtifact, Step: "archive", Version: payloadVersion(ev)},
            {Type: ActionReconvert, Step: "reconvert"},
            {Type: ActionNotify, Step: "notify", Version: payloadVersion(ev)},
        }

    case ev.URI == "aiifc://model/"+ev.ModelID+"/pending/discarded" && !st.HasStagingScript:
        // 无脚本路径：discard 完成即收尾（不产生版本）。
        return []Action{
            {Type: ActionReconvert, Step: "reconvert"},
            {Type: ActionNotify, Step: "notify"}, // Version 空 → viewer.committed 无版本
        }

    case isFailure(ev): // URI == "…/script/failed"（含取消归一）
        return []Action{{Type: ActionNotifyFailed, Step: stepOf(ev), Reason: reasonOf(ev)}}

    default: // 中间状态事件（staged / run / 中间 discard）无需新动作
        return nil
    }
}
```

零 IO 约束：`payloadVersion / stepOf / reasonOf / isFailure` 只解析 ev.Payload，不 IO。`st.HasStagingScript / st.Script` 由调用方（Shell）读盘注入——Core 自身绝不碰文件系统，保证可单测。

### 5.3 Shell 执行模型

Shell 是**唯一 IO 层**，职责：

1. **事件适配**：opencode `/event` 订阅 → 归一为总线 Event（`file.edited`→`model/{id}/edited`、`session.idle`→`chat/{cid}/idle`）；mtime 兜底检测；REST 结果合成（staged/run/saved/discarded）。
2. **Action 执行**：逐条**按序**执行 Core 返回的 Action 列表（顺序即契约，现状测试断言不变）：
   - `discard_pending` → `editsvc.DeletePending`（强制磁盘重载 = 坏文件自检）
   - `stage_script` → `PUT /models/{id}/script`（body = Action.Script）
   - `run_script` → `POST /models/{id}/script/run`（沙箱）
   - `save_script` → `POST /models/{id}/script/save` → version（失败时保留现状的 `GetVersions` 兜底 + 显式 `save_version` fail）
   - `archive_artifact` → fs 归档 `staging/{id}.py` → `models/{id}/scripts/v{n}.py` + 删 staging 源（复用 archiveStagingArtifact）
   - `reconvert` → `St.SetStatus(converting)` + `Q.Enqueue`
   - `notify` → `pushSystem(cid, "viewer.committed", {modelId, version, committed:true})`
   - `notify_failed` → `pushSystem(cid, "viewer.notify_failed", {modelId, step, reason})`
3. **结果回填闭环**：每步执行结果 → 新 Event → 再次调 `planNotify`（驱动多轮），直到返回终态（done / failed / cancelled）。

**失败语义**：fail-fast（不跨步重试）；恢复 = staging 脚本保留（现状）+ 下次 `edited`/`idle` 重新触发。与现状行为完全一致，只是决策从命令式 if-else 挪进纯函数。

### 5.4 in-flight 取消

- 每个 Action 执行前检查 ctx；所有 REST 调用带 ctx（editsvc 已支持 `Do(ctx,…)` / `DoSlow(ctx,…)`）。
- 外层 context 来源：现状为 `notify` 内 180s 超时；事件化后由触发方（dispatchLoop 的触发点）管理。
- **abort 语义扩展**：现状 `POST /chat/sessions/{cid}/abort` 只取消 agent turn；事件化后**扩展到可取消 in-flight notify**——取消 → 归一为 `script/failed {step:"cancelled"}` → Core 产出 `notify_failed`（或按用户裁决静默，见 §9 开放问题 3）。
- 子进程（converter 重转）：convert.Queue 已有进程组 kill 先例（沙箱语义），沿用。

### 5.5 幂等 / 重放

| 关注点 | 策略 |
|---|---|
| 事件去重 | 每会话 seq 递增（复用 pushLocked 的 seq），已处理 seq 集合去重（最近 N 条），防同事件双触发 |
| dirty 防抖 | 同一 turn 只触发一次（现状 `cs.dirty=false` 语义保留） |
| 幂等步骤 | `discard_pending`（DELETE pending 天然幂等）、`stage_script`（PUT 覆盖）可安全重放 |
| 非幂等步骤 | `run_script`/`save_script` 不可重放（save 产生新版本）→ **重放窗口只到第一轮 batch 前**；saved 后进入 done 终态，不再受理 |
| 状态生命周期 | state 为内存态，重启丢失（v1 限制，与现状一致）；重启后 staging 脚本仍在，下一次 `edited`+`idle` 重新触发——正是现状「staging 保留防静默吞版本」的语义 |

---

## 6. chat notify 事件化细则（Task 2 实施蓝本）

### 6.1 现状命令式流程（chat_orchestrator.go:171 `notify`）

```
① DELETE /models/{id}/pending          —— 坏文件自检（强制 edit-service 磁盘重载）
② staging/{id}.py 存在？
   ├─ 是：读脚本 → PUT /script → POST /script/run → POST /script/save
   │        → version（save 响应；失败兜底 GetVersions；仍不可解析 → fail("save_version")）
   └─ 否：跳过 script 管线
③ 置 converting + 入队重转（run/save 已重写 uploads/{id}.ifc）
④ 制品归档：staging/{id}.py → models/{id}/scripts/v{n}.py（删 staging 源）
⑤ 推 viewer.committed {modelId, version, committed:true}
   任一步失败 → 推 viewer.notify_failed {modelId, step, reason}
```

命令式问题：决策（要不要跑脚本、失败怎么办）与副作用（REST/fs/queue/sse）揉在一个函数里，分支只能靠集成测试覆盖，无法单测每个决策分支。

### 6.2 Core 纯函数

即 §5.2 的 `planNotify`，分支覆盖：有脚本 / 无脚本 / 失败 step / 版本不可解析（`save_version`）/ 取消。**每个分支都是纯函数单测的断言点**（Task 2 Step 1 先写失败测试）。

### 6.3 Shell 副作用清单（完整）

| # | 副作用 | 调用 | 成败 → 事件 |
|---|---|---|---|
| 1 | DELETE pending | `editsvc.DeletePending(ctx, modelID)` | 成功→`pending/discarded`；失败→`script/failed {step:discard_pending}` |
| 2 | 读 staging 脚本 | `os.ReadFile(staging/{modelId}.py)` | 读不到→跳过脚本分支；失败→`script/failed {step:read_staging_script}` |
| 3 | 暂存脚本 | `ed.Do(PUT /models/{id}/script, {script})` | 成功→`script/staged`；失败→`script/failed {step:stage_script}` |
| 4 | 沙箱试跑 | `ed.DoSlow(POST …/script/run)` | 成功→`script/run`；失败→`script/failed {step:run_script}` |
| 5 | 落版本 | `ed.DoSlow(POST …/script/save)` + 兜底 `GetVersions` | 成功→`script/saved {version}`；不可解析→`script/failed {step:save_version}` |
| 6 | 制品归档 | fs 复制 `staging/{id}.py`→`models/{id}/scripts/v{n}.py` + 删源 | 失败→日志（现状非致命，保留） |
| 7 | 置 converting | `St.SetStatus(modelID, "converting", "")` | 日志（现状非致命） |
| 8 | 入队重转 | `Q.Enqueue(modelID)` | 已在队→日志 |
| 9 | 推送 committed | `pushSystem(cid, "viewer.committed", …)` | — |
| 10 | 推送 notify_failed | `pushSystem(cid, "viewer.notify_failed", …)` | — |

### 6.4 行为保持契约（Task 2 必须保留）

- script 管线顺序不变：`DELETE pending → PUT /script → run → save`；无脚本路径只 `DELETE pending`。
- `viewer.committed` / `viewer.notify_failed` 事件语义、字段不变。
- 版本不可解析 → 显式 `fail("save_version")`、不排重转、staging 脚本保留（防下次 idle 重复 save）。
- run 失败 → `fail("run_script")`、不排重转、staging 脚本保留（可修后重试）。
- 归档成功后 staging 源删除；无脚本不产生版本、不归档。
- 现有 `chat_notify_test.go` 四个契约测试（script pipeline / no-script / save_version / run failure）断言全部保持可转绿；新增 Core 纯函数单测（`chat_core_test.go`）覆盖各分支 Action 列表。
- 事件 URI：`aiifc://model/{id}/script/{staged|run|saved|failed}`（与本 spec §5.1 一致）。

---

## 7. 子 Agent 划分与提示词封装

### 7.1 职责边界

| Agent | 域 | 输入 / 输出契约 | 承载 |
|---|---|---|---|
| **orchestrator**（整体 Agent） | 用户对话面 + 意图路由 + 子 agent 提示词封装 + 结果汇总 + notify 落盘编排 | 对话 ↔ `uploads/{id}.ifc` / staging 脚本；事件 `aiifc://chat/{cid}/idle` | Go 编排层（意图路由决定把本轮 dispatch 给哪个子 agent） |
| **IFCagent** | ifcopenshell 建模 / 构建脚本编写与增量修改 | `build(PARAMS)` 脚本契约；脚本 diff 上下文注入（W-0016 机制扩展） | aiifc skill（`.opencode/agent/ifc-agent.md`） |
| **CADAgent** | 几何 / DXF 生成（对接同事 aidxf，AI_CAD 段） | cad 落盘（分层 DXF + 绘制参数） | `.opencode/agent/cad-agent.md`（skill 域，本仓不实现） |
| **designerAgent** | 设计规范 / 审查 / 设计意图框定 | plan 落盘（关键参数） | `.opencode/agent/designer-agent.md`（plan skill 域） |

- 输入归一（W-0018 已交付 MCP 侧）：上传 DXF/IFC、改 IFC、改 DXF → 统一「用户修改」事件（`aiifc://model/{id}/edited`），orchestrator 据此路由。
- diff 上下文（W-0016 机制扩展到编排层）：orchestrator 在 dispatch 前注入「最近两个大版本脚本 diff + PARAMS 变化」到子 agent 上下文（`scriptDiffContext` 已有，按子 agent 域裁剪）。

### 7.2 提示词封装位置

- `.opencode/agent/{ifc-agent,cad-agent,designer-agent}.md`（opencode 多 agent 名），现有 `ifc-demo.md` 收敛为 orchestrator 面；orchestrator 路由 = 「选择 agent 名 + 注入系统上下文前缀」。
- 与 skill 侧纪律（aiifc SKILL.md 契约条款）保持：子 agent 提示词只封装「职责/输入输出/纪律」，技能细节仍在 skill。

### 7.3 A2A 出口（对外暴露形态，M7+，不实现）

按 §2.1 叙事：子 agent 经 A2A 协议暴露给外部主 agent（§4.5 的 plan/cad/bim subagent 集群）。本 spec 只定边界：**A2A 是薄出口**——外部主 agent 经 A2A 调子 agent = 触发一次「落盘输入 + 事件回填」的编排，与内向对话面共享同一 Core/Shell；实现留 M7+，届时重评 Eino（AgentAsTool）vs opencode 多 agent 名两条出口实现路径。

---

## 8. 里程碑切分

| 里程碑 | 内容 | 依赖 |
|---|---|---|
| **v0.3**（今天，本迭代） | 本 spec 定稿 + notify 事件化（Task 2：Core/Shell 重构，行为保持）+ 5 项 deferred minor 清扫 | 本 spec |
| **M6**（orchestrator 骨架） | 事件总线壳落地（bus 类型 + 归一适配 + 通用 dispatch 循环）、意图路由层（首条消息 → 子 agent 名）、opencode 多 agent 名拆分、abort 扩展至 in-flight notify | v0.3 |
| **M6+**（子 Agent 接入） | IFCagent / CADAgent / designerAgent 提示词封装 + 结果汇总呈现；输入归一与 diff 注入贯通编排层 | M6 |
| **M7+**（A2A 出口 / Eino 决策点） | A2A 薄出口 PoC；Eino 重评（§4.2 触发条件）——「替换执行器」路径或维持 opencode | M6+ |

Eino 评估不阻塞任何前置：事件总线、Core/Shell、意图路由全部运行时无关；Eino 只影响「Shell 的 LLM 调用端」的实现选择。

---

## 9. 风险与开放问题（需用户裁决）

1. **【裁决】框架主轨**：§4.2 建议保持现状（opencode serve）为主轨、Eino 留 M7+ 备轨——是否认可？迁移触发条件（独立上下文委派承载不住 / Eino 稳定至 1.0 + provider 实测）是否合适？
2. **【裁决】事件总线载体**：v1 定为进程内逻辑总线（无持久化，重启丢 state，与现状一致）；是否接受？若 v2 需要跨进程/可重放总线（event store），再立工作项。
3. **【裁决】abort 扩展语义**：取消 in-flight notify 时，推 `notify_failed {step:"cancelled"}` 还是静默？现状无此场景（abort 只取消 agent turn），事件化后是新增能力。
4. **【确认】子 agent 命名**：`.opencode/agent/` 拆出 `ifc-agent / cad-agent / designer-agent` 三个 agent 名（`ifc-demo` 收敛为 orchestrator 面）——命名与拆分粒度是否认可？
5. **【确认】Eino provider 适配**：现用 zhipuai/GLM 在 eino-ext 的适配未核实（【B2】）；M7+ PoC 首项就是验证它。
6. **【诚实注明】调研局限**：Eino 基于官方文档（GitHub README / CloudWeGo 手册 / Agent Collaboration / FAQ）静态调研，未跑通 Hello World、未核对 eino-ext 全量 provider 列表、未实测流式与 SSE 衔接——PoC 前不构成「可迁移」结论。

---

## 附：自查清单

- [x] 事件 URI 与 W-0025 一致（同 scheme / 同路径段 / modelId 嵌入同一位置；staged/run/saved/failed 为新延伸，注明来源）
- [x] 纯函数签名零 IO 可单测（Core 不读盘、不调 REST、不写状态；staging 内容由 Shell 注入）
- [x] Shell 副作用清单完整（§6.3 十条逐一对应现状 `notify` 全部 IO 点）
- [x] Eino 对比诚实（证据等级标注；未验证项记为【B2】并写入开放问题 5/6）

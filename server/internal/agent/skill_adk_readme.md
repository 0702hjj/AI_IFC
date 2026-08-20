# skill 模块：迁移前必须摸清（2026-08-19）

> 目的：迁移到 ADK 前，把还没细读、但对接时必然要碰的模块逐个记录清楚。
> 本文件是「读代码索引 + 对接要点」，不是设计结论。边读边补。
> 源码：`eino@v0.9.13/adk/middlewares/skill/` · 示例：`eino-examples/quickstart/chatwitheino/cmd/ch09`（+ 配套 msgops/mem/helpers/deep）

> **2026-08-19 已落地（v1 骨架）**：`agent.New` 已支持 `WithSkillsDir`，按本文 §3
> 装配官方 skill middleware（local backend → skill backend → NewTyped），模型工具面
> 获得 `skill` 工具 + progressive disclosure 提示词；实测仓库 `skills/` 目录可扫出
> 6 个 skill（全 inline 模式）。测试见 `skill_adk_test.go`。尚未做：fork 模式 / 文件工具 /
> CustomSystemPrompt 定制（后续 D 系列）。

## 0. 一句话结论

官方 skill 接入 = **一个 middleware**（`skill.NewTyped`）+ **一个 backend**（`NewBackendFromFilesystem`）。middleware 挂进 ADK agent 的 `Handlers`，backend 指向扁平 skills 目录。模型/agent 侧零自写，全部官方。

## 1. skill 包源码结构（`adk/middlewares/skill/`）

| 文件 | 内容 | 对接要点 |
|---|---|---|
| `skill.go`（711 行） | 全部核心：FrontMatter/Skill/Backend + middleware 构造 + skill 工具 | 见 §2 |
| `filesystem_backend.go`（186 行） | `NewBackendFromFilesystem`：扫描 `<BaseDir>/*/SKILL.md`，frontmatter 解析 | 只扫**第一层**；目录名 = frontmatter `name`（否则 List 空） |
| `prompt.go`（154 行） | 默认系统提示词（progressive disclosure 协议，中/英双版） | middleware 自动注入 `runCtx.Instruction`；可用 `CustomSystemPrompt` 覆盖 |
| `doc.go` | 包说明（inline/fork/fork_with_context 三种模式） | — |

## 2. skill.go 核心类型与生命周期

### FrontMatter（SKILL.md YAML frontmatter 解析出的 schema）

```go
type FrontMatter struct {
    Name        string      `yaml:"name"`
    Description string      `yaml:"description"`
    Context     ContextMode `yaml:"context"` // ""(inline) | "fork" | "fork_with_context"
    Agent       string      `yaml:"agent"`   // fork 模式指定 agent 名
    Model       string      `yaml:"model"`   // 模型覆盖名
}
```

- **我们三个 skill 的 frontmatter 只有 name/description/license/version/compatibility/metadata**——`context` 为空 = inline 模式（默认），无需 AgentHub/ModelHub。
- 若将来某个 skill 想用 fork 模式，需要额外配 AgentHub/ModelHub。

### Backend 接口（最小）

```go
type Backend interface {
    List(ctx) ([]FrontMatter, error)
    Get(ctx, name) (Skill, error)   // Skill{Content=SKILL.md 正文, BaseDirectory}
}
```

`NewBackendFromFilesystem` 需要传入一个 `filesystem.Backend`（读取真实磁盘）。ch09 用 `eino-ext/adk/backend/local`。

### middleware 注入时机（`BeforeAgent`）

```go
func (h *typedSkillHandler) BeforeAgent(...) {
    runCtx.Instruction = runCtx.Instruction + "\n" + h.instruction   // 追加 progressive disclosure 系统提示词
    runCtx.Tools = append(runCtx.Tools, h.tool)                       // 追加 skill 工具
}
```

**关键**：middleware 往 agent 上下文追加「系统提示词 + skill 工具」。所以「挂载 skill」=「往 Handlers 塞一个 middleware」，agent 自己完全不用改。

### skill 工具（`typedSkillTool`）——模型可见面

- **默认工具名**：`skill`
- **入参**：`{"skill": "<name>"}`
- **Info()**：调 `Backend.List` 渲染工具描述（含全部 skill 的 name+description 列表）→ 模型知道有哪些 skill
- **InvokableRun()**：调 `Backend.Get` → 按 frontmatter `Context` 分流：
  - inline（默认）：`buildSkillResult` 返回 SKILL.md 正文 + BaseDirectory（`defaultSkillContent` 组装）
  - fork / fork_with_context：`runAgentMode` 起一个子 agent 跑 skill（需 AgentHub）

### 三个可定制钩子（对接我们时可能要用）

| 钩子 | 作用 |
|---|---|
| `CustomSystemPrompt` | 覆盖 progressive disclosure 系统提示词（可改成中文/平台风格） |
| `CustomToolDescription` | 覆盖 skill 工具描述渲染 |
| `BuildContent` / `BuildForkMessages` / `FormatForkResult` | 定制 skill 内容返回 / fork 消息 / fork 结果格式化 |

## 3. ch09 示例装配（`cmd/ch09/main.go`）

### 装配骨架（关键行）

```go
// ① 真实磁盘 backend（eino-ext）
backend, _ := localbk.NewBackend(ctx, &localbk.Config{})      // :125

// ② skill backend（扫 skillsDir）
skillBackend, _ := skill.NewBackendFromFilesystem(ctx, &skill.BackendFromFilesystemConfig{
    Backend: backend, BaseDir: skillsDir,                     // :140-143
})

// ③ skill middleware
skillMiddleware, _ := skill.NewTyped[M](ctx, &skill.TypedConfig[M]{
    Backend: skillBackend,                                    // :148-150
})
handlers = append(handlers, skillMiddleware)

// ④ 挂进 DeepAgent
cfg := &deep.TypedConfig[M]{
    ChatModel: cm, Instruction: agentInstruction,
    Backend: backend, StreamingShell: backend, MaxIteration: 50,
    Handlers: handlers,                                        // :159-173
}
agent, _ := deep.NewTyped[M](ctx, cfg)
```

### skillsDir 解析（ch09 `resolveSkillsDir`）

- 环境变量 `EINO_EXT_SKILLS_DIR`，绝对路径 + 目录存在才启用；不存在则跳过（skill 工具不挂）。

### 会话与 Runner（ch09）

- `Runner.Run(ctx, history, WithCheckPointID(sessionID))` —— **传完整历史**，不是单条用户消息
- `PrintAndCollect` 消费 AgentEvent 流（`helpers`）
- interrupt 处理：`handleInterrupt` → `ResumeWithParams(ctx, checkPointID, {interruptID: resumeData})`

### 配套包（迁移要摸清）

| 包 | 作用 | 对我们 |
|---|---|---|
| `msgops` | Message 类型（`*schema.Message` / `*schema.AgenticMessage`）与用户/助手消息构造 | 平台当前用 `*schema.Message`；AgenticMessage 是新的双通道形态 |
| `mem` | 会话持久化（`GetOrCreate`/`Append`/`GetMessages`） | 我们已有 EventStore JSONL，未必用它 |
| `helpers` | `PrintAndCollect`（消费事件流 + 捕获 interrupt） | **关键**——翻译层 2.0 要重写等价物 |
| `deep` | DeepAgent 预构建（Backend + StreamingShell + TaskTool） | 是否用 DeepAgent 还是 ChatModelAgent，迁移时裁决 |

## 4. 与我们平台的对接点（迁移前要拍板的）

| 对接点 | 现状（经典侧） | ADK 侧对应 | 决策 |
|---|---|---|---|
| **系统提示词注入** | persona 常量（subagent.go） | skill middleware 自动追加；`CustomSystemPrompt` 可定制 | 我们的 OrchestratorPersona / 子 agent persona 如何与 skill 的 progressive disclosure 提示词共存 |
| **skill 工具入参** | 无（薄壳方案有 `load_skill{skill}`） | `skill{"skill": name}` | 用官方工具名 `skill`；前端/翻译层是否感知 |
| **skill 工具结果形状** | 无 | inline 返回 SKILL.md 正文 + BaseDirectory（`defaultSkillContent` 组装） | 翻译层 2.0 的 tool/result 帧怎么渲染这个 |
| **fork 模式** | 无（深度预算 1，子不见父历史） | `context: fork` 需 AgentHub | 我们三个 skill 默认 inline；是否需要 fork 待裁决 |
| **前端边栏子事件** | subagentId 打标上浮 | AgentAsTool + EmitInternalEvents / AgentEvent.RunPath | 子 agent 事件到 SSE 的映射 |
| **filesystem 访问** | 无 | `eino-ext/adk/backend/local`（真实磁盘）+ DeepAgent Backend | 是否直接挂 DeepAgent 拿文件工具，还是只挂 skill middleware |

## 5. 需要补读的（本次没读完）

- `filesystem_backend.go` 的 frontmatter 解析边界（`parseFrontmatter` / `stripLineNumbers`）——与 `tools/skill_pack.py` 的 frontmatter 校验是否冲突
- `prompt.go` 默认系统提示词全文——决定是否 `CustomSystemPrompt`
- `msgops` / `mem` / `helpers` 三个配套包的实现（ch09 的会话/事件/中断处理细节）
- `deep.TypedConfig` 完整字段（Backend/StreamingShell/Handlers/AgentHub 的关系）——是否用 DeepAgent 还是 ChatModelAgent
- `eino-ext/adk/backend/local` 的 Read/GlobInfo 实现边界（读 skill 目录时的路径行为）

> **2026-08-19 已补（D12）**：`adk/middlewares/filesystem/`（filesystem.go：MiddlewareConfig:222 / read_file:611 / execute:1009，
> 注入 ls/read_file/write_file/edit_file/glob/grep + execute）——「读 skill references + 执行 skill scripts」的官方路径；
> `local` backend 的 `ValidateCommand`（local.go:42）即命令白名单钩子；DeepAgent（prebuilt/deep/deep.go:219）自动挂
> filesystem middleware = 官方「标准包接入」形态。skill 格式遵循 agentskills.io 开放标准。

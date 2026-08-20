# HITL（question / FollowUp）官方支持代码群（2026-08-19）

> 目的：迁移 ADK 后，question 断点确认要用官方 interrupt/resume，先把这个代码群的
> 分层、调用链、可复用组件摸清。源码在 eino 主模块 + eino-examples。

## 0. 一句话

官方 question = **三层代码**：最底层 `components/tool` 的中断原语 → ADK 层的事件/恢复载体 → examples 层的可复用工具封装（FollowUpTool / Approval / ReviewEdit）。迁移时要复用前两层，第三层是「参考实现」。

## 1. 三层结构总览

```
 ┌── 第 1 层：components/tool/interrupt.go（eino 主模块）──────┐
 │  中断原语（任意 compose/tool 环境可用，不依赖 ADK）            │
 │    tool.Interrupt / StatefulInterrupt / CompositeInterrupt    │
 │    tool.GetInterruptState[T] / GetResumeContext[T]            │
 └──────────────────────────────────────────────────────────────┘
                              │ 底层 core.Interrupt
                              ▼
 ┌── 第 2 层：adk/interrupt.go + adk/runner.go（eino 主模块）───┐
 │  ADK 事件载体 + 恢复驱动                                      │
 │    adk.TypedInterrupt / StatefulInterrupt（返回 AgentEvent）  │
 │    AgentEvent.Action.Interrupted.InterruptContexts[].ID       │
 │    Runner.ResumeWithParams(ctx, checkPointID, ResumeParams)   │
 └──────────────────────────────────────────────────────────────┘
                              │ 参考实现（examples，非库）
                              ▼
 ┌── 第 3 层：eino-examples/adk/common/tool/ ──────────────────┐
 │  可复用工具封装（直接用或改造）                                │
 │    follow_up_tool.go      FollowUpTool：问开放问题            │
 │    approval_wrapper.go    InvokableApprovableTool：危险工具审批 │
 │    review_edit_wrapper.go InvokableReviewEditTool：审阅+改参  │
 └──────────────────────────────────────────────────────────────┘
```

## 2. 第 1 层：components/tool/interrupt.go（最底层，185 行）

**这是所有中断的最小原语，compose/工具环境就能用**（不依赖 ADK）。

| 函数 | 作用 |
|---|---|
| `tool.Interrupt(ctx, info)` | 暂停工具执行，`info` 是给用户看的中断原因 |
| `tool.StatefulInterrupt(ctx, info, state)` | 带内部状态的中断（state 需 gob 可序列化） |
| `tool.CompositeInterrupt(ctx, info, state, errs...)` | 聚合子中断（工具内部跑图/子工具时） |
| `tool.GetInterruptState[T](ctx)` | 工具被中断后恢复：判断是否被中断过 + 取保存的 state |
| `tool.GetResumeContext[T](ctx)` | 判断本工具是不是 resume 目标 + 取恢复数据 |

**核心模式**（所有 question 类工具都长这样）：

```go
func MyTool(ctx, input) (string, error) {
    wasInterrupted, _, storedState := tool.GetInterruptState[MyState](ctx)
    if !wasInterrupted {
        return "", tool.StatefulInterrupt(ctx, &MyInfo{...}, &MyState{...})  // 首次：中断
    }
    isTarget, hasData, data := tool.GetResumeContext[MyInfo](ctx)
    if !isTarget {
        return "", tool.StatefulInterrupt(ctx, &MyInfo{...}, storedState)     // 不是我的 resume：重新中断
    }
    if !hasData {
        return "", fmt.Errorf("resumed without data")                        // 无数据：报错
    }
    return data.Answer, nil                                                   // resume 目标：继续
}
```

关键：**区分「被 resume 的目标」vs「被旁路重执行」**（`GetResumeContext` 的 isResumeTarget）。

## 3. 第 2 层：adk/（中断事件 + Runner 恢复驱动）

### adk/interrupt.go（412 行）

- `adk.TypedInterrupt[M]` / `adk.StatefulInterrupt[M]`——返回 **AgentEvent**（带 `Action.Interrupted`），携带 `RunPath`（层级地址，供多层嵌套中断定位）
- `InterruptInfo{Data, InterruptContexts []*InterruptCtx}`
- `InterruptCtx`（= core.InterruptCtx）：`{ID, Address, Info, IsRootCause...}` —— **resume 时按 ID 定位**
- `WithCheckPointID(id)`：中断持久化的 checkpoint 标识
- `AppendAddressSegment` / `FromInterruptContexts`：嵌套地址处理

### adk/runner.go（恢复驱动）

```go
runner := adk.NewRunner(ctx, adk.RunnerConfig{Agent, EnableStreaming, CheckPointStore})

iter := runner.Query(ctx, input, adk.WithCheckPointID(cid))
// 消费事件，捕获 Interrupted：
//   interruptID := lastEvent.Action.Interrupted.InterruptContexts[0].ID
//   ic.Info 是用户可见的中断信息（如 FollowUpInfo）

// 用户回答后：
iter2, err := runner.ResumeWithParams(ctx, cid, &adk.ResumeParams{
    Targets: map[string]any{ interruptID: resumeData },
})
```

**必须配 CheckPointStore**（中断状态持久化；`ResumeWithParams` 从 checkpoint 恢复运行）。

## 4. 第 3 层：examples 参考实现（三种 HITL 形态）

### follow_up_tool.go（FollowUpTool）—— 问开放问题（对齐我们的 question）

```go
type FollowUpInfo struct { Questions []string; UserAnswer string }  // UserAnswer 由用户填
type FollowUpState struct { Questions []string }                    // 中断时保存
type FollowUpToolInput struct { Questions []string `json:"questions"` }

func FollowUp(ctx, input) (string, error) {
    // 首次：StatefulInterrupt(info=Questions, state=Questions)
    // resume 目标：返回 resumeData.UserAnswer
}
func GetFollowUpTool() tool.InvokableTool  // InferTool 包装，工具名 "FollowUpTool"
```

**这正是我们 question 断点的参考实现**：模型主动调 `FollowUpTool{questions:[...]}` → 中断 → 前端弹问题 → 用户回答 → resume。

### approval_wrapper.go（InvokableApprovableTool）—— 危险工具审批（Y/N）

```go
type ApprovalInfo { ToolName, ArgumentsInJSON }
type ApprovalResult { Approved bool; DisapproveReason *string }
type InvokableApprovableTool struct { tool.InvokableTool }  // 包任意工具
// InvokableRun: 首次中断(ApprovalInfo) → resume 后 Approved 才真正执行被包工具
```

**对应我们「交付工具调了先问人」**（save/deliver 外包）。

### review_edit_wrapper.go（InvokableReviewEditTool）—— 审阅 + 改参

```go
type ReviewEditInfo { ToolName, ArgumentsInJSON, ReviewResult }
type ReviewEditResult { EditedArgumentsInJSON *string; NoNeedToEdit bool; Disapproved bool; DisapproveReason *string }
// 用户可：ok / 提供改后 JSON / N 拒绝
```

**对应例 6 形态**（改参数再执行）。

## 5. 与 ch09 的配套（中断在完整 demo 里怎么接）

ch09 `cmd/ch09/main.go` 展示了完整闭环：

```go
result := helpers.PrintAndCollect(events, PrintOptions{CaptureInterrupt: true})
if result.InterruptInfo != nil {
    assistantText = handleInterrupt(ctx, runner, checkPointID, result.InterruptInfo, reader)
    // handleInterrupt：找 IsRootCause 的 InterruptContext → 读用户输入 →
    // runner.ResumeWithParams(ctx, cid, {ic.ID: resumeData}) → 递归处理后续中断
}
```

- `helpers.PrintAndCollect`：消费 AgentEvent 流 + 捕获 interrupt（我们翻译层 2.0 的参考）
- `handleInterrupt`：中断 → 用户输入 → ResumeWithParams 的完整循环

## 6. 迁移时对接点（要拍板）

| 对接点 | 官方组件 | 我们的平台 |
|---|---|---|
| question 工具 | FollowUpTool 参考实现（examples） | 工具名/参数形状（questions[]）是否直接采用 |
| 交付审批 | approval_wrapper（包任意工具） | 包 save_script/deliver |
| 中断到 SSE | AgentEvent.Action.Interrupted | 翻译层 2.0：中断帧 → `question.ask` SSE 事件 |
| 用户回答回填 | Runner.ResumeWithParams | `POST /chat/sessions/{cid}/answer` → 组装 ResumeParams |
| checkpoint | CheckPointStore | 与 EventStore JSONL 的关系（迁移时裁决） |
| 多轮中断 | handleInterrupt 递归 | 连续多个断点（S0→S1→...）的恢复顺序 |

## 7. 待补读

- `adk/runner.go` ResumeWithParams 完整实现（resumeData 怎么注回工具 ctx）
- `adk/interrupt.go` 后半（checkpoint gob 序列化、preprocessADKCheckpoint 兼容逻辑——老 checkpoint 恢复）
- `components/tool/interrupt.go` 的 core 实现（`internal/core.Interrupt`——中断信号如何穿越 graph）
- 例 4_follow-up / 6_plan-execute-replan 的 main.go 完整 handleInterrupt 循环

# W-0051: agent 完整接入前端——流程对齐审查 + 交付执行代码加固

- **状态：** open
- **优先级：** P1
- **Milestone：** v0.13（见 PLAN-v0.1.0.md）
- **来源：** 2026-08-21 用户裁决：「目前有了这个初始版本的 agent 完整接入当前前端，需要重点关注流程对齐以及交付执行相关代码」
- **执行者/分支：** （领取时填）

## 背景

agent 初始版（Eino ChatModelAgent + AgentAsTool 三角色编排，W-0043 起）已能跑通，前端 ChatSidebar（`web/src/viewer/ChatSidebar*` + `useChatStream`）已接入 SSE。但这是「完整接入前端」的**初始版**——需要做一次系统性流程对齐审查，重点在：

1. **流程对齐**：chat 各环节（plan→cad→ifc / cad→ifc 消化 / ifc 独立）在真实前端对话里是否按设计走通，SSE 帧形状（`api_regulation.md` W-0043 契约红线）是否每一环都符合，错误文本化 + 64KB 截断是否生效。
2. **交付执行代码**：交付工具（`init_model` / `deliver_plan` / `deliver_building` / `stage_plan_to_workdir` / `stage_upstream_to_workdir` / `get_project_models` / `get_skill_workdir` / `stage_script` / `run_script` / `save_script`）在真实对话里是否可靠执行、产物是否规范落盘、失败路径是否可见。

已知待核查点（2026-08-21 整体检查已发现并修复一批，但还有深水区）：

- ifcAgentPersona 消费上游桥接已补（`stage_upstream_to_workdir` + `aiifc consume-upstream`），但**真实对话中 ifc-agent 是否真会按指引走**未被端到端验证。
- execute 白名单已修（`aiplan,aidxfv3,aiifc`），但 cad 管线**带计划执行**（`stage_plan_to_workdir` → `aidxfv3 --plan`）的真实对话未验证。
- 交付 REST 层（modelId 注册、plan 版本化）与 agent 工具层的对接只在单测层面验证，未在真实对话 + 前端刷新闭环验证。

## 涉及位置

- `server/internal/agent/`（agent.go、agents.go、tools.go、fs_backend.go、events.go）
- `server/internal/api/chat_eino.go`、`chat.go`、`project.go`、`plan.go`
- `web/src/viewer/ChatSidebar.tsx`、`useChatStream.ts`
- `docs/work/items/W-0043`（主子编排初始契约）

## 方案

1. **流程对齐审计**：用 scriptedModel（确定性 mock）走一遍「plan→cad→ifc」全链对话 + 「cad 带计划」对话 + 「ifc 独立」对话，核对每一环的 SSE 帧序列是否符合契约（含子事件标签 `sa_{turn}_{seq}`、subagent/status 合成、错误 kind 路由）。
2. **交付执行加固**：对交付工具链做「真实对话 + 前端刷新」端到端——工具调用后产物落盘 → 前端拿到 modelId → 刷新看得到。补失败路径（工具执行中途失败 → 错误可见 + 可恢复）。
3. **契约回归**：对照 `api_regulation.md` 的 SSE 帧形状 / REST 7 路由 + envelope / 前端零改动红线，逐条核对，发现偏离即修。

## 验收标准

- 三类对话（plan→cad→ifc / cad 带计划 / ifc 独立）在 scriptedModel 下全链 SSE 帧序列符合 `api_regulation.md`（子事件标签、subagent/status、错误文本化 + 64KB 截断、kind 路由）。
- 交付工具在真实对话中产物落盘正确（plan/bim/building 进 PlanStore 版本化；DXF/IFC 平台模型进 `models/{modelId}/` 注册），前端刷新能看到交付产物。
- 失败路径可观测：工具执行失败 → 用户看到错误 + 可恢复（不会卡死会话）。
- 前端零改动（除非发现前端 bug，改动需另行评估）。

## 测试要求

- 新增/更新 agent 集成测试：scriptedModel 驱动三类对话，断言 SSE 帧序列（含子事件边界）与产物落盘。
- 交付工具链补「真实对话 → 前端可见」的契约测试（REST + SSE）。
- 测试量 ≥ 实现量。

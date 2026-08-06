# W-0017: 整体 Agent（orchestrator）与子 Agent 编排

- **状态：** open
- **优先级：** P1
- **Milestone：** M6 多 Agent 编排（见 spec 2026-08-06-script-as-source-design.md §多 Agent 编排）
- **来源：** 2026-08-06 用户愿景
- **执行者/分支：** （领取时填）

## 背景

平台演化方向：一个整体 Agent 作为与设计师对话的总交互面，按任务调用子 Agent（IFCagent / CADAgent / designerAgent），并统一封装各子 Agent 的提示词设计。现有 chat 模块（chat_orchestrator.go + opencode serve）是单 agent 形态，需升级为编排层。

## 涉及位置

- `viewer/server/internal/api/chat_orchestrator.go`（现状：单 opencode 会话）
- 可能新增 `viewer/server/internal/orchestrator/` 或独立服务
- 子 Agent 提示词：`.opencode/agent/` 或 skill 侧

## 方案（待细化，先在实施前补 spec）

1. 整体 Agent 职责：用户对话、意图路由（IFC 生成/CAD 几何/设计决策）、子 Agent 提示词封装、结果汇总呈现
2. 子 Agent：IFCagent（ifcopenshell 建模，aiifc skill）、CADAgent（几何/DXF）、designerAgent（设计规范/审查）
3. 用户输入归一：上传 DXF/IFC、改 IFC、改 DXF → 统一「用户修改」事件（与 W-0018 的 MCP 解析衔接）
4. diff 上下文：大版本 + 小版本 diff 注入（W-0016 的机制扩展到编排层）

## 验收标准

- 实施前必须补独立 spec（多 Agent 是会话管理/成本/失败语义的大设计面）
- 设计师与一个入口对话，路由到子 Agent 的过程对用户透明

## 测试要求

- spec 先行；实现阶段 TDD

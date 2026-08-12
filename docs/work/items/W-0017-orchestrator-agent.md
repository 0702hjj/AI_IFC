# W-0017: 整体 Agent（orchestrator）与子 Agent 编排

- **状态：** done
- **关闭于：** 本迭代分支 feat/v0.5-portability-reuse（PR #31）
- **优先级：** P1
- **Milestone：** M6 多 Agent 编排（见 spec 2026-08-06-script-as-source-design.md §多 Agent 编排）
- **来源：** 2026-08-06 用户愿景
- **执行者/分支：** opencode / feat/v0.5-portability-reuse

## 背景

平台演化方向：一个整体 Agent 作为与设计师对话的总交互面，按任务调用子 Agent（IFCagent / CADAgent / designerAgent），并统一封装各子 Agent 的提示词设计。现有 chat 模块（chat_orchestrator.go + opencode serve）是单 agent 形态，需升级为编排层。

## 形态变更（2026-08-12 用户裁决）

落地形态由「代码级 orchestrator（Eino 评估方向）」改为「agent-agnostic 提示词包 + 数据契约」（skills/aibim-orchestrator，spec 2026-08-12-portability-reuse-design.md §4）。代码级编排与 A2A 出口不再追求；已交付的 notify 事件化/事件 URI 化保留为平台地基，不被提示词包依赖。

## 涉及位置

- `server/internal/api/chat_orchestrator.go`（现状：单 opencode 会话）
- 可能新增 `server/internal/orchestrator/` 或独立服务
- 子 Agent 提示词：`.opencode/agent/` 或 skill 侧

## 方案（待细化，先在实施前补 spec）

**spec 已定稿（2026-08-11）：docs/superpowers/specs/2026-08-11-orchestrator-design.md**

**叙事已定（2026-08-07 用户裁决）**：平台自持 orchestrator 为**内向**用户对话面；A2A 协议仅作为子 agent 的**对外暴露形态**（与同事的外部主 agent 对接，见 docs/internal/architecture/ai-bim-agent-page.md §4.5）。两者不冲突：orchestrator 是内部枢纽，A2A 是出口。

**框架候选（2026-08-07 用户建议）**：Go **Eino**（CloudWeGo LLM 应用框架，Chain/Graph 编排 + Tool 抽象）——与 Go server 同语言，评估其对 opencode serve 的替代/包裹关系。spec 阶段必须对比：Eino 编排 vs 现状裸 opencode-serve 编排（会话管理/成本/失败语义/与 SSE 地基的衔接）。

**架构基调（2026-08-08，help.md 架构精要入约）**：Pure Core + Imperative Shell——Core 是纯函数（Event+State→Action 列表，零 IO，可单测），Shell 执行全部副作用（LLM 调用、edit-service REST、converter 子进程）并把结果转为新 Event 回填闭环；不在 LLM 调用上同步等待；in-flight 任务必须可取消（子进程用进程组物理 kill，沙箱已有此先例）；事件 URI 化（如 `aiifc://model/{id}/script/saved`）为多 agent 协同打底。

1. 整体 Agent 职责：用户对话、意图路由（IFC 生成/CAD 几何/设计决策）、子 Agent 提示词封装、结果汇总呈现
2. 子 Agent：IFCagent（ifcopenshell 建模，aiifc skill）、CADAgent（几何/DXF，对接同事 aidxf）、designerAgent（设计规范/审查）
3. 用户输入归一：上传 DXF/IFC、改 IFC、改 DXF → 统一「用户修改」事件（W-0018 已交付 MCP 侧）
4. diff 上下文：大版本 + 小版本 diff 注入（W-0016 的机制扩展到编排层）

## 验收标准

- 实施前必须补独立 spec（多 Agent 是会话管理/成本/失败语义的大设计面）
- 设计师与一个入口对话，路由到子 Agent 的过程对用户透明

## 测试要求

- spec 先行；实现阶段 TDD

# Agent 编排历史演进（导读）

> 从 agent_orchestrate.md 拆分（历史演进文档，2026-08-20 拆分为多文件满足 ≤500 行门控）。本文 = 全景 + 决策问答 + 探索路线；其余拆入 *_runtime.md / *_web.md / *_decisions.md。

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

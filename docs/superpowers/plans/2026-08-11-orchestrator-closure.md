# 2026-08-11 迭代：W-0017 orchestrator 方向 + notify 事件化 + deferred minors 清扫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一天收口 W-0017 的 spec 方向 + chat notify 事件化重写（昨天止血版升级为 Pure Core + Imperative Shell）+ 昨天终审 deferred 的 5 项 minor 清扫。分支 `feat/v0.2-orchestrator-closure`（从 main a8f4e0c 切出）。

**Architecture:** 沿用 help.md 架构精要（Pure Core + Imperative Shell——Core 是纯函数 Event+State→Action 零 IO 可单测，Shell 执行全部副作用并把结果转新 Event 回填闭环）。W-0025 已把事件 URI 化打底（`aiifc://model/{id}/script/validated`），chat notify 的完整事件化是落实点。

## Global Constraints

- 测试纪律：先失败测试后实现；测试量 ≥ 实现量；测试与源码同目录（`test_*.py` / `*.test.ts(x)` / `*_test.go`）。
- verify*/validate* 校验隔离机器强制契约测试已入 CI（本迭代改动不得触发新违规）。
- 沙箱/异步测试必须条件等待（轮询+超时，禁止固定 sleep）。
- API 变更走 envelope + 契约测试；改端点后 `cd docs && npm run gen:api && npm run check:api`。
- Go 测试：`cd viewer/server && go vet ./... && go test ./...`（PG 无 DSN 自动 skip）。
- commit 信息中文、前缀式；一天一次 PR。

---

## Task 1: W-0017 spec——Eino 调研 + orchestrator 事件总线设计

**Files:**
- Add: `docs/superpowers/specs/2026-08-11-orchestrator-design.md`
- Modify: `docs/work/items/W-0017-orchestrator-agent.md`（补「方案已定稿」锚点；状态保持 open）

**Interfaces:**
- 调研 Go Eino（CloudWeGo LLM 应用框架：Chain/Graph 编排 + Tool 抽象）vs 现状裸 opencode-serve 编排。对比维度：会话管理、成本、失败语义、与现有 SSE 地基的衔接、对 notify 事件化的承载。需 webfetch Eino 官方资料。
- 设计：orchestrator 职责（用户对话面 + 意图路由 + 子 Agent 提示词封装 + 结果汇总）、子 Agent 划分（IFCagent / CADAgent / designerAgent）、**事件总线规约**（事件 URI 表、Event+State→Action 纯函数签名、Shell 执行模型、in-flight 取消、幂等/重放）。
- 结论裁决点：Eino 替代/包裹 opencode-serve，或保持现状演进——spec 给出对比矩阵与建议，最终裁决留用户。
- **不写实现**——今天只落 spec + 把 notify 事件化设计细则写进 spec（供 Task 2 实施）。

- [x] **Step 1: 调研 Eino**（webfetch 官网/文档，收集能力与限制）
- [x] **Step 2: 写 spec**（架构基调、事件总线、纯函数签名、notify 事件化细则、对比矩阵、建议结论）
- [x] **Step 3: W-0017 item 锚点 + 评审 spec 自查**（事件 URI 与 W-0025 一致、纯函数可单测、Shell 副作用清单完整）

## Task 2: chat notify 事件化重写（Pure Core + Imperative Shell）

**Files:**
- Add: `viewer/server/internal/api/chat_core_test.go`（纯函数单测）
- Modify: `viewer/server/internal/api/chat_orchestrator.go`（notify 拆 Core 纯函数 + Shell 副作用）、`viewer/server/internal/api/chat_notify_test.go`（Shell 契约测试保留/适配）
- 事件 URI 按 spec（`aiifc://model/{id}/script/{staged|run|saved|failed}`）

**Interfaces:**
- **Pure Core**（零 IO，可单测）：`planNotify(ev, state) -> []Action`——输入事件（file.edited/session.idle+dirty）+ 状态（是否有 staging 脚本、当前 staged 步数、版本），输出动作列表（`{type:"discard_pending"}` / `{type:"stage_script", script}` / `{type:"run_script"}` / `{type:"save_script"}` / `{type:"reconvert"}` / `{type:"notify", event:"viewer.committed", payload}` / `{type:"notify_failed", step, reason}`）。纯决策，不 IO。
- **Imperative Shell**：执行 Action 列表（edit-service REST、staging 读、SetStatus/Enqueue、归档），每步结果转为新 Event 回填 Core（驱动多轮）。保留现有契约测试断言（顺序、失败分支、重转、归档）。
- 保持对外行为不变：`viewer.committed` / `viewer.notify_failed` 事件语义、script 管线顺序（DELETE pending → PUT /script → run → save）、无脚本路径。
- 重构目标：决策逻辑与副作用分离，Core 单测覆盖所有分支（有/无脚本、失败 step、版本不可解析）。

- [x] **Step 1: 写失败测试**（Core 纯函数单测：各分支 Action 列表断言；当前命令式实现无此形态 → RED）
- [x] **Step 2: 重构 notify 为 Core + Shell**（行为保持，既有 chat_notify_test.go 契约测试转绿）
- [x] **Step 3: 全量 go test + go vet**（PG skip）

## Task 3: deferred minors 清扫（终审 triage 5 项）

**Files:**
- Modify: `viewer/server/internal/api/api_verify_isolation_test.go`（Go 侧补闭包 handler 扫描 + 自证）
- Modify: `viewer/edit-service/tests/test_verify_isolation.py`（Python 侧别名 import 逃逸检测补注 + 自证）
- Modify: `tests/skill/test_script_contract.py`（骨架 origin 恒真断言改锁具体值 "traced"）
- Modify: `viewer/web/src/viewer/DesignPanel.tsx`（嵌套键 scrollIntoView 前缀匹配）+ `viewer/web/src/viewer/DesignPanel.test.tsx`（聚焦 effect + 手动切模式清焦点测试）
- Modify: `skills/aiifc/hooks/opencode-plugin.ts`（win32 注释：超时终止只杀父进程）或文档注

**Interfaces:**
1. Go 契约测试：`inlineWriteErrCalls` 补 `HandleFunc(path, func(w,r){...})` 闭包 handler 扫描（handleFunc 工厂返回的 FuncLit 也扫）。
2. Python 契约测试：补「别名 import HTTPException 逃逸」自证/文档注（`from fastapi import HTTPException as H` 形态检出或显式声明 out-of-scope）。
3. 骨架 origin 断言：`in ("literal","params","traced")` → 锁 `== "traced"`。
4. web：嵌套键 scroll 前缀匹配 + 手动切模式清 focusKeys + 重复 jump nonce 测试。
5. win32 孤儿沙箱：注释/文档标注（平台限制）。

- [x] **Step 1: 各项先写失败测试/自证（当前红）**
- [x] **Step 2: 逐项修**
- [x] **Step 3: 对应套件全绿**（go / edit-service / skill / web lint+test）

---

## Finish

- 全分支终审（final code review）→ 更新工作项状态（W-0017 补 spec 锚点，其余不需要）+ PLAN 勾掉（新增 v0.3 行）→ 一天一次 PR。

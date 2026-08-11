# 2026-08-11 迭代二：可复用性加速（Go OpenAPI / skill 打包泛化 / ifc 独立调用文档）+ 上线健壮性（diff 超时 / 重转去重 / stale 清扫）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户裁决「毕业（只剩 CAD）前非 CAD 全做」；本轮做 AB 两组 6 项，聚焦可复用性加速与上线健壮性。分支 `feat/v0.2-orchestrator-closure` 累积（一天一次 PR 收口）。

**用户核心诉求（2026-08-11）**：可复用性优先——skill 封装可被其他人复用；核心 diff/修改业务封装好；保留前端与 PG 的接口；接口可直接调用或移植；vitepress 文档介绍清楚方便调用。

## Global Constraints

- 测试纪律：先失败测试后实现；测试量 ≥ 实现量；测试与源码同目录。
- verify*/validate* 校验隔离机器强制契约测试已入 CI；改动不得触发新违规。
- API 变更走 envelope + 契约测试；改端点后 `cd docs && npm run gen:api && npm run check:api`。
- Go：`cd server && go vet ./... && go test ./...`（PG skip）；edit-service：`cd services/ifc && uv run --group dev pytest`；docs：`cd docs && npm run docs:build`。
- commit 信息中文、前缀式；全部在本分支累积，收工一次 PR。

---

## Task 1 (A1): Go 网关 OpenAPI 3.0 生成 + 路由覆盖漂移检测

**Files:**
- Add: `docs/scripts/go-openapi-schema.mjs`（手工维护的 schema 定义源：每端点 request/response schema，内容来自 rest-api.md 契约）
- Add: `docs/scripts/gen-go-openapi.mjs`（生成器：读 routes.json 端点清单 + schema 源 → 输出 OpenAPI 3.0）
- Modify: `docs/package.json`（`gen:api` 加入 gen-go-openapi；`check:api` 加 go-server.openapi.json）
- Modify: `docs/site/public/go-server.openapi.json`（生成物）
- Modify: `docs/site/reference/openapi.md` + `rest-api.md`（Go server 机器可消费 OpenAPI 文档）

**Interfaces:**
- 设计（诚实边界）：Go 用 stdlib mux，无 schema 反射——请求/响应 schema 无法从代码自动导出。方案 = **路由清单自动（已有 gen-go-routes 从 mux 注册提取）+ schema 手工维护 + 覆盖漂移检测**：生成器断言「schema 定义的 path/method ⊆ routes 清单 且 routes 清单 ⊆ schema」——新路由未配 schema 会红，schema 有死路由会红。
- 输出 OpenAPI 3.0：info/tags/paths（每端点 summary/operationId/parameters（path/query）/requestBody/response envelope schema）。envelope 统一 `{code,message,data}`。
- `check:api` 三件生成物漂移检测（edit-api-reference + go-routes + go-server.openapi）。

- [ ] **Step 1: 写失败测试/自证**（生成器对「routes 有端点 schema 缺」断言红；「schema 有死路由」断言红）
- [ ] **Step 2: 写 schema 源**（覆盖 rest-api.md 全部端点：models/issues/changes/overrides/chat/script 代理）
- [ ] **Step 3: 写生成器 + 接入 gen:api/check:api**
- [ ] **Step 4: docs 文档更新 + docs build 绿**

## Task 2 (A2): skill 打包器泛化（skill_pack.py <name>）

**Files:**
- Modify: `tools/skill_pack_aiifc.py` → 泛化 `tools/skill_pack.py`（保留 aiifc 默认与兼容）
- Modify: `tests/skill/test_skill_pack_aiifc.py` → 泛化测试（含对任意 skill 目录打包）
- Modify: `tools/` 下 README 或引用处、AGENTS.md 组件表命令

**Interfaces:**
- `python tools/skill_pack.py --skill aiifc --archive`（默认 aiifc 向后兼容）；`--skill-dir` 指向任意 skill 目录。
- REQUIRED_PATHS 改为按 skill 的 frontmatter 校验（SKILL.md 必在 + name 匹配目录）+ 每 skill 可选扩展路径清单（aiifc 的 references/docs/flows 等保持必查）。
- CI `tests/skill/` 保持全绿；新增「对 CAD 目录（AI_CAD/skills/aidxfv1）打包可成功」测试（CAD skill 有 MIT LICENSE 保留，仅验证打包器通用性不迁移）。

- [ ] **Step 1: 写失败测试**（现有打包器对 aidxfv1 目录必失败：REQUIRED_PATHS 写死 aiifc 路径）
- [ ] **Step 2: 泛化打包器**（skill 名参数 + 按 frontmatter 校验 + aiifc 扩展路径保留）
- [ ] **Step 3: 迁移测试 + AGENTS/tools 引用同步**

## Task 3 (A3): services/ifc 独立调用文档（vitepress）

**Files:**
- Modify: `docs/site/reference/edit-api.md` 或新增 `docs/site/guide/services-ifc.md`（编辑 API 独立部署/调用指南）
- Modify: `docs/site/reference/ai.md`（AI 直连全流程已有 curl，补「脱离 viewer 独立部署」节）
- Modify: `docs/site/.vitepress/config.mts`（sidebar 加入）

**Interfaces:**
- 文档回答：只装 `services/ifc/`（uv sync）能否跑？`VIEWER_DATA_DIR` 与模型文件布局？独立调用端点全清单（script-as-source 编辑 + diff + locate + edit-call）？Go server / web / converter / PG 各自的「可缺省」边界？移植到新宿主的最小步骤？
- 复用性承诺落文档：`services/ifc` 是业务核心、可直接调用或移植。

- [ ] **Step 1: 核对 edit-service 独立运行事实**（config env、模型布局、依赖自包含）
- [ ] **Step 2: 写 services/ifc 独立调用文档 + sidebar + docs build**

## Task 4 (B4): diff 超时控制

**Files:**
- Modify: `services/ifc/app/routes_diff.py`（diff 计算加超时防护，超时返回错误不阻塞 threadpool）
- Modify: `services/ifc/app/config.py`（`DIFF_TIMEOUT_S` 配置，默认 60）
- Modify: `services/ifc/tests/test_diff.py`（超时分支测试）
- Modify: `server/internal/editsvc/editsvc.go`（diff 相关注释/超时语义同步；slow client 120s 保留）

**Interfaces:**
- edit-service diff 是 CPU 密集（ifcopenshell/ifcdiff），asyncio.wait_for 不适用 CPU 阻塞。方案：`concurrent.futures` 线程池执行 compute_diff + `future.result(timeout=DIFF_TIMEOUT_S)`，超时 → 504 错误信封（`{"detail": "diff timed out"}`）。或 ifc_materialize 重建也在同一超时内。
- Go slow client 已 120s——edit-service 60s 超时先触发，Go 收到 504 透传。known-limits「diff 无超时控制」→ 移除。

- [ ] **Step 1: 写失败测试**（超时分支：mock compute_diff 阻塞，断言 504）
- [ ] **Step 2: 实现超时防护 + config**
- [ ] **Step 3: known-limits 更新 + 全测试绿**

## Task 5 (B5): 重转去重（同源跳过全量重转）

**Files:**
- Modify: `server/internal/convert/queue.go`（新增 `EnqueueIfStale(id)` 或 `ShouldReconvert` 判断）
- Modify: `server/internal/api/script.go`（scriptMutatingPost 用去重判断）、`server/internal/api/chat_shell.go`（reconvert action 用去重判断）
- Modify: `server/internal/convert/queue_test.go`（去重测试）
- Modify: `docs/site/project/roadmap.md`（「增量重转」措辞改为「重转去重」落地）

**Interfaces:**
- 去重规则：`uploads/{id}.ifc` 的 mtime ≤ `model.xkt` 的 mtime → IFC 未变 → 跳过 SetStatus(converting)+Enqueue（返回 false 语义）。
- 防误跳过：仅当 XKT 存在且 IFC mtime 不新于它才跳过；任何判断失败（文件缺失）→ 保守重转。
- 调用点：scriptMutatingPost（run/save/rollback）、chat_shell reconvert、notify。注意 save 一定重写 uploads——正常 save 后 mtime 必新于 xkt，去重不误伤；重复 run 同脚本、无脚本手术路径的重放被去重。

- [ ] **Step 1: 写失败测试**（XKT mtime ≥ IFC mtime → 跳过；IFC 更新 → 重转）
- [ ] **Step 2: 实现 EnqueueIfStale + 调用点接入**
- [ ] **Step 3: roadmap 措辞 + 全测试绿**

## Task 6 (B6): stale 文档清扫

**Files:**
- Modify: `docs/site/project/known-limits.md`（「Docker Compose 未完成」→ 已交付；「英文文档为子集」实测修正；逐条对账）
- Modify: `docs/site/guide/quickstart.md` 或 project-intro（如有 stale）
- Modify: 其他被 B4/B5 影响的已知限制（diff 超时/重转条目）

**Interfaces:**
- known-limits 逐条与实现对账：compose（已交付，CI compose-smoke 在跑）、英文文档子集（实测 en 页数）、diff 无超时（B4 修复后移除）、几何 diff（已修，上轮）、pending 持久化（已落盘，非限制）。
- 只改 stale，不引入新承诺。

- [ ] **Step 1: 逐条核对 known-limits 与实现**
- [ ] **Step 2: 修正 stale 条目 + docs build**

---

## Finish

- 全分支终审（final code review）→ PLAN 勾掉（v0.3 补 B4/B5）+ 收工一次 PR。

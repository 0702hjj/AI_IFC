# 2026-08-10 迭代：script-as-source 收口（v0.2 工程契约 + 工作流加固）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一天迭代收口 script-as-source 余量：W-0024（校验隔离机器强制）、W-0023（create_skeleton 确定性化）、W-0022（ScriptMap params_keys + PARAMS 表单聚焦）、W-0021（直改退役残留收口：migrate 退役 + chat notify 止血 + smoke.sh）、W-0025（skill hooks 事件化）。分支 `feat/v0.2-script-closure`（已并入昨日 docs 尾巴）。

**Architecture:** 沿用 spec `docs/superpowers/specs/2026-08-08-script-editing-unified-design.md`；事件化完整重写（Pure Core + Imperative Shell）归 W-0017，今天只做止血（chat notify 改走 script 管线）。

**Tech Stack:** Python 3.10 / FastAPI / ifcopenshell / Go 1.26 / React 19 + zustand / opencode plugin。

## Global Constraints

- 测试纪律：先失败测试后实现；测试量 ≥ 实现量；测试与源码同目录（`test_*.py` / `*.test.ts(x)` / `*_test.go`）。
- 看到 `verify*`/`validate*` 函数名，新增检查只允许加在该函数内部（AGENTS.md 硬规则）。
- API 变更走 envelope `{code,message,data}` + 契约测试；改端点后 `cd docs && npm run gen:api && npm run check:api`。
- edit-service 测试：`cd viewer/edit-service && uv run --group dev pytest`；web：`cd viewer/web && npm test && npm run lint`；server：`cd viewer/server && go test ./...`；skill：`python -m pytest tests/skill/ -q`。
- 沙箱/异步相关测试结束必须等异步落地（条件轮询，禁止固定 sleep）。
- commit 信息中文、前缀式；全部工作在同一迭代分支累积，当天一次 PR。

---

## Task 1: W-0024 校验隔离机器强制（契约测试 + AGENTS.md 副作用禁令）

**Files:**
- Add: `viewer/edit-service/tests/test_verify_isolation.py`（契约测试，含自证）
- Add: `viewer/server/internal/api/api_verify_isolation_test.go`（Go 侧契约测试，含自证）
- Modify: `AGENTS.md`（verify* 副作用禁令入约）

**Interfaces:**
- 契约断言（Python）：edit-service 路由文件 `app/routes_*.py` 中，`raise HTTPException` 语句只能出现在 `verify*`/`validate*` 函数体内，或所在模块是 `route_common.py`。用 ast 解析实现（不依赖 grep 行号误报）。
- 契约断言（Go）：handler 函数（`viewer/server/internal/api/*.go` 中注册路由的 handler）不得内联业务规则 `writeErr`（请求形状校验的 `writeErr(w, http.StatusBadRequest, ...)` 除外——按 status code 区分）。
- 自证：每个契约测试必须对一段故意违规的样例代码断言「会变红」（对违规样例该断言失败，证明检查有区分力）。

- [ ] **Step 1: 写失败测试**（先写契约测试本身，含自证逻辑；对当前代码库应 PASS——存量已合规）
- [ ] **Step 2: 实现契约检查逻辑**（若测试对存量也失败则需收拢存量；预期存量已合规直接通过）
- [ ] **Step 3: AGENTS.md 补 verify* 副作用禁令**：`verify*` 只做检查（可返回派生数据），禁止副作用/写盘/IO。
- [ ] **Step 4: 全测试套件跑绿**（edit-service + server）

## Task 2: W-0023 create_skeleton 确定性化

**Files:**
- Modify: `skills/aiifc/references/docs/flows/script_lib.py`（create_skeleton 走确定性路径）
- Modify: `viewer/edit-service/tests/test_ifc_lazy_materialize.py`（43-47 显式绕过删除，改直接断言确定性）
- Add: `tests/skill/test_script_contract.py`（或新增骨架确定性单测）
- Modify: `viewer/edit-service/tests/test_script_locate.py`（骨架实体 locate 端到端）

**Interfaces:**
- `create_skeleton(model, name, storeys)` 内部改走 `create_entity`：骨架实体 key 固定层级式（name 无关，避免改名产生 diff 幻影：`skeleton:project` / `skeleton:site` / `skeleton:building` / `skeleton:storey:{storey名}`），GlobalId 经 `deterministic_guid`，designKey 自动写入 Pset_AIIFC，调用点重记为**用户脚本** `create_skeleton(...)` 行（origin "traced"——用户行无 `key=` 字面量，edit-call 本就不应改写骨架；2026-08-10 用户裁决：接受 traced，plan 文本同步）。
- 兼容性：已生成模型骨架 GlobalId 会变——changelog 标注。

- [ ] **Step 1: 写失败测试**：同一模板脚本两次 run，`compute_diff` 为空（含骨架实体）；骨架实体 designKey 存在；storey guid → locate 命中 create_skeleton 调用行。当前应失败（骨架随机 GlobalId）。
- [ ] **Step 2: 改 create_skeleton 走确定性路径**（用 `create_entity` 替代裸 `root.create_entity`）
- [ ] **Step 3: 更新存量测试绕过**（test_ifc_lazy_materialize.py 不再手动 fixed GlobalId）
- [ ] **Step 4: 重跑同脚本 map 字节一致性测试**（spec §8 留白一并补：两次 run 的 map.json 字节一致）
- [ ] **Step 5: 全测试套件跑绿**（skill + edit-service）

## Task 3: W-0022 ScriptMap 补 params_keys + PARAMS 表单聚焦

**Files:**
- Modify: `skills/aiifc/references/docs/flows/script_lib.py`（`_record_callsite` 落 `params_keys`）
- Modify: `viewer/edit-service/app/routes_scripts.py`（locate 透传，自动经 entry 展开）
- Modify: `viewer/edit-service/tests/test_script_locate.py` + `test_script_map_capture.py`（params_keys 断言）
- Modify: `viewer/web/src/api/types.ts`（ScriptLocateResult 加 paramsKeys）、`viewer/web/src/viewer/store.ts`（ScriptJump 携带 paramsKeys）、`viewer/web/src/viewer/PropertyPanel.tsx`（透传）、`viewer/web/src/viewer/DesignPanel.tsx`（origin=params → 切表单聚焦首个键）
- Add: `viewer/web/src/viewer/DesignPanel.test.tsx`（聚焦逻辑 vitest）

**Interfaces:**
- CallSite 条目新增 `params_keys: list[str]`：origin=params 时用 ast 解析调用行，收集 `params[...]` / `PARAMS[...]` 下标键（单键/多键/嵌套下标）。
- locate 响应带 `params_keys`；前端 origin=params 且 params_keys 非空 → DesignPanel 切 PARAMS 表单并聚焦首个键；否则维持跳脚本行。

- [ ] **Step 1: 写失败测试**（script_lib 单测：单键/多键/嵌套下标提取；locate 契约测试：params_keys 透传；前端 vitest：聚焦逻辑）
- [ ] **Step 2: 后端实现**（_record_callsite 落 params_keys；locate 透传）
- [ ] **Step 3: 前端实现**（types/store/PropertyPanel/DesignPanel 聚焦）
- [ ] **Step 4: 全测试套件跑绿**（edit-service + web lint + web test）

## Task 4: W-0021 直改退役残留收口（migrate 退役 + chat notify 止血 + smoke.sh）

**Files:**
- Modify: `viewer/server/internal/api/edit.go`（删 migrate 路由/handler/结构体 + 注释修正）、`viewer/server/internal/api/api_verify_isolation_test.go`（W-0024 Go 白名单删 `"migrateOverrides"` 行——stale 对账会拦）、`viewer/server/internal/api/edit_test.go`（TestMigrate* 改断言退役）、`viewer/server/internal/api/chat_orchestrator.go`（notify 止血：改走 script 管线，移除 PutEntity/Commit 调用）、`viewer/server/internal/api/chat_test.go`（notify 契约测试）、`viewer/scripts/smoke.sh`（脚本管线冒烟）、`docs/site/development/testing.md`（旧链路描述同步）
- 注意：`PUT /entities/{entityId}/properties`（putEntityProperties）写 Go override store、不调 edit-service——非下游 410，**保留**（overrides 历史显示依赖 GET；smoke 覆盖段仍有效），本 task 不动它

**Interfaces:**
- migrate 退役：移除 `POST /api/v1/models/{id}/overrides/migrate` 路由 + handler；`TestMigrateSuccess`/`TestMigratePartialFailure` 改为断言退役（410/404 或路由不存在），不再脚本化假阳性 200。
- chat notify 止血：notify 不再调 `PutEntity`/`Commit`；改为「若 staging 有脚本 → script 管线（暂存→run→save）；否则仅删除 pending + 重转」。契约测试断言 script 暂存→run→save 顺序。
- smoke.sh 的 edit flow 段改走 script 管线（PUT /script → run → save），不再打 `PUT /edit/entities/{guid}` + `POST /edit/commit`。
- 保留 `GET /overrides`（历史显示）与 override store 只读路径。

- [ ] **Step 1: 写失败测试**（TestMigrate* 改断言退役；chat notify 契约测试 script 管线顺序；当前应失败）
- [ ] **Step 2: migrate 退役**（删路由/handler/结构体；修 api_test.go:206 死路由调用）
- [ ] **Step 3: chat notify 止血**（改走 script 管线；移除对已退役端点调用）
- [ ] **Step 4: smoke.sh + testing.md 同步**
- [ ] **Step 5: go vet + go test ./... 跑绿**（含 PG 测试 skip）

## Task 5: W-0025 skill hooks——校验即事件 + 事件 URI 化

**Files:**
- Add: `skills/aiifc/hooks/`（opencode 形态 hooks 配置 + Claude Code 形态 hooks 配置 + 校验脚本）
- Modify: `tools/skill_pack_aiifc.py`（REQUIRED_PATHS 纳入 hooks；copy 时保留）
- Modify: `tests/skill/test_skill_pack_aiifc.py`（hooks 存在性/归档内容断言 + schema 校验测试）
- Modify: `skills/aiifc/SKILL.md`（hooks 用法 + 降级路径文档）

**Interfaces:**
- hooks：agent 写入/编辑构建脚本（匹配 `*.py` 且含 `def build(params` 契约）时自动触发 `validate_script_contract` + 沙箱试跑；结果作为事件回填（`aiifc://model/{id}/script/validated` URI 形态）。
- 不支持 hooks 的环境降级为现状（SKILL.md 注明手动校验路径）。
- 打包器纳入 hooks 文件；pack 测试断言归档内容 + schema。

- [ ] **Step 1: 写失败测试**（hooks 文件存在性 + schema 校验；pack 归档含 hooks；当前应失败）
- [ ] **Step 2: 实现 hooks 配置**（opencode + Claude Code 双形态 + 校验脚本）
- [ ] **Step 3: 打包器纳入 + SKILL.md 文档 + 降级路径**
- [ ] **Step 4: 全测试套件跑绿**（skill tests）

---

## Finish

- 全分支终审（final code review）后：更新 6 个 work item 状态为 done + PLAN-v0.1.0.md 勾掉；一天一次 PR 提合并。

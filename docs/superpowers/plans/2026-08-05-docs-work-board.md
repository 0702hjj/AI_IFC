# 文档架构落地 + 遗留清理 + 工作项看板 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地「三层 + 工作项看板」文档架构，激进清理历史遗留，把 2026-08-05 审计的 19 个问题与四步方案写入 docs/work/，新增 AGENTS.md 人机协同契约。

**Architecture:** 纯文档/删除工作，无生产代码改动。删除 → 新建 docs/work 体系 → AGENTS.md → README 修正 → site/internal 同步 → 全量验证 → gh PR。

**Tech Stack:** Markdown、VitePress（docs）、gh-cli。

**Spec:** `docs/superpowers/specs/2026-08-05-docs-architecture-design.md`

## Global Constraints

- 远程 `main` 受保护：一切改动在分支 `docs/work-board-and-cleanup` 上进行，完成后 `gh pr create`
- 仓库根：`/home/hjj0702/projects/work/AI_IFC`（下称 `<repo>`）
- 本轮**不改任何生产代码**（viewer/、skills/、tools/ 的 .go/.py/.ts 均不动；唯一例外是 `docs/scripts/internal-site.mjs` 的文档清单）
- 删除清单以 spec §4 为准，不得超出
- 实测测试数（2026-08-05）：Go 98、pytest 54、web 107（vitest 用例）、converter 1
- commit 信息用中文、遵循仓库现有风格（如 `docs(spec): ...`）

---

### Task 1: 创建迭代分支

**Files:**
- 无（git 操作）

- [ ] **Step 1: 确认基线干净并开分支**

```bash
cd /home/hjj0702/projects/work/AI_IFC
git status --short   # 期望：无输出（spec 两个 commit 已在 main）
git checkout -b docs/work-board-and-cleanup
```

Expected: `切换到新分支 'docs/work-board-and-cleanup'`

---

### Task 2: 删除遗留（archive / test/ / 旧 tests / SCAD examples / 脏文件）

**Files:**
- Delete: `docs/archive/`（整目录）
- Delete: `test/`（整目录，31 个旧 SCAD 测试）
- Delete: `tests/test_ocp_core_no_cadquery.py`、`tests/test_topology_identity.py`、`tests/skill/test_skill_pack.py`
- Delete: `research/` 下全部 `*:Zone.Identifier` 文件
- Delete: `examples/` 下 `01_*`–`20_*`（含 16/18/19/20 子目录）；保留 `build_two_storey.py`、`smoke_test_minimal.py`、`README.md`

**Interfaces:**
- Produces: 干净的 tests/ 目录（只剩 `tests/skill/test_skill_pack_aiifc.py` 与 `tests/skill/fixtures/`）；Task 4 依赖本任务后的 examples/ 结构

- [ ] **Step 1: 删除前确认无活跃引用**

```bash
cd <repo>
grep -rn "test_ocp_core\|test_topology_identity\|from auto_tools import skill_pack\|auto_tools.skill_pack" --include="*.py" --include="*.yml" . | grep -v ".venv\|node_modules"
grep -rn "docs/archive" --include="*.md" --include="*.mts" --include="*.mjs" docs README.md | grep -v node_modules
```

Expected: 第一组无输出；第二组只有 `README.md:82` 与 `README.zh-CN.md:82`（Task 12 修）

- [ ] **Step 2: 执行删除**

```bash
cd <repo>
git rm -r -q docs/archive test tests/test_ocp_core_no_cadquery.py tests/test_topology_identity.py tests/skill/test_skill_pack.py
find research -name "*:Zone.Identifier" -delete
git rm -r -q examples/01_basic_modeling.py examples/02_graph_replay.py examples/03_expressions.py examples/05_loft_sweep_revolve.py examples/06_parametric_gear_model.py examples/07_serialization_operation_tree.py examples/08_constrained_sketch.py examples/09_naca0016_blade_freecad.py examples/10_part_assembly.py examples/11_stdlib_gears.py examples/12_herringbone_planetary_gears.py examples/13_cycloidal_reducer.py examples/14_ball_bearing.py examples/15_cached_mesh_obj_export.py examples/16_compact_two_stage_planetary_reducer examples/17_static_collision_verifier.py examples/18_leg_wheel_robot_dog_leg examples/19_four_planet_planetary_reducer examples/20_integrated_bldc_joint_actuator
find research -name "*:Zone.Identifier" | wc -l   # 期望 0
ls examples
```

Expected: examples 只剩 `README.md build_two_storey.py smoke_test_minimal.py`

- [ ] **Step 3: 验证 CI 守门路径不受影响**

```bash
cd <repo>
uv venv .ci-venv 2>/dev/null || true
uv pip install --python .ci-venv pytest -q
.ci-venv/bin/python -m pytest tests/skill/ -q
```

Expected: 11 passed（test_skill_pack_aiifc.py），无关于已删文件的收集错误

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: 删除 SCAD 遗留（docs/archive、test/、旧 tests、SCAD 示例、research 脏文件）"
```

---

### Task 3: 精简 docs/internal（删 11 篇）+ 更新 internal-site.mjs

**Files:**
- Delete: `docs/internal/ai-integration.md`、`docs/internal/usage.md`、`docs/internal/open-source-plan.md`（内容先由 Task 7 迁移——**注意：本任务删除时 Task 7 尚未执行，open-source-plan.md 的迁移内容已完整写在本计划 Task 7 Step 1 中，不依赖原文件存在**）、`docs/internal/architecture/{roadmap,viewer,viewer-detail,viewerstatus}.md`、`docs/internal/viewer/{api,design,plan,README,demo_plan}.md`
- Modify: `docs/scripts/internal-site.mjs`（第 39-63 行生成首页、第 124-150 行 sidebar）

**Interfaces:**
- Consumes: Task 2 完成的分支状态
- Produces: 保留的 internal 结构：`README.md`、`team-sync.md`、`architecture/ai-bim.md`、`viewer/demo_connect.md`

- [ ] **Step 1: 删前核对保留篇目不引用被删篇目**

```bash
cd <repo>
grep -n "usage\|ai-integration\|open-source-plan\|viewer-detail\|viewerstatus\|architecture/roadmap\|architecture/viewer\|viewer/api\|viewer/design\|viewer/plan\|viewer/README\|demo_plan" \
  docs/internal/README.md docs/internal/team-sync.md docs/internal/architecture/ai-bim.md docs/internal/viewer/demo_connect.md
```

对命中的每一行：把链接改为指向替代文档（`docs/site` 对应页或 `docs/work/PLAN-v0.1.0.md`）；dead 链接直接删句。已知命中包括 `team-sync.md` 开头深入阅读行与 `ai-bim.md` 开头引用行。

- [ ] **Step 2: 执行删除**

```bash
cd <repo>
git rm -q docs/internal/ai-integration.md docs/internal/usage.md docs/internal/open-source-plan.md \
  docs/internal/architecture/roadmap.md docs/internal/architecture/viewer.md \
  docs/internal/architecture/viewer-detail.md docs/internal/architecture/viewerstatus.md \
  docs/internal/viewer/api.md docs/internal/viewer/design.md docs/internal/viewer/plan.md \
  docs/internal/viewer/README.md docs/internal/viewer/demo_plan.md
find docs/internal -type f | sort
```

Expected: 只剩 `README.md`、`architecture/ai-bim.md`、`team-sync.md`、`viewer/demo_connect.md`

- [ ] **Step 3: 更新 internal-site.mjs 生成首页（替换「内部文档」一节）**

把生成首页中（现第 50-56 行附近）：

```
## 内部文档

- [内部首页](/internal/README) · [团队同步](/internal/team-sync)
- [总体架构（源）](/internal/architecture/ai-bim) · [Viewer 详细（源）](/internal/architecture/viewer-detail) · [现状评估](/internal/architecture/viewerstatus)
- [内部 Roadmap](/internal/architecture/roadmap) · [开源方案](/internal/open-source-plan)
- [使用文档（源）](/internal/usage) · [AI 接入（源）](/internal/ai-integration)
- [Viewer 历史文档](/internal/viewer/README)
```

替换为：

```
## 内部文档

- [内部首页](/internal/README) · [团队同步](/internal/team-sync)
- [总体架构（源）](/internal/architecture/ai-bim) · [Chat 模块契约](/internal/viewer/demo_connect)

## 工作项看板

- [看板规则](/work/README) · [审计 2026-08-05](/work/AUDIT-2026-08-05) · [v0.1.0 计划](/work/PLAN-v0.1.0)
```

- [ ] **Step 4: 更新 internal-site.mjs sidebar（替换前两个分组）**

把 `internalSidebar` 的前两个分组（现第 124-143 行）替换为：

```js
  {
    text: '内部 · 团队',
    items: [
      { text: '内部首页', link: '/internal/README' },
      { text: '团队同步', link: '/internal/team-sync' },
      { text: '总体架构（源）', link: '/internal/architecture/ai-bim' },
      { text: 'Chat 模块契约', link: '/internal/viewer/demo_connect' },
    ],
  },
  {
    text: '工作项看板',
    items: [
      { text: '看板规则', link: '/work/README' },
      { text: '审计 2026-08-05', link: '/work/AUDIT-2026-08-05' },
      { text: 'v0.1.0 计划', link: '/work/PLAN-v0.1.0' },
    ],
  },
```

并在脚本第 36-37 行附近（复制 internal/superpowers 处）加一行复制 work 目录：

```js
cpSync(join(docsRoot, 'work'), join(out, 'work'), { recursive: true })
```

注：`docs/work/` 在 Task 5 才创建，此处先加复制逻辑，Task 14 统一验证构建。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "docs(internal): 精简至 4 篇有效文档，internal wiki 清单同步"
```

---

### Task 4: 重写 examples/README.md

**Files:**
- Modify: `examples/README.md`（整文件替换）

- [ ] **Step 1: 替换为以下内容**

```markdown
# AI_IFC Examples

IFC 时代的示例脚本。从仓库根运行（需 `viewer/edit-service` 的 Python 环境，含 ifcopenshell）：

```bash
cd viewer/edit-service && uv run python ../../examples/<script>.py
```

- `build_two_storey.py` — 用 ifcopenshell 直写一栋两层小楼（墙/板/开洞），演示骨架优先建模流程；产物 `two_storey.ifc` 可上传到 viewer 查看。
- `smoke_test_minimal.py` — 最小冒烟：建单墙模型并自检，用于快速验证 ifcopenshell 环境可用。

历史 SimpleCADAPI 示例（齿轮/减速器/机器人等 01-20）已于 2026-08-05 随仓库清理移除，见 git 历史。
```

- [ ] **Step 2: Commit**

```bash
git add examples/README.md
git commit -m "docs(examples): README 重写为 IFC 时代示例说明"
```

---

### Task 5: docs/work/README.md（看板规则）

**Files:**
- Create: `docs/work/README.md`

- [ ] **Step 1: 创建，内容如下**

````markdown
# 工作项看板规则

> 本目录是 AI_IFC 的可追踪工作项看板：AI agent 与人从这里领取任务、更新状态、追溯决策。
> 配套：`AGENTS.md`（人机协同契约，仓库根）· `docs/superpowers/specs/`（设计规范）。

## 目录

- `README.md` — 本规则
- `AUDIT-YYYY-MM-DD.md` — 审计报告（问题全清单 + 技术细节），工作项的来源
- `PLAN-<版本>.md` — milestone 计划，把工作项排进发布节奏
- `items/<ID>-<slug>.md` — 每个工作项一个文件

## ID 规范

- 审计发现项：`P<严重度>-<序号>`，如 `P0-1`（P0=功能 bug，P1=结构性债务，P2=卫生/小修）
- 后续新项：`W-<四位序号>` 递增，如 `W-0001`；序号不回收

## 状态机

`open → in-progress → done`，或 `wontfix`（必须写理由）。
- 领取：把状态改为 `in-progress` 并填「执行者/分支」字段
- 关闭：状态改 `done`，填「关闭于」（commit/PR 号），并确认验收标准逐条满足

## item 文件模板

```markdown
# <ID>: <标题>

- **状态：** open
- **优先级：** P0|P1|P2
- **Milestone：** M1|M2|M3|M4（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** （领取时填）

## 背景
## 涉及位置
## 方案
## 验收标准
## 测试要求
```

## 纪律

1. 修 bug 必须先写**复现/失败测试**，再改实现（测试纪律见根 AGENTS.md：测试量目标 ≈ 实现 3 倍）。
2. item 的「测试要求」是验收的硬条件，不可跳过。
3. 完成工作项后：更新 item 状态 + 在对应 PLAN 的 milestone 表勾掉。
4. 新增工作项：任何人/agent 都可新建 item 文件，初始状态 `open`，ID 按规范分配。
````

- [ ] **Step 2: Commit**

```bash
git add docs/work/README.md
git commit -m "docs(work): 工作项看板规则"
```

---

### Task 6: docs/work/AUDIT-2026-08-05.md（审计报告）

**Files:**
- Create: `docs/work/AUDIT-2026-08-05.md`

- [ ] **Step 1: 创建，内容如下**

```markdown
# 审计报告 2026-08-05

> 基线：`main @ de48dce`（PR #8 合并后）。方法：两路并行全仓调研（viewer 四组件 / skill·CI·文档·测试）+ CI/PR 状态核查。
> 结论速览：CI 全绿、8 个 PR 干净落地；工程质量高于一般 demo（统一 envelope、原子写、接口抽象 + 双存储、较密测试）。问题：4 个 P0、5 个 P1、10 个 P2。
> 本文件是工作项的唯一事实来源；领取任务见 `items/` 各文件。

## 索引

| ID | 标题 | 严重度 | Milestone | item |
|---|---|---|---|---|
| P0-1 | design 代理契约断裂 | P0 | M1 | [items/P0-1-design-proxy-envelope.md](items/P0-1-design-proxy-envelope.md) |
| P0-2 | dxf_from_design 楼梯 shaft KeyError | P0 | M1 | [items/P0-2-dxf-stair-shaft.md](items/P0-2-dxf-stair-shaft.md) |
| P0-3 | createChatProject 路径与 Go 注册不符 | P0 | M1 | [items/P0-3-chat-projects-path.md](items/P0-3-chat-projects-path.md) |
| P0-4 | demo 环境文档与实际 venv 不符 | P0 | M1 | [items/P0-4-demo-venv.md](items/P0-4-demo-venv.md) |
| P1-1 | 零鉴权 + CORS * | P1 | M4 | [items/P1-1-auth-token.md](items/P1-1-auth-token.md) |
| P1-2 | put_entity pset 修改无回滚 | P1 | M4 | [items/P1-2-put-entity-atomicity.md](items/P1-2-put-entity-atomicity.md) |
| P1-3 | edit-service 全内存状态 | P1 | M4 | [items/P1-3-editsvc-memory-state.md](items/P1-3-editsvc-memory-state.md) |
| P1-4 | chat.go 上帝文件 | P1 | M4 | [items/P1-4-chat-god-file.md](items/P1-4-chat-god-file.md) |
| P1-5 | PG 测试默认 skip | P1 | M2 | [items/P1-5-pg-tests-ci.md](items/P1-5-pg-tests-ci.md) |
| P2-1 | pyproject/uv.lock 仍是 simplecadapi 身份 | P2 | M4 | [items/P2-1-python-identity.md](items/P2-1-python-identity.md) |
| P2-2 | test/ 与 tests/ 双轨混乱 | P2 | 本轮/M4 | [items/P2-2-test-dirs.md](items/P2-2-test-dirs.md) |
| P2-3 | DESIGN_JSON_SCHEMA 示例违反自身契约 | P2 | M1 | [items/P2-3-schema-example.md](items/P2-3-schema-example.md) |
| P2-4 | README 多处过时 | P2 | M1 | [items/P2-4-readme-stale.md](items/P2-4-readme-stale.md) |
| P2-5 | examples/ 两时代混合 | P2 | 本轮 | [items/P2-5-examples-cleanup.md](items/P2-5-examples-cleanup.md) |
| P2-6 | research/ :Zone.Identifier 脏文件 | P2 | 本轮 | [items/P2-6-zone-identifier.md](items/P2-6-zone-identifier.md) |
| P2-7 | 文档站英文缺 Viewer 使用 6 页 | P2 | M3 | [items/P2-7-en-viewer-pages.md](items/P2-7-en-viewer-pages.md) |
| P2-8 | design_diff 与 ifc_fingerprint 重复实现 | P2 | M4 | [items/P2-8-diff-dedup.md](items/P2-8-diff-dedup.md) |
| P2-9 | routes_design.py:56 `__import__("os")` 手误 | P2 | M1 | [items/P2-9-os-import.md](items/P2-9-os-import.md) |
| P2-10 | dxf_from_design 次要问题 | P2 | M1 | [items/P2-10-dxf-minor.md](items/P2-10-dxf-minor.md) |

## P0 详情

### P0-1 design 代理契约断裂
`viewer/server/internal/api/design.go:54-63` 的 `designProxy` 把 Python 原始 JSON 直接写出，不包 `{code,message,data}` envelope；前端 `viewer/web/src/api/client.ts:8-13` 的 `request()` 强制要求 `env.code === 0`。Python 返回无 `code` 字段 → 所有 `/api/v1/models/{id}/design*` 端点前端必然 reject。三方测试盲区叠加：Go 侧 design.go 全部 11 条路由无测试；前端 DesignPanel 测试整体 mock 了 `@/api/client`（DesignPanel.test.tsx:50-59）；smoke.sh 不覆盖 design。**修复前必须实测验证**（起 Go server + edit-service，curl 一遍 design 端点）。

### P0-2 dxf_from_design 楼梯 shaft KeyError
`skills/aiifc/references/docs/flows/design_builder.py:114-119` 把 shaft 展开为 `{x0,x1,y0,y1}` 坐标矩形；`dxf_from_design.py:141-147` 仍按轴网索引 `s["x"][0]` 读取 → 含 shaft 楼梯必 KeyError。CI 冒烟 fixture（tests/skill/fixtures/sample_design.json）不含楼梯，绕开此路径。

### P0-3 createChatProject 路径不匹配
前端 `viewer/web/src/api/client.ts:35` 调 `POST /api/v1/chat/projects`；Go 只注册 `POST /api/v1/projects`（`viewer/server/internal/api/chat.go:96`，`cmd/server/main.go:129`）。经 `/api/v1/chat/` 前缀 mux 落到 chat mux 后 404。**修复前实测验证**；统一方向建议：Go 侧改注册 `/api/v1/chat/projects`（与 chat 模块其余端点前缀一致），README/文档同步。

### P0-4 demo 环境文档与实际 venv 不符
`skills/aiifc/SKILL.md:133` 与 `.opencode/agent/ifc-demo.md:14` 声称 demo 用根 `.venv`（已装 ifcopenshell）；实测根 `.venv` 无 ifcopenshell/ezdxf/ifcquery（装在 `viewer/edit-service/.venv`）。按文档执行直接 ImportError。修复方向：统一为 `viewer/edit-service/.venv`（edit-service 的 uv 项目自包含），改两处文档 + examples/README.md 已按此写。

## P1 详情

### P1-1 零鉴权 + CORS *
`viewer/server/internal/api/api.go:74` `Access-Control-Allow-Origin: *`；全部端点（含删除模型、edit commit、AI 聊天）无认证。默认绑 127.0.0.1 尚可，改 host 即裸奔。方案：最小 API token 中间件（env 配置，未设置=关闭，保持单机体验），CORS 白名单化。

### P1-2 put_entity pset 修改无回滚
`viewer/edit-service/app/routes_edits.py:113-145`：fields 修改包 try/except 可回滚；pset 修改（132-145 行）在 try 之外——edit_pset 抛异常时内存模型已被部分修改且无 pending 记录，与模块 docstring 宣称的原子性矛盾。

### P1-3 edit-service 全内存状态
pending（main.py:23）、design staging（main.py:24）、ModelRegistry（registry.py，无淘汰机制）均内存态：重启即丢，内存随模型数增长。方案：staging/pending 可选落盘、Registry LRU 淘汰。

### P1-4 chat.go 上帝文件
`viewer/server/internal/api/chat.go` 697 行：会话管理 + SSE 分发 + IFC GlobalId 生成 + 骨架 IFC 模板 + 三连编排 + 制品归档；`ChatHandler` 持 6 依赖 + 4 map（chat.go:57-70）。`pushLocked` 订阅者慢时丢帧（chat.go:681-688）无重同步。拆为 session/sse/orchestrator/artifact 四文件。

### P1-5 PG 测试默认 skip
`*_pgstore_test.go` 需 `VIEWER_TEST_PG_DSN`，未设即 skip → CI 跑不到 PG 路径，File/PG 双实现 parity 无保障。方案：CI 加 Postgres service container job。

## P2 详情

- **P2-1** 根 `pyproject.toml`/`uv.lock`/`MANIFEST.in` 仍是 simplecadapi 2.0.1b1 包定义；`[project.scripts]` 四个入口指向 src/。收编决策（改 aiifc 身份 / 删除 / 拆仓）见 item。
- **P2-2** `test/`（31 个旧 SCAD 测试，CI 不跑）与 `tests/` 并存；`test/test_all_features.py:16` sys.path 指向不存在的 `test/src`。本轮已删 test/ 与 tests/ 内 SCAD 测试；CI 钩子在 archived 打包器上的部分随 `tests/skill/test_skill_pack.py` 删除关闭。
- **P2-3** `skills/aiifc/references/DESIGN_JSON_SCHEMA.md:148` 示例同时给 `at` 和 `shaft`，且 shaft 用未定义的 `{w,l}` 键；`design_builder.py:113-127` 静默走 at 分支丢弃 shaft。LLM 会学到错误格式。
- **P2-4** README 修正点：`docs/archive/` 布局行（已删）、布局块补 `docs/work/` 与 `AGENTS.md`。中英两版同步。
- **P2-5** examples/ SCAD 示例已删（本轮），README 已重写。
- **P2-6** research/ 约 20 个 `:Zone.Identifier` 已删（本轮）。
- **P2-7** `docs/site/en/` 无 viewer/ 目录，英文 sidebar 缺 Viewer 使用 6 页（config.mts:130-167）。
- **P2-8** `design_diff.py:97-114` 与 `ifc_fingerprint.py:55-75` added/removed/changed 三段循环几乎逐行相同；`versions.py` 与 `design_versions.py` 同构。
- **P2-9** `routes_design.py:56` 用 `__import__("os").path.isfile` 而非正常 import。
- **P2-10** `dxf_from_design.py`：`--scale` 参数解析后未使用（:160 定义）；开口 jamb 线对水平墙退化为零长线段（:121-122）；门弧固定 0–90° 不考虑墙朝向（:124-127）。

## 未列入工作项的观察（记录在案，不行动）

- convert/queue.go:111-113 SetStatus 错误吞咽；edit.go:406-411 metadata.json 失败静默降级；diffing.py:86 跳过无法解析的 GUID——均为低severity日志缺失，随 M4 结构加固顺带处理。
- 前端轮询 2s/30 次、上传 200MB 等魔法值——记录于 site known-limits，暂不收敛。
```

- [ ] **Step 2: Commit**

```bash
git add docs/work/AUDIT-2026-08-05.md
git commit -m "docs(work): 2026-08-05 审计报告（19 个工作项索引 + 技术细节）"
```

---

### Task 7: docs/work/PLAN-v0.1.0.md（四步方案 + open-source-plan 迁移）

**Files:**
- Create: `docs/work/PLAN-v0.1.0.md`

**Interfaces:**
- Consumes: 被删除的 `docs/internal/open-source-plan.md` 的有效内容（已全部写在本任务 Step 1，无需读原文件）

- [ ] **Step 1: 创建，内容如下**

````markdown
# PLAN v0.1.0：从审计到发布

> 来源：AUDIT-2026-08-05 的四步方案 + 原 `docs/internal/open-source-plan.md`（2026-07-30）仍有效的执行细节。
> 目标：修掉 P0 → 补齐测试 → Docker Compose 一键部署 + v0.1.0 发布 → 结构加固与 SCAD 遗产收编。

## Milestone 总览

| M | 名称 | 包含工作项 | 完成判据 |
|---|---|---|---|
| M1 | 修复冲刺 | P0-1, P0-2, P0-3, P0-4, P2-3, P2-4, P2-9, P2-10 | 全部 done，CI 绿 |
| M2 | 测试补盲 | P1-5, W-0001, W-0002, W-0003 | 新增测试合入，PG job 在 CI 运行 |
| M3 | 发布化 | W-0004, W-0005, P2-7 | `docker compose up` 一键起，v0.1.0 tag + Release |
| M4 | 结构加固 + 身份收编 | P1-1, P1-2, P1-3, P1-4, P2-1, P2-8 | 全部 done，SCAD 遗产收编决策落地 |

## M1 修复冲刺（建议分支 `fix/post-v2-audit`）

顺序：每个 P0 先实测验证 → 写失败测试 → 修 → 测试转绿 → commit。P2 小修随同分支顺带。
1. P0-1（契约断裂，影响面最大）→ 2. P0-3（同为契约）→ 3. P0-2 + P2-10（同文件）→ 4. P0-4（文档）→ 5. P2-3 / P2-4 / P2-9（小修）

## M2 测试补盲

- **P1-5**：CI 加 Postgres service job，`VIEWER_TEST_PG_DSN` 指向它，跑 `go test ./...`（含 pgstore 测试）
- **W-0001**：`viewer/server/internal/api/design.go` 全部 11 条路由的 Go 测试（mock edit-service，断言 envelope 包装）——与 P0-1 修复同 PR 或紧随其后
- **W-0002**：ChatSidebar SSE 测试（viewer/web，MockEventSource）
- **W-0003**：flows 单测——`design_builder.py` SchemaError 分支、`dxf_from_design.py`（含 shaft fixture）；converter 测试加进 CI（当前 ci.yml 有 converter job，确认其在） 
- 目标比率（AGENTS.md 纪律）：新增实现代码的测试量 ≥ 3 倍

## M3 发布化（v0.1.0）

- **W-0004**：Docker Compose 一键启动（server / web / PostgreSQL / edit-service / converter），配置外置（env 文件），文档写进 site quickstart
- **W-0005**：仓库卫生——Issue/PR 模板、CONTRIBUTING 完善、示例模型入库
- **P2-7**：英文 Viewer 使用 6 页
- 许可证审计收尾（沿用原 open-source-plan 结论，下表）→ `git tag v0.1.0` + `gh release create`

### 许可证审计表（自 open-source-plan.md 迁入，2026-07-30 核对）

| 依赖 | 许可证 | 结论 |
|---|---|---|
| ifcopenshell / ifcdiff / ifcquery | LGPL-3.0 | 独立进程/PyPI 依赖使用，兼容 AGPL；已全部 PyPI 自包含（roadmap 已完成项），原「ifcdiff 本地 editable」问题已关闭 |
| deepdiff | MIT | 兼容 |
| pgx/v5 | MIT | 兼容 |
| xeokit-sdk / xeokit-convert | AGPL-3.0 | 同许可证，保持 AGPL 的现实理由 |
| web-ifc | MPL-2.0 | 兼容 |
| React / Vite / zustand / FastAPI / pydantic | MIT/BSD | 兼容 |

LICENSE 策略维持 AGPL-3.0-only + NOTICE 归档边界声明（现状已规范）。

## M4 结构加固 + 身份收编

- P1-2（put_entity 原子性）→ P1-3（状态持久化 + LRU）→ P1-4（chat.go 拆分）→ P1-1（token 中间件）
- P2-8（diff 去重）：抽 `summarize_changes()` 公共函数
- **P2-1 SCAD 遗产收编**（需用户裁决，三选一）：
  1. **保留归档**：pyproject/uv.lock/MANIFEST 改为 aiifc 身份或删除，`src/`、`skills/simplecadapi/` 加归档说明保留
  2. **移出仓库**：`src/`、`skills/simplecadapi/` 拆到独立 repo，主仓瘦身
  3. **彻底删除**：靠 git 历史留存
- 顺带：convert/queue.go 错误吞咽、edit.go metadata 静默降级、diffing.py 跳 GUID 的日志补齐

## 节奏建议

M1（1-2 天）→ M2 与 M3 可并行 → v0.1.0 发布 → M4 排入 v0.2。
````

- [ ] **Step 2: Commit**

```bash
git add docs/work/PLAN-v0.1.0.md
git commit -m "docs(work): v0.1.0 计划（四 milestone + 许可证审计迁移）"
```

---

### Task 8: 创建 19 个 item 文件

**Files:**
- Create: `docs/work/items/` 下 19 个文件，文件名与 AUDIT 索引表一致

**Interfaces:**
- Consumes: Task 5 的 item 模板、Task 6 的技术细节
- Produces: AUDIT 索引的所有链接目标

- [ ] **Step 1: 写 P0 四个 item**

每个文件按 Task 5 模板，正文从 AUDIT 对应章节取「背景/涉及位置」，补「方案/验收标准/测试要求」。逐文件内容要点（必须全部落实为实际文字，不得留空）：

`P0-1-design-proxy-envelope.md`：方案二选一——(a) Go 侧 designProxy 包 envelope（推荐，与系统一致）；(b) 前端 design 调用走裸 fetch。验收：curl 全 design 端点返回 envelope 且 code=0；前端 DesignPanel 真实联调通过。测试要求：Go 侧 design_test.go 覆盖全部 11 条路由（mock editsvc 返回裸 JSON，断言 Go 输出包 envelope）；前端 client.ts 的 design 方法加契约测试（mock fetch 返回 envelope，断言解包正确）。

`P0-2-dxf-stair-shaft.md`：方案：dxf_from_design.py 楼梯分支改为读 `{x0,x1,y0,y1}` 矩形（与 design_builder 输出对齐），兼容 design JSON 原始输入时先经 design_builder.normalize。验收：含 shaft 楼梯的 design JSON 成功出 DXF。测试要求：新增含 shaft 楼梯的 fixture，跑 dxf_from_design 断言图层含 STAIR 实体且不抛 KeyError；CI skill-pack 冒烟 fixture 同步加楼梯。

`P0-3-chat-projects-path.md`：方案（推荐）：Go 侧注册改为 `/api/v1/chat/projects`（与 chat 模块前缀一致），保留 `/api/v1/projects` 兼容一个版本或直接替换（单机产品，直接替换即可）。验收：前端「新建 AI 项目」按钮真实可用。测试要求：Go chat 路由测试断言 POST /api/v1/chat/projects 201/200；前端 client.createChatProject 测试断言请求路径。

`P0-4-demo-venv.md`：方案：SKILL.md:133 与 .opencode/agent/ifc-demo.md:14 改指 `viewer/edit-service/.venv`（uv sync 自包含）；核实 ifc-demo.md 其余命令在 edit-service 根下可跑。验收：在新 shell 按文档逐条执行不 ImportError。测试要求：CI skill-pack 的 flows 冒烟已覆盖环境正确性；文档修复本身无新测试，但验收必须人工/脚本走一遍文档命令。

- [ ] **Step 2: 写 P1 五个 item**

`P1-1-auth-token.md`：方案：Go server 加 token 中间件（`VIEWER_API_TOKEN` env，未设置=关闭保持单机体验；设置后除 /health 外全部要求 `Authorization: Bearer`）；CORS 从 `*` 改可配置白名单（默认 localhost:5173）。edit-service 侧 token 由 Go 代理注入或同样 env。验收：设置 token 后无头请求 401，带头通过；未设置时行为不变。测试要求：中间件单测（无 token/错 token/对 token/关闭四种）；现有全部 API 测试在 token 关闭下不回归。

`P1-2-put-entity-atomicity.md`：方案：把 pset 修改移入同一 try 块，异常时对已应用的 fields 回滚（现有回滚逻辑扩展覆盖 pset：先快照原 pset 值，异常时还原）。验收：构造 edit_pset 抛错的请求，模型内存态与 pending 均无残留。测试要求：pytest 新增——mock edit_pset 抛异常，断言实体 fields 与 pset 均恢复原值、pending 列表为空。

`P1-3-editsvc-memory-state.md`：方案：(a) design staging 与 pending 可选落盘（dataDir 下 `staging/{modelId}.json`，重启恢复）；(b) ModelRegistry 加 LRU（上限可配，默认 8，淘汰时先 flush 原子写）。验收：重启服务后 staging 可继续 undo/redo；连续加载 20 个模型内存稳定。测试要求：落盘/恢复 round-trip 测试；LRU 淘汰顺序与淘汰后可重新加载测试。

`P1-4-chat-god-file.md`：方案：按职责拆四文件——`chat.go`（路由+handler 装配）、`chat_session.go`（会话 CRUD+幂等）、`chat_sse.go`（事件流+pushLocked+重同步 Last-Event-ID）、`chat_orchestrator.go`（三连触发+制品归档+骨架 IFC 模板）。纯移动不改行为。验收：go vet + 现有 chat 测试全绿；SSE 断线重连不丢事件（新测试）。测试要求：现有 chat 测试不改断言全部通过；新增 SSE 重同步测试（Last-Event-ID 续传）。

`P1-5-pg-tests-ci.md`：方案：ci.yml server job 加 `services: postgres:16`（健康检查 + 端口映射），env `VIEWER_TEST_PG_DSN` 指向它。验收：CI 日志中 pgstore 测试显示 ran 而非 skip。测试要求：本项即测试基建；验证方式为 CI 运行输出。

- [ ] **Step 3: 写 P2 十个 item**

`P2-1-python-identity.md`：方案：三选一（保留归档改身份 / 拆仓 / 删除，见 PLAN-v0.1.0 M4），用户裁决后执行。验收：根 pyproject 不再自称 simplecadapi，或文件删除；uv.lock 同步。测试要求：若保留打包配置，tests/skill 与 CI skill-pack 不回归。

`P2-2-test-dirs.md`：状态直接写 `done`（关闭于本分支：test/ 与 tests/ 内 SCAD 测试已删；CI 钩子随 test_skill_pack.py 删除关闭）。背景/验收照 AUDIT 写。

`P2-3-schema-example.md`：方案：DESIGN_JSON_SCHEMA.md:148 示例改为合法形式（at+size 或 shaft 二选一，shaft 用 schema 定义的键），与 design_builder.py 行为对齐。验收：示例 JSON 过 design_builder.normalize 不抛 SchemaError 且不丢字段。测试要求：tests/skill 新增——把 schema 文档中的示例提取跑 normalize（防再次漂移）。

`P2-4-readme-stale.md`：方案：README 布局块删 `docs/archive/` 行、加 `docs/work/` 与 `AGENTS.md` 行；中英同步。验收：grep 无 archive 引用。测试要求：无（文档）。

`P2-5-examples-cleanup.md`、`P2-6-zone-identifier.md`：状态直接写 `done`（关闭于本分支对应 commit）。

`P2-7-en-viewer-pages.md`：方案：翻译 docs/site/viewer/ 6 页到 docs/site/en/viewer/，config.mts 英文 sidebar 补组。验收：英文站 sidebar 与中文对等；docs:build 通过。测试要求：CI docs job 的 vitepress build 即验证（死链会 fail build）。

`P2-8-diff-dedup.md`：方案：抽公共 `summarize_changes(base_items, target_items, key_fn)`，design_diff 与 ifc_fingerprint 各提供 key_fn/指纹提取；versions.py 与 design_versions.py 同构部分可选抽 `snapshot_store`。验收：行为不变。测试要求：现有 test_design_diff 全绿 + 为公共函数补参数化单测。

`P2-9-os-import.md`：方案：routes_design.py:56 改正常 `import os`（文件头）。测试要求：现有 design 路由测试不回归。

`P2-10-dxf-minor.md`：方案：删掉未使用的 --scale（或实现缩放，推荐删——YAGNI）；jamb 线按墙方向向量计算垂足；门弧起点角按墙朝向。随 P0-2 同分支修。测试要求：水平/垂直/斜向墙各一个 fixture 断言 jamb 线非零长。

- [ ] **Step 4: 验证索引与文件一一对应**

```bash
cd <repo>
ls docs/work/items/ | wc -l   # 期望 19
for f in $(grep -oE "items/[A-Za-z0-9._-]+\.md" docs/work/AUDIT-2026-08-05.md | sort -u); do test -f "docs/work/$f" || echo "MISSING: $f"; done
```

Expected: 19；无 MISSING 输出

- [ ] **Step 5: Commit**

```bash
git add docs/work/items/
git commit -m "docs(work): 19 个工作项（P0×4 P1×5 P2×10，含方案/验收/测试要求）"
```

---

### Task 9: AGENTS.md（人机协同契约）

**Files:**
- Create: `AGENTS.md`

- [ ] **Step 1: 创建，内容如下**

````markdown
# AGENTS.md — AI_IFC 人机协同契约

> AI agent 的第一入口。读完本文件即可在不问人的情况下：起服务、跑测试、领工作项、遵守契约。
> 人类入口：README.md · 产品文档：https://0702hjj.github.io/AI_IFC/

## 项目是什么

自托管、开源（AGPL-3.0）的 IFC 审查与编辑平台：真改 IFC（pending→commit）、版本快照 + 语义 diff、人/AI 双角色同一套 REST 编辑 API、aiifc 建模 skill。

```
浏览器 (React+xeokit) ──► Go server :8090 ──► edit-service :8100 (FastAPI+IfcOpenShell)
                               │                  └─ 真改 IFC + 版本 + diff
                               ├─► converter (Node, IFC→XKT)
AI agent ──► REST 编辑 API ────┘
           └─► skills/aiifc/（agent 直接写 ifcopenshell.api 代码）
```

## 组件与命令

| 组件 | 目录 | 测试 | 启动 |
|---|---|---|---|
| web (React 19 + xeokit + zustand) | `viewer/web` | `npm test`（vitest，107 用例）；`npm run lint`（oxlint）；`npm run build`（含 tsc） | `npm run dev`（:5173） |
| server (Go 1.26，stdlib + pgx/v5) | `viewer/server` | `go test ./...`（98 测试）；`go vet ./...` | `go run ./cmd/server`（:8090） |
| converter (Node，web-ifc + xeokit-convert) | `viewer/converter` | `npm test`（node --test） | 被 server 以子进程调用 |
| edit-service (Python 3.10 + FastAPI + ifcopenshell) | `viewer/edit-service` | `uv run pytest`（54 测试） | `VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100` |
| skill 打包 | `tools/skill_pack_aiifc.py` | `python -m pytest tests/skill/ -q`（11 测试，CI 用独立 .ci-venv） | `python tools/skill_pack_aiifc.py --archive` |
| 端到端 | `viewer/scripts/smoke.sh` | 需 server 运行 | 上传→转换→下载 |
| 文档站 | `docs/` | `npm run docs:build`；`npm run check:api`（API 文档漂移检测） | `npm run docs:dev`；内部 wiki `npm run docs:dev:internal` |

## 测试纪律（硬规则）

1. **测试量目标 ≈ 实现代码的 3 倍**（经验比例 ~75% 内容用于测试）。
2. 修 bug：先写**复现该 bug 的失败测试**，再改实现，测试转绿才允许 commit。
3. 新功能：TDD，先失败测试后实现。
4. 测试与源码同目录（`*_test.go` / `*.test.ts(x)` / `test_*.py`）。

## API 契约

- Go server 是唯一对外入口，对外路径统一 `/api/v1/{resource}/{id}`。
- 响应统一 envelope `{code, message, data}`，`code=0` 成功；**新增/修改端点必须包 envelope 并配契约测试**。
- 改 API 后必须：`cd docs && npm run gen:api && npm run check:api`（漂移检测会拦 PR）。
- modelId 格式 `^m_[0-9a-f]{16}$`；issue 截图、上传大小等限制见 `viewer/server/internal/api/api.go`。

## Git 工作流（硬规则）

- 远程 `main` **受保护，禁止直推**。一切改动开分支：`feat/...`、`fix/...`、`docs/...`。
- 用 gh-cli 提 PR：`gh pr create`；CI（ci.yml 6 job + docs.yml）绿后合并；合并后删本地/远程分支。
- commit 信息中文、前缀式（`feat(server): ...` / `fix(web): ...` / `docs: ...` / `chore: ...`）。

## 工作项流程

1. 从 `docs/work/items/` 选 `open` 项（规则见 `docs/work/README.md`）。
2. 置 `in-progress`，填执行者/分支。
3. 按 item 的「方案/验收标准/测试要求」执行；测试要求是硬条件。
4. 完成后置 `done`、填关闭 commit/PR，并在 `docs/work/PLAN-v0.1.0.md` 勾掉 milestone 行。

## 边界（不要碰）

- `src/`、`skills/simplecadapi/`：SimpleCADAPI 归档区，收编决策（P2-1）落地前冻结。
- `docs/site/public/` 下的自动生成物（`go-rest-api.routes.json` 等）：只经 `npm run gen:api` 更新。
- `viewer/data/`：运行时数据，gitignored，不要手工改。
- 内部文档（`docs/internal/`、`docs/work/`、`docs/superpowers/`）的内容**不得**复制进 `docs/site/`（公开站）。

## 环境注意

- edit-service 与 Go server 共享 `VIEWER_DATA_DIR`：两边必须指向同一 `viewer/data` 绝对路径，配错会 404 或改错文件。
- demo/flows 用 `viewer/edit-service/.venv`（含 ifcopenshell/ezdxf/ifcquery）；**根 `.venv` 没有这些包**。
- AI agent 直连 edit-service :8100 时传 `provenance.source="AI"`。
````

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: AGENTS.md 人机协同契约（命令/测试纪律/git 工作流/工作项流程/边界）"
```

---

### Task 10: README 修正（中英）+ internal/README 更新

**Files:**
- Modify: `README.md:74-84`、`README.zh-CN.md`（对应布局块）
- Modify: `docs/internal/README.md`

- [ ] **Step 1: README.md 布局块替换**

把（74-84 行）：

```
```
viewer/            # active product: the IFC platform (web / server / converter / edit-service)
skills/aiifc/      # AI authoring skill (distributable, agent-agnostic)
tools/             # skill packager (skill_pack_aiifc.py)
docs/site/         # public docs site (VitePress, published to GitHub Pages)
docs/internal/     # internal plans and team sync (not published)
docs/archive/      # archived SimpleCADAPI documentation
src/  examples/    # archived: SimpleCADAPI (SCAD), the repo's origin
```
```

替换为：

```
```
AGENTS.md          # human-AI collaboration contract (agent entry point)
viewer/            # active product: the IFC platform (web / server / converter / edit-service)
skills/aiifc/      # AI authoring skill (distributable, agent-agnostic)
tools/             # skill packager (skill_pack_aiifc.py)
docs/site/         # public docs site (VitePress, published to GitHub Pages)
docs/work/         # work-item board (audit, plans, trackable items)
docs/internal/     # internal team docs (not published)
docs/superpowers/  # design specs and implementation plans (process artifacts)
src/               # archived: SimpleCADAPI (SCAD), the repo's origin (frozen)
examples/          # IFC-era example scripts
```
```

- [ ] **Step 2: README.zh-CN.md 同步替换对应布局块**（中文措辞：`AGENTS.md # 人机协同契约（AI agent 入口）`、`docs/work/ # 工作项看板（审计/计划/可追踪工作项）`、`docs/superpowers/ # 设计规范与实施计划（过程产物）`、`src/ # 已归档：SimpleCADAPI（冻结）`、`examples/ # IFC 时代示例脚本`）

- [ ] **Step 3: 更新 docs/internal/README.md**

整文件替换为：

```markdown
# docs/internal

团队内部文档（**不发布**到公开文档站；公开内容见 `docs/site/`）。

## 保留篇目

- `architecture/ai-bim.md` — 总体架构 + 愿景映射 + 分工声明（2026-07-30 版，仍有参考价值）
- `team-sync.md` — 技术路线与关键选型决策表（2026-07-30 快照，ADR 性质）
- `viewer/demo_connect.md` — chat 模块（对话式 AI 建模）接入契约，site 无对应页

## 边界

- 可追踪的工作项、审计与 milestone 计划 → `docs/work/`
- 设计规范与实施计划（过程产物）→ `docs/superpowers/`
- 2026-08-05 精简前的历史文档（usage、ai-integration、viewer 设计/计划等）见 git 历史
```

- [ ] **Step 4: Commit**

```bash
git add README.md README.zh-CN.md docs/internal/README.md
git commit -m "docs: README 布局块更新（docs/work + AGENTS.md，删 archive 引用）+ internal README 重写"
```

---

### Task 11: site 同步（roadmap 引用工作项看板）

**Files:**
- Modify: `docs/site/project/roadmap.md`

- [ ] **Step 1: 检查 site 是否有指向已删文档的链接**

```bash
cd <repo>
grep -rn "docs/archive\|internal/usage\|internal/ai-integration\|viewer-detail\|viewerstatus\|demo_plan\|open-source-plan" docs/site --include="*.md" --include="*.mts"
```

Expected: 无输出；有则逐处修正。

- [ ] **Step 2: roadmap.md 顶部引用块后追加一行**

在 `> 公开版只保留已完成、近期与后续；内部迭代细节见仓库 docs/internal/。` 这行改为：

```
> 公开版只保留已完成、近期与后续；可追踪的工作项与实施计划见仓库 `docs/work/`（审计 + milestone 计划）。
```

- [ ] **Step 3: Commit**

```bash
git add docs/site/project/roadmap.md
git commit -m "docs(site): roadmap 指向 docs/work 工作项看板"
```

---

### Task 12: 全量验证

**Files:**
- 无新增（验证 + 可能的修复）

- [ ] **Step 1: 各组件测试**

```bash
cd <repo>/viewer/server && go vet ./... && go test ./...
cd <repo>/viewer/edit-service && uv run pytest -q
cd <repo>/viewer/web && npm test && npm run lint && npm run build
cd <repo>/viewer/converter && npm test
cd <repo> && .ci-venv/bin/python -m pytest tests/skill/ -q
```

Expected: 全绿（Go 98、pytest 54、vitest 107、converter 1、skill 11）

- [ ] **Step 2: skill 打包全链路（模拟 CI）**

```bash
cd <repo>
.ci-venv/bin/python tools/skill_pack_aiifc.py --archive --output-root /tmp/skill-dist
test -f /tmp/skill-dist/aiifc.tar.gz && echo OK
```

- [ ] **Step 3: 文档站构建 + API 漂移检测 + 内部 wiki 构建**

```bash
cd <repo>/docs
npm run docs:build
npm run check:api
npm run docs:build:internal
```

Expected: 三者成功；check:api 无 diff；internal wiki 构建无死链报错（vitepress 对死链 fail）

- [ ] **Step 4: 死链总检查**

```bash
cd <repo>
grep -rn "docs/archive" --include="*.md" . | grep -v ".venv\|node_modules\|docs/.internal\|git 历史\|2026-08-05"
grep -rn "test_skill_pack\.py" --include="*.yml" --include="*.md" .github docs | grep -v node_modules
```

Expected: 无残留引用（item/AUDIT 中以「已删」语境提及的除外）

---

### Task 13: 提交 PR

- [ ] **Step 1: 推送并创建 PR**

```bash
cd <repo>
git push -u origin docs/work-board-and-cleanup
gh pr create --title "docs: 文档架构重设计 + 遗留清理 + 工作项看板（19 项）" --body "$(cat <<'EOF'
## 概要
按 spec `docs/superpowers/specs/2026-08-05-docs-architecture-design.md` 执行：

- 新增 `AGENTS.md` 人机协同契约（命令/测试纪律/git 工作流/工作项流程/边界）
- 新增 `docs/work/` 工作项看板：规则 + AUDIT-2026-08-05（19 项）+ PLAN-v0.1.0（M1-M4）+ 19 个 item 文件
- 遗留清理：docs/archive、test/、tests 内 SCAD 测试、SCAD examples、research 脏文件
- docs/internal 16 篇 → 4 篇（open-source-plan 有效内容迁入 PLAN-v0.1.0）
- README 中英布局块更新；site roadmap 指向 docs/work；internal-site.mjs 清单同步

## 验证
- Go 98 / pytest 54 / vitest 107 / converter 1 / skill 11 全绿
- docs:build + check:api + docs:build:internal 通过
EOF
)"
```

- [ ] **Step 2: 确认 CI 绿后报告 PR URL**

```bash
gh pr checks --watch
```

---

## Self-Review 记录

- Spec §6 执行顺序全部覆盖：Task 1（分支）→ Task 2-3（删除）→ Task 5-8（docs/work）→ Task 9（AGENTS.md）→ Task 10（README）→ Task 7 内含 open-source-plan 迁移 → Task 11（site）→ Task 12（验证）→ Task 13（PR）。
- 无占位符：所有新建文件的完整内容已内联；item 文件以「内容要点」形式给出（19 个文件全部字段齐全的正文要求），执行时必须展开为完整 Markdown。
- 类型一致性：AUDIT 索引表的 item 文件名与 Task 8 Step 4 验证逻辑一致；internal-site.mjs 的 work 链接依赖 Task 5-7 的文件名（README/AUDIT-2026-08-05/PLAN-v0.1.0）。

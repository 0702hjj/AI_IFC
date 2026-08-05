# 文档架构重设计 + 遗留清理 + 审计工作项落盘

**日期：** 2026-08-05
**状态：** 待用户审阅
**前置：** 2026-08-05 全仓评估（两路并行调研 + CI/PR 状态核查），结论：CI 全绿、8 个 PR 干净落地，但存在 4 个 P0 功能 bug、5 个 P1 结构性债务、一批 P2 仓库「双身份」问题。
**本轮范围（用户已裁决）：** 只做文档——架构落地、遗留清理、审计问题与四步方案写入文档。代码修复另起分支按文档执行。

---

## 1. 目标

1. 建立「三层 + 工作项看板」文档架构，服务人机协同：AI agent 能快速找到「现在该做什么、怎么做、边界在哪」；人能追踪进度。
2. 激进清理历史遗留（git 历史可恢复）。
3. 将评估发现的 P0/P1/P2 问题与四步方案写成可追踪、可领取的工作项文档。

## 2. 目标文档架构

```
AGENTS.md                   ← 新增：人机协同契约（AI agent 第一入口）
README.md / README.zh-CN.md ← 人类入口（修正过时内容）
docs/
├── site/                   ← 公开产品文档（VitePress，结构不动；英文补齐列为工作项）
├── internal/               ← 团队内部（精简至 4 篇，见 §4.2）
├── work/                   ← 新增：工作项看板
│   ├── README.md           ← 看板规则：ID 规范、状态机、领取/关闭流程
│   ├── AUDIT-2026-08-05.md ← 本次审计全清单（P0/P1/P2 → 工作项索引 + 完整技术细节）
│   ├── PLAN-v0.1.0.md      ← 四步方案 → milestone 映射
│   └── items/              ← 每个问题一个文件
│       ├── P0-1-design-proxy-envelope.md
│       └── ...（共约 15 个）
└── superpowers/            ← specs/plans 过程产物（保持）
```

### 2.1 AGENTS.md（根目录，新增）

人机协同契约，内容：

- 项目一句话定位 + 架构图（四组件 + skill 两条 AI 路线）
- 各组件启动 / 测试 / 构建命令速查（go test ./...、pytest、vitest、node --test、smoke.sh、skill 打包）
- **测试纪律**：测试代码量目标约为实现代码的 3 倍（用户经验比例 ~75% 内容用于测试）；新代码必须先写失败测试；修复 bug 必须先写复现测试
- API 契约规则：Go 对外统一 `{code,message,data}` envelope，新增端点必须包 envelope 并加契约测试
- 文档更新义务：改 API 必须跑 `docs` 的 gen 脚本并保证 `check:api` 通过；完成工作项必须更新 item 状态
- 工作项领取流程：从 `docs/work/items/` 选 open 项 → 置 in-progress → 按验收标准执行 → 关闭
- 边界：不碰 `src/`、`skills/simplecadapi/`（归档区，收编前冻结）；不把内部文档内容泄露到 site

### 2.2 docs/work/ 工作项体系

- **ID 规范**：本次审计项 `P0-1`…`P2-12`；后续新项 `W-0001` 递增
- **状态机**：`open → in-progress → done`（或 `wontfix` + 理由）
- **item 模板**：状态 / 优先级 / 背景 / 涉及位置（file:line）/ 方案 / 验收标准 / 测试要求（明确要先写的失败测试）/ 关联 spec 或 commit
- **AUDIT-2026-08-05.md**：索引表（ID → 标题 → 严重度 → milestone）+ 每项完整技术细节（评估原始结论）
- **PLAN-v0.1.0.md**：四个 milestone——
  - M1 修复冲刺（P0-1..P0-4，先写失败测试再修）
  - M2 测试补盲（design.go 全路由、ChatSidebar SSE、converter 进 CI、PG CI job、flows 单测）
  - M3 发布化（Docker Compose、仓库卫生、许可证审计收尾、v0.1.0 tag）
  - M4 结构加固 + 身份收编（edit-service 状态持久化、chat.go 拆分、最小鉴权、put_entity 原子性、SCAD 遗产收编决策）

## 3. 工作项清单（写入 docs/work/items/）

| ID | 标题 | 严重度 | Milestone |
|---|---|---|---|
| P0-1 | design 代理契约断裂：Go 透传裸 JSON vs 前端强制 envelope | P0 | M1 |
| P0-2 | dxf_from_design.py 楼梯 shaft KeyError | P0 | M1 |
| P0-3 | 前端 createChatProject 路径与 Go 注册路径不符 | P0 | M1 |
| P0-4 | demo 环境文档与实际 venv 不符（根 .venv 无 ifcopenshell） | P0 | M1 |
| P1-1 | 零鉴权 + CORS *（最小 token 中间件占位） | P1 | M4 |
| P1-2 | put_entity pset 修改无回滚（原子性缺口） | P1 | M4 |
| P1-3 | edit-service 全内存状态 + ModelRegistry 无淘汰 | P1 | M4 |
| P1-4 | chat.go 上帝文件（697 行）拆分 + SSE 重同步 | P1 | M4 |
| P1-5 | PG 测试默认 skip，双实现 parity 无 CI 保障 | P1 | M2 |
| P2-1 | pyproject.toml/uv.lock 仍是 simplecadapi 身份 | P2 | M4 |
| P2-2 | test/ 与 tests/ 双轨混乱（本轮删 test/ 等，CI 钩子收编列 M4） | P2 | 本轮/M4 |
| P2-3 | DESIGN_JSON_SCHEMA.md 自带示例违反自身契约 | P2 | M1 |
| P2-4 | README 多处过时（测试数、docs/ 引用、ifcdiff 说法矛盾） | P2 | M1 |
| P2-5 | examples/ 两时代混合 + README 引用不存在的示例 | P2 | 本轮 |
| P2-6 | research/ 约 20 个 :Zone.Identifier 脏文件 | P2 | 本轮 |
| P2-7 | 文档站英文缺 Viewer 使用 6 页 | P2 | M3 |
| P2-8 | design_diff.py 与 ifc_fingerprint.py 重复实现 | P2 | M4 |
| P2-9 | routes_design.py:56 `__import__("os")` 手误 | P2 | M1 |
| P2-10 | dxf_from_design.py 次要问题（--scale 未使用、jamb 零长线、门弧朝向） | P2 | M1 |

> P2-2/5/6 在本文档轮随 §4 删除一并完成（删除即 done）；P2-3/4/9/10 是小修，并入 M1 修复冲刺。

## 4. 删除清单（激进方案，用户已批准，git 历史可恢复）

### 4.1 直接删除

| 对象 | 理由 |
|---|---|
| `docs/archive/`（~200 页 SCAD 文档） | 归档遗产，活跃代码零引用 |
| `test/`（31 个旧 SCAD 测试） | CI 不跑，测归档代码 |
| `tests/test_ocp_core_no_cadquery.py`、`tests/test_topology_identity.py` | SCAD 核心测试，无处可跑 |
| `tests/skill/test_skill_pack.py` | 测归档的 simplecadapi 打包器；CI 跑整目录，删文件即可 |
| `research/` 全部 `:Zone.Identifier` 文件 | 下载残留脏文件 |
| `examples/` SCAD 示例（01-20 各目录） | 两时代混合；保留 `build_two_storey.py`、`smoke_test_minimal.py`，重写 `examples/README.md` |

### 4.2 docs/internal/ 审查结论（保留 4 篇，删 10 篇，1 篇迁移后删）

**保留（4）：**

| 篇目 | 理由 |
|---|---|
| `README.md` | 边界自述，更新后保留 |
| `architecture/ai-bim.md` | 总体架构 + 愿景映射 + 分工声明，仍有效 |
| `team-sync.md` | 关键选型决策表（ADR 性质），标注快照日期后保留 |
| `viewer/demo_connect.md` | chat 模块唯一契约文档（site 无 chat 页），保留 |

**迁移后删（1）：**

| 篇目 | 处置 |
|---|---|
| `open-source-plan.md` | 仍有效的 v0.1.0 执行细节（许可证审计表、ifcdiff 处理等）并入 `docs/work/PLAN-v0.1.0.md`，原篇删除 |

**删除（10）：**

| 篇目 | 理由 |
|---|---|
| `ai-integration.md` | 被 site 的 ai/edit-api/edit-api-reference 页取代；删前核对无独有信息 |
| `usage.md` | 被 site/guide/quickstart 取代，且含过时内容（ifcdiff editable 已解决） |
| `architecture/roadmap.md` | N+1/N+2 已完成，被 site/project/roadmap + docs/work/PLAN 取代 |
| `architecture/viewer.md` | 迭代路线图全部完成，纯历史 |
| `architecture/viewer-detail.md` | 被 site 开发指南（web/server/converter/edit-service 各页）取代 |
| `architecture/viewerstatus.md` | 2026-07-30 旧评估快照（仍提 gaiass 目录），完全过时 |
| `viewer/api.md` | 被 site rest-api + 自动生成的 go-rest-api.routes.json 取代 |
| `viewer/design.md` | 2026-07-27 初始设计，已落地，纯历史 |
| `viewer/plan.md`（1317 行） | 初始实施计划，已完成 |
| `viewer/README.md` | 测试数字过时（24/47），被 site/testing 页取代 |
| `viewer/demo_plan.md` | demo 实施计划，已随 PR #4 落地 |

**统计：** internal 共 16 篇 —— 删 11、保留 4、迁移 1（open-source-plan）。

### 4.3 本轮不动的

`src/`、`skills/simplecadapi/`、`pyproject.toml`/`uv.lock`/`MANIFEST.in` 的身份收编属 P2-1/P2-2 后续工作项（M4），需单独决策「保留归档 vs 移出仓库」，本轮冻结。

## 5. README 修正（P2-4 随本轮文档一并修）

- Go 测试数 56 → 实际约 100；web 84 → 实际 84+（按实测修正）
- 删除对已不存在目录的引用；统一 ifcdiff 说法（PyPI 自包含）
- chat projects 端点路径与代码对齐（或记入 P0-3 修复时统一）
- README 与 README.zh-CN 同步

## 6. 执行顺序

1. 本 spec 用户审阅通过 → writing-plans 出实施计划
2. 删除（§4.1、§4.2）→ 验证 CI 不受影响（本地跑 pytest tests/skill/ 残余、确认无引用）
3. 新建 `docs/work/`（README + AUDIT + PLAN + ~15 个 item）
4. 新建 `AGENTS.md`
5. 修 README（§5）+ 重写 examples/README.md + 更新 internal/README.md
6. 迁移 open-source-plan 有效内容入 PLAN-v0.1.0.md
7. site 相关页同步（roadmap 引用 docs/work、testing 页数字校准——若 site 数字正确则不动）
8. 提交（按删除/新增/修正分组 commit）

## 7. 验收标准

- `docs/work/` 体系完整：每个评估发现的问题都有对应 item，且含可执行的测试要求
- AGENTS.md 足以让一个全新 AI agent 在不问人的情况下：起服务、跑测试、领工作项、遵守契约
- 删除后 CI 全绿（push 前本地验证：go test、pytest、vitest、skill-pack、docs build + check:api）
- site 无指向已删文档的死链（grep 验证）
- README 无过时陈述

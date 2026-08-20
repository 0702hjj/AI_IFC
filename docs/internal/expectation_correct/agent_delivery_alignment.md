# Agent 交付对齐设计（2026-08-20 调查裁决版）

> 上一阶段（ADK 引擎 + skill 地基 + 三角色编排）已入库（PR #55/#56）。
> 本阶段目标：**交付对齐**——让 CAD（aidxf）像 IFC（aiifc）一样有完整的
> 「run_script 交付」链路；辅助产物（plan.json / bim_supplement.json / building.json）
> 融入现有 script-as-source 版本体系，**不自创存储**。
> 前置：`agent_deployment_plan.md`（主方案 M0-M4）+ `api_regulation.md`（契约）。

## 1. 背景与目标

- **IFC 参考链路（已交付）**：create_project（骨架 IFC）→ aiifc skill 产出构建脚本
  → `run_script` 沙箱执行 → `save_script` 大版本化 → 平台模型。
- **CAD 现状**：aidxf skill 走 CLI（execute 白名单）产物落 skill 工作区——
  无 modelId、不入 store、不版本化、前端不可见；`create_project` 无 CAD kind。
- **目标**：交付对齐 = ① CAD 交付主链路「骨架脚本 + run_script」；② 辅助产物
  按方案③融入现有体系（**方案级目录 + 版本级 sidecar**）；③ 前端新建表单支持 kind。
- **2026-08-20 核实升级（用户裁决）**：create_project 语义升级为**「唯一且通用项目」**
  （projectID，单 kind = 项目下主交付模型；dxf→ifc 管线 = 项目下多模型共享 projectID）；
  **会话绑定项目**（非模型）；plan/cad/ifc **一人一个 run_script**（交付级统一用户共享沙箱，
  中间流程 execute 自由探索）；**plan 交付 = 独立端点**（B，不碰几何 script_runner）；
  **交付脚本 = normalize 产物 + 画法库**（能力保持，normalize 仍在 execute 中间流程）；
  **方案级存储 = Go 侧单点**（与 kind 无关）。

## 1.5 业务编排流（2026-08-20 用户澄清：真实项目场景）

> 现状的「新建项目 = 新建一个 IFC 模型」是旧逻辑残留（只适配 ifc 单模型）。真实业务：

```
聊天框入口（会话/项目列表）
  ├─ 新建项目：创建 project（projectID）→ 进入项目会话（1 session = 1 project）
  │     └─ 上传计划书（需求文档）→ 对话构建 → 生成多个建筑（项目下多模型）
  ├─ 历史项目：点击 → 进入该项目会话（幂等恢复，会话连续性）
  └─ 每个项目绑定一个 session（chat-sessions.json 已有持久化 + listSessions 已有）
```

关键约束（用户）：
1. **入口是聊天框**（不是 LibraryPage 新建按钮）：点聊天框 → 新建项目 → 项目会话 → 开始对话构建。
2. **一个 session 进行一个项目**：会话绑定项目（A2 方向确认）；多轮构建/隔段时间再进 → 同一会话恢复。
3. **接口兼容**：初始化空白 ifc、重命名等接口**先不变**（兼容保留）；变的是**编排逻辑**（入口 = 项目会话，不是直接建模型）。
4. **项目 = 兼容版本**：单 kind（ifc/dxf）= 项目下主交付模型；管线（dxf→ifc）= 项目下多模型共享 projectID。
5. **上传计划书**是项目初始动作（不是传 DXF/IFC）——计划书 → aiplan 归一 → plan.json → 生成建筑。
6. **历史项目 = 会话列表**：现有 `chat-sessions.json`（按 projectId 幂等）+ `listSessions` 直接支撑；前端补「历史项目/新建项目」列表 UI。

## 2. 调查结论（2026-08-20，现状盘点）

### 2.1 已对齐（无需动）

| 链路 | 位置 | 状态 |
|---|---|---|
| CAD script-as-source 端点全套（get/put/run/save/versions/diff/locate/edit-call/staging/diff/rollback） | `services/cad/app/routes_scripts.py` | ✅ 与 :8100 同构 |
| CAD 脚本契约层（PARAMS + XDATA 确定性 key + `build(params, out_path)` + write_and_validate + map.json） | `services/cad/flows/cad_script_lib.py` | ✅ 镜像 aiifc script_lib |
| 沙箱 run 语义（执行 → 原子替换 `uploads/{id}.dxf` + `current.map.json` + semanticDiff） | `services/cad/app/script_runner.py` | ✅ 同构 |
| agent 工具 kind 路由（`resolve` 按 `KindDXF` → :8200） | `server/internal/agent/tools.go:69` | ✅ run/save 对 CAD 直接可用 |
| 版本 lockstep sidecar 先例（`scripts/v{n}.py` + `meta.json` + `map.json` + `versions/v{n}.dxf`） | `services/cad/app/script_versions.py:101` | ✅ 融入锚点 |

### 2.2 缺口（本阶段要补）

| # | 缺口 | 现状 | 对齐目标 |
|---|---|---|---|
| A | create_project 只有 IFC kind | `skeletonProjectIFC`（chat_orchestrator.go:53），无 CAD 骨架 | kind=dxf → `gen_dxf` 骨架契约脚本 + 前端表单 kind 选择 |
| B | aidxf skill 产物不进平台模型 | CLI 产物落 skill 工作区，无 modelId/版本化 | 骨架脚本 + run_script 主链路；building.json 随版本 sidecar |
| C | 辅助产物（plan/bim_supplement/building.json）体系外 | 仅 fs_backend.go:15 注释提及，服务端零认知 | 方案③挂载（见 §4） |
| D | M3 交付工具未做 | locate/edit-call 工具缺；design_review 门禁化缺；HITL question SSE + /answer + 交付审批缺 | 逐项补（沿用主方案 M3） |

## 3. 已裁决决策（2026-08-20，不再讨论）

| # | 决策 | 依据 |
|---|---|---|
| D13 | **辅助产物挂载 = 方案③结合（2026-08-20 细化）**：plan.json + bim_supplement.json 作**方案级目录**（`{DATA}/plans/{projectID}/`，方案级版本化，P-1）；building.json 作**版本级 sidecar**（save 时随 `scripts/v{n}.building.json` lockstep 快照，P-2 内容源 = 服务端读 CLI 已写文件） | plan 演化独立于模型版本；building 随交付迭代需追溯 |
| D14 | **CAD 交付主链路 = 骨架脚本 + run_script（P-5 细化）**：aidxf S0-S4 中间流程走通用独立脚本（execute，自由探索）；**最终交付 = cad_script_lib 契约构建脚本 → `run_script` 沙箱（用户共享）→ DXF 进 uploads + building.json 同期落盘**。create_project kind=dxf 产 gen_dxf 骨架契约脚本。**plan/cad/ifc 一人一个 run_script**（plan = aiplan land 落盘脚本沙箱执行 → plan.json/bim_supplement.json 落方案级目录；cad = 构建脚本 → DXF+building.json；ifc = 现状 aiifc 脚本） | 与 ifc 同构；交付级统一走用户共享沙箱（三级执行模型：交付级沙箱 / 中间流程 execute） |
| D15 | **前端新建表单加 kind 选择**（ifc/dxf），createChatProject 带 kind 参数 | 对齐 A 缺口；前端零改动红线不破（新增可选项，既有行为不变） |

## 4. 目标交付链路（plan/cad/ifc 一人一个 run_script）

```
【plan 阶段】
aiplan CLI 中间流程（execute 通用脚本）──► aiplan land 落盘脚本（staged）
    ──► run_script 沙箱（用户共享）──► {DATA}/plans/{projectID}/plan.json + bim_supplement.json
    ──► save/落盘（方案级版本化 plan_history）

【cad 阶段】
create_project(kind=dxf) ──► gen_dxf 骨架契约脚本（staged）
aidxf CLI 中间流程（execute，S0-S4 生成 DSL/过程产物，自由探索）
    ──► cad_script_lib 契约构建脚本（stage_script）
    ──► run_script 沙箱（用户共享）──► uploads/{id}.dxf + current.map.json + building.json（同期落盘）
    ──► save_script ──► scripts/v{n}.py + meta.json + map.json + building.json(sidecar)
                        versions/v{n}.dxf          （lockstep，script_versions.save 扩展）

【ifc 阶段】（现状）
aiifc 脚本（stage_script）──► run_script 沙箱（用户共享）──► uploads/{id}.ifc ──► save

共享 ID：projectID 贯穿 plan/building/bim_supplement 的 project 字段（方案级目录键）
```

### 4.1 辅助产物存取契约（方案③落地）

| 产物 | 挂载 | 端点 | 说明 |
|---|---|---|---|
| `plan.json` | `{DATA}/plans/{projectID}/plan.json` | 读：`GET /projects/{projectID}/plan.json`；写：`PUT /projects/{projectID}/plan.json` | **项目资源前缀**（plan/cad/ifc 共享项目；非 chat 专属模块）；方案级当前态 + 方案级版本化（P-1） |
| `bim_supplement.json` | `{DATA}/plans/{projectID}/bim_supplement.json` | 同上（bim_supplement） | BIM 补充；随方案演化 |
| `building.json` | `scripts/v{n}.building.json` | 随 save lockstep（内容源 = **run_script 同期产物**：交付脚本把 building.json 写入沙箱 workdir，save 时服务端读；P-2）；`GET /versions` 列出 sidecar 清单 | 交付物追溯（随模型版本） |

- 写盘走现有 atomic 机制（`_write_atomic`）；读不存在返回 404（与 script 读一致）。
- **前端不加载**这些产物（仅 DXF / render.json / model.xkt），契约不变。

> **2026-08-20 调查修正（reconcile_current.md 全 6 step 收敛）**：
> - building.json 内容已按 **v2 落地**（plan 形态整栋楼 + 逐 zone DXF 指针 `zones[].dxf/sha256/floors_from/to`，schema 已更新）——sidecar 挂载不变。
> - **plan/bim_supplement 落盘修正（P-1/P-3 已裁决）**：改为**方案级目录** `{DATA}/plans/{projectID}/`（plan.json + bim_supplement.json）+ **方案级版本化**（plan 演化独立于模型版本可追溯）；**不挂模型 context、不挂模型版本 sidecar**。building.json 仍挂模型版本 sidecar（随 cad 交付迭代）。**共享 ID = projectID（方案 ID，格式 p_... 实施细化）**，贯穿 plan/building/bim_supplement 的 `project` 字段。
> - **P-5 已裁决（2026-08-20）**：**交付级（最终 DXF/plan/building）统一走用户共享 run_script 沙箱**（一人一个 run_script：plan/cad/ifc）；**中间流程走通用独立脚本**（execute 自由探索，产物为 run_script 输入工作区）。不再要求中间产物落服务端认知区——最终产物经 run_script 落规范位置（uploads / 方案级目录 / 版本 sidecar）。
> - **P-2 已裁决**：building.json sidecar 内容源 = **run_script 同期产物**（交付脚本把 building.json 写沙箱 workdir，save 时服务端读——对齐 map_text 模式 routes_scripts.py:572-576，不存在则无 sidecar）；不选 agent 工具传内容（64KB 截断 + CLI 同源一致性）。
> - **P-4 已裁决**：shot.svg **砍掉前端透出**——留 skill 工作区（人的视觉返图备查）；不进服务端/不透出前端；模型自检靠文本链（geom_check/readback/validate），svg 非模型可读图像（read_file 是 XML 文本）。
> - create_project kind=dxf = **两件事**：store 落骨架 DXF 产物（uploads）+ staging 落骨架脚本（§9.4）。


## 5. 工作分解（对齐阶段，2026-08-20 核实版）

> 核实升级：create_project = 项目级（projectID）；会话绑定项目；交付级一人一个 run_script。

| # | 工作项 | 内容 | 位置 |
|---|---|---|---|
| **A 项目创建** | A1: create_project 升级为项目级 | 创建「项目」（projectID `p_...`）+ 首交付模型（kind 可选 ifc/dxf）；单 kind = 项目下主模型；管线 = 项目下多模型共享 projectID；diff/版本**复用现有模型级逻辑**；**旧接口（初始化空白 ifc / 重命名）不变，仅编排变化** | `server/internal/api/chat_orchestrator.go` + `store`（方案级目录 + 模型） |
| | A2: 会话绑定项目 | chatSession 加 ProjectID（兼容保留 ModelID）；**1 session = 1 project**（幂等键 = projectId）；sessionBoundProject 替代 sessionBoundModel；agent 会话内可访问项目下全部模型与方案产物；旧会话无 ProjectID → 视单模型项目 | `server/internal/api/chat_session.go` + `chat_tools.go` |
| | A3: 前端聊天框入口 + 历史项目列表 | 聊天框 → 新建项目/历史项目（复用现有 listSessions + chat-sessions.json）；新建后进入项目会话；kind 选择（ifc/dxf，默认 ifc 不变）；createChatProject(title, kind) | `client.ts` + `LibraryPage.tsx` + 会话列表 UI |
| **B 方案级存储** | B1: 方案级目录（Go 单点，P-1/P-3） | `{DATA}/plans/{projectID}/`（plan.json + bim_supplement.json + plan_history/）；projectID 生成；读写端点；方案级版本化 | Go 侧（`store` 或新 `plans` 包） |
| | B2: plan 交付端点（选 B，P-5） | `POST /plans/{id}/deliver`——沙箱执行 aiplan land 落盘脚本 → 校验 → 落方案级目录；**不碰几何 script_runner** | 新（Go 或 services） |
| **B 方案级存储** | B1: 方案级目录（Go 单点，P-1/P-3） | `{DATA}/plans/{projectID}/`（plan.json + bim_supplement.json + plan_history/）；projectID 生成；读写端点；方案级版本化 | Go 侧（`store` 或新 `plans` 包） |
| | B2: plan 交付端点（选 B，P-5） | `POST /plans/{id}/deliver`——沙箱执行 aiplan land 落盘脚本 → 校验 → 落方案级目录；**不碰几何 script_runner** | 新（Go 或 services） |
| **C cad 交付链路** | C1: building.json 版本 sidecar（P-2） | `script_versions.save()` 加可选 building_text 参数（同 n lockstep）；save 读 run_script 同期产物；versions 列 sidecar 清单 | `script_versions.py` + `routes_scripts.py` |
| | C2: 交付脚本形态（③ 能力保持） | 交付脚本 = **normalize 坐标产物（只读输入）+ cad_script_lib 画法库**；normalize 仍在 execute 中间流程（唯一坐标计算点不变） | `cad_script_lib.py` + skill 交付步骤 |
| | C3: run_script 沙箱 bind normalize 产物 | 现有 `_sandbox_cmd` 只 bind 临时 workdir → 扩展 bind normalize 产物目录（输入工作区） | `script_runner.py` |
| **D 工具面 + HITL** | D1: locate/edit-call 工具（M3-①） | 工具面补漏 | `tools.go` |
| | D2: 项目/方案工具（对接 A/B） | 项目内模型列表、方案读写 | `tools.go` |
| | D3: HITL 收尾（agent 侧 ask_user **已做** 2026-08-19，补 chat 层接线） | D3a: SSE question.ask 翻译（agent 事件→前端帧）；D3b: `/answer` 端点 → `Agent.Resume`；D3c: 交付审批 middleware（save/deliver 调了先问，官方 approval_wrapper 形态） | `chat_*` + `agent`（tools.go ask_user 已有不动） |

> 依赖序：A1/A2（项目+会话）→ A3（前端）→ B1/B2（方案存储+plan 交付）→ C1-C3（cad 交付）→ D1-D3（工具面/HITL）。
> M2-③ 管线白名单端点族**不做**（aidxf CLI 已走 execute 白名单，选型已定）。

## 6. 契约对齐（api_regulation.md）

- 工具面新增必须：静态 schema（`mustTool`）、错误文本化、64KB 截断、kind 路由守卫（A1/D1/D2）。
- **create_project 禁止 MarkDirty 规则演化**：项目创建（A1）不 MarkDirty（新项目 ≠ 会话绑定项目——但 A2 后会话绑项目，规则按新绑定语义重审）。
- 新增端点必须包 envelope + 契约测试；`modelId` 格式不变；kind 路由 dxf→:8200 / ifc→:8100。
- 前端零改动红线：SSE 帧形状 / REST 7 路由不变；新建表单 kind 是可选项，既有行为不变。
- 会话绑定升级（模型→项目）：**兼容旧会话**（ModelID 保留，无 ProjectID 的旧会话按单模型项目处理）。

## 7. 测试要求（仓内硬规则）

- A1：create_project 创建项目 + 首模型（ifc/dxf 双 kind）；项目下多模型共享 projectID；diff/版本复用现有逻辑（回归）。
- A2：会话绑定项目；旧会话兼容（无 ProjectID 视为单模型项目）。
- B1：方案级目录读写 + 版本化 + projectID 格式；verify* 校验 + 404 语义 + 契约测试（≥1:1）。
- B2：plan 交付端点（沙箱执行 aiplan land → 落方案级目录；产物格式校验）。
- C1：save 带 building sidecar lockstep（同 n）；versions 列表含 sidecar 清单。
- C2/C3：交付脚本（normalize 产物 + 画法库）契约测试；run_script 沙箱 bind normalize 产物目录。
- D3：question.ask SSE 翻译（agent 事件已有，补 chat 层）；/answer 续跑；审批 middleware（确认前不执行 save）。**ask_user 工具本体已做不动**。
- 异步写盘条件等待；scriptedModel 确定性；禁止固定 sleep。

## 8. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 项目/会话绑定升级破坏旧会话 | ModelID 保留 + 无 ProjectID 视单模型项目（向后兼容） |
| aidxf 交付脚本化失真（normalize 能力丢失） | 交付脚本 = normalize 产物 + 画法库（不重算 normalize）；能力保持验证（同 DSL 两跑几何一致） |
| 多次交付版本膨胀 | 与 DXF 快照同策略：可重建则剪枝（`_prune_rebuildable_snapshots` 同款） |
| 前端新建 kind 选择 UI 复杂度 | 极薄（select 两值），默认 ifc 保持既有行为 |

## 9. 关键代码位置索引

| 想查的 | 位置 |
|---|---|
| 版本 lockstep save（扩展锚点） | `services/cad/app/script_versions.py:101` |
| CAD 脚本契约层（骨架脚本要满足的契约） | `services/cad/flows/cad_script_lib.py` |
| 骨架 IFC 生成（P1 参照） | `server/internal/api/chat_orchestrator.go:51` |
| agent 工具 kind 路由 | `server/internal/agent/tools.go:69` |
| 前端新建表单 | `web/src/pages/LibraryPage.tsx` + `web/src/api/client.ts:45` |
| 主方案 M3（HITL/交付审批） | `docs/internal/expectation_correct/agent_deployment_plan.md:394` |

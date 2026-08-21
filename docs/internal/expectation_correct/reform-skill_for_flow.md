# reform-skill_for_flow —— Skill × 三管线流程编排（业务连续性 + 改造颗粒度）

> 本文梳理 **skill 本身 + 三管线（ifc / cad / cad->ifc）的可执行化单元流程**，回答：
> 1. agent 现有 tool 外接接口是什么（含 mcp/app 项目逻辑）？
> 2. 三个管线的可执行化单元流程是什么（skill 步骤 × tool 编排）？
> 3. 业务是否正常连续（断点/依赖/产物链）？
> 4. **skill 最后交差怎么改造**（颗粒度到 aidxf S4 交付改造 / deliver 被 script 工具替代 /
>    init_model 前置 / aiifc 解析消费链）？
>
> 定位：**流程编排设计文档**——给后续 skill 编排/管线可执行化（M3+）定骨架。
> 颗粒度：aidxf S4 交付改造（§2.3「S4 交付改造」+ §4.1）已定到「每步怎么改」——
> deliver 的复制 DXF 被 script 工具链替代，building.json 指针改 modelId，init_model 前置，
> draw 调用序列固化 build() 脚本是唯一新增改造（前置沙箱共享画法层已完成）。

---

## 一、Agent 工具外接接口（现状全景）

### 1.1 平台 chat REST 工具（项目/方案链，orchestrator 级）

| 工具 | 作用 | 外接接口 | 管线归属 |
|---|---|---|---|
| `create_project` | 创建项目（kind 必选；ifc/cad->ifc 建项目即初始化 ifc 骨架） | `POST /api/v1/chat/projects` | 三管线入口 |
| `init_model` | 项目下初始化骨架模型（分配 modelId；script-as-source 骨架脚本沙箱构建） | 内部 initModel（stage/run/save + AddModel） | 模型初始化 |
| `get_project_plans` | 读项目方案产物（plan.json + bim_supplement.json） | `GET /api/v1/projects/{id}/plans` | plan→下游依赖 |
| `deliver_plan` | plan 交付（aiplan land → 方案级目录版本化） | `POST /api/v1/projects/{id}/plans/deliver` | plan 交付 |
| `get_project_models` | 列项目下模型聚合（id/kind/name/status） | Project.Models | 项目模型查询 |

### 1.2 模型编辑链工具（edit-service script-as-source，子 agent 级）

| 工具 | 作用 | 外接接口（edit-service :8100/:8200） |
|---|---|---|
| `list_models` / `get_model_info` | 平台模型查询 | 平台 store（非 edit-service） |
| `get_script` | 读模型当前构建脚本（暂存 or 大版本基线） | `GET /api/v1/models/{id}/script` |
| `stage_script` | 暂存构建脚本（全量替换，不执行） | `PUT /api/v1/models/{id}/script` |
| `run_script` | 沙箱执行暂存脚本（验证可构建，重写工作区模型文件） | `POST /api/v1/models/{id}/script/run` |
| `save_script` | 沙箱执行并落大版本（scripts/v{n}.py + 版本快照，原子） | `POST /api/v1/models/{id}/script/save` |
| `get_versions` | 列脚本大版本 | `GET /api/v1/models/{id}/script/versions` |
| `get_diff` | 两大版本脚本 diff | `GET /api/v1/models/{id}/script/diff` |
| `get_script_locate` | XDATA key → 脚本调用点定位 | `GET /api/v1/models/{id}/script/locate` |
| `edit_script_call` | libcst 标量改写调用点实参（沙箱 run + staging.push） | `POST /api/v1/models/{id}/script/edit-call` |

**编辑链核心**：`stage_script → run_script → save_script`（script-as-source：脚本是模型唯一事实源，沙箱构建派生模型文件）。

### 1.3 plan 命令工具（aiplan CLI，orchestrator 级）

`run_aiplan_command` 执行 aiplan CLI（plan 阶段流程命令）：

| 命令 | 作用 | plan 步骤归属 |
|---|---|---|
| `aiplan route` | 中断路由（判定 P0/P1/P2） | step 0 路由 |
| `aiplan validate` | 门禁（plan/bim/intent） | step 2 门禁 |
| `aiplan derive` | 派生事实（aspect_ratio/exposure/deep_zone） | step 1 设计依据 |
| `aiplan normalize` | 语义→坐标翻译（design_intent→outline_mm/core） | step 1 设计 |
| `aiplan geom check` | 几何校验（逐 zone 轮廓 + 跨层对齐） | step 1 设计校验 |
| `aiplan gate` | 落盘前设计质量门禁（design_rationale 必填） | step 2 门禁 |
| `aiplan land` | 成对落盘（plan.json + bim_supplement.json） | step 2 落盘 |
| `aiplan canon` | canon sha256 | step 2 落盘 |
| `aiplan area` | 面积配比 | step 1 设计 |
| `aiplan pack-drift` | 类型包漂移（维护） | 维护 |

### 1.4 对话 + 子 agent 派发

| 机制 | 作用 |
|---|---|
| `ask_user`（HITL） | 断点问询（question tool 弹选择框；answer 恢复） |
| AgentAsTool（`ifc-agent` / `cad-agent`） | orchestrator 派发子 agent（按 kind 装配） |

### 1.5 mcp/app 项目相关逻辑（旁路，USER 上传解析）

| mcp 工具 | 作用 | 与主流线关系 |
|---|---|---|
| `ifc_upload_modified` | 解析 USER 修改的 IFC 上传 → diff（provenance=USER） | **旁路**（USER 直改上传，非 agent 主链） |
| `dxf_upload_modified` | 解析 USER 修改的 DXF 上传 → diff | **旁路** |
| `model_versions` / `model_diff` / `model_current_context` | 模型状态查询 | 查询辅助 |

> **mcp/app 定位**：USER 直改上传的 diff 解析（provenance=USER 打标），与 agent 主链（AI 改模型）**并行旁路**——主流线是 agent 经 script-as-source 改模型（provenance=AI），mcp 处理 USER 直接上传改后的模型。

---

## 二、三个管线的可执行化单元流程

### 2.1 管线总览

```
ifc 管线      create_project(ifc) → ifc 骨架 → ifc-agent(aiifc) → 脚本链 → IFC 交付
cad 管线      create_project(cad) → 空白 → cad-agent(aidxf) → S0-S4 → DXF 交付
cad->ifc 管线 create_project(cad->ifc) → ifc 骨架(绑定先) → plan(aiplan) → cad(aidxf) → ifc(aiifc) → IFC 交付
```

### 2.2 ifc 管线（单模型：骨架 → 深化 → 交付）

```
① 建项目   create_project(ifc)
            └→ initModel(ifc)：骨架脚本沙箱构建最小 IFC v1，分配 modelId（m_xxx 绑定）

② 派发     orchestrator → AgentAsTool(ifc-agent)（只 ifc，不挂 aiplan）
            └→ ifc-agent 加载 aiifc skill（薄包 ifcopenshell 参考 + 建模纪律 + 脚本契约 MUST #25-31）

②.5 前置设计（可选） aiifc 工作流 ① plan 草稿：design.json / plan.dxf（纯语义设计意图框定，
            无坐标）——**ifc 独立管线专属**：ifc 管线无 aiplan 前置，aiifc 自己产 design.json
            框定设计意图供用户确认（复杂平面/异形/多层时）。design.json 是辅助信息（非完整
            表示、不进版本、不做 diff），确认后进入 script。与 aiplan plan.json 定位重复
            （见 §2.5 产物定位），但 ifc 独立管线无 aiplan，需保留此前置设计能力。

③ 深化     ifc-agent 与用户对话 → 编辑模型（script-as-source）
            └→ get_script（读当前脚本）→ stage_script（暂存改）→ run_script（沙箱验证）→ save_script（落大版本）
            └→ 辅助：get_versions / get_diff（版本追溯）；get_script_locate / edit_script_call（选中定位改）

④ 交付     版本化模型（scripts/v{n}.py + versions/v{n}.ifc）+ XKT 派生（模型页 3D 渲染）
```

**可执行化单元**：`stage_script → run_script → save_script`（script-as-source 编辑链，沙箱构建派生 IFC）。

**业务连续性**：
- 建项目即骨架初始化（modelId 绑定）→ 后续深化都在该骨架上 ✅
- 骨架 → 深化连续（骨架脚本 v1 → 深化 save_script v2/v3/...）✅
- aiifc 工作流编排（PLAN_DXF_IFC.md）：plan（可选）→ script（事实源）→ IFC（派生物）——ifc 独立管线是「design.json 草稿（可选）→ script→IFC」主链。design.json 前置设计**对 ifc 独立管线保留**（无 aiplan，aiifc 自己框定设计供确认；与 plan.json 定位重复但各有归属，见 §2.5）✅

### 2.3 cad 管线（plan → DXF：aiplan → aidxf）

**前置依赖**：cad 管线需 plan.json（aiplan 产物）——**无 plan 不能 cad**。

```
① 建项目   create_project(cad) → 空白（不初始化模型）

② plan     orchestrator 挂 aiplan skill（plan 阶段）：
            └→ step 0 摄取归一化（外部资料 → 意图卡片 + 缺口清单；aiplan route 路由）
            └→ step 1 渐进设计对话（4 轮：骨架→几何→功能→结构空间；aiplan derive/normalize/geom check/gate/area）
            └→ step 2 生成落盘（aiplan validate/gate/canon/land → plan.json + bim_supplement.json → deliver_plan 方案版本化）

③ 派发     orchestrator → AgentAsTool(cad-agent)（只 cad，不挂 aiplan skill）
            └→ cad-agent persona：先 get_project_plans 读 **plan.json**（任务书，对接 cad）
               ——plan 缺失→报告不硬画。**cad 只消费 plan.json，不消费 bim_supplement.json**
               （bim_supplement 是 BIM 补充，对接 bim/ifc，非 cad 输入，见 §2.5）

④ cad      cad-agent 加载 aidxf skill（plan→cad 建筑平面管线）——**大改**：
            ├─ S0 预处理（不变）：aidxfv3 preprocess --plan plan.json → derived/（floors + zone 包 + skeleton_base）→ 断点⓪
            ├─ S1 骨架设计（不变）：LLM 声明 skeleton.json → aidxfv3 validate/normalize/check → 断点①
            ├─ S2 房间设计（**改造① draw 记录**）：LLM 声明 rooms.json → 复制 skeleton.dxf →
            │   LLM 逐构件调 dxfkit.draw 画 floor.dxf（draw_api 能力规范不变）
            │   【dxfkit/archdxf 埋记录点：LLM 画的同时机器侧记录 draw 调用序列
            │     ——函数 + 参数 + 次序，draw_composition 组装序（底座→墙→门窗→柱→标注）】
            ├─ S3 细节（**改造① 续**）：LLM 调 draw（门窗统一规律 + 柱网 + 标注）→ floor.dxf【继续记录】
            └─ S4 交付（**改造② deliver 拆分**——见下「S4 交付改造」）
            └─ 状态机（不变）：aidxfv3 state sync/advance/reconcile（逐 zone 线性推进 + 中断恢复）

⑤ 交付     每 zone 一个平台模型（modelId + build() 脚本 + DXF + 版本化）+ building.json（方案级，引用各 zone modelId）
```

#### S4 交付改造（aidxf 最后交差——颗粒度到每步）

**原 deliver（`aidxfv3 deliver`）只做的两件事，改造后拆分归属**：

| 原 deliver 工作 | 改造后归属 | 说明 |
|---|---|---|
| 扫 confirmed missions → **复制 DXF 到 deliver/** | **被 script 工具链替代** | 不再复制文件——每 zone 走 init_model + stage/run/save（沙盒跑 build 产 DXF 注册平台模型） |
| **汇总 building.json**（plan 形态整栋楼 + DXF 指针 sha256） | **deliver 保留**（改造指针） | building.json 仍是 deliver 产出，但 DXF 指针从「deliver/ 文件路径 + sha256」改为「**平台模型 modelId**」 |

**S4 改造后的三个子步骤**：
```
S4-a 每 zone build() 脚本固化（机器，skill 侧新增能力）
      draw 调用序列（S2/S3 记录）→ 固化为 archdxf 可运行的 build() 脚本：
        PARAMS = {skeleton, rooms, details DSL}（LLM 声明，JSON 字面量）
        def build(params, out_path): 重放整层画法（dxfkit.draw 调用序列）
      → 每 zone 一个 build() 脚本（对齐 services/cad script-as-source 契约）

S4-b 每 zone DXF 注册平台模型（agent 经 script 工具链——**init_model 前置**）
      对每 zone：
        init_model(dxf, title=zone名)         ← 分配 modelId + 建骨架（前置，已敲定）
        stage_script(build() 脚本)             ← 暂存该 zone 构建脚本
        run_script()                           ← 沙盒跑 build 产 DXF（共享画法层 archdxf/dxfkit）
        save_script()                          ← 落 v1 版本（scripts/v1.py + DXF 快照）
      → 每 zone DXF 成为平台模型（modelId + script-as-source 版本化 + viewer render.json 可看）
      【这步替代了原 deliver 的「复制 DXF 到 deliver/」——DXF 交付 = script 工具链】

S4-c building.json 汇总（deliver 保留，指针改造）
      deliver 汇总整栋楼：site/standards/vertical_relations/design_rationale/requirements
        + zones[]（每 zone：floors_from/to + **modelId**（替代原 dxf 文件路径）+ 非几何属性）
      → building.json 挂项目/方案（方案级产物），ifc 经 modelId 拿到各 zone DXF 平台模型
```

**init_model 前置（已敲定）**：S4-b 对每 zone 调 `init_model(dxf)` 建骨架——这是 cad 管线
「每次新建 DXF 时初始化」的落地（create_project(cad) 空白 → aidxf 每 zone 画完固化脚本后
init_model 注册）。与 ifc 管线的「建项目即 init_model(ifc)」对齐——**骨架初始化 → 深化**
统一模式。

**deliver 后清理中间产物（已敲定，2026-08-21）**：S4 完成后清空工作区过程产物
（missions/derived/floor.dxf 过程态）——
- **事实源已转移**：平台模型的 build() 脚本（models/{modelId}/scripts/）是该 zone 唯一事实源。
- **再次修改不依赖中间产物**（已实测核实 ✅：改 build 脚本 → 沙箱跑 → 新 DXF，实体随改变化）——
  再次修改走平台模型 script-as-source（stage/run/save），**不会重跑 aidxf S0-S4 全流程**。
- **残留误导**：过程文件（missions/prompt/floor.dxf 过程态）残留会让再次修改误以为要按
  missions/derived 继续，其实该改平台模型脚本——故清理。
- 保留：平台模型 build() 脚本 + DXF + building.json（方案/项目级）。

**可执行化单元**：
- plan：`aiplan <cmd>`（route/derive/normalize/geom/gate/validate/canon/land）——step 0-2
- cad：`aidxfv3 <cmd>`（preprocess/validate/normalize/check/pack/state/draw/deliver）——S0-S4
- cad 交付（改造后）：`init_model` + `stage_script`/`run_script`/`save_script`（script 工具链，替代 deliver 的复制 DXF）——S4-b

**业务连续性**：
- plan → cad 依赖链：cad 需 plan.json（cad-agent persona 硬纪律：先读 plan，缺失报告）✅
- cad 状态机：aidxfv3 state sync/advance/reconcile（逐 zone 推进 + 中断恢复）✅
- 断点（⓪①②）：HITL（ask_user question tool）→ 用户确认 → advance 推进 ✅
- **交付改造（S4）**：deliver 的「复制 DXF」被 script 工具链替代（init_model 前置 + 沙盒跑 build 注册平台模型）；building.json 保留（deliver 汇总，DXF 指针改 modelId）——**draw 固化（S4-a）是唯一新增改造**，注册（S4-b）复用现有 script 工具链，传递（S4-c）经 modelId。

### 2.4 cad->ifc 管线（plan → cad → ifc 全链）

```
① 建项目   create_project(cad->ifc) → ifc 骨架初始化（绑定先，modelId 分配）

② plan     orchestrator 挂 aiplan skill（同 cad 管线 ②）：
            └→ step 0-2 → plan.json + bim_supplement.json → deliver_plan

③ cad      orchestrator → AgentAsTool(cad-agent)（同 cad 管线 ④，含 S4 交付改造）：
            └→ aidxf S0-S3 → LLM 调 draw 画各 zone floor.dxf【机器记录 draw 调用序列】
            └→ S4 交付改造：S4-a 固化每 zone build() 脚本 → S4-b init_model+script 工具链
               注册平台模型（每 zone modelId）→ S4-c building.json 汇总（zones[] 记 modelId）
            └→ 产物：每 zone DXF 平台模型（modelId + 版本化）+ building.json（方案级，引用 modelId）

④ ifc      orchestrator → AgentAsTool(ifc-agent)（同 ifc 管线 ③）：
            └→ aiifc skill：消费 bim_supplement.json + building.json + cad DXF
               （**不消费 plan.json**——plan.json 只对接 cad；ifc 消费的是 bim 补充 +
               aidxf 交付物，见 §2.5 产物定位）
               【拿到文件：bim_supplement=get_project_plans；building.json=方案产物；
                 各 zone DXF=building.json 的 modelId 经 get_project_models/get_script 拿】
            └→ **现状（先做到拿到文件）**：ifc-agent 能正确拿到相关文件——
               bim_supplement.json（get_project_plans 读方案产物）+ building.json / 逐 zone DXF
               （aidxf deliver 落盘 deliver/，经产物传递机制拿到，见 §4.2）✅
            └→ **后续大工程量（未做）**：aiifc 解析消费——把 bim_supplement.json（BIM 补充：
               屋顶/特殊结构/PSET）+ building.json（plan 形态整栋楼 + DXF 指针）+ 相应 DXF
               解析转成 IFC 构建脚本（script-as-source）——**这是 aiifc skill 的大改写**
               （见 §4.5），当前未做。
            └→ script-as-source：骨架 ifc（建项目已初始化）→ 深化（stage/run/save）→ IFC 交付
            └→ aiifc 工作流：plan（草稿）→ script（事实源）→ IFC

⑤ 交付     IFC 交付（版本化模型 + XKT 派生）
```

**可执行化单元**：
- plan：`aiplan <cmd>`（step 0-2）
- cad：`aidxfv3 <cmd>`（S0-S4）
- ifc：`stage_script → run_script → save_script`（script-as-source）

**业务连续性**：
- ifc 骨架绑定先（create_project 初始化 ifc 骨架）→ plan → cad → ifc 在绑定骨架上深化 ✅
- plan → cad 依赖：cad 需 plan.json ✅
- cad → ifc 依赖：ifc 消费 **bim_supplement.json + building.json + cad DXF**（**不消费 plan.json**——plan.json 只对接 cad）✅（拿到文件层面）；**解析消费未做**（大工程量，见 §4.5）
- **缺口**：cad deliver 的 DXF 如何注册平台模型 + 如何传给 ifc-agent（当前 aidxf deliver 落盘 missions/，未注册平台模型）

---

### 2.5 产物定位（谁产谁消费——避免重复与错配）

三管线涉及 4 类设计/交付产物，定位必须分清（**谁产、谁消费、是否进版本**）：

| 产物 | 产出方 | 消费方 | 定位 | 进版本 |
|---|---|---|---|---|
| **plan.json** | aiplan（step 2 落盘） | **只 cad（aidxf）** | 任务书（对接 cad）：竖向功能分区/面积表/设计要求 | ✅ 方案版本化（deliver_plan） |
| **bim_supplement.json** | aiplan（step 2 落盘） | **只 bim/ifc（aiifc）** | BIM 补充（CAD 覆盖不了的：屋顶/特殊结构/PSET） | ✅ 方案版本化 |
| **building.json** | aidxf（S4-c deliver 汇总） | **只 bim/ifc（aiifc）** | plan 形态整栋楼 + **逐 zone modelId 指针**（改造后，替代原 DXF 文件路径）——bim 接口文件 | ✅ 方案/项目级产物 |
| **逐 zone DXF（平台模型）** | aidxf（S4-b init_model+script 工具链） | **只 bim/ifc（aiifc）** | 每 zone 平台模型（modelId + build() 脚本 + DXF）——几何载体 | ✅ script-as-source 版本化 |
| **design.json** | aiifc（工作流 ① plan 草稿，可选） | **只 aiifc 自己**（ifc 独立管线设计框定） | 纯语义设计意图（墙轴/洞口沿轴/层高，无坐标）——辅助确认 | ❌（辅助信息，非完整表示） |

**关键区分（避免重复/错配）**：
1. **plan.json 只给 cad，ifc 不消费**——ifc 消费的是 bim_supplement.json（aiplan 的 bim 补充）
   + building.json（aidxf 的 bim 接口）+ 逐 zone DXF。**cad 只消费 plan.json，不消费
   bim_supplement.json**（bim 补充非 cad 输入）。
2. **design.json vs plan.json 定位重复但各有归属**：
   - plan.json = aiplan 产（cad/cad->ifc 管线的任务书，完整设计意图，**进版本**）
   - design.json = aiifc 产（**ifc 独立管线**的设计草稿，可选辅助确认，**不进版本**）
   - 重复点：都是「前置设计意图框定」。**但 design.json 对 ifc 独立管线必须保留**——
     ifc 独立管线无 aiplan 前置，aiifc 需自己产 design.json 框定设计供用户确认
     （复杂平面/异形/多层时）。cad->ifc 管线里 aiifc 不产 design.json（有 plan.json/
     building.json 输入），只有 ifc 独立管线才走 aiifc 的 design.json 前置。

---

## 三、业务连续性核查（断点/依赖/产物链）

### 3.1 依赖链完整度

| 依赖 | 状态 | 说明 |
|---|---|---|
| **plan → cad** | ✅ | cad-agent 消费 **plan.json**（任务书）：先 get_project_plans 读 plan.json，缺失报告不硬画 |
| **cad → ifc** | ⚠️ 拿到文件 ✅ / 解析 ❌ | ifc 消费 **bim_supplement.json + building.json + cad DXF**（不消费 plan.json）；**拿到文件已可做**（get_project_plans + 产物传递），**解析消费成 IFC 未做**（aiifc 大改写，见 §4.5） |
| **ifc 骨架绑定** | ✅ | ifc/cad->ifc 建项目即初始化 ifc 骨架（modelId 绑定） |
| **cad 模型初始化** | ⚠️ | cad 项目空白 → agent init_model(dxf) 按需；**aidxf deliver DXF 注册平台模型待设计** |

### 3.2 断点连续性（HITL）

| 断点 | 状态 |
|---|---|
| plan step 1（4 轮设计对话） | ✅ ask_user question tool 弹选择框（HITL） |
| aidxf S0/S1/S2 断点（⓪①②） | ✅ ask_user → 用户确认 → aidxfv3 state advance 推进 |
| aiplan gate/validate（门禁） | ✅ 门禁失败 → 报告 → 修改 → 重交 |
| 中断恢复 | ✅ aiplan route（plan）+ aidxfv3 state reconcile（cad） |

### 3.3 产物链（plan → DXF → IFC）

| 产物 | 落盘 | 平台模型 | 状态 |
|---|---|---|---|
| plan.json + bim_supplement.json | `{workspace}/plan/`（aiplan land） | 方案级版本化（deliver_plan） | ✅ |
| aidxf 中间产物（missions/） | `{project}/missions/` | 不注册平台模型（中间产物：DSL/mission/prompt） | ⚠️ 设计态 |
| aidxf S2/S3 的 floor.dxf（LLM 画的过程产物） | `{project}/missions/<node>/floor.dxf` | 不注册（过程产物——被 S4-a build() 脚本取代为事实源） | ⚠️ 过程态 |
| **每 zone build() 脚本 + DXF（S4-a/S4-b）** | models/{modelId}/（init_model + script 工具链） | **✅ 注册平台模型**（S4-b：init_model 前置 + 沙盒跑 build + save 版本化） | 🔧 P0 改造中 |
| building.json（S4-c） | 方案/项目级（deliver 汇总，zones[] 记 modelId） | 方案级产物（引用各 zone modelId） | 🔧 P0 改造中 |
| ifc 骨架（v1） | models/{modelId}/（initModel） | ✅ 注册（AddModel） | ✅ |
| ifc 深化（v2/v3/...） | scripts/v{n}.py + versions/v{n}.ifc | ✅ 注册 | ✅ |

---

## 四、缺口与后续（skill 编排 / 管线可执行化 M3+）

### 4.1 aidxf S4 交付改造（方案已定，P0 进行中）

> 原「deliver DXF 注册平台模型机制」缺口，经调查与裁决已定为 **S4 交付改造**（见 §2.3「S4 交付改造」）：
> **deliver 的「复制 DXF」被 script 工具链替代，building.json 保留（指针改 modelId），init_model 前置**。

**核心决策（已敲定）**：
- aidxf 的 DXF 是 **LLM 逐构件调 dxfkit.draw 画的**（非机器算好的确定性产物）——draw_api 能力规范不变
- **S4-a（唯一新增改造）**：dxfkit/archdxf 埋记录点，LLM 画的同时机器记录 draw 调用序列 → 固化为
  archdxf 可运行的 build() 脚本/zone（对齐 services/cad script-as-source 契约）
- **S4-b（复用现有工具链，非新机制）**：每 zone `init_model(dxf)` 前置（已敲定——cad 管线每次新建
  DXF 时初始化）→ `stage_script`（build 脚本）→ `run_script`（沙盒跑 build 产 DXF，共享画法层
  archdxf/dxfkit 单一事实源）→ `save_script`（v1 版本化）→ 平台模型。**这步替代了 deliver 的复制 DXF**。
- **S4-c（deliver 保留）**：building.json 汇总，但 zones[] 的 DXF 指针从「deliver/ 文件路径 + sha256」
  改为「**平台模型 modelId**」。

**前置已完成（2026-08-21）**：services/cad 沙箱接入共享画法层（archdxf + dxfkit，dist 单一事实源，
零版本差异）——沙箱可同时 import cad_script_lib（用户编辑线）与 dxfkit.draw/archdxf（skill 固化
脚本），为 S4-b「沙盒跑 build 产 DXF」打通底座。

**待做**：S4-a 的 draw 调用序列记录 + build() 脚本固化（dxfkit/archdxf 埋记录点 + deliver 翻译固化）。

### 4.2 cad→ifc 产物传递（经平台模型，方案已定）

**机制（已定：经平台模型）**：
- `bim_supplement.json`：`get_project_plans` 读方案产物 ✅（已有）
- `building.json`：S4-c 产出，挂项目/方案（方案级产物），ifc 可读 ✅
- **各 zone DXF**：S4-b 注册为平台模型（modelId）→ building.json 的 zones[] 记 modelId →
  ifc-agent 经 `get_project_models`（列项目模型）+ `get_script`/`get_model_info`（读 DXF 平台模型）拿到 ✅

**注意**：ifc-agent 消费的是 **bim_supplement.json + building.json + DXF**（**不消费 plan.json**——
plan.json 只给 cad，见 §2.5）。拿到文件后，**解析消费成 IFC 是大工程量**（见 §4.5），当前先做到
「能正确拿到文件」（经平台模型 + modelId）。

### 4.3 skill 编排（orchestrator 按 kind 编排管线）

**现状**：orchestrator persona 按 kind（personaCAD/personaIFC/全装）——编排规则在 persona 提示词（文本纪律）。

**M3+ 可执行化**：管线编排从「persona 文本纪律」升级为「skill 编排契约」（aiplan → aidxf → aiifc 的 skill 步骤编排 + 断点 + 产物链）——需要：
- orchestrator 的管线编排逻辑（按 kind 决定执行哪些 skill 步骤）
- skill 步骤间的产物传递（plan.json → aidxf → DXF → aiifc → IFC）
- 断点编排（HITL 断点的统一处理）

### 4.4 skill 改写（按管线分工）

- **aidxf（大改，方案已定 §4.1）**：S4 交付改造——draw 调用序列记录 + build() 脚本固化（S4-a，
  唯一新增）；deliver 的复制 DXF 被 script 工具链替代（S4-b 复用现有工具）；building.json 指针改
  modelId（S4-c）。**前置已完成**：沙箱接入共享画法层（archdxf/dxfkit 单一事实源）。
- **aiifc（大改，§4.5）**：改「直接在数据目录写 IFC 版本」→ 「平台模型 API + script-as-source」；
  加「消费 bim_supplement/building.json/DXF → IFC 脚本」解析链；区分两条 ifc 深化路径
  （cad->ifc 消费上游 vs ifc 独立 design.json 前置）。
- **aiplan**：产物传递对齐（plan.json→cad、bim_supplement→bim 的消费方明确，见 §2.5）+ 管线编排。

### 4.5 aiifc 解析消费链（cad->ifc 管线的 ifc 深化——大工程量，未做）

**现状**：cad->ifc 管线里 aiifc **先做到「能正确拿到相关文件」**：
- `bim_supplement.json`（aiplan 产物，BIM 补充）——经 `get_project_plans` 读方案产物 ✅
- `building.json`（aidxf S4-c 汇总，zones[] 记 modelId）——方案级产物，可读 ✅
- **各 zone DXF**（S4-b 注册的平台模型）——经 building.json 的 modelId + `get_project_models`/
  `get_script` 拿到 ✅（拿到文件层面打通）

**未做（大工程量）**：aiifc **解析消费**这些文件转成 IFC 构建脚本：
- 解析 bim_supplement.json（屋顶/特殊结构/PSET）→ IFC 对应建模（IfcRoof/特殊构件/Pset）
- 解析 building.json（plan 形态整栋楼 + 逐 zone modelId）→ 楼层/分区结构
- 解析相应 DXF（各 zone 平台模型的 outline/core/墙/房间/门窗几何）→ IFC 几何构建（墙/板/门窗实体）
- 综合三者 → 产出符合脚本契约的 IFC 构建脚本（script-as-source：PARAMS + build() + validate）

**工程量大**，涉及：
- **skill 本身改写**：aiifc 加「消费 bim_supplement/building.json/DXF → IFC 脚本」的解析逻辑与
  建模纪律（当前 aiifc 是「从零建模」薄包参考，没有「消费上游产物」的解析链）
- **subagent 装配改写**：ifc-agent 的工具/上下文装配——拿到文件后如何喂给 aiifc
  （文件路径传递 / 内容注入 / 分阶段解析的断点编排）
- **与 design.json 前置的关系**：cad->ifc 管线 aiifc 走「消费上游产物」（不产 design.json）；
  ifc 独立管线 aiifc 走「design.json 前置 → 从零建模」（见 §2.5）——两条 ifc 深化路径
  需在 aiifc skill 里区分编排。

**定位**：这是 cad->ifc 管线「业务完全连续」的最后一块——当前先做到「拿到文件」，
解析消费待 skill 改写（与 §4.4 的 aiifc 改写同一波）。

---

## 五、结论

### 三管线可执行化单元流程（定稿）

| 管线 | 可执行单元链 |
|---|---|
| **ifc（独立）** | `create_project(ifc)` → ifc 骨架 → ifc-agent(aiifc) → 【可选 design.json 前置设计框定】→ `stage_script→run_script→save_script` → IFC 交付 |
| **cad** | `create_project(cad)` → 空白 → plan(aiplan step 0-2: `aiplan <cmd>` → plan.json) → cad-agent(aidxf S0-S3 LLM 调 draw 画 DXF【记录调用序列】) → **S4 交付改造**：S4-a 固化 build() 脚本 → S4-b `init_model`+`stage/run/save_script` 注册平台模型（每 zone modelId）→ S4-c building.json 汇总（zones 记 modelId） |
| **cad->ifc** | `create_project(cad->ifc)` → ifc 骨架(绑定先) → plan(aiplan → plan.json+bim_supplement.json) → cad(aidxf，消费 plan.json → 每 zone DXF 平台模型 + building.json 记 modelId) → ifc(aiifc，经 modelId 拿 bim_supplement+building.json+DXF 深化骨架) → IFC 交付 |

### 业务连续性评估

- **依赖链**：plan → cad ✅（plan.json 只给 cad）；cad → ifc ⚠️（拿到文件 ✅ 经 modelId / 解析消费 ❌ 大工程量）；ifc 骨架绑定 ✅
- **断点**：plan/aidxf 断点 HITL 连续 ✅；中断恢复（route/reconcile）✅
- **产物链**：plan.json+bim_supplement → 方案版本化 ✅；**每 zone DXF → S4-b 注册平台模型（init_model 前置+沙盒跑 build）** 🔧 P0 改造中；building.json → S4-c 记 modelId 🔧 P0 改造中；ifc 深化版本化 ✅
- **产物定位**：plan.json→只 cad、bim_supplement/building.json/DXF→只 ifc、design.json→aiifc ifc 独立管线（见 §2.5）✅ 已分清

### 核心缺口与状态（M3+ skill 编排前置）

1. **aidxf S4 交付改造**（§4.1，方案已定 🔧 P0 进行中）：deliver 的复制 DXF 被 script 工具链替代，
   building.json 指针改 modelId，init_model 前置；**唯一新增 = S4-a draw 调用序列记录 + build() 固化**
   （前置已完成：沙箱接入共享画法层 archdxf/dxfkit 单一事实源）。
2. **cad→ifc 产物传递**（§4.2，方案已定 ✅ 经平台模型 + modelId）：ifc 经 get_project_models/get_script
   拿到 bim_supplement/building.json/DXF（拿到文件层面打通）。
3. **aiifc 解析消费链**（§4.5，bim_supplement + building.json + DXF → IFC 构建脚本——**大工程量**，
   skill + subagent 装配改写）。
4. **skill 编排契约**（orchestrator 按 kind 编排 aiplan→aidxf→aiifc 步骤 + 断点 + 产物链；含 aiifc
   两条路径：cad->ifc 消费上游 vs ifc 独立 design.json 前置）。

> 缺口 1/2 方案已定（S4 交付改造，P0 进行中）——draw 固化是唯一新增改造，注册/传递复用现有
> script 工具链与 modelId。缺口 3（aiifc 解析消费）是 cad->ifc 管线业务完全连续的最后一块，
> 也是最大工程量。当前先做到「能正确拿到相关文件」，解析消费与 design.json 前置编排待 skill 改写。

---

## 六、执行波次（当前进度 + 每波产出）

> 三管线改造的落地波次。前置已完成；**当前在 P0 波（产物链打通——拿到文件）**。

### 前置波（✅ 已完成，2026-08-21）

| 改造 | 产出 | commit |
|---|---|---|
| **services/cad 沙箱接入共享画法层**（archdxf + dxfkit 单一事实源，零版本差异） | 沙箱可同时 import cad_script_lib（用户编辑线）+ dxfkit.draw/archdxf（skill 固化脚本）；用户编辑线库升级到 skill 新版 | `a177eb8` |

### P0 波：产物链打通——拿到文件（🔧 进行中）

> 目标：aidxf S4 交付改造落地——每 zone DXF 注册平台模型 + building.json 记 modelId + ifc 拿到文件。
> **每个波次 = 代码改造 + 对应 skill 文档同步更新**（避免代码改了但文档残留旧逻辑不适配，见 §6.1）。

| 波次 | 代码改造 | skill 文档同步更新 | 产出/状态 | commit |
|---|---|---|---|---|
| **P0-1** | **draw 调用序列记录 + build() 脚本固化**（S4-a，唯一新增） | `SKILL.md`、`references/draw_composition.md`、`references/machine_contract.md`、`references/draw_api.md`（record 契约） | ✅ 代码 + 文档完成 | `45ec6e3`/`9478511` |
| **P0-2a** | **skill 工作区地基**（`{DATA}/skill-work/{projectID}`，projectId 隔离 + get_skill_workdir 工具 + persona 注入 + 级联清理） | —（agent 配置，非 skill 文档） | ✅ 已完成 | `a6a5ea5` |
| **P0-2** | **S4-b 每 zone 注册平台模型**（init_model 前置 + stage/run/save 编排——复用现有 script 工具链） | `steps/step-04-deliver.md`、`references/machine_contract.md`、`references/orchestrator/dispatch.md`（S4 交付改造 + skill-work 工作区 + deliver 后清理） | ✅ 文档完成（deliver.py 代码下一轮） | `9478511` |
| **P0-2b** | **aiplan 交付对齐**（deliver_plan/deliverPlanCore 已有——代码不动） | `skills/aiplan/SKILL.md`、`steps/step-02-deliver.md`、`steps/step-00-ingest.md`（交付 deliverPlanCore + PlanStore 版本化 + 工作区 skill-work/{projectID}/aiplan/ + deliver 后清理） | 🔧 文档待做 | — |
| **P0-3** | **S4-c building.json 指针改 modelId + cad→ifc 传递** | `references/schemas/building.schema.json`（zones[] DXF 指针从文件路径+sha256 改 modelId）、`steps/step-04-deliver.md`（S4-c building.json）、`references/machine_contract.md`（building 契约） | 🔧 待做（代码 + 文档） | — |

**P0 验收**：cad->ifc 管线跑到 ifc 阶段，ifc-agent 能正确拿到 bim_supplement.json + building.json（含 modelId）+ 各 zone DXF 平台模型（文件层面），不解析。

### 6.1 skill 文档残留清单（旧逻辑 ↔ 当前接口不适配点）

> aidxf skill 内部文档的旧逻辑残留（deliver 复制 DXF、无 build() 脚本、非平台模型体系），
> 与当前接口（script-as-source / 平台模型 / init_model / modelId / record 固化）不适配——
> **按波次同步清理**（不单独设波次，随代码改造同波更新）。

| 文档 | 旧逻辑残留 | 当前接口（改为） | 所属波次 |
|---|---|---|---|
| `SKILL.md` | S4 行「building.json + 逐层 DXF + 封存 rooms」；中段「复制 DXF」 | S4-a 固化→S4-b 注册平台模型（modelId）→S4-c building.json 记 modelId | P0-1/P0-2（✅ 已改） |
| `steps/step-04-deliver.md` | `aidxfv3 deliver` 复制 `deliver/<floor>.dxf` + `<floor>.rooms.json` + building.json（checksums） | S4 交付改造三子步（S4-a 固化/S4-b 注册/S4-c building.json 记 modelId）+ **deliver 后清理中间产物** | P0-2（✅ 已改） |
| `references/machine_contract.md` | deliver 扫 missions → 复制 DXF 到 deliver/ + building.json（sha256）；**`<project>` 任意目录** | deliver 不再复制 DXF（被 script 工具链替代）；record 固化契约 + modelId 指针；**`<project>` = `{DATA}/skill-work/{projectID}`**；deliver 后清理中间产物 | P0-1/P0-2（✅ 已改）/P0-3（building） |
| `references/draw_composition.md` | 出口 `doc.saveas("floor.dxf")`（无 record/固化） | 出口加 record 记录（LLM 画时机器记录调用序列）→ S4-a 固化 build() 脚本（draw_api 不变）+ 过程产物清理说明 | P0-1（✅ 已改） |
| `references/draw_api.md` | 画图流程无 record 步骤 | 流程加 ⓪ record.start+wrap 开记录 + ⑤ record.to_build_script 固化（draw_api 能力规范不变） | P0-1（✅ 已改） |
| `references/schemas/building.schema.json` | zones[] 记 `dxf`（文件路径）+ `sha256` | zones[] 记 `modelId`（平台模型指针，替代文件路径） | P0-3（🔧 待改） |
| `references/orchestrator/dispatch.md` | 编排无 init_model/script 工具链；`<project>` 任意 | 编排加 建造段 record 开记录/固化 + S4-b init_model/script 工具链注册；`<project>` = skill-work/{projectID} | P0-2（✅ 已改） |

### 6.2 aiplan 文档残留（P0-2b——交付 deliverPlanCore 已有，文档对齐）

> aiplan 的 agent 适配（`deliver_plan` 工具 → deliverPlanCore → PlanStore 版本化 `plans/{projectID}/`）
> 已完善，但 **aiplan skill 文档还是旧逻辑**（land 落 `{workspace}/plan/` 自包含工作区，没对齐
> deliver_plan 工具链 + PlanStore 版本化 + skill-work 工作区 + deliver 后清理）——同样流程对齐 aidxf。

| 文档 | 旧逻辑残留 | 当前接口（改为） | 状态 |
|---|---|---|---|
| `skills/aiplan/SKILL.md` | step 2 落盘 `{workspace}/plan/`（自包含）；无 deliver_plan/工作区/清理 | step 2 交付 = **deliver_plan 工具**（deliverPlanCore → PlanStore 版本化 `plans/{projectID}/`）；中间产物 skill-work/{projectID}/aiplan/；deliver 后清理（再次修改走 deliver_plan 读当前态重交） | 🔧 待改 |
| `skills/aiplan/steps/step-02-deliver.md` | `aiplan land --outdir {workspace}/plan/`（run 目录落自包含工作区） | 交付走 deliver_plan 工具（agent 提供）；land 经 deliverPlanCore（临时区 → PlanStore）；工作区 skill-work/{projectID}/aiplan/；deliver 后清理 | 🔧 待改 |
| `skills/aiplan/steps/step-00-ingest.md` | `aiplan route <workspace>`（自包含工作区） | `aiplan route skill-work/{projectID}/aiplan/`（get_skill_workdir 拿，projectId 隔离） | 🔧 待改 |

**决策（2026-08-21 用户敲定）**：
- **交付路径**：中间产物 skill-work/{projectID}/aiplan/（与 aidxf 同一工作区根，projectId 隔离）；
  交付 deliver_plan 走现有 deliverPlanCore（PlanStore 版本化 plans/{projectID}/）——代码不动，文档对齐。
- **deliver 后清理**：与 aidxf 一致——deliver_plan 后清理 aiplan 过程产物（design_intent/normalized/
  run 过程态）；再次修改走 deliver_plan（从 get_project_plans 读当前态改了重交），不依赖过程残留。
- **自包含纪律保留**：aiplan 独立使用时 land 仍可落任意目录（自包含可迁移）；平台内交付走
  deliver_plan 工具链——文档区分「独立使用」vs「平台内」。

**清理纪律**：
1. **同波同步**：改代码的同一波次更新对应文档（文档随代码 commit 同波落地，不滞后）。
2. **改完打包**：skill 文档改在源 `skills/aidxf`，改完 `python3 tools/skill_pack.py --skill aidxf` 同步 dist。
3. **schema 联动**：`building.schema.json` 改 modelId 后，`deliver.py` 的 building 生成逻辑同步改（P0-3 代码+schema 一起）。

### P1 波：skill 编排契约（后续，P0 之后）

- orchestrator 按 kind 编排 aiplan→aidxf→aiifc 步骤 + 断点 + 产物链（从 persona 文本纪律升级为编排契约）
- aiifc 两条 ifc 深化路径区分（cad->ifc 消费上游 vs ifc 独立 design.json 前置）

### P2 波：aiifc 解析消费链（大工程量，最后）

- aiifc 把 bim_supplement.json + building.json + 各 zone DXF 解析转成 IFC 构建脚本
- skill 本身改写（消费上游产物解析链）+ subagent 装配（文件喂给 aiifc + 断点编排）

### 波次依赖

```
前置（沙箱共享画法层）✅
  ↓（沙箱能跑 draw 链 build()）
P0-1（draw 固化 build() 脚本）✅ 代码 / 🔧 文档残留（draw_composition/machine_contract record 契约）
  ↓（有 build() 脚本才能进沙箱注册）
P0-2a（skill 工作区地基 skill-work/{projectID}）✅ ← projectId 隔离 + get_skill_workdir + persona + 级联
  ↓（工作区定了中间产物落盘根）
P0-2（init_model + script 工具链注册平台模型）🔧 ← 当前（代码 + step-04/deliver 契约/dispatch 文档）
  ↓（注册平台模型后产物可经 modelId 传递）
P0-3（building.json 记 modelId + 传递）🔧（代码 + building.schema/deliver 文档）
  ↓
P1（编排契约）→ P2（aiifc 解析消费）
```

> 当前进度：前置 ✅ + P0-1 代码 ✅ + **P0-2a 工作区地基 ✅**（`a6a5ea5`：skill-work/{projectID}
> projectId 隔离 + get_skill_workdir 工具 + persona 注入 + 级联清理）。
> **下一步 P0-2**（S4-b 注册平台模型 + 同波更新 step-04/deliver 契约/dispatch——`<project>` 落盘位置
> 改为 skill-work/{projectID}，见 §6.1）。
> **每个波次代码与 skill 文档同步落地**（§6.1 清单，避免文档残留旧逻辑不适配）。

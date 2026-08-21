# reform-skill_for_flow —— Skill × 三管线流程编排（业务连续性梳理）

> 本文梳理 **skill 本身 + 三管线（ifc / cad / cad->ifc）的可执行化单元流程**，回答：
> 1. agent 现有 tool 外接接口是什么（含 mcp/app 项目逻辑）？
> 2. 三个管线的可执行化单元流程是什么（skill 步骤 × tool 编排）？
> 3. 业务是否正常连续（断点/依赖/产物链）？
>
> 定位：**流程编排设计文档**——给后续 skill 编排/管线可执行化（M3+）定骨架。

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

④ cad      cad-agent 加载 aidxf skill（plan→cad 建筑平面管线）：
            └→ S0 预处理（aidxfv3 preprocess：plan.json → derived/（floors + zone 包 + skeleton_base）→ 断点⓪）
            └→ S1 骨架设计（skeleton.json 声明 → aidxfv3 validate/normalize/check → 断点①）
            └→ S2 房间设计（rooms.json + floor.dxf → 断点②）
            └→ S3 细节（门窗/柱网/标注 → floor.dxf）
            └→ S4 交付（aidxfv3 deliver → building.json + 逐 zone DXF）
            └→ 状态机：aidxfv3 state sync/advance/reconcile（逐 zone 线性推进 + 中断恢复）

⑤ 交付     各层 DXF（deliver 后注册平台模型；init_model(dxf) 建骨架 → 深化 → 逐层 DXF）
```

**可执行化单元**：
- plan：`aiplan <cmd>`（route/derive/normalize/geom/gate/validate/canon/land）——step 0-2
- cad：`aidxfv3 <cmd>`（preprocess/validate/normalize/check/pack/state/draw/deliver）——S0-S4

**业务连续性**：
- plan → cad 依赖链：cad 需 plan.json（cad-agent persona 硬纪律：先读 plan，缺失报告）✅
- cad 状态机：aidxfv3 state sync/advance/reconcile（逐 zone 推进 + 中断恢复）✅
- 断点（⓪①②）：HITL（ask_user question tool）→ 用户确认 → advance 推进 ✅
- **缺口**：aidxf 各层 DXF 是中间产物（missions/），deliver 最终 DXF 才落盘——**deliver 产物注册平台模型机制待设计**（deliver 后 init_model(dxf) 建骨架？还是 deliver 直接注册？）

### 2.4 cad->ifc 管线（plan → cad → ifc 全链）

```
① 建项目   create_project(cad->ifc) → ifc 骨架初始化（绑定先，modelId 分配）

② plan     orchestrator 挂 aiplan skill（同 cad 管线 ②）：
            └→ step 0-2 → plan.json + bim_supplement.json → deliver_plan

③ cad      orchestrator → AgentAsTool(cad-agent)（同 cad 管线 ④）：
            └→ aidxf S0-S4 → 逐 zone DXF（中间产物 missions/）
            └→ deliver → building.json + DXF（落盘）

④ ifc      orchestrator → AgentAsTool(ifc-agent)（同 ifc 管线 ③）：
            └→ aiifc skill：消费 bim_supplement.json + building.json + cad DXF
               （**不消费 plan.json**——plan.json 只对接 cad；ifc 消费的是 bim 补充 +
               aidxf 交付物，见 §2.5 产物定位）
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
| **building.json** | aidxf（S4 deliver） | **只 bim/ifc（aiifc）** | plan 形态整栋楼 + 逐 zone DXF 指针（sha256）——bim 接口文件 | ❌（不含几何，几何在 DXF） |
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
| aidxf 中间产物（missions/） | `{project}/missions/` | **不注册平台模型**（中间产物） | ⚠️ 设计态 |
| aidxf deliver DXF（各层） | deliver 后落盘 | **待注册平台模型**（init_model(dxf)？） | ❌ 缺口 |
| ifc 骨架（v1） | models/{modelId}/（initModel） | ✅ 注册（AddModel） | ✅ |
| ifc 深化（v2/v3/...） | scripts/v{n}.py + versions/v{n}.ifc | ✅ 注册 | ✅ |

---

## 四、缺口与后续（skill 编排 / 管线可执行化 M3+）

### 4.1 aidxf deliver DXF 注册平台模型机制（关键缺口）

**现状**：aidxf S4 deliver 落盘 building.json + 逐 zone DXF（missions/）——**DXF 未注册平台模型**。

**需要的机制**：deliver 后把各层 DXF 注册为平台模型（分配 modelId，挂项目）：
- 选项 A：deliver 命令产出 DXF 后，agent 调 `init_model(dxf)` 建骨架 → 再 stage/run/save 深化到 deliver DXF 形态（骨架 → 深化链）
- 选项 B：deliver 直接把 DXF 注册为模型（不建骨架，直接 AddModel + DXF 文件落 models/{modelId}/）

**倾向**：选项 A（骨架 → 深化链，与 ifc 一致——init_model(dxf) 建骨架，deliver DXF 内容经 stage_script/run_script/save_script 深化到骨架上）——保持「骨架初始化 → 深化」统一模式。

**但**：aidxf deliver 的 DXF 是**确定性构建产物**（机器算好的图纸），不是「用户编辑脚本」——直接注册（选项 B）可能更自然（deliver 产出即模型）。

**待定**：与用户确认 deliver DXF 的注册方式（骨架→深化链 vs 直接注册）。

### 4.2 cad DXF 传给 ifc-agent（cad→ifc 链）

**现状**：cad deliver DXF 落盘 missions/（未注册平台模型）——ifc-agent 怎么拿到 cad DXF + building.json？

**需要的机制**：
- deliver DXF 注册平台模型后，ifc-agent 经 get_project_models 拿到 dxf 模型 → 读 dxf（+ building.json）参考
- 或：cad-agent deliver 后把 building.json + dxf 路径传给 orchestrator → orchestrator 传给 ifc-agent（派发时带产物上下文）

**注意**：ifc-agent 消费的是 **bim_supplement.json + building.json + DXF**（**不消费 plan.json**——plan.json 只给 cad，见 §2.5）。拿到文件后，**解析消费成 IFC 是大工程量**（见 §4.5），当前先做到「能正确拿到文件」。

**待定**：cad→ifc 的产物传递机制（经平台模型 or 派发上下文）。

### 4.3 skill 编排（orchestrator 按 kind 编排管线）

**现状**：orchestrator persona 按 kind（personaCAD/personaIFC/全装）——编排规则在 persona 提示词（文本纪律）。

**M3+ 可执行化**：管线编排从「persona 文本纪律」升级为「skill 编排契约」（aiplan → aidxf → aiifc 的 skill 步骤编排 + 断点 + 产物链）——需要：
- orchestrator 的管线编排逻辑（按 kind 决定执行哪些 skill 步骤）
- skill 步骤间的产物传递（plan.json → aidxf → DXF → aiifc → IFC）
- 断点编排（HITL 断点的统一处理）

### 4.4 skill 改写（十二波 C2/C3 后置）

- aiifc：改「直接在数据目录写 IFC 版本」→ 「平台模型 API + script-as-source」
- aidxf/aiplan：产物传递 + 注册机制 + 管线编排

### 4.5 aiifc 解析消费链（cad->ifc 管线的 ifc 深化——大工程量，未做）

**现状**：cad->ifc 管线里 aiifc **先做到「能正确拿到相关文件」**：
- `bim_supplement.json`（aiplan 产物，BIM 补充）——经 `get_project_plans` 读方案产物 ✅
- `building.json` + 逐 zone DXF（aidxf S4 deliver 产物）——经产物传递机制拿到（见 §4.2）✅

**未做（大工程量）**：aiifc **解析消费**这些文件转成 IFC 构建脚本：
- 解析 bim_supplement.json（屋顶/特殊结构/PSET）→ IFC 对应建模（IfcRoof/特殊构件/Pset）
- 解析 building.json（plan 形态整栋楼 + 逐 zone DXF 指针/sha256）→ 楼层/分区结构
- 解析相应 DXF（outline/core/墙/房间/门窗几何）→ IFC 几何构建（墙/板/门窗实体）
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
| **cad** | `create_project(cad)` → 空白 → plan(aiplan step 0-2: `aiplan <cmd>` → plan.json) → cad-agent(aidxf S0-S4: `aidxfv3 <cmd>`，消费 plan.json) → DXF 交付（deliver 注册待设计） |
| **cad->ifc** | `create_project(cad->ifc)` → ifc 骨架(绑定先) → plan(aiplan → plan.json+bim_supplement.json) → cad(aidxf，消费 plan.json → building.json+DXF) → ifc(aiifc，消费 bim_supplement+building.json+DXF 深化骨架) → IFC 交付 |

### 业务连续性评估

- **依赖链**：plan → cad ✅（plan.json 只给 cad）；cad → ifc ⚠️（拿到文件 ✅ / 解析消费 ❌ 大工程量）；ifc 骨架绑定 ✅
- **断点**：plan/aidxf 断点 HITL 连续 ✅；中断恢复（route/reconcile）✅
- **产物链**：plan.json+bim_supplement → 方案版本化 ✅；building.json+DXF 注册平台模型 ❌（缺口）；ifc 深化版本化 ✅
- **产物定位**：plan.json→只 cad、bim_supplement/building.json/DXF→只 ifc、design.json→aiifc ifc 独立管线（见 §2.5）✅ 已分清

### 核心缺口（M3+ skill 编排前置）

1. **aidxf deliver DXF + building.json 注册平台模型机制**（deliver → init_model(dxf) 骨架→深化？还是直接注册？）
2. **cad DXF + building.json 传给 ifc-agent**（cad→ifc 产物传递——拿到文件层面）
3. **aiifc 解析消费链**（bim_supplement + building.json + DXF → IFC 构建脚本——**大工程量**，skill + subagent 装配改写，见 §4.5）
4. **skill 编排契约**（orchestrator 按 kind 编排 aiplan→aidxf→aiifc 步骤 + 断点 + 产物链；含 aiifc 两条路径：cad->ifc 消费上游 vs ifc 独立 design.json 前置）

> 这四个缺口是「skill 编排 / 管线可执行化」的前置——其中 §4.5（aiifc 解析消费）是 cad->ifc
> 管线业务完全连续的最后一块，也是最大工程量（aiifc skill + subagent 装配改写）。
> 当前先做到「能正确拿到相关文件」，解析消费与 design.json 前置编排待 skill 改写。

# reform-skill 执行改造计划 —— 三管线产物链打通 + skill 编排 + aiifc 消费链

> 基于 `reform-skill_for_flow.md` 的调查结论，给出可执行的改造计划。
> 范围裁决（2026-08-21 用户确认）：**先 P0 拿到文件**；产物传递**经平台模型**；
> DXF 事实源模式 = **skill 做适配（唯一脚本对应唯一 zone，对齐用户编辑线 script-as-source）**。

---

## 〇、现状基线（已完成，不重做）

- agent 工具面：19 DomainTools + mcp 3 个（model_current_context + ifc/dxf_upload_modified，已接入，三 agent 共享一个 MCP session）
- 三管线 kind 装配（D13）：orchestrator 按 kind 选择性装配 AgentAsTool + persona
- init_model 骨架初始化 + kind 约束（cad 只 dxf / ifc 只 ifc / cad->ifc 两者）
- create_project 分化（ifc / cad->ifc 建项目即 ifc 骨架；cad 空白）
- versions/diff 组合视图（agent 统一一套，mcp 去重合保留独有）

---

## 一、关键事实澄清（调查确认，避免幻想）

### 1.1 aidxf 的 DXF 是「LLM 逐构件调 draw 画的」，不是机器算好的

```
S1 skeleton.json（LLM 声明骨架 DSL）→ aidxfv3 validate/normalize/check（机器校验+算坐标）
S2 rooms.json（LLM 声明房间 DSL）→ 复制 skeleton.dxf → **LLM 逐构件调 dxfkit.draw** → floor.dxf
S3 细节（**LLM 调 draw**：门窗统一规律 + 柱网 + 标注）→ floor.dxf
S4 deliver（机器）：扫 confirmed missions → 复制 DXF 到 <project>/deliver/ + building.json 汇总
```

- **画 DXF = LLM 主导**（draw_api/draw_composition 是 LLM 画图手册：一次调用一个构件）
- **机器只做**：normalize（DSL→坐标，唯一坐标计算点）+ check/validate（校验）+ readback/reconcile（对账）+ deliver（封存复制 + building.json 汇总）
- **dxfkit.draw 确定性可重放**（machine_contract：「同一输入→同一输出，字节级」+ gold replay 可重放）→ **可在 build() 里重放整层画法**

### 1.2 deliver 的固定部分 vs 不适配本项目的部分

| deliver 步骤 | 状态 |
|---|---|
| 扫 confirmed missions → 复制 DXF 到指定位置 + building.json 汇总 | ✅ 固定（保留） |
| 落盘位置 `<project>/deliver/`（aidxf 自包含工作目录） | ❌ 不适配——不是本项目平台模型目录（`data/models/{modelId}/`） |
| 分配（注册平台模型：modelId + AddModel + 挂项目 + 版本化） | ❌ 缺失——deliver 产物是游离文件，非平台模型 |

**核心不适配**：aidxf 是「自包含工作目录」模式（plan/skeleton/derived/missions/deliver 全在 skill 自己的 `<project>/`），**不知道本项目平台模型体系**（modelId + data/models/ + script-as-source 版本化）。

### 1.3 事实源模式适配（用户定方向：唯一脚本对应唯一 zone）

- 用户编辑线 = script-as-source：构建脚本（PARAMS + build()）是唯一事实源，存 scripts/v{n}.py，沙箱构建派生产物
- aidxf 适配：**每 zone 的 LLM draw 调用链固化为唯一构建脚本**（PARAMS=skeleton/rooms/details DSL，build() 重放整层画法 → floor.dxf），与用户编辑线统一
- dxfkit.draw 确定性可重放 → build() 重放可行

---

## 二、P0：产物链打通——拿到文件（本波目标）

> 目标：aidxf deliver 的 building.json + 逐 zone DXF **注册为平台模型**（唯一脚本/zone + script-as-source 版本化），并能**经平台模型传给 ifc-agent**（拿到文件层面）。aiifc 解析消费（P2）不在本波。

### P0-1：aidxf 适配——每 zone 单一构建脚本（draw_api 不变 + 调用序列固化）

**目标**：draw_api 能力规范**不变**（LLM 逐次调 dxfkit.draw 的画法手册保留——skill 设计重点依赖），
但最后产出一个**在自定义 archdxf 环境下可运行的单一构建脚本**（每 zone 一个，对齐
services/cad script-as-source 契约）。

**机制（draw_api 零改动 + 机器记录固化）**：
```
LLM 逐次调 dxfkit.draw（draw_api 不变：wall_run/door/window/... 一次一构件）✅ 保留
  ↓（dxfkit/archdxf 侧在 LLM 画的同时记录：每次 draw 调用的函数 + 参数 + 次序
     ——draw_composition 组装序：底座→墙→门窗→柱→标注）
机器记录该 zone 的完整 draw 调用序列
  ↓（S4 deliver 时）
机器把调用序列固化为单一构建脚本（archdxf 环境可运行）：
  PARAMS = {skeleton: {...}, rooms: {...}, details: {...}}   # LLM 声明的 DSL（JSON 字面量）
  def build(params, out_path):
      doc = dxfkit.new_doc()
      # 按记录的调用序列重放整层画法（确定性：同 PARAMS → 同 DXF，字节级）
      wall_run(...); door(...); window(...); draw_stair(...); ...
      write_and_validate(doc, out_path)   # saveas + audit + map.json 侧车
  if __name__ == "__main__": build(PARAMS, ...)
```

**契约对齐** `services/cad/flows/cad_script_lib.py`：PARAMS 顶层字面量 + build(params, out_path)
入口 + __main__ + XDATA 确定性 key（AIDXF）+ write_and_validate 出口。**脚本在自定义 archdxf
环境下可运行**（import dxfkit/archdxf，build() 重放 draw 调用序列）。

**改动点**：
- dxfkit/archdxf：加 **draw 调用序列记录**能力（LLM 逐次调 draw 时，机器侧累积记录
  函数+参数+次序——不改 draw_api 的调用面，只在 draw 实现里埋记录点）
- aidxf S4 deliver：把记录的调用序列**翻译固化为 build() 脚本**（每 zone 一个）
- 这是 skill 侧新增「draw 调用序列 → 可重放 build() 脚本」的固化能力（能力规范不变，
  只加记录 + 固化）

**测试**：契约测试（validate_script_contract 过）+ archdxf 环境跑 build() 可重放
（同 PARAMS 同 DXF 字节级）+ 与 LLM 实画的 DXF 一致（golden 对比）。

### P0-2：deliver 落盘对接 + 注册平台模型（每 zone）

**目标**：deliver 的每 zone DXF（+ 构建脚本）注册为平台模型（modelId + AddModel + 挂项目 + 版本化）。

**改动点**（server + aidxf deliver 适配）：
- deliver 落盘位置对接：`<project>/deliver/<zone>.dxf` → 注册为平台模型（每 zone 一个 modelId）
  - 经 `init_model(dxf)` 分配 modelId + 建 models/{modelId}/ 骨架 → 把 zone 构建脚本 stage/run/save 深化（script-as-source：脚本存 scripts/v1.py，沙箱 build 派生 DXF 落 models/{modelId}/）
  - 即：**deliver 的产物 = 每 zone（构建脚本 + DXF），经 init_model + 编辑链注册为平台模型**
- 注册后挂项目（Project.Models），building.json 作为方案级产物（挂 plan 或项目）
- **reform 修正**：deliver 不再只落 `<project>/deliver/`（游离），而是触发平台模型注册（每 zone）

**裁决点**：注册触发的位置——
- (a) aidxf deliver 命令本身调平台 API 注册（skill 感知平台）
- (b) deliver 落盘后，由 agent（cad-agent/orchestrator）调 init_model + 编辑链注册（平台感知 skill 产物）
- **倾向 (b)**：skill 保持「产文件」（deliver 落盘），agent 负责「注册平台模型」（init_model + stage/run/save）——skill 不感知平台，平台注册逻辑在 agent 侧（职责分清，skill 可独立用）。

**测试**：deliver → 每 zone 注册平台模型（modelId + AddModel + 挂项目）+ 模型页可见 + viewer 可看（render.json）。

### P0-3：cad→ifc 产物传递（经平台模型，拿到文件）

**目标**：ifc-agent 能经平台模型拿到 building.json + 逐 zone DXF + bim_supplement.json（拿到文件层面，不解析）。

**改动点**：
- bim_supplement.json：`get_project_plans` 已有 ✅（方案产物）
- building.json + DXF：P0-2 注册平台模型后 → `get_project_models` 拿到 dxf 模型 → `get_script`/`get_model_info` 读
- building.json 本身：作为方案级/项目级产物暴露（挂 plan 或项目，agent 可读）——需要一个读取入口（get_project_plans 扩展 or 新工具）

**测试**：cad->ifc 管线，ifc-agent 能 get_project_plans（bim_supplement）+ get_project_models（dxf 模型）+ 读 building.json —— 三样文件都拿到 ✅。

**P0 验收**：cad->ifc 管线跑到 ifc 阶段，ifc-agent 能正确拿到 bim_supplement.json + building.json + 逐 zone DXF（文件层面），不解析。

---

## 三、P1：skill 编排契约（后续，P0 之后）

> 目标：orchestrator 按 kind 编排 aiplan→aidxf→aiifc 步骤；aiifc 区分两条路径。

- **P1-1**：orchestrator 按 kind 编排管线（aiplan→aidxf→aiifc 步骤 + 断点 + 产物链）——从 persona 文本纪律升级为编排契约
- **P1-2**：aiifc 两条路径区分——
  - cad->ifc 管线：aiifc 消费上游产物（bim_supplement + building.json + DXF），**不产 design.json**
  - ifc 独立管线：aiifc 走 design.json 前置设计框定（可选）→ 从零建模
  - 需在 aiifc skill 里区分编排（两条 ifc 深化路径）

---

## 四、P2：aiifc 解析消费链（大工程量，最后）

> 目标：aiifc 把 bim_supplement.json + building.json + DXF 解析转成 IFC 构建脚本。

- 解析 bim_supplement.json（屋顶/特殊结构/PSET）→ IFC 建模（IfcRoof/特殊构件/Pset）
- 解析 building.json（plan 形态整栋楼 + DXF 指针/sha256）→ 楼层/分区结构
- 解析相应 DXF（outline/core/墙/房间/门窗几何）→ IFC 几何构建
- 综合 → IFC 构建脚本（script-as-source）
- **工程量大**：aiifc skill 加「消费上游产物」解析链 + subagent 装配（文件喂给 aiifc + 断点编排）

---

## 五、执行顺序与依赖

```
P0-1（aidxf 适配：唯一脚本/zone，draw 链固化）
   ↓（构建脚本是注册的前提——script-as-source 需要脚本）
P0-2（deliver 注册平台模型：init_model + 编辑链，每 zone）
   ↓（注册平台模型后，产物可经平台模型传递）
P0-3（cad→ifc 产物传递：经平台模型拿到文件）
   ↓
【P0 完成：拿到文件】
   ↓
P1（skill 编排契约）→ P2（aiifc 解析消费，大工程量）
```

**依赖链**：P0-1 → P0-2 → P0-3（严格顺序：先固化脚本 → 再注册 → 再传递）。

---

## 六、本波（P0）裁决点汇总（需用户确认）

| 裁决 | 选项 | 定稿 |
|---|---|---|
| **P0-1 draw 链固化方式** | (a) draw_api 不变 + 机器记录调用序列固化 build() / (b) LLM 直接产 build() 脚本 | **(a) 已定**——draw_api 能力规范不变（skill 设计重点依赖），机器记录 draw 调用序列 → 固化为 archdxf 可运行的单一 build() 脚本/zone |
| **P0-2 注册触发位置** | (a) skill 感知平台调 API / (b) agent 侧 init_model+编辑链注册 | **(b)**——skill 产文件不感知平台，注册逻辑在 agent 侧（职责分清） |
| **P0-3 building.json 读取入口** | get_project_plans 扩展 / 新工具 | 待定（看 building.json 挂哪——方案级 or 项目级） |

> P0-1 已定（draw_api 不变 + 调用序列固化单一脚本，archdxf 可运行）。余下两个裁决确认后，
> P0 可拆任务执行（TDD，测试≥实现，对齐 api_regulation 硬标准）。

---

## 六、执行波次（原 reform-skill_for_flow.md 拆入，2026-08-21）

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
| **P0-2** | **S4-b 每 zone 注册平台模型**——**复用 tools.go 现有工具链（init_model+stage_script+run_script+save_script），零新代码**（LLM 按 cadAgentPersona 对每 zone 调） | `steps/step-04-deliver.md`、`references/machine_contract.md`、`references/orchestrator/dispatch.md`（S4 交付改造 + skill-work 工作区 + deliver 后清理） | ✅ 文档完成；**代码零新增**（复用现有工具链） | `9478511` |
| **P0-2b** | **aiplan 交付对齐**（deliver_plan/deliverPlanCore 已有——代码不动） | `skills/aiplan/SKILL.md`、`steps/step-02-deliver.md`、`steps/step-00-ingest.md`（交付 deliverPlanCore + PlanStore 版本化 + 工作区 skill-work/{projectID}/aiplan/ + deliver 后清理） | ✅ 文档完成 | `5679db5` |
| **P0-3** | **S4-c building.json agent 组装 + 交付工具 ✅**——`deliver_building` 工具（agent 组装 building.json → PlanStore 版本化 plans/{projectID}/building.json）+ **get_project_plans 扩展读全部方案产物（plan+bim+building，building 容忍缺失）** + building.schema.json v2（zones 记 modelId）。**`aidxfv3 deliver` 命令已退役 ✅**（复制 DXF→S4-b、building.json→agent 组装） | `references/schemas/building.schema.json`（zones 记 modelId ✅）、`steps/step-04-deliver.md`（S4-c ✅）、`references/machine_contract.md`（building 契约 ✅） | ✅ 完成（deliver_building 工具 + get_project_plans 扩展 + building.schema + deliver 退役） | `c175796`/`45bc5c4` |

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
3. **schema 联动**：`building.schema.json` 改 modelId 后，building.json 由 agent 侧组装（不再
   `deliver.py` 产——它不知道 agent init_model 的 modelId），`deliver_building` 工具落 PlanStore
   （P0-3 代码：deliver_building 工具 + get_project_plans 扩展读 building.json + schema 一起）。

### P1 波：skill 编排契约（后续，P0 之后）

- **orchestrator 编排契约细化 ✅（P1-1，2026-08-21，`ce3de7f`）**：
  - **无空 kind，三个 kind 强制装配**：kind 强制必选（create_project 强制 ifc|cad|cad->ifc），
    orchestrator 按 kind 强制装配 persona：cad→personaCAD、ifc→personaIFC、cad->ifc→OrchestratorPersona。
  - **OrchestratorPersona = cad->ifc 专属全链编排**（不是空 kind 全装默认兜底）——cad->ifc 用全装
    （aiplan+cad+ifc）：① plan（aiplan 对话框定+断点主持 → deliver_plan）→ ② cad（plan 锚点
    +stage_plan_to_workdir → 各 zone modelId + deliver_building）→ ③ ifc（消费上游路径 CONSUME_UPSTREAM
    + 上游锚点）→ IFC 交付。
  - **personaCAD**（cad 管线）：aiplan 前置（断点主持 → deliver_plan）→ cad（plan 锚点 → init_model
    注册 → deliver_building）。
  - **personaIFC**（ifc 独立管线）：design.json 前置路径（PLAN_DXF_IFC，断点确认设计意图）→ 骨架深化。
  - **产物传递锚点显式化**：aiplan→cad=plan.json+stage_plan_to_workdir；cad→ifc=building.json+
    zones modelId+DXF modelId——步骤编排 + 产物锚点 + 断点主持都写进编排契约。
- **aiifc 两条 ifc 深化路径区分 ✅（P1-2，2026-08-21，`058d99c`）**：
  - **设计要点**：判断逻辑**不在 skill/ifc-agent**（它们不判断），**在 orchestrator 按 kind 强制注入**。
  - **aiifc skill**：声明两条路径（不判断）——`workflows/CONSUME_UPSTREAM.md`（cad->ifc 消费上游：
    bim_supplement+building.json+DXF → IFC 脚本，新增英文）+ `workflows/PLAN_DXF_IFC.md`（ifc 独立
    design.json 前置，已有）；`references/consume_upstream/`（解析参考骨架，P2 填充）。
  - **ifcAgentPersona**：路径由主 Agent 指定（不自己判断）。
  - **OrchestratorPersona**：ifc 路径强制注入（派 ifc-agent 时 request 指定：cad->ifc→消费上游路径
    带上游锚点；ifc 独立→design.json 前置路径）。
  - **语言统一**：aiifc skill 全英文（与原有英文一致），persona 保持中文。

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

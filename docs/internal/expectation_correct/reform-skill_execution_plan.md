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

### P0-1：aidxf 适配——每 zone 唯一构建脚本（draw 链固化）

**目标**：aidxf 每 zone 的 LLM draw 调用链固化为 script-as-source 构建脚本（对齐 services/cad 契约）。

**改动点**（aidxf skill + services/cad 协同）：
- aidxf 在 S2/S3 主 agent 画完一 zone 后，**产出该 zone 的构建脚本**：
  - `PARAMS = {skeleton, rooms, details}`（LLM 声明的 DSL，JSON-compatible 字面量）
  - `build(params, out_path)`：重放整层画法（dxfkit.new_doc → 底座 → wall_run/door/window → 柱 → 标注 → write_and_validate）
  - 契约对齐 `services/cad/flows/cad_script_lib.py`（PARAMS/build/__main__/XDATA key/write_and_validate）
- **位置**：这是 skill 侧新增「draw 链 → 构建脚本」的固化能力——需要 aidxf skill 改写（在 draw_composition 组装序基础上，把 LLM 的 draw 调用链记录/固化为可重放的 build()）

**裁决点**：draw 链固化的实现方式——
- (a) LLM 画的同时**记录 draw 调用序列**，deliver 时把调用序列翻译成 build() 脚本（机器生成）
- (b) LLM 直接**产出构建脚本**（不调零散 draw，而是一次写出 build() 脚本，沙箱跑 build() 产 DXF）——更接近用户编辑线
- **倾向 (b)**：LLM 直接产 build() 脚本（与用户编辑线完全一致：script-as-source，沙箱 build→DXF），draw_api/draw_composition 作为「写 build() 脚本时的画法参考手册」而非逐次调用。这样 aidxf 的 DXF 天然就是 script-as-source，无需额外固化。

**测试**：契约测试（validate_script_contract 过）+ 沙箱 build→DXF 可重放（同 PARAMS 同 DXF）+ golden 对比。

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

| 裁决 | 选项 | 倾向 |
|---|---|---|
| **P0-1 draw 链固化方式** | (a) 记录调用序列机器翻译 build() / (b) LLM 直接产 build() 脚本 | **(b)**——与用户编辑线完全一致（script-as-source，沙箱 build→DXF），draw_api 作为写法参考 |
| **P0-2 注册触发位置** | (a) skill 感知平台调 API / (b) agent 侧 init_model+编辑链注册 | **(b)**——skill 产文件不感知平台，注册逻辑在 agent 侧（职责分清） |
| **P0-3 building.json 读取入口** | get_project_plans 扩展 / 新工具 | 待定（看 building.json 挂哪——方案级 or 项目级） |

> 确认这三个裁决后，P0 可拆任务执行（TDD，测试≥实现，对齐 api_regulation 硬标准）。

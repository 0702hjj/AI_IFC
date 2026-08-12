# 接力数据契约：plan.json → DXF → IFC

主 Agent 编排 plan→cad→ifc 全链路时，三个锚点的落盘格式与确认门禁。
**字段名全部以真实 skill 源为准**：锚点 1/2 复制自 `skills/aidxfv/v2/references/plan_contract.md`（§1/§2/§3），锚点 3 复制自 `skills/aiifc/SKILL.md`（MUST #25-31）与 `skills/aiifc/workflows/PLAN_DXF_IFC.md`。本文件不重定义，只做接力视角的索引与门禁约定。

## 锚点 1：plan.json

**Schema 事实源：`skills/aidxfv/v2/references/plan_contract.md` §1**（本包正例 fixture `fixtures/plan.sample.json` 由该节复制简化）。

```json
{
  "version": 1,
  "project": "string",
  "building_type": "office | retail | residence | adu | custom",
  "site": {
    "lot_width_mm": 15000,
    "lot_depth_mm": 20000,
    "setbacks_mm": {"front": 0, "rear": 0, "left": 0, "right": 0}
  },
  "floors": [
    {"name": "1F", "height_mm": 3600, "usage": "lobby + open office"}
  ],
  "program": {
    "area_target_sqm": 0,
    "rooms": [{"name": "meeting", "count": 2, "area_sqm": 20}],
    "notes": "free text, untrusted intent hints"
  },
  "constraints": {
    "max_footprint_sqm": 0,
    "accessibility": false,
    "custom": {}
  },
  "draft": null,
  "confirmed": false
}
```

约定（v2 plan_contract.md §1/§3 原文要点）：

- 单位 **mm**；`floors[].height_mm` 为层高；`floors[].name` 即后续 DXF 文件名（`<name>.dxf`，v2 step-00 归一化规则）。
- `building_type` / `site` / `floors` 是 cad 阶段**硬约束**；`program` 是意图，cad 可在 step1 草案中重排但必须在 step2 向用户说明偏差。
- `draft` / `confirmed` 由 cad 阶段写回，plan 阶段一律留初值（`draft: null, confirmed: false`）。
- 状态机：`draft: null, confirmed: false` → 待草拟；`draft` 存在、`confirmed: false` → 待确认；`confirmed: true` → 已定稿（draft 冻结为硬约束，只许构建）。
- 可选 `plan.dxf` 确认图：由 aiifc 的 `dxf_from_design.py` 或 cad-agent 草案渲染产出，仅供设计师确认平面，不是契约的一部分。

## 锚点 2：DXF（+ building.json）

**Schema 事实源：`skills/aidxfv/v2/references/plan_contract.md` §2**；交付纪律见 v2 `steps/step-04-deliver.md`。

v2 管线交付物 = 逐层 DXF 集 + `building.json`（bim 段唯一输入）：

```json
{
  "version": 1,
  "project": "string",
  "floors": [
    {
      "name": "1F",
      "dxf": "1F.dxf",
      "elevation_mm": 0,
      "height_mm": 3600,
      "sha256": "hex of the canonical dxf"
    }
  ],
  "metadata": {
    "materials": {},
    "occupancy": "string",
    "non_geometric_notes": "DXF 承载不了、bim 建模需要的建筑信息"
  }
}
```

约定：

- 每层 DXF 命名 = plan.json `floors[].name` + `.dxf`；`dxf` 为相对 building.json 所在目录的路径。
- 所有 DXF 必须过 `archdxf.canon.canonicalize_dxf`；`sha256` 在 canon **之后**计算，bim 段据此校验图纸未被手改。
- `elevation_mm` 由 `height_mm` 累加（step-04 规则）。
- DXF 承载不了的信息（层高、材质、竖向标高关系）**必须**写进 building.json，不许口头传递。
- building.json 与 plan.json 的对应关系：`floors[]` 的 name / height_mm 必须与 plan.json 一致（step-04 一致性自检项）。

## 锚点 3：IFC

**事实源：`skills/aiifc/SKILL.md` MUST #25-31 + `workflows/PLAN_DXF_IFC.md`。**

- IFC 段唯一事实源是**构建脚本**（`scripts/v{n}.py`）；IFC 文件（`versions/v{n}.ifc`）是脚本运行的派生物，从不直接手改。
- 脚本 PARAMS 从 plan.json / building.json 派生：层高 ← `floors[].height_mm`，竖向标高 ← `elevation_mm` 累加关系，轮廓/开洞 ← 对应层 DXF。非几何信息（材质/occupancy）← building.json `metadata`。
- 追溯锚点：构件 GlobalId 由 `script_lib.deterministic_guid(key)` 派生，key 稳定唯一 `{storey}:{kind}:{n}`；`script_lib.create_entity` 自动写 `Pset_AIIFC.designKey`——IFC 语义 diff 的跨版本对齐与「选中构件→定位脚本」都依赖它。
- 版本对应：每次确认保存成对快照 `scripts/v{n}.py` + `versions/v{n}.ifc`；回退 = 恢复脚本 → 重跑。

## 确认门禁

每个锚点交付前必须经设计师确认，主 Agent 负责卡点：

1. **plan.json 确认**：设计师确认 plan（或明确跳过）后才派 cad-agent 构建；v2 状态机 `confirmed: true` 即此门禁的落盘形式。
2. **DXF 确认**：cad-agent 交付 DXF 集 + building.json + 校验摘要后，设计师确认才进入 IFC 段。
3. **IFC 交付**：ifc-agent 报告 validate / design_review 结果，设计师确认保存为大版本。

**反例约定**：缺硬约束字段（`building_type` / `site` / `floors` 任一缺失）的 plan.json 应被 cad-agent 在 step-00 **拒收并停步**，报告缺哪些字段，补齐后才许进 step1（v2 `steps/step-00-ingest-plan.md` 执行 §2）。主 Agent 收到此类报告应原样转述字段清单向设计师索取，不得自行编造默认值填充硬约束。

# Plan → DXF → IFC 工作流（辅助设计师）

> 本文是 aiifc skill 的**可选工作流编排层**：规定「先 plan、再 DXF、最后 IFC」三阶段顺序。
> 与 `SKILL.md` 的关系：`SKILL.md` 讲「怎么建 IFC」（建模纪律），本文讲「一次任务走哪几步、每步产什么」。
> **选择性地使用**：适用于「从想法到 IFC」的辅助设计师场景；简单的直接建模（单墙/板）或用户已明确指向某阶段的输入，**不必走完整流程**。
> 顺序**固定**，但可依用户输入**跳步**（见 §4）。

## 定位

辅助**设计师**开发：AI 首先生成方案，设计师在方案上确认 / 修改，最终产出 IFC。不追求逐步回溯，只保留**大版本之间**的差异。

## 三阶段总览

```
① plan   design.json  设计意图（纯语义：墙轴/洞口沿轴/层高，无坐标）
  │       由 LLM 依用户需求产出；用户确认 plan 后再往下
  ▼
② dxf    plan.dxf     2D 平面图（每层一个图层：footprint/墙/门窗/楼梯）
  │       由 dxf_from_design.py 生成；前端可转 svg 预览
  ▼
③ ifc    model.ifc    最终 IFC 模型
         design_builder → build_script_template → model.ifc
```

## 每阶段的 MUST

### ① plan

- 读 `references/DESIGN_JSON_SCHEMA.md` 和 `references/SPATIAL_QUALITY.md` 再产出 plan。
- plan = design JSON，只描述**意图**（哪里/多大），**绝不计算坐标**。
- 产出文件：`designs/v{n}.json`（version 由系统编排；无系统时写当前目录 `design.json`）。
- 完成标准：design JSON 通过 `design_builder` 规范化（`SchemaError` → 修正重出，Self-Refine 循环）。

### ② dxf

- 由 design JSON 生成 2D 平面图，**不改设计**，只做可视化/交付。
- 命令：
  ```bash
  <your-python> <skill_root>/references/docs/flows/dxf_from_design.py design.json -o plan.dxf
  <your-python> <skill_root>/references/docs/flows/dxf_from_design.py design.json -o plan-1F.dxf --storey "1F"
  ```
- 产出：`plan.dxf`（米坐标，DXF INSUNITS=6）。
- 完成标准：DXF 可打开；每层图层齐备（FOOTPRINT/WALL/WALL_CENTER/OPENING/STAIR/LABEL）。

### ③ ifc

- 用 `design_builder.py` 规范化 design JSON → features.json，再 `build_script_template.py` → model.ifc。
- 产出：`model.ifc`（工作目录）或系统约定的 `uploads/{modelId}.ifc`。
- 完成标准：`ifcopenshell.validate` 通过 + `design_review.py` 无 ERROR。

## 跳步规则（依用户输入）

| 用户输入 | 走哪几步 |
|---|---|
| 「建一栋两层小楼」 | ①→②→③（完整流程，②用于用户确认平面） |
| 「把外墙改厚到 300」 | ③（直接改 design JSON 的 t → 重生成） |
| 「先看看平面图」 | ①②（到 DXF 为止，不生成 IFC） |
| 「上传一个 IFC 让我看」 | 只渲染，不生成 |
| 「改这面墙位置」 | ③（改 design JSON 该墙 axis → 重生成） |

> 跳步判断依据：用户是否提供了足够信息直接进入某阶段。**设计类需求默认走 ①→②→③**，让用户确认 plan 后再生成，避免返工。

## 与版本/暂存的关系

- ① 产出的 design JSON 是**唯一编辑面**（用户/AI 后续修改都改它）。
- 每次**确认保存**（大版本）成对快照：`designs/v{n}.json` + `versions/v{n}.ifc`。
- ③ 生成的 IFC 含确定性 GlobalId 与 `Pset_AIIFC.designKey`（见 `DESIGN_JSON_SCHEMA.md` §key），供跨版本 diff 对齐。

## 相关

- `references/DESIGN_JSON_SCHEMA.md` — design JSON 契约（含 `key` 字段）
- `references/docs/flows/dxf_from_design.py` — plan → DXF
- `references/docs/flows/design_builder.py` — design JSON → features.json
- `references/docs/flows/build_script_template.py` — features.json → IFC

---
name: step-01-draft-type
description: Select the building-type pack and draft the design (areas, room breakdown, floor organization) into plan.json's draft field.
---

# Step 1: 草拟 building_type 设计方案

## 输入
- 校验通过的 plan.json（来自 step0）
- `references/building_types/_template.md`（T0 通用标准，必读）
- `references/building_types/<type>.md`（plan 指定类型的包；没有则按模板现场编写）

## 执行
1. 读类型包 T1：若 plan 的 `building_type` / 层数 / 面积目标落在包的 NOT FOR
   范围 → 停步，建议换包或回 plan 阶段改参数。
2. 草拟方案，写进 plan.json 的 `draft` 字段：
   ```json
   "draft": {
     "type_pack": "office",
     "floor_area_sqm": 500,
     "typology": "central corridor, core at west",
     "bay_mm": 8400,
     "wall_thickness_mm": {"exterior": 200, "partition": 100},
     "floors": [{"name": "1F", "rooms": ["lobby", "open office", "meeting x2"]}],
     "deviations": ["program 要 3 间会议室，面积只够 2 间"],
     "defaults_used": ["走廊宽 2400（T1 默认，plan 未指定）"]
   }
   ```
3. `deviations` 与 `defaults_used` **必须如实填写**——它们是 step2 交互的素材，
   隐瞒即违反不臆造原则。
4. 逐层房间划分只需到"哪些房间、大致分区"粒度，具体坐标是 step3 的事。

## 输出
- plan.json 写回 `draft`，`confirmed` 保持 false

## 完成条件
draft 各字段齐全、与硬约束无矛盾（面积不超场地、层数一致），然后进 step2。

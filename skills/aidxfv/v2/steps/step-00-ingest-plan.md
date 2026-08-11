---
name: step-00-ingest-plan
description: Load and validate the plan 落盘, route by its state machine, and stop on missing hard constraints.
---

# Step 0: 对齐 plan 落盘

只读与校验，不画图。

## 输入
- `plan.json`（路径由用户/主 agent 指定；契约见 `references/plan_contract.md` §1）
- `references/plan_contract.md`

## 执行
1. 读 plan.json。不存在 → 询问用户项目参数，按契约现场生成一份并让 plan 阶段
   （或用户）补齐；存在则继续。
2. 校验硬约束：`building_type` / `site` / `floors`。
   - 缺失或非法 → **停步**，向用户列出缺哪些字段，补齐后才许进 step1。
3. 硬约束齐全时，读 `draft` / `confirmed` 路由：
   - `draft: null, confirmed: false` → step1
   - `draft` 存在、`confirmed: false` → step2（中断恢复，直接拿草案去确认）
   - `confirmed: true` → step3（定稿冻结，不许再改设计，只许构建）
4. 归一化：把 `floors[].name` 与后续 DXF 文件名的对应规则定下来
   （`<name>.dxf`，写进 building.json 时保持一致）。

## 输出
- 校验通过的 plan.json（可能补了缺失字段）
- 明确的下一步路由

## 完成条件
硬约束校验通过且路由确定。硬约束缺失时本步是唯一允许"空手等待用户"的步骤。

---
name: step-02-confirm
description: Present the draft to the user with option-box interaction, apply revisions, and freeze it as confirmed hard constraints.
---

# Step 2: 交互确认

## 输入
- plan.json（`draft` 存在、`confirmed: false`）

## 执行
1. 向用户展示草案摘要：类型包、单层面积、层数组织、房间划分、**全部
   deviations 与 defaults_used**。
2. 选项框式逐条确认（harness 的 question 工具或等价交互）：
   - 每个 deviation：接受 / 调整（给出新值）
   - 每个 defaults_used：采用默认 / 覆盖
   - 整体布局取向（走廊式/核心筒式等 T1 提供的 typology 选项）
3. 把用户修订写回 `draft` 对应字段；用户提出 draft 之外的新需求 → 记为新
   deviation 并确认。
4. 全部确认后：`confirmed: true`，draft 冻结为 step3 的硬约束。
   **冻结后任何设计修改都必须回到本步重新确认**，step3 无权改设计。

## 输出
- plan.json：`draft` 为修订后定稿，`confirmed: true`

## 完成条件
用户明确确认定稿。用户中途离开 → 保持 `confirmed: false`，下次 step0 会路由回本步。

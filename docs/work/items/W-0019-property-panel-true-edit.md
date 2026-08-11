# W-0019: 属性面板真改直通 + 类型化表单 + 构件删除（Revit L1）

- **状态：** done
- **关闭于：** 2863785 + 852d1fc + 96c6831 + 302dcb7
- **优先级：** P1
- **Milestone：** v0.2（Revit 式编辑 L1 层）
- **来源：** 2026-08-07 v0.2 规划（参考 Revit/Autodesk 属性面板即改即存）
- **执行者/分支：** opencode / feat/v0.2-batch

## 背景

当前 PropertyPanel 的 5 个硬编码字段走 overrides 旁路（显示层标注，不改 IFC），真改需手动 migrate 且 Classification 多数 422（edit.go:440）。Revit 式体验 = 属性面板即改即存真改 IFC。后端 REST edit API 能力已够（任意 fields + psets 增改，pending/commit 原子回滚），缺口在前端接入与表单类型化。

## 涉及位置

- `web/src/viewer/PropertyPanel.tsx`、`overrides.ts`
- `services/ifc/app/routes_edits.py`（实体属性/pset 编辑，能力已备）
- 类型元数据：pset 值类型（str/int/float/bool）+ IFC 枚举字段（如 PredefinedType）

## 方案

1. **真改直通**：PropertyPanel 编辑 → `PUT /entities/{guid}`（pending）→ 用户确认 → commit 编排（现成）→ 重转刷新。替代 overrides 旁路（overrides 保留只读展示历史，新编辑不再产生）
2. **类型化表单**：按 IFC 属性类型渲染——bool 复选、int/float 数字输入（带单位）、PredefinedType 等枚举下拉（从 ifcopenshell schema 声明类型取枚举值，后端提供 `GET /models/{id}/entities/{guid}/editable-schema` 或前端静态表，选更简单的）
3. **pset 编辑**：常用 pset 属性可编辑（值类型 str/int/float/bool）
4. **构件删除**：`DELETE /entities/{guid}`（后端新增：ifcopenshell 删除实体 + 级联关系处理，进 pending/commit 流）+ 前端删除按钮（确认弹窗）

## 验收标准

- 属性面板改 Name/Description/FireRating 等 → 真改 IFC → diff 可见
- 枚举字段下拉合法值；非法值服务端 422 不破坏模型
- 构件删除后模型树/3D 刷新，版本快照含删除
- 全流程 TDD

## 测试要求

- 后端：删除实体的级联用例、schema 端点、枚举校验 422
- 前端：类型化渲染、提交链路、删除确认
- 遵从 envelope 契约 + AGENTS.md 测试纪律

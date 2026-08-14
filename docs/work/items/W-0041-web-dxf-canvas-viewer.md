# W-0041: web DXF Canvas 查看器（只读，ViewerPage 按 kind 分流 + 七类实体绘制 + 图层/选中交互）

- **状态：** done
- **优先级：** P1
- **Milestone：** v0.6（services/cad script-as-source，chunk D）
- **来源：** spec 2026-08-12-services-cad-script-as-source-design.md §二「实现路径：前端显示」2 + 「工作项建议」6
- **执行者/分支：** opencode / feat/v0.8-dxf-viewer
- **关闭于：** 本迭代分支 feat/v0.8-dxf-viewer（PR 待提）

## 背景

chunk C（W-0039 render payload v2 + W-0040 Go kind 分流/代理）已交付：kind=dxf 模型有实体级 `render.json`（schemaVersion=2，实体带 XDATA key），且 Go 侧 `GET /v1/models/{id}/render.json` 只读直挂可达。本项是 chunk D：web 前端新增 Canvas 2D CAD 查看器，ViewerPage 按模型 kind 路由——dxf 走 Canvas 查看器，ifc 维持 XKT viewer 不回归。对应 spec 决策 3（entity-keyed JSON + Canvas 2D，不引 WebGL——2D 图纸 YAGNI）。

## 涉及位置

- `web/src/`：新增 CAD Canvas 查看器组件（自绘 Canvas 2D 或 Konva）；ViewerPage 按 kind 分流
- 参照：ViewerPage 现有 XKT viewer 装载路径；`web` 现有 zustand store 与组件风格
- 数据源：`GET /v1/models/{id}/render.json`（W-0040 直挂只读端点，非 envelope）

## 方案

1. **ViewerPage 分流**：模型记录带 kind；kind=dxf 渲染 Canvas 查看器，kind=ifc（或缺省）走现有 XKT viewer，路径不回归。
2. **七类实体绘制**：LINE / LWPOLYLINE（含 arc 段，bulge 已展开）/ CIRCLE / ARC / TEXT / MTEXT / INSERT，按 render.json 几何字段绘制；bounds 用于初始视图 fit。
3. **交互**：pan/zoom；图层开关（payload `layers`）；hover 高亮；点击选中显示实体 key 与属性面板。
4. **unsupported 明面化**：`unsupported` 列表计数在 UI 明面展示（对齐 ai-cad-v2-contract 纪律），不静默忽略。
5. **健壮性**：空 payload（bounds null / 无实体）不崩，渲染空态提示。

**显式范围外：** render.json 生成与 Go 代理（chunk C 已交付）、DXF 编辑 UI（拖拽端点/locate/edit-call 下钻——Phase 2，另立 chunk，见测试要求门禁）、ifc 侧查看器改动。

## 验收标准

- kind=dxf 模型 ViewerPage 分流到 Canvas 查看器；kind=ifc 维持 XKT viewer 不回归。
- render.json 七类实体（含 LWPOLYLINE arc 段）绘制正确。
- pan/zoom、图层开关可用；hover 高亮 + 点击选中显示 key 与属性。
- unsupported 计数在 UI 明面化。
- 空 payload（bounds null）不崩。
- `cd web && npm test && npm run lint && npm run build` 全绿（既有 194 用例不回归）。

## 测试要求

- ViewerPage 按 kind 分流的组件测试（dxf → Canvas、ifc → XKT）。
- 七类实体绘制用例（含 arc 段）；空 payload（bounds null）不崩用例。
- 交互测试：图层开关、hover 高亮、点击选中显示 key/属性；unsupported 计数展示。
- 新增测试量 ≥ 新增实现量（仓内 ≥1:1 硬规则）；既有 194 用例全绿。
- **只读边界（CAD 编辑门禁）：** 本项只交付只读查看器；DXF 编辑 UI（拖拽编辑、locate/edit-call 下钻）另立 chunk，且开工需用户确认后方可立项。

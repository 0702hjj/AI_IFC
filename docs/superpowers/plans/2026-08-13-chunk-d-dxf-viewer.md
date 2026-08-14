# Chunk D：web DXF Canvas 查看器（只读）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** DXF 模型在 web 端可见：Canvas 2D 查看器消费 render.json（payload v2），pan/zoom、图层开关、hover/选中得 XDATA key + 属性面板；ViewerPage 按 model.kind 分流。只读——编辑属后续 chunk。

**Architecture:** render.json 实体 → Fabric Object（key 挂 `data.key`，参考 gaia 的 `gaissData` 模式）经 `useDxfCanvasEngine` hook 挂载（生命周期/选中事件参考 gaia `useCanvasEngine`）；纯函数层只做 payload→对象规格转换与几何（arc→path），命中/高亮用 Fabric 内建（perTarget 选中）。jsdom 无 canvas 环境——组件测试 mock `fabric` 模块（既有 xeokit mock 模式），纯转换函数直接单测。与 xeokit viewer 并存：kind==="dxf" 走新组件，否则走原 ViewerProvider。性能守卫：实体 >2000 时按 layer 合并为 Group（fabric 对象数控制），选中经 Group data 反查 key。

**Tech Stack:** React 19 + zustand + **fabric@7**（新增依赖，与 gaia_web 同栈——用户 2026-08-13 裁决：Canvas 参考 gaia_{web,api,agent} 做成开源对齐）+ vitest/jsdom。hook 组织参考 `~/projects/gaia_web/src/hooks/canvas/`（useCanvasEngine/useCanvasZoomPan 模式）。

## Global Constraints

- 分支 `feat/v0.8-dxf-viewer`（自 main 新建）；commit 中文前缀式；TDD；新增测试量 ≥ 新增实现量。
- 本 chunk 只读：不引 DesignPanel/script 编辑接线（dxf 编辑 UI 属后续 chunk，开工前需再向用户确认——CAD 编辑门禁）。
- 既有 xeokit 链路零改动（回归测试现有 194 用例全绿）。
- render.json 契约：`GET /v1/models/{id}/render.json`（auth 豁免、直挂静态）；payload `{schemaVersion:2, bounds, layers, entities, unsupported}`；`bounds` 可空；块展开子实体 key=None 带 `block` 标记。
- unsupported 实体明面化：UI 上列出数量（不静默丢——ai-cad-v2-contract 纪律）。
- 坐标系：payload 是原始 DXF 坐标（Y 向上）；Canvas Y 向下——变换层统一翻转，纯函数可测。

---

### Task 1: 立项 W-0041 + PLAN 行

- [ ] W-0041「web DXF Canvas 查看器（只读）」：验收——kind=dxf 模型 ViewerPage 分流到 Canvas 查看器；render.json 七类实体绘制（含 arc 段）；pan/zoom；图层开关；hover 高亮 + 点击选中显示 key 与属性；unsupported 计数明面化；空 payload（bounds null）不崩；测试 ≥1:1 且既有 194 全绿。注明只读边界（编辑另立 chunk + 用户门禁）。
- [ ] PLAN v0.6 加 chunk D 行。
- [ ] Commit `docs(work): W-0041 立项 + PLAN chunk D 行`

---

### Task 2: dxfviewer 纯函数层（TDD）

**Files:**
- Create: `web/src/dxfviewer/types.ts`（RenderPayload/RenderEntity TS 类型，与 services/cad render.py 对齐）
- Create: `web/src/dxfviewer/geometry.ts`（payload → fabric 对象规格：LINE→Line 规格、CIRCLE→Circle、ARC/bulge 段→Path 规格（arc 转 SVG path A 指令，含跨 0°）、TEXT/MTEXT→FabricText、INSERT 展开子实体并入）
- Create: `web/src/dxfviewer/fit.ts`（fit-bounds 计算 initial viewport，参考 gaia canvasConfig 的 FIT 常量模式）
- Modify: `web/package.json`（+ `fabric` 依赖）
- Test: `web/src/dxfviewer/*.test.ts`

**Interfaces（Produces——Task 3 组件层消费）:**

```ts
// types.ts（同前：RenderPayload/RenderEntity/Bounds/LayerInfo/Unsupported）
// geometry.ts
export interface FabricObjectSpec { kind: "line"|"circle"|"path"|"text"; layer: string; key: string | null; block?: boolean; props: Record<string, unknown> }
export function payloadToObjectSpecs(payload: RenderPayload): FabricObjectSpec[]  // Y 翻转在此统一处理（DXF Y 向上 → canvas Y 向下）
export function arcToPathD(cx: number, cy: number, r: number, startDeg: number, endDeg: number): string  // 含跨 0° 判定
// fit.ts
export function fitZoomPan(bounds: Bounds, canvasW: number, canvasH: number, padding?: number): { zoom: number; panX: number; panY: number }
```

- [ ] **Step 1: 失败测试**——geometry：七类实体各出正确规格（LINE 坐标、CIRCLE radius、ARC path d 含 large-arc/sweep 标志正确 + 跨 0° 段、bulge 段转 path、TEXT insert/内容）；Y 翻转后 bounds 与实体一致；空 entities → 空数组；fit：居中 + 比例正确 + padding；arcToPathD 专项（0-90、270-45 跨零、180 半圆 large-arc=1）。
- [ ] **Step 2: 实现**（不 import fabric——规格是纯数据，组件层才实例化，测试无需 canvas 环境）
- [ ] **Step 3: `cd web && npm test` 绿 + Commit** `feat(web): dxfviewer 纯函数层——transform/pick/geometry（W-0041 上半）`

---

### Task 3: Canvas 组件 + 页面分流（TDD）

**Files:**
- Create: `web/src/dxfviewer/DxfViewer.tsx`（canvas 挂载 + 事件：wheel zoom、drag pan、mousemove hover、click select；图层开关侧栏；选中属性面板）
- Create: `web/src/dxfviewer/useDxfCanvasEngine.ts`（fabric.Canvas 生命周期 + fit + 选中/hover 事件，参考 ~/projects/gaia_web/src/hooks/canvas/useCanvasEngine.ts 模式：canvasEl ref、onReady/onObjectSelected 回调、dispose）
- Create: `web/src/dxfviewer/useDxfRender.ts`（fetch render.json → payloadToObjectSpecs → 实例化 fabric 对象入 canvas；图层分组/开关）
- Modify: `web/src/api/types.ts`（ModelInfo 加 `kind?: "ifc"|"dxf"`）、`web/src/api/client.ts`（`renderJsonUrl(id)` helper，照 modelAssetUrl 模式）
- Modify: `web/src/pages/ViewerPage.tsx` + css（kind==="dxf" → DxfViewer 分支；轮询/status 逻辑复用——dxf 直接 ready）
- Modify: `web/src/pages/LibraryPage.tsx`（模型表加 kind 列/徽标，一行级）
- Test: `web/src/dxfviewer/DxfViewer.test.tsx`、`web/src/pages/ViewerPage.test.tsx`（加 dxf 分支用例）

**Interfaces:**
- Consumes: Task 2 纯函数；`renderJsonUrl(id) -> string`；`ModelInfo.kind`
- Produces: `DxfViewer({ modelId: string })` 组件；选中状态写 `useViewerStore.selectedId`（复用既有 store 的 selectedId 语义——值为 XDATA key 字符串；高亮由组件内部完成，不走 xeokit 的 useVisibility）

- [ ] **Step 1: 失败测试**
  - DxfViewer：`vi.mock("fabric")` 桩（假 Canvas 类：add/remove/getObjects/setZoom/requestRenderAll/on/fire 可编程，照既有 xeokit mock 模式）+ mock fetch；七类实体规格→实例化调用断言；wheel/drag → viewportTransform 变化；fabric 选中事件 → key 写入 store + 属性面板渲染 key/类型/图层；图层 toggle → 对应 layer 对象 visible=false；unsupported>0 角标；bounds null 空态不崩；>2000 实体触发 Group 合并路径。
  - ViewerPage：kind="dxf" → 渲染 DxfViewer 且不渲染 ViewerProvider（桩断言）；kind 缺省/"ifc" → 原路径回归（既有测试不破坏）。
  - client：renderJsonUrl 返回 `/v1/models/m_x/render.json`。
- [ ] **Step 2: 实现**
- [ ] **Step 3: `npm test && npm run lint && npm run build` 全绿 + W-0041 done + Commit** `feat(web): DXF Canvas 查看器 + ViewerPage kind 分流（W-0041 下半）`

---

### Task 4: 收口

- [ ] AGENTS.md（web 行测试计数/描述同步；逻辑二行：「web 查看器（DXF Canvas 只读）已交付」）；PLAN chunk D ✅；README（web/README 如有端点/功能清单补一句）
- [ ] `cd web && npm test && npm run lint && npm run build` 复跑
- [ ] Commit `docs: chunk D 收口`

---

## Self-Review 记录

- 覆盖：spec §二.2（Canvas 2D + pan/zoom + 图层 + hover/选中 key + 属性面板）→Task 2/3；只读边界与编辑门禁→Global Constraints；web-ifc IFC 查看器明确出 chunk（下一 chunk）。
- 类型一致：RenderPayload/RenderEntity 与 services/cad `render.py` 字段逐一对应（Task 2 注释标源）；selectedId 复用不新造 store 字段。
- 风险：jsdom 无真实 canvas——绘制断言基于 mock 调用序列（既有 xeokit mock 模式同款）；arc 角度跨 0° 命中是易错点已列专项；INSERT 展开实体 key=None 不参与选中（pick 过滤）。

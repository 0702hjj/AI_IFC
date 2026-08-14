# Chunk D：web DXF Canvas 查看器（只读）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** DXF 模型在 web 端可见：Canvas 2D 查看器消费 render.json（payload v2），pan/zoom、图层开关、hover/选中得 XDATA key + 属性面板；ViewerPage 按 model.kind 分流。只读——编辑属后续 chunk。

**Architecture:** 绘制/命中/变换全部为纯函数（`web/src/dxfviewer/`），React 壳只负责 canvas 挂载与事件转发；jsdom 下纯函数直接单测，组件层 mock `getContext("2d")`。与 xeokit viewer 并存：kind==="dxf" 走新组件，否则走原 ViewerProvider，互不影响。

**Tech Stack:** React 19 + zustand + vitest/jsdom（既有栈，不引新依赖）。

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
- Create: `web/src/dxfviewer/geometry.ts`（payload → 绘制基元归一化）
- Create: `web/src/dxfviewer/transform.ts`（世界→屏幕仿射：fit-bounds、pan 平移、zoom 缩放、Y 翻转）
- Create: `web/src/dxfviewer/pick.ts`（点→最近实体命中：line 点线距、circle/arc 径向距、text insert 点距阈值）
- Test: `web/src/dxfviewer/*.test.ts`（四个文件各配）

**Interfaces（Produces——Task 3 组件层消费）:**

```ts
// types.ts
export interface RenderPayload { schemaVersion: 2; bounds: Bounds | null; layers: LayerInfo[]; entities: RenderEntity[]; unsupported: Unsupported[] }
export interface RenderEntity { key: string | null; type: string; layer: string; color: number; linetype: string; block?: boolean; [geom: string]: unknown }
// transform.ts
export interface ViewTransform { scale: number; tx: number; ty: number }  // screen = world*scale + t（含 Y 翻转约定）
export function fitBounds(bounds: Bounds, canvasW: number, canvasH: number, padding?: number): ViewTransform
export function applyPan(t: ViewTransform, dxPx: number, dyPx: number): ViewTransform
export function applyZoom(t: ViewTransform, factor: number, centerPx: [number, number]): ViewTransform
export function worldToScreen(t: ViewTransform, x: number, y: number): [number, number]
export function screenToWorld(t: ViewTransform, px: number, py: number): [number, number]  // pick 用
// pick.ts
export function pickEntity(entities: RenderEntity[], worldPt: [number, number], tolWorld: number): RenderEntity | null
```

- [ ] **Step 1: 失败测试**——transform：fit 居中且比例正确、Y 翻转、pan/zoom 复合、round-trip（worldToScreen∘screenToWorld = 恒等）；pick：线段中点命中/端点外 miss、圆径向命中、弧仅弧段命中（角度区间判定，含跨 0° 段）、tol 随 zoom 换算（tolWorld = tolPx / scale）；geometry：七类归一化（bulge 段保留为 arc 基元）、空 entities → bounds null 路径。
- [ ] **Step 2: 实现**（不依赖 DOM/Canvas API，纯数学）
- [ ] **Step 3: `cd web && npm test` 绿 + Commit** `feat(web): dxfviewer 纯函数层——transform/pick/geometry（W-0041 上半）`

---

### Task 3: Canvas 组件 + 页面分流（TDD）

**Files:**
- Create: `web/src/dxfviewer/DxfViewer.tsx`（canvas 挂载 + 事件：wheel zoom、drag pan、mousemove hover、click select；图层开关侧栏；选中属性面板）
- Create: `web/src/dxfviewer/useDxfRender.ts`（fetch render.json → state；重绘 effect）
- Modify: `web/src/api/types.ts`（ModelInfo 加 `kind?: "ifc"|"dxf"`）、`web/src/api/client.ts`（`renderJsonUrl(id)` helper，照 modelAssetUrl 模式）
- Modify: `web/src/pages/ViewerPage.tsx` + css（kind==="dxf" → DxfViewer 分支；轮询/status 逻辑复用——dxf 直接 ready）
- Modify: `web/src/pages/LibraryPage.tsx`（模型表加 kind 列/徽标，一行级）
- Test: `web/src/dxfviewer/DxfViewer.test.tsx`、`web/src/pages/ViewerPage.test.tsx`（加 dxf 分支用例）

**Interfaces:**
- Consumes: Task 2 纯函数；`renderJsonUrl(id) -> string`；`ModelInfo.kind`
- Produces: `DxfViewer({ modelId: string })` 组件；选中状态写 `useViewerStore.selectedId`（复用既有 store 的 selectedId 语义——值为 XDATA key 字符串；高亮由组件内部完成，不走 xeokit 的 useVisibility）

- [ ] **Step 1: 失败测试**
  - DxfViewer：mock `renderJsonUrl` fetch + `canvas.getContext("2d")`（vi.fn 桩，断言调用序列含 arc/lineTo）；七类实体各触发对应绘制调用；wheel 事件 → transform 变化（spy applyZoom）；click → 选中实体 key 写入 store + 属性面板渲染 key/类型/图层；图层开关 toggle 后对应 layer 不绘制；unsupported>0 时角标显示数量；bounds null（空图纸）显示空态不崩。
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

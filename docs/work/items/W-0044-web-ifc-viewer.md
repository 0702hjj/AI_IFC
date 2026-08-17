# W-0044: web-ifc IFC 查看器（并存渐进，web-ifc+three 最小 loader + 引擎开关默认 xeokit）

- **状态：** done
- **优先级：** P1
- **Milestone：** v0.6（chunk E：Eino 替换 opencode + 主子编排 + web-ifc 查看器）
- **来源：** plan 2026-08-14-chunk-e-eino-webifc.md（Task 7；用户裁决 2026-08-14：本 chunk 与 Eino 合并为一个 PR）
- **执行者/分支：** opencode / feat/v0.9-eino-webifc
- **关闭 commit：** add70a3（依赖地基）+ 本 commit（组件实现，见下方验收记录）

## 背景

现有 IFC 查看器走 xeokit + converter 预转 XKT 链路。本项交付 web-ifc（0.0.77，wasm）+ three（0.185）手写最小 loader 的 IFC 直读查看器，与 xeokit **并存渐进**：用户级开关（localStorage）切换，默认 xeokit，webifc 分支不建 xeokit Viewer、不依赖 converter 转换产物。明确**不用** web-ifc-three（2024 停更，three 版本冲突）。

## 涉及位置

- `web/package.json`：+ three@0.185、web-ifc@0.0.77；wasm 文件拷 `web/public/wasm/`
- `web/src/ifcviewer/IfcLiteViewer.tsx`（新建）：three 场景 + web-ifc IfcAPI 加载 `/v1/models/{id}/download` IFC → BufferGeometry；轨道控制；模型树；属性面板；选中高亮
- `web/src/ifcviewer/ifcLoader.ts`（新建）：纯逻辑层（IfcAPI 装配/几何提取，可 mock wasm 单测）
- `web/src/pages/ViewerPage.tsx`：引擎开关（localStorage `viewerEngine=xeokit|webifc`，默认 xeokit；Toolbar 或设置入口切换）
- `web/Dockerfile` / `web/nginx.conf`：wasm MIME `application/wasm`（检查现状补）

## 方案

1. **加载/渲染**：IfcAPI.Init → OpenModel → 遍历 ExpressID → GetGeometry → BufferGeometry 合批（web-ifc 官方 three.js 示例模式）；wasm 路径 `WebIFC.IfcAPI.SetWasmPath("/AI_IFC/wasm/")`（base 对齐 vite base）。
2. **模型树**：IfcAPI 空间结构遍历，取 IFCPROJECT/IFCSITE/IFCBUILDING/IFCBUILDINGSTOREY 层级。
3. **属性/选中**：选中 → GetLine 属性行展示；选中高亮。
4. **引擎开关**：localStorage `viewerEngine`，默认 xeokit；webifc 分支渲染 IfcLiteViewer 且不建 xeokit Viewer；切换即时生效并持久化。
5. **wasm 部署**：vite public 直出 + nginx MIME `application/wasm`。

**显式范围外：** xeokit 链路改动与下线（并存，不替换）；IFC 编辑交互下钻；web-ifc-three 适配；converter 改动。

## 验收标准

- web-ifc+three 加载 IFC：几何渲染正确，轨道控制可用。
- 模型树（空间结构层级）与属性面板（选中实体属性行）可用；选中高亮。
- 引擎开关切换：localStorage 持久化，默认 xeokit；webifc 分支不建 xeokit Viewer；xeokit 路径不回归。
- wasm 部署：vite public 拷出 + nginx MIME `application/wasm`；wasm 路径拼接含 vite base。
- 测试 mock wasm：jsdom 下 web-ifc wasm 不可执行，全部经 mock IfcAPI 测试。
- `cd web && npm test && npm run lint && npm run build` 全绿（既有用例不回归）。

## 测试要求

- `ifcLoader.test.ts`：mock IfcAPI（OpenModel/GetGeometry/GetLineIDsWithType/GetName 等）→ 几何/树/属性提取断言；wasm 路径拼接含 base 用例。
- `IfcLiteViewer.test.tsx`（mock three/web-ifc）：引擎开关持久化 + 分流渲染（webifc 分支不建 xeokit Viewer）。
- 既有 ViewerPage/xeokit 用例不回归。
- 新增测试量 ≥ 新增实现量（仓内 ≥1:1 硬规则）。
- 节奏：本项与 W-0043 同属 chunk E，整 chunk 单 PR 收口（分支 feat/v0.9-eino-webifc 累积，当天收工一次 PR）。

## 验收记录（2026-08-17）

- 分层落地：`ifcLoader.ts`（纯提取，IfcApiLike 窄接口注入可 mock）→ `ifcScene.ts`（裸 three 挂载层 + IfcSceneHandle，移植 gaia R3F 友好）→ `IfcLiteViewer.tsx`（React 桥接 + 文案集中常量）。
- 几何提取走 `StreamAllMeshes`（官方示例模式）；wasm 路径经 `import.meta.env.BASE_URL` 拼接（勘误：原方案写死 `/AI_IFC/`，与 vite base `/` 及 nginx `/wasm/` 实况不符，改为自适应）。
- IfcLiteViewer 经 `React.lazy` 动态分包：three+web-ifc 独立 chunk（3.9M），默认 xeokit 主路径不加载。
- 测试：web 288 通过（基线 264 + 新增 24——loader 13 + 组件 6 + 引擎开关 5）；lint 0 error（2 存量警告非本项）；build 绿。
- store.selectedId 语义对齐 xeokit/Dxf 查看器（expressID 字符串），选中联动与属性面板共用同一管路。

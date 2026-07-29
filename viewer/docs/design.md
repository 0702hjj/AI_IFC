# IFC Viewer 设计文档

> 日期：2026-07-27
> 状态：已确认（方案 A'：Go + Node 转换子进程）
> 接口契约落地见 [api.md](./api.md)

## 1. 目标与定位

在 AI_IFC 仓库下构建一个**独立全栈小应用**：服务器到浏览器的 IFC 文件查看方案。

- 技术路线：xeokit + React（前端），Go（stdlib net/http，后端），Node `@xeokit/xeokit-convert`（IFC→XKT 转换）
- 支持用户上传 IFC、在线查看、本地下载原始 IFC
- 单机无认证，本地文件系统存储，无数据库
- 参考 Online3DViewer 的交互形态（模型库 + 查看器两页）

非目标（YAGNI）：用户体系、与 gaia 平台集成、IFC 编辑/生成、方案 B（Three.js/web-ifc）viewer。

## 2. 总体架构与数据流

```
┌─────────────────────────────────────────────────────────┐
│ 浏览器  React+Vite+TS (viewer/web)                        │
│  ├─ 模型库页：上传/列表/删除/下载 IFC                       │
│  └─ 查看器页：xeokit Viewer + 插件                         │
└──────────────┬──────────────────────────────────────────┘
               │ HTTP /api/*
┌──────────────▼──────────────────────────────────────────┐
│ Go 后端 (stdlib net/http, 无DB, 单二进制)   (viewer/server)    │
│  ├─ 上传 → 存 data/uploads/{id}.ifc                       │
│  ├─ 转换队列(内存) → exec convert2xkt → data/models/{id}/ │
│  │    ├─ model.xkt                                      │
│  │    └─ metadata.json (树+属性，由转换器一并导出)          │
│  ├─ 状态跟踪：converting / ready / failed（状态文件）       │
│  └─ 静态服务 /models/{id}/*                               │
└─────────────────────────────────────────────────────────┘
```

前端只认 XKT + metadata.json，永不直接解析 IFC。

## 3. 模块划分

| # | 模块 | 职责 | 位置 |
|---|------|------|------|
| 1 | backend (Go stdlib net/http) | 上传 IFC、触发转换、模型列表/删除、XKT+元数据静态服务、IFC 原文件下载 | `viewer/server/` |
| 2 | converter (Node CLI) | 封装 `@xeokit/xeokit-convert`，输入 IFC 输出 XKT + metadata.json | `viewer/converter/` |
| 3 | frontend (React+Vite+TS) | 模型列表页、查看器页（xeokit Viewer + 树/属性/剖切/测量插件） | `viewer/web/` |
| 4 | 共享契约 | API 接口定义 + 元数据 JSON schema | `viewer/docs/api.md` |

### 目录结构

```
AI_IFC/viewer/
├── server/                  # Go 后端
│   ├── cmd/server/main.go
│   ├── internal/
│   │   ├── api/             # handlers, routes, dto
│   │   ├── convert/         # 转换队列 + 子进程管理
│   │   └── store/           # 文件系统存储 + 状态(model.json)
│   ├── go.mod
│   └── server_config.json   # host/端口、数据目录、converter 脚本路径
├── converter/               # Node 转换器
│   ├── package.json         # @xeokit/xeokit-convert
│   ├── convert.js           # IFC → XKT + metadata.json
│   ├── lib/metadata.js      # web-ifc 提取空间结构树 + 属性集
│   └── test/                # 转换器测试（fixtures 样例 IFC）
├── web/                     # React 前端
│   ├── src/
│   │   ├── pages/LibraryPage.tsx
│   │   ├── pages/ViewerPage.tsx
│   │   ├── viewer/          # xeokit 封装（见 §5）
│   │   ├── api/client.ts
│   │   └── components/ui/
│   └── vite.config.ts       # dev proxy → :8090
└── docs/
    ├── design.md            # 本文档
    └── api.md               # 接口契约
```

## 4. 后端设计

### 4.1 转换流程

上传落盘 → 写 `model.json{status:"converting"}` → 入内存队列（worker 数=2，串行 exec 防内存爆）→ `node converter/convert.js in.ifc outDir/` → 成功写 `{status:"ready"}`，失败写 `{status:"failed", error}`。

- 前端每 2s 轮询 `GET /api/models` 直到 ready/failed
- 服务重启后扫描数据目录恢复状态：残留 `converting` 一律标记为 `failed`（可重试）
- 重试：对 failed 模型提供重新入队接口（见 api.md）

### 4.2 存储布局

```
data/
├── uploads/{id}.ifc         # 原始 IFC
└── models/{id}/
    ├── model.json           # 状态与元信息 {id,name,size,status,createdAt,error?}
    ├── model.xkt            # 转换产物
    ├── metadata.json        # 树 + 属性
    ├── issues.json          # Issue/Markup 持久化（审查标记）
    └── issues/              # Issue 截图 {issueId}.png
```

Issue/Markup 持久化采用文件存储（`models/{id}/issues.json` + `issues/*.png`），由 `internal/issue.Store` 接口抽象，后期可平移 PostgreSQL（新增 PgStore 实现，API/前端零改动）。

### 4.3 约束

- 上传仅接受 `.ifc`，大小上限 200MB
- 错误统一 JSON 信封 `{code, message, data}`

## 5. 前端设计

```
ViewerPage
├─ <XeokitCanvas/>        viewer/ViewerContext.tsx — 初始化 Viewer + XKTLoaderPlugin，
│                          加载 model.xkt + metaModelSrc=metadata.json（xeokit 标准元模型格式），
│                          向子组件暴露 viewer/sceneModel/metaModel
├─ <Toolbar/>             复位视角 / 剖切开关 / 测量开关 / 下载 IFC
├─ <ModelTreePanel/>      左栏：TreeViewPlugin(containment) 容器 + 显隐/隔离/高亮联动
├─ <PropertyPanel/>       右栏：pick 构件 → viewer.metaScene.metaObjects[id].propertySets 展示
└─ <SectionControl/>      SectionPlanesPlugin：轴向选择 + 滑杆拖剖切面
```

- 树/属性/拾取全部基于 `viewer.metaScene`（MetaModel），metadata.json 采用 xeokit 标准元模型格式（见 api.md §4），由 converter 用 web-ifc 从原 IFC 提取（convert2xkt 直接转 IFC 不产出元数据）
- 测量：DistanceMeasurementsPlugin + DistanceMeasurementsMouseControl（开关式，双击结束）；测量标签不做持久化，随会话保留
- 状态管理：轻量 Zustand store（当前选中 objectId、工具模式）；xeokit 实例放 ref/context，不进响应式状态
- 代码规范沿用 gaia_web 惯例：`@` 别名、文件 ≤500 行

### 5.1 错误处理

- 转换失败 → 列表显示错误信息 + 重试按钮
- XKT 加载失败 → 查看器页提示并可返回列表
- 上传非 .ifc 或 >200MB → 前端直接拒绝

## 6. 测试策略

- server：Go httptest 覆盖上传/列表/下载/删除；convert 队列用 fake converter 脚本测试状态机
- converter：用 `research/ifc` 样例 IFC 做快照测试（XKT 非空、metadata 含 storey 树）
- web：组件级测试从简；e2e 冒烟 MVP 后补

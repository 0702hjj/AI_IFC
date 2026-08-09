# Web 前端

`viewer/web/`：React 19 + TypeScript + Vite + zustand + xeokit-sdk，开发端口 `:5173`。

## 命令

```bash
cd viewer/web
npm install
npm run dev        # 开发服务器，/api 与 /models 代理到 :8090
npm test           # vitest 单测
npm run build      # tsc -b + vite build（类型检查）
npm run lint       # oxlint
```

## 目录与组件树

```
src/
├── App.tsx                 路由：/ → LibraryPage，/view/:id → ViewerPage
├── api/client.ts           request<T> 解包 {code,message,data}；全部 API 函数
├── pages/LibraryPage.tsx   上传（拖拽 .ifc ≤200MB）、状态轮询、重试/删除/下载
├── pages/ViewerPage.tsx    ViewerProvider + Toolbar + 各面板；模型状态轮询
└── viewer/
    ├── ViewerContext.tsx   xeokit Viewer + XKTLoaderPlugin（xkt + metadata 双加载）
    ├── ModelTreePanel.tsx  空间树（搜索/类型过滤/显隐，默认展开 1 层）
    ├── PropertyPanel.tsx   pset 只读展示（历史 override 带标记）+「定位脚本」按钮
    ├── DesignPanel.tsx     PARAMS 表单（ast 提取）+ 脚本编辑器 + 版本/暂存 diff 视图
    ├── IssuePanel.tsx      Issues / 修改历史双 tab；新建 Issue（相机 + 截图）
    ├── IssuePins.tsx       3D HTML 钉 overlay（每帧投影同步，点击定位）
    ├── DiffPanel.tsx       版本选择 → diff 着色 + old→new 列表 + 点击定位
    ├── Toolbar.tsx         复位视角/剖切/测量/Diff/可见性/下载
    ├── VisibilityToolbar.tsx / SectionControl.tsx / useMeasurements.ts
    ├── usePicking.ts       拾取 + 选中高亮
    ├── overrides.ts        applyOverrides 渲染合并（历史 override 只读标记）
    ├── scriptEdit.ts       脚本 PARAMS 读写辅助
    └── store.ts            zustand：selectedId/tool/hiddenIds/overrides/scriptJump/...
```

## 关键机制

- **选中链路**：`setSelected(id)` → usePicking 高亮 → PropertyPanel 显示该 GlobalId 的 pset（只读）。
- **定位脚本**：PropertyPanel「定位脚本」→ `GET /api/v1/models/{id}/script/locate?guid=` → hit 时写 `store.scriptJump`，DesignPanel 切脚本编辑器态并把光标落到调用行（选中行高亮）；`origin=traced` 提示手改；miss/不可用降级只读提示。
- **override 显示**：渲染时 `applyOverrides` 把历史 override 值覆盖在原值上并带只读标记；属性面板不再提供行内编辑（直改链路退役）。
- **Diff 着色**：diff 返回的 guid 即 scene object id；`entity.colorize` 设置颜色，清除时置 null；removed 构件在当前 XKT 无几何，仅列表呈现。
- **自动刷新**：ViewerPage 持续轮询模型状态，`converting → ready` 转换时 remount ViewerProvider 重载 XKT（script run/save/rollback 触发的重转也能捕获）。

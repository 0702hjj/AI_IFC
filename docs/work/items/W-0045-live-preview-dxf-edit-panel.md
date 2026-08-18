# W-0045: v0.10 中途预览（live preview）+ DXF/webifc 编辑面补齐

- **状态：** done
- **优先级：** P1
- **Milestone：** v0.10（中途预览 + DXF 编辑面）
- **来源：** 用户裁决 2026-08-18：viewer.staged 中途预览 + DXF 编辑面补齐合并为单 PR（分支 feat/v0.10-live-preview-dxf-edit）；同分支前置清理：aidxfv v1/v2 遗留删除（flows 契约层已迁入 services/cad，v3 为唯一基线）
- **执行者/分支：** kimi-code / feat/v0.10-live-preview-dxf-edit
- **关闭 commit：** 0969532（skills 清理）+ 2db0f0f（server viewer.staged + diff 摘要）+ cac0482（web 分流刷新）+ 69385cf（DesignPanel 复用 + dxf 定位脚本）+ c665a2d（文档收口）（PR 待提）

## 背景

chat agent 的 `run_script` 试跑产物此前不可见：save 之前的中间结果要等人手动刷。同时 DXF 查看器（W-0041）与 web-ifc 查看器（W-0044）都只有只读画布，右侧没有 DesignPanel 编辑面，AI/人对 dxf、webifc 管线的脚本编辑（PARAMS/暂存/试跑/保存/diff）无 UI 入口。本项一次补齐两块。

## 涉及位置

- `server/internal/agent/`：run_script 成功后推 SSE `event: viewer.staged`（`data: {"modelId","kind":"ifc"|"dxf"}` 严格 2 字段，走 pushSystem 管线，含递增 id、入重同步缓冲）；工具结果末尾追加 `[staging diff] added=N removed=M` + `PARAMS +/-/~ key ...` 摘要（复用既有 `GET /script/staging/diff` 轻量调用，不可用时空串降级）；run 失败不推事件
- `web/src/store`：新增 `stagedPreview {modelId, kind, nonce}` + `flagStagedPreview`；ChatSidebar 监听 viewer.staged（非法帧静默跳过）
- `web/src/pages/ViewerPage.tsx`：消费 stagedPreview——kind=dxf → 自动 reloadKey+1（render.json 直挂）；ifc+webifc → 自动重挂 IfcLiteViewer；ifc+xeokit → 画布左上角角标「AI 中间结果 · 点击预览」，点击才 reload（重转 XKT 慢且闪烁）
- `web/src/pages/ViewerPage.tsx` + `DesignPanel`：dxf / webifc 分支右侧挂 DesignPanel（PARAMS 表单/脚本编辑/staging/试跑/保存/大版本 diff 全套；DesignPanel 纯 store+REST 无 viewer context 依赖）
- `web/src/dxfviewer/DxfViewer.tsx` + `web/src/api/client.ts`：选中面板加「定位脚本」按钮（XDATA key → `GET script/locate?key=` → requestScriptJump → DesignPanel 跳行聚焦；无 key 选中不渲染按钮，miss/stale/失败降级提示）；client 新增 `locateScriptByKey`

## 方案

1. **server**：run_script 工具成功后（1）轻量调 staging diff 拼摘要行追加到工具结果文本（供 AI 自纠）；（2）pushSystem 推 viewer.staged 事件，与既有 notify 事件同管线（SSE id 递增 + resync buffer）。
2. **web 分流刷新**：ChatSidebar SSE 收 viewer.staged → `flagStagedPreview`（nonce 保证连续事件都触发）；ViewerPage 按 kind/引擎分流：dxf/webifc 重载廉价自动刷，xeokit 重转贵且闪烁改手动角标。
3. **编辑面复用**：DesignPanel 本就纯 store+REST（无 viewer context 依赖），dxf/webifc 分支直接同挂；dxf 选中实体的 XDATA key 走 `script/locate?key=`（既有端点既有代理），命中复用既有 requestScriptJump 跳行链路。

## 验收标准

- run_script 成功推 viewer.staged（严格 2 字段、走 pushSystem 含 id/resync）；run 失败不推；工具结果带 staging diff 摘要，diff 不可用时空串降级不报错。
- dxf 管线：viewer.staged 后画布自动刷新；ifc+webifc：自动重挂；ifc+xeokit：出现角标、点击才 reload、reload 后角标消失；非法帧静默跳过。
- dxf / webifc 分支右侧 DesignPanel 全套可用（PARAMS/脚本/staging/试跑/保存/diff），xeokit 分支不回归。
- dxf 选中带 key 实体 → 定位脚本按钮 → 命中跳行聚焦；无 key 不渲染按钮；miss/stale/失败有降级提示。
- `cd web && npm test && npm run lint && npm run build`、`cd server && go test ./... && go vet ./...` 全绿（既有用例不回归）。

## 测试要求

- server：run_script 成功/失败两条路径的 SSE 帧断言（事件名、data 字段、id 递增、resync buffer）+ diff 摘要文本断言（含降级空串）。
- web：ViewerPage staged preview 分流（dxf 自动 / webifc 自动 / xeokit 角标手动）；DesignPanel 在 dxf/webifc 分支挂载；DxfViewer 定位脚本链路（命中/miss/stale/失败/无 key）。
- 新增测试量 ≥ 新增实现量（仓内 ≥1:1 硬规则）。

## 验收记录（2026-08-18）

- 测试计数落地：web 289→312（用例）/26→27（文件）；server 238→245；services/cad 209→210；tests/skill 143（v1/v2 删除后口径）。
- API 契约零变化：viewer.staged 为 SSE 事件非 REST；`locate?key=` 为既有端点既有代理；`gen:api + check:api` 无本 PR 漂移。
- 全量回归（web/server/services/cad/services/ifc）由收口任务后台并行执行，结果见当日收口汇报。

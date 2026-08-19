# W-0046: 编辑面对齐收尾——params_keys 断链修复 + webifc 定位脚本 + DesignPanel 回滚 + run 构件级摘要

- **状态：** done
- **优先级：** P1
- **Milestone：** v0.10.1（编辑面对齐收尾）
- **来源：** W-0045 交付后的对齐收尾 + v0.10 遗留观察兑现（用户裁决 2026-08-18：dxf 分支 IssuePanel/DiffPanel 对称不重点考虑，排除在外）
- **执行者/分支：** kimi-code / feat/edit-parity-followups
- **关闭 commit：** e6f5dd3（web params_keys 断链修复）+ 4c93fd7（webifc 定位脚本）+ 99c0242（DesignPanel 回滚按钮）+ 8bdb47a（services run 附 semanticDiff）+ e4b4952（server run_script 摘要升级）+ 119fb83（aiplan SKILL.md 补 version）+ 本 commit（文档收口，hash 随 PR 回填）（待提 PR）

## 背景

W-0045 把 dxf/webifc 编辑面与中途预览交付后，留下若干对齐缺口与断链：locate 响应的 `params_keys` 在 web 侧误读 camelCase 导致 PARAMS 聚焦高亮断链（W-0022 功能回归）；webifc 查看器选中面板没有 dxf 侧已有的「定位脚本」入口；DesignPanel 版本列表只能看 diff 不能回滚；`run_script` 试跑结果只有行级 staging diff 摘要，AI 自纠要看构件增减；aiplan SKILL.md 缺 `version` 字段导致 `--skill-dir skills/aiplan --archive` 打包报错。本项一次收口。

## 涉及位置

- `web/src/api/client.ts` + store：locate 响应在 API 边界做 snake→camel 映射（服务端 snake_case、Go 透传），store 内部字段不变。
- `web/src/ifcviewer/`（IfcLiteViewer 选中面板）：属性行取 GlobalId → `locateScript(guid)` → scriptJump；miss/stale/失败降级提示；无 GlobalId 不渲染按钮。
- `web/src/components/DesignPanel`：版本列表非当前版本行加「回滚到版本」按钮（window.confirm 确认 → rollbackScript → 刷新 + pendingModelReload）。
- `services/ifc/app/routes_scripts.py` + `services/cad/app/routes_scripts.py`：run 前快照旧 uploads 产物，run 后 compute_diff，响应 data 新增可选字段 `semanticDiff: {added, removed, changed} | null`（diff 失败/首次 run 降级 null，绝不让 run 失败；camelCase 对齐同文件 modelId/canUndo 先例）。
- `server/internal/agent/tools.go`：run_script 工具结果摘要优先构件级 `[staging diff] 构件 +2 -1 ~3`，semanticDiff 为 null 回退行级 staging diff 摘要，再不行无摘要；viewer.staged 不动。
- `skills/aiplan/SKILL.md`：frontmatter 补 `version: 0.1.0`。

## 方案

1. **断链修复**：web 端在 locate 响应进入 store 前做一次 snake→camel 边界映射，不动服务端契约与 store 内部结构。
2. **webifc 定位脚本**：复用 dxf 侧既有 locateScript + requestScriptJump 跳行链路，选中面板按 GlobalId 触发，全降级路径有提示。
3. **回滚按钮**：复用既有 rollbackScript store action + pendingModelReload 刷新链路，仅 UI 入口 + 确认。
4. **构件级摘要**：services 在 run 端点内做快照+diff（容错纪律照抄 `_bootstrap_alignment`），server 工具层消费 semanticDiff 拼摘要，null 时回退行级。

## 验收标准

- locate 命中 PARAMS 后 DesignPanel 表单正确聚焦高亮（snake_case 响应不再断链）。
- webifc 选中带 GlobalId 构件 → 「定位脚本」→ 命中跳行聚焦；无 GlobalId 不渲染按钮；miss/stale/失败有降级提示。
- DesignPanel 版本列表非当前版本出现回滚按钮，确认后回滚并刷新画布。
- ifc/cad `script/run` 响应带 `semanticDiff`（首次 run/diff 失败为 null 且 run 本身不失败）；run_script 工具结果优先构件级计数摘要，null 回退行级。
- `python tools/skill_pack.py --skill-dir skills/aiplan --archive` 打包成功。

## 测试要求

- web：locate 边界映射、webifc 定位脚本链路（命中/miss/stale/失败/无 GlobalId）、DesignPanel 回滚按钮。
- services：run semanticDiff 正常/降级两路（ifc + cad 同构）。
- server：run_script 摘要三级（构件级/行级兜底/无摘要）。
- 新增测试量 ≥ 新增实现量（仓内 ≥1:1 硬规则）。

## 验收记录（2026-08-19）

- 测试计数落地：web 312→322（用例，27 文件不变）；server 245→248；services/ifc 243→246；services/cad 210→213；tests/skill 141→142（+2skip 不变）。
- API 契约变化：`script/run` 响应 data 新增可选 `semanticDiff` 字段——`export_openapi.py` + `gen:api` 重跑，go-openapi-schema `ScriptRunResult` 补字段，`check:api` 生成物随收口 commit 提交。
- 全量回归（web/server/services/cad/services/ifc）由收口任务后台并行执行，结果见当日收口汇报。

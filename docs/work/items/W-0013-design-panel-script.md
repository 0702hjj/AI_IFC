# W-0013: 前端 DesignPanel 重构（PARAMS 表单 + 脚本编辑器）

- **状态：** done
- **关闭于：** 1e8bf15（PR 见 M5 合并）
- **优先级：** P1
- **Milestone：** M5 script-as-source
- **来源：** spec 2026-08-06-script-as-source-design.md
- **执行者/分支：** opencode / feat/script-as-source

## 背景

design JSON 表单下线。设计师编辑面 = 从脚本 PARAMS 块生成的表单；技术用户可下钻脚本编辑器。staging/undo/redo/save 交互语义不变（WPS 式），内容换脚本。

## 涉及位置

- `viewer/web/src/viewer/DesignPanel.tsx`（重构）、`designEdit.ts`（改脚本语义）、`client.ts`（design 方法 → script 端点）
- `DiffPanel`：加脚本 diff tab（数据来自 W-0012）

## 方案

1. client.ts：design 系列方法换 script 端点（fetchScript/stageScript/scriptUndo/.../fetchScriptParams）
2. DesignPanel：`GET script/params` → 按值类型渲染表单（number/string/bool/枚举）；提交 → PUT script（整个脚本：PARAMS 替换后重拼接，服务端做 PARAMS 替换更安全——与 W-0011 约定）
3. 下钻：脚本编辑器（textarea + 等宽字体 + 行号即可，不引第三方编辑器——YAGNI）
4. staging UI（<- -> 撤销重做、保存版本、放弃）语义不变，接 script staging
5. DiffPanel 加「脚本 diff」tab（纯文本 pre 渲染 + params 变化摘要）

## 验收标准

- 表单改参数 → 暂存 → undo/redo → 保存大版本 → 3D 刷新 全流程可用
- 脚本编辑与表单编辑不互相覆盖（同一 staging 源）
- 老模型（无脚本）：面板显示「该模型无构建脚本」降级态

## 测试要求

- DesignPanel 测试重构（现 mock client 的方式保留）：PARAMS 渲染各类型、提交拼接、staging 状态机
- client.ts 契约测试（envelope）
- vitest 全绿 + lint 无新增 warning + build 过

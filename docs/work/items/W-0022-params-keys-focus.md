# W-0022: ScriptMap 补 params_keys + PARAMS 表单聚焦（spec §5.3 路径 A 闭环）

- **状态：** done（2026-08-10，分支 feat/v0.2-script-closure，commit fa2df7b/68b2139/f8ea0ae）
- **优先级：** P2
- **Milestone：** v0.2（script-as-source 统一编辑，spec: docs/superpowers/specs/2026-08-08-script-editing-unified-design.md）
- **来源：** feat/script-editing-unified Task 9 任务评审（2026-08-08）

## 背景

spec §5.3 路径 A 要求：origin=params 的构件，web 端定位后聚焦到 PARAMS 表单的具体键改值。当前 ScriptMap 的 CallSite 不落 `params_keys`（script_lib 调用点捕获只记 line/col/snippet/origin），前端降级为统一跳脚本编辑器对应行（feat/script-editing-unified Task 9 已落地的行为）。信息等价但体验降档，且 spec 最终态不能静默缩水。

## 方案

1. 后端：`script_lib._record_callsite` 在 origin=params 时解析 key/参数的 params 引用链，落 `params_keys: list[str]` 入 CallSite（ast 解析调用行，收集 `params[...]` / `PARAMS[...]` 下标键）。
2. locate 端点透传 params_keys。
3. 前端：origin=params 且 params_keys 非空 → DesignPanel PARAMS 表单聚焦首个键（现有表单已按 PARAMS 渲染）；否则维持跳脚本行。

## 验收标准

- origin=params 构件「定位脚本」→ PARAMS 表单对应键高亮聚焦。
- 多键引用（一个构件用多个 params）全部列出。

## 测试要求

- script_lib 单测：params 引用提取（单键/多键/嵌套下标）。
- locate 端点契约测试：params_keys 字段透传。
- 前端 vitest：聚焦逻辑（mock store）。

# P2-3: DESIGN_JSON_SCHEMA 示例违反自身契约

- **状态：** open
- **优先级：** P2
- **Milestone：** M1（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** （领取时填）

## 背景

DESIGN_JSON_SCHEMA.md 中的示例同时给出 `at` 和 `shaft` 两种楼梯定位方式（契约要求二选一），且 shaft 用的是 schema 未定义的 `{w,l}` 键。design_builder 遇到这种输入会静默走 `at` 分支并丢弃 shaft，不报错。该文档是 LLM 生成 design JSON 的参照，示例错误会直接教会 LLM 产出错误格式。

## 涉及位置

- `skills/aiifc/references/DESIGN_JSON_SCHEMA.md:148` — 示例同时给 `at` 和 `shaft`，shaft 用未定义的 `{w,l}` 键
- `skills/aiifc/references/docs/flows/design_builder.py:113-127` — 静默走 at 分支丢弃 shaft

## 方案

把 DESIGN_JSON_SCHEMA.md:148 的示例改为合法形式：`at`+`size` 或 `shaft` 二选一；若保留 shaft 示例，则使用 schema 实际定义的键。示例与 design_builder.py 的实际行为对齐。

## 验收标准

修正后的示例 JSON 通过 `design_builder.normalize` 不抛 SchemaError，且不丢任何字段。

## 测试要求

tests/skill 新增测试：从 schema 文档中提取示例 JSON 跑 normalize，断言合法且字段无丢失，防止文档与实现再次漂移。

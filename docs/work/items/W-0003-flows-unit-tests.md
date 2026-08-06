# W-0003: flows 单测补全 + converter CI 确认

- **状态：** in-progress
- **优先级：** P1
- **Milestone：** M2（见 PLAN-v0.1.0.md）
- **来源：** PLAN-v0.1.0（M2 测试补盲）
- **执行者/分支：** opencode / test/m2-coverage

## 背景

aiifc flows 的核心脚本此前只有 CI 冒烟（一条 happy path）：`design_builder.py` 的 SchemaError 分支（斜线路径、footprint 不闭合等）无单测；`dxf_from_design.py` 部分已随 P0-2/P2-10 补齐（tests/skill/test_flows_dxf.py，含 shaft fixture）。converter 有 1 个集成测试，需确认其在 CI 运行。

## 涉及位置

- `skills/aiifc/references/docs/flows/design_builder.py`（SchemaError 分支 :81-83 等）
- `tests/skill/`（新测试落点，CI skill-pack job 自动纳入）
- `.github/workflows/ci.yml`（converter job 确认）

## 方案

1. 新增 `tests/skill/test_flows_design_builder.py`：每个 SchemaError 分支一条用例（斜线路径抛错、footprint 不闭合、非法结构），断言错误类型与信息；另加 normalize happy path 的确定性 key 分配断言
2. 确认 ci.yml converter job 存在且跑 `npm test`（存在则仅记录，无需改动）

## 验收标准

- design_builder 所有 SchemaError 分支各有 ≥1 条失败用例（先看红再确认其本就该红——此处测的是既有行为，测试应直接通过；若发现某分支不抛错则是 bug，单独上报）
- `pytest tests/skill/` 全绿；CI skill-pack job 通过

## 测试要求

- 每用例构造最小非法 design JSON，断言 SchemaError 及消息关键词
- 不 mock 内部函数，直接调 normalize

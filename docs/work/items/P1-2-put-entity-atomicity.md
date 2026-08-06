# P1-2: put_entity pset 修改无回滚

- **状态：** in-progress
- **优先级：** P1
- **Milestone：** M4（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** opencode / feat/m4-hardening

## 背景

routes_edits.py 的 put_entity 中，fields 修改包在 try/except 内、异常可回滚；但 pset 修改在 try 块之外——edit_pset 抛异常时，内存中的模型已被部分修改且没有 pending 记录，与模块 docstring 宣称的原子性保证直接矛盾。

## 涉及位置

- `viewer/edit-service/app/routes_edits.py:113-145` — put_entity 处理逻辑
- 其中 132-145 行的 pset 修改在 try/except 之外，无回滚保护

## 方案

把 pset 修改移入与 fields 修改相同的 try 块；扩展现有回滚逻辑以覆盖 pset：修改前先快照原 pset 值，任一步骤异常时把 fields 与 pset 一并还原到修改前状态，并保证不产生 pending 残留。

## 验收标准

构造 edit_pset 抛错的请求后，模型的内存态（fields 与 pset）与 pending 列表均无残留，与请求发出前完全一致。

## 测试要求

pytest 新增用例：mock edit_pset 抛异常，断言实体 fields 与 pset 均恢复原值、pending 列表为空。

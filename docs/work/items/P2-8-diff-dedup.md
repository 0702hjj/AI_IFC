# P2-8: design_diff 与 ifc_fingerprint 重复实现

- **状态：** done
- **关闭于：** 8238085
- **优先级：** P2
- **Milestone：** M4（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** opencode / feat/m4-hardening

## 背景

design_diff.py 与 ifc_fingerprint.py 中 added/removed/changed 三段对比循环几乎逐行相同，是两处独立维护的重复实现；versions.py 与 design_versions.py 的快照存储逻辑亦同构。重复代码意味着修一处忘另一处的风险。

## 涉及位置

- `skills/aiifc/references/docs/flows/design_diff.py:97-114` — added/removed/changed 三段循环
- `skills/aiifc/references/docs/flows/ifc_fingerprint.py:55-75` — 与上几乎逐行相同
- `versions.py` 与 `design_versions.py` — 同构的快照存储逻辑

## 方案

抽公共函数 `summarize_changes(base_items, target_items, key_fn)`；design_diff 与 ifc_fingerprint 各自提供 key_fn/指纹提取逻辑后复用该函数。versions.py 与 design_versions.py 的同构部分可选抽 `snapshot_store`（视收益决定，不强制）。

## 验收标准

去重后行为不变：两个模块的 diff 输出与重构前完全一致。

## 测试要求

1. 现有 test_design_diff 全部保持绿色。
2. 为公共函数 `summarize_changes` 补参数化单元测试。

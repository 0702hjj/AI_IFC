# P2-2: test/ 与 tests/ 双轨混乱

- **状态：** done
- **优先级：** P2
- **Milestone：** 本轮/M4（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** docs/work-board-and-cleanup
- **关闭于：** 本分支（2026-08-05 清理）

## 背景

仓库同时存在 `test/` 与 `tests/` 两套测试目录：`test/` 里是 31 个旧 SCAD 测试，CI 不跑，且 `test/test_all_features.py:16` 的 sys.path 指向不存在的 `test/src`（本身即坏）；`tests/` 是现行测试目录。双轨并存造成认知混乱，新人/新 agent 容易跑错目录。

## 涉及位置

- `test/` — 31 个旧 SCAD 测试，CI 不跑
- `test/test_all_features.py:16` — sys.path 指向不存在的 `test/src`
- `tests/` — 现行测试目录
- CI 钩子中挂在 archived 打包器上的部分 — 随 `tests/skill/test_skill_pack.py` 删除一并关闭

## 方案

删除 `test/` 整个目录与 `tests/` 内的 SCAD 测试；CI 钩子中依赖 archived 打包器的部分随 `tests/skill/test_skill_pack.py` 的删除一并关闭。

## 验收标准

`test/` 目录不复存在，`tests/` 内无 SCAD 测试残留；CI 绿。

## 测试要求

删除类变更无新增测试；以 CI 全绿作为回归保障。

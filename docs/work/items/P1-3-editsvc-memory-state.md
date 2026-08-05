# P1-3: edit-service 全内存状态

- **状态：** open
- **优先级：** P1
- **Milestone：** M4（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** （领取时填）

## 背景

edit-service 的关键状态全部驻留内存：pending 编辑队列、design staging 区、ModelRegistry（无淘汰机制）。后果有二：服务重启即丢失全部未提交的编辑与 staging 数据；加载的模型只增不减，内存随模型数量持续增长。

## 涉及位置

- `viewer/edit-service/main.py:23` — pending 编辑队列（内存态）
- `viewer/edit-service/main.py:24` — design staging（内存态）
- `viewer/edit-service/app/registry.py` — ModelRegistry，无淘汰机制

## 方案

1. **staging/pending 可选落盘**：design staging 与 pending 写入 dataDir 下 `staging/{modelId}.json`（原子写），服务重启后自动恢复，可继续 undo/redo。
2. **ModelRegistry 加 LRU 淘汰**：上限可配置（默认 8 个模型），淘汰时先把该模型的脏状态 flush（原子写）再卸载；再次访问时可从磁盘重新加载。

## 验收标准

1. 重启服务后 staging 数据可恢复，可继续 undo/redo。
2. 连续加载 20 个模型，内存占用保持稳定（LRU 生效）。

## 测试要求

1. 落盘/恢复 round-trip 测试：写入 → 模拟重启 → 恢复后状态一致。
2. LRU 淘汰顺序测试，以及被淘汰模型可重新加载的测试。

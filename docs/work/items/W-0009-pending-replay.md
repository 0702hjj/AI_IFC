# W-0009: 重启/LRU 淘汰后 pending 回放（edit-service）

- **状态：** open
- **优先级：** P2
- **Milestone：** 待排（v0.2）
- **来源：** P1-3 审查发现（2026-08-06）
- **执行者/分支：** （领取时填）

## 背景

P1-3 实现了 pending/staging 落盘恢复，但存在语义缺口：重启（或 LRU 淘汰）后 pending.json 条目恢复，而其对应的 **IFC 内存修改已丢失**（pending 修改只作用于内存模型，commit 时才写盘）。此时 commit 会把未实际生效的条目写进 history 并快照「未改」的 IFC——history 与版本文件静默背离，且用户在 pending 列表看到条目会误以为修改仍在。LRU 淘汰带未提交 pending 的模型同源。

## 涉及位置

- `viewer/edit-service/app/registry.py`（LRU 淘汰）
- `viewer/edit-service/app/routes_edits.py`（pending 恢复与 commit）

## 方案（二选一或组合）

1. **回放**：恢复 pending 条目时按条目重新应用编辑到内存模型（需要 pending 条目携带完整编辑指令——核实现有序列化内容是否足够回放）
2. **降级提示**：恢复时标记 pending 为 `stale`，commit 前要求确认/重放；UI 层展示「重启后需确认」

## 验收标准

- 重启 → pending 恢复 → commit：history 条目与实际 IFC 内容一致（不回放则拒绝 commit 并提示）
- LRU 淘汰带 pending 的模型后再访问：同上语义

## 测试要求

- TDD：重启后 commit 的一致性用例（history 与 IFC 快照比对）
- 淘汰-重载-回放链用例

## 附带小修（同源可一并）

- `PendingStore.get` 纯 GET 创建内存条目、`StagingRegistry._staging` 无淘汰（随模型数缓增）
- pending.json 合法 JSON 但非 list 时 `_load` 无类型校验 → append 500

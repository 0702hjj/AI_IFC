# W-0023: create_skeleton 确定性化（骨架实体 GlobalId 随机 → I5/C-locate 缺口）

- **状态：** done（2026-08-10，分支 feat/v0.2-script-closure，commit 9c9d893，PR #28）
- **优先级：** P1
- **Milestone：** v0.2（script-as-source 统一编辑，spec: docs/superpowers/specs/2026-08-08-script-editing-unified-design.md）
- **来源：** feat/script-editing-unified 终审 Important #2（2026-08-08）

## 背景

`script_lib.create_skeleton`（skills/aiifc/references/docs/flows/script_lib.py:124-144）用裸 `root.create_entity` 创建 Project/Site/Building/Storey，GlobalId 每次运行随机。后果：

1. **I5 失真**：真实模板脚本的大版本间 IFC 语义 diff 每次都带骨架 added/removed 幻影噪声（Diff Viewer 数据源被污染）；历史版本按需重建（§5.5 prune 的依据）语义不稳定。测试已在 test_ifc_lazy_materialize.py:43-47 显式绕过。
2. **C-locate 缺口**：骨架实体无 designKey 不可定位，而契约自己的工厂产出契约违规物。

## 方案

- create_skeleton 内部改走确定性路径：骨架实体 key 固定（如 `{building}:skeleton:site` / `{storey_name}` 层级 key），GlobalId 经 `deterministic_guid`，designKey 写入 Pset_AIIFC，调用点经 `_record_callsite` 记录（origin 标 "literal"）。
- 兼容性：已生成模型的骨架 GlobalId 会变——属于生成期脚本契约变更，在 changelog 标注；存量 bootstrap 对齐报告首跑会多骨架噪声，可接受并注明。

## 验收标准

- 同一模板脚本两次运行，骨架实体 GlobalId 一致；`compute_diff` 为空。
- 骨架实体可经 locate 定位（designKey → create_skeleton 调用行）。

## 测试要求

- script_lib 单测：骨架确定性（两次 build 语义 diff 为空，含骨架）。
- locate 端到端：storey guid → 调用点。
- 重跑同脚本 map 字节一致性测试（spec §8 留白，一并补上）。

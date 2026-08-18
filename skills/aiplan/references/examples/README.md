# examples/ —— 契约夹具，非设计模板

本目录文件（`plan_demo.json`、`bim_supplement_demo.json`）的唯一用途：

1. **schema 校验正例**：`tests/test_bim_supplement.py` 等测试的正反例输入；
2. **字段示例**：配合 `references/schemas/plan.schema.json` / `references/schemas/bim_supplement.schema.json`
   展示契约字段怎么填。

**角色红线**：本目录**不是**设计模板。其中的 outline_mm 坐标、面积配比、core_anchor_mm
取值仅为让 schema 有可校验的内容而手写，**从未经过设计评审**，可能存在不合理的
布局选择。

- 模型：**禁止**把本目录的布局当范例模仿或作为草案起点；设计意图从用户交互
  （step-01 渐进设计对话）出发，`plan_demo.json` 只作为契约校验夹具。
- 人类：新增/修改本目录文件后必须重跑
  `pytest tests/ -q`；`bim_supplement_demo.json` 的 `source_plan_sha256` 与
  `plan_demo.json` 内容哈希成对，改动任一侧需重算（算法见测试
  `test_bim_supplement.py::test_demo_pair_sha_consistent`）。

## 文件职责

| 文件 | 对应 schema | 定位 |
|---|---|---|
| `plan_demo.json` | `plan.schema.json`（v3.1） | plan 阶段机器产出金样——cad 段下游消费 |
| `bim_supplement_demo.json` | `bim_supplement.schema.json` | bim 段下游补充金样——CAD 覆盖不了的信息直供 BIM |

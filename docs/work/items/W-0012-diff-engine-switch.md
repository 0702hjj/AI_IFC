# W-0012: diff 引擎切换（脚本 diff + design_diff 退役）

- **状态：** done
- **优先级：** P0
- **Milestone：** M5 script-as-source
- **来源：** spec 2026-08-06-script-as-source-design.md
- **执行者/分支：** opencode / feat/script-as-source
- **关闭 commit：** ed83c07（edit-service）、9d0c8c1（server）

## 背景

design JSON diff 引擎（design_diff.py）废弃。大版本 diff 三层：脚本文本 diff（AI）、IFC 语义 diff（ifcdiff，现役 diffing.py）、IFC 指纹兜底（ifc_fingerprint.py，保留）。

## 涉及位置

- 删：`services/ifc/app/design_diff.py` + `tests/test_design_diff.py`（改写为脚本 diff 测试）
- 改：`routes_diff.py`（design/diff、design/diff-ifc 端点 → script/diff）、`diff_summary.py`（保留共用）
- 新：`script_diff.py`（unified diff 生成 + 摘要统计）

## 方案

1. **script_diff.py**：`difflib.unified_diff` 生成 scripts/v{a}.py ↔ v{b}.py 的文本 diff；附摘要（+/- 行数、PARAMS 块变化键列表——解析两版 PARAMS dict 对比，供 AI 快速定位）
2. 端点：`POST /models/{id}/script/diff {base,target}` → `{text_diff, params_changes, stats}`；IFC 语义 diff 端点保留（/diff 现役）
2b. **小版本 diff（2026-08-06 用户补充）**：暂存链步与步之间的轻量 diff——`GET /models/{id}/script/staging/diff?from={i}&to={j}`（默认相邻两步），返回行内文本 diff + PARAMS 变化；AI 与用户均可见（前端 staging 区加 diff 视图，W-0013 落地）
3. `POST .../design/diff` 与 `/design/diff-ifc` 删除；design_diff.py 删除；ifc_fingerprint 保留作外部模型兜底
4. Diff Viewer 前端：大版本对比增加「脚本 diff」tab（语法纯文本展示即可）（前端部分可在 W-0013 一并，本项负责 API + 数据）

## 验收标准

- 脚本 diff 端点返回 unified diff + PARAMS 变化键
- design_diff 相关代码/测试/文档引用全清（grep 无残留）
- IFC 语义 diff 与指纹 diff 不回归

## 测试要求

- script_diff：文本 diff 正确性、PARAMS 变化提取（键增删改）、版本不存在 404
- Go 代理契约测试同步

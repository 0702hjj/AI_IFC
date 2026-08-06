# W-0015: design JSON 下线 + 文档声明与重构

- **状态：** in-progress
- **优先级：** P1
- **Milestone：** M5 script-as-source
- **来源：** spec 2026-08-06-script-as-source-design.md + 2026-08-06 用户裁决
- **执行者/分支：** opencode / feat/script-as-source

## 背景

design JSON 直接下线（用户裁决）。需要：文档明确「design JSON/params.json 是辅助信息，不是完整信息，不是 IFC 标注文件」；发布页与内部文档按 script-as-source 重构（research/ 与 skill 已有详细素材）。

## 涉及位置

- `docs/site/reference/design-edit.md` + en 版（重写为 script 工作流）
- `docs/site/project/roadmap.md`（已完成区补 M5 项、后续区更新）
- `docs/internal/`（记录转向决策）
- README 中英（两条 AI 路线的表述）
- 顺带清理重评估发现的漂移：NOTICE:52-55 ifcdiff editable 陈旧表述 + open-source-plan 死链；NOTICE:23 examples 归档表述；research/overview.md 三个死链；AGENTS.md 组件表测试计数（Go 123 / vitest 131 / pytest 86 / skill 42 / CI 7 job）；.gitignore SCAD 残留条目（examples.py、output/、sandbox/）

## 方案

1. design-edit 页重写：script-as-source 工作流（plan 草稿 → script → IFC）、PARAMS 表单、diff 三层、版本模型
2. 边界声明（明确写入）：「design JSON 是 AI 起草阶段的辅助草稿——不是模型的完整表示、不是 IFC 的标注文件、不进版本不参与 diff；唯一与 IFC 一一对应的是构建脚本」
3. 漂移清理按上面清单逐项
4. docs:build + check:api 通过；中英文同步

## 验收标准

- site 无 design JSON 作为「编辑面/事实源」的表述残留（历史 spec 除外）
- 漂移清单逐项销账；grep 验证
- docs CI 绿

## 测试要求

- docs:build（死链 fail 即拦）+ check:api

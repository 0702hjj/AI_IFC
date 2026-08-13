---
name: aidxfv
description: AI 生成 CAD（DXF）skill 正式入口。包含 v1（通用 DXF 生成/校验，fork 自 earthtojake/text-to-cad，MIT）与 v2（建筑平面管线：plan.json 对齐 → 草案 → 确认 → 逐层 DXF → building.json）。实际入口内容位于 v1/ 与 v2/，本文件仅做指针。
version: 0.1.0
license: MIT
compatibility: 自包含运行时（scripts/dxf + vendored slim cadpy），唯一外部依赖 ezdxf。v1/v2 的 LICENSE 与运行时保持各自独立，勿与主仓 Apache 文件混排。
---

# AI 生成 CAD（aidxfv）

CAD 逻辑的 skill 封装正式入口。两个版本各自独立、自包含：

- **v1**：通用 DXF 生成/校验（fork 自 earthtojake/text-to-cad，MIT）——见 `v1/SKILL.md`
- **v2**：建筑平面管线（plan.json 对齐 → 草案 → 确认 → 逐层 DXF → building.json，plan→cad→bim 管线的 cad 段）——见 `v2/SKILL.md`

> 历史路径 `AI_CAD/skills/aidxfv1`、`AI_CAD/skills/aidxfv2` 已迁移为本目录下的 `v1/`、`v2/`。MIT 归属保留在各子目录的 LICENSE 文件内。

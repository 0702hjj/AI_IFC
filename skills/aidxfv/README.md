# skills/aidxfv — AI 生成 CAD skill（正式入口）

CAD 逻辑的 skill 封装正式入口，物理内容由 `AI_CAD/skills/aidxfv*` 迁移收敛而来。

| 子目录 | 能力 | 来源 |
|---|---|---|
| `v1/` | 通用 DXF 生成/校验 | fork 自 earthtojake/text-to-cad（MIT），独立自包含运行时 |
| `v2/` | 建筑平面管线（plan.json 对齐 → 草案 → 确认 → 逐层 DXF → building.json） | 同源演进，独立自包含运行时 |

- 入口指针见 `SKILL.md`，实际内容以 `v1/`、`v2/` 为准。
- **MIT 归属保留在各子目录的 LICENSE 文件内，勿与主仓 Apache 文件混排。**

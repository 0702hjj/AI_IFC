# skills/aidxfv — AI 生成 CAD skill（正式入口）

CAD 逻辑的 skill 封装正式入口，物理内容由 `AI_CAD/skills/aidxfv*` 迁移收敛而来。

| 子目录 | 能力 | 来源 |
|---|---|---|
| `v3/` | **plan→cad 建筑平面管线正式版**（接 `aiplan` 落盘的 plan.json → 骨架/房间声明 → building.json + 各层 DXF）；唯一迭代基线 | 主仓原创，MIT 自包含 |

- 入口指针见 `SKILL.md`，实际内容以 `v3/` 为准。
- 上游输入契约（plan.json）由 `skills/aiplan/` 提供（`references/schemas/plan.schema.json`），v3 回读以 aiplan 为母本单向同步（`v3/references/schemas/plan.schema.json`）。
- v1/v2（fork 自 earthtojake/text-to-cad，MIT）已于 2026-08-18 删除；其 flows 契约层（cad_script_lib，主仓 Apache-2.0）迁入 `services/cad/flows/`。
- **MIT 归属保留在 v3/ 的 LICENSE 文件内，勿与主仓 Apache 文件混排。**

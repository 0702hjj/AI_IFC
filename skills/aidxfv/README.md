# skills/aidxfv — AI 生成 CAD skill（正式入口）

CAD 逻辑的 skill 封装正式入口。物理内容由 `AI_CAD/skills/aidxfv*` 渐进收敛而来（MIT 归属保留在其 LICENSE 文件，勿与主仓 AGPL 文件混排）。

- `aidxfv1`：通用 DXF 生成/校验（fork 自 earthtojake/text-to-cad，MIT）
- `aidxfv2`：建筑平面管线（plan.json 对齐 → 草案 → 确认 → 逐层 DXF → building.json）
- 收敛完成前，实际内容以 `AI_CAD/skills/aidxfv1`、`aidxfv2` 为准；本目录是目标命名空间的指针。

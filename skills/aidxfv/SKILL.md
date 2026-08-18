---
name: aidxfv
description: AI 生成 CAD（DXF）skill 正式入口。当前版本为 v3（plan→cad 建筑平面管线正式版：接 aiplan 落盘的 plan.json → 骨架/房间声明 → building.json + 各层 DXF）。实际入口内容位于 v3/，本文件仅做指针。
version: 0.1.0
license: MIT
compatibility: v3 自包含运行时（纯 Python 包 floorgeom/dxfkit/goldlib/flowops），外部依赖 ezdxf + shapely。MIT 归属见 v3/ 内 LICENSE，勿与主仓 Apache 文件混排。
---

# AI 生成 CAD（aidxfv）

CAD 逻辑的 skill 封装正式入口。当前唯一版本：

- **v3**：plan→cad 建筑平面管线正式版（接 `aiplan` 落盘的 plan.json → 骨架/房间声明 → building.json + 各层 DXF）——见 `v3/SKILL.md`

> 历史版本 v1/v2（fork 自 earthtojake/text-to-cad，MIT）已于 2026-08-18 删除——v3 上线为唯一迭代基线；其中主仓 Apache-2.0 的 flows 契约层（cad_script_lib）迁入 `services/cad/flows/`。更早的历史路径 `AI_CAD/skills/aidxfv1`、`AI_CAD/skills/aidxfv2` 曾迁移为本目录下的 `v1/`、`v2/`，现仅存于 git 历史。

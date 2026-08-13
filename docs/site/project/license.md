# License 与第三方组件

## 仓库许可证

AI_IFC 以 **Apache-2.0** 发布（[LICENSE](https://github.com/0702hjj/AI_IFC/blob/main/LICENSE)）。2026-08-13 前为 AGPL-3.0-only；经全体贡献者同意改为 Apache-2.0，与上游 [SimpleCADAPI](https://github.com/NiJingzhe/SimpleCADAPI) 2026-08-12 的协议调整（AGPL→Apache-2.0）对齐。

`web/`、`server/`、`converter/`、`services/`、`mcp/`、`skills/` 与 `docs/` 下全部自有代码 Copyright (C) 2026 0702hjj（SPDX-License-Identifier 头）。

### 例外目录（保留各自原许可）

| 目录 | 许可证 | 上游 |
| --- | --- | --- |
| `skills/aidxfv/v1/`、`skills/aidxfv/v2/` | MIT | earthtojake/text-to-cad（各自 LICENSE 文件） |
| `skills/aiblueprint-mcp/` | MIT | thebossnow/aiblueprint-mcp |

> ⚠️ **xeokit 注意**：本仓代码是 Apache-2.0，但 `web/` 前端依赖 AGPL-3.0 的 @xeokit/xeokit-sdk——分发含 xeokit 的前端构建产物时整体受 AGPL 约束（网络使用即触发）。闭源/商用场景请改用 three.js（MIT）+ web-ifc（MPL-2.0）。converter/ 以子进程方式使用 xeokit-convert，其输出（XKT 数据）不受 AGPL 覆盖。详见根 NOTICE。

## 归档代码边界

本仓库 fork 自 SimpleCADAPI（OCP 原生 CAD 生成，论文 artifact）。SCAD 遗产代码（`src/simplecadapi/`、`skills/simplecadapi/`、根 `pyproject.toml` 等 SCAD 时代打包配置）已于 2026-08-06 移至私有归档仓 [0702hjj/SimpleCADAPI-archive](https://github.com/0702hjj/SimpleCADAPI-archive)，保留原始版权与许可证（SimpleCAD API Team），**不是**活跃产品，本仓不再包含。

## 第三方组件

完整列表见仓库根 [NOTICE](https://github.com/0702hjj/AI_IFC/blob/main/NOTICE)。要点：

| 组件 | 许可证 |
| --- | --- |
| @xeokit/xeokit-sdk / xeokit-convert | AGPL-3.0（见上方注意） |
| web-ifc | MPL-2.0 |
| ifcopenshell / ifcdiff | LGPL-3.0-or-later |
| ezdxf / libcst / pgx (jackc/pgx/v5) | MIT |
| React / Vite / zustand / react-router-dom | MIT |
| FastAPI / uvicorn / pydantic / deepdiff | MIT / BSD-3-Clause |

> Python 依赖（`ifcopenshell` / `ifcdiff` / `ifcquery` / `ezdxf`）均为 PyPI 官方发布，`uv sync` 直接安装，不随本仓分发。

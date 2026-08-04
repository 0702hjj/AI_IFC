# License 与第三方组件

## 仓库许可证

AI_IFC 以 **AGPL-3.0-only** 发布（[LICENSE](https://github.com/0702hjj/AI_IFC/blob/main/LICENSE)）。许可证继承自 SimpleCADAPI fork，也与 AGPL-3.0 的 xeokit 栈保持一致。

`viewer/` 与 `docs/` 下全部新代码 Copyright (C) 2026 0702hjj（SPDX-License-Identifier 头）。

## 归档代码边界

本仓库 fork 自 SimpleCADAPI（OCP 原生 CAD 生成，论文 artifact）。以下部分保留原始版权与许可证，作为归档参考，**不是**活跃产品：

- `src/simplecadapi/`（SimpleCAD API Team）
- `skills/simplecadapi/`（SimpleCAD API Team）
- `examples/`（SimpleCAD API Team）
- 根 `pyproject.toml`（SimpleCADAPI 包元数据，归档）
- `docs/archive/simplecadapi/`（原 SCAD API/core/stdlib/legacy 文档）

## 第三方组件

完整列表见仓库根 [NOTICE](https://github.com/0702hjj/AI_IFC/blob/main/NOTICE)。要点：

| 组件 | 许可证 |
| --- | --- |
| @xeokit/xeokit-sdk / xeokit-convert | AGPL-3.0 |
| web-ifc | MPL-2.0 |
| ifcopenshell / ifcdiff | LGPL-3.0-or-later |
| pgx (jackc/pgx/v5) | MIT |
| React / Vite / zustand / react-router-dom | MIT |
| FastAPI / uvicorn / pydantic / deepdiff | MIT / BSD-3-Clause |

> Python 依赖（`ifcopenshell` / `ifcdiff` / `ifcquery`）均为 PyPI 官方发布（LGPL-3.0），随 edit-service 正常分发，`uv sync` 直接安装。

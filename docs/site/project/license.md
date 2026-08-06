# License 与第三方组件

## 仓库许可证

AI_IFC 以 **AGPL-3.0-only** 发布（[LICENSE](https://github.com/0702hjj/AI_IFC/blob/main/LICENSE)）。许可证继承自 SimpleCADAPI fork，也与 AGPL-3.0 的 xeokit 栈保持一致。

`viewer/` 与 `docs/` 下全部新代码 Copyright (C) 2026 0702hjj（SPDX-License-Identifier 头）。

## 归档代码边界

本仓库 fork 自 SimpleCADAPI（OCP 原生 CAD 生成，论文 artifact）。SCAD 遗产代码（`src/simplecadapi/`、`skills/simplecadapi/`、根 `pyproject.toml` 等 SCAD 时代打包配置）已于 2026-08-06 移至私有归档仓 [0702hjj/SimpleCADAPI-archive](https://github.com/0702hjj/SimpleCADAPI-archive)，保留原始版权与许可证（SimpleCAD API Team），**不是**活跃产品，本仓不再包含。本仓内保留原始版权与许可证的归档部分：

- `examples/`（SimpleCAD API Team）
- `docs/archive/simplecadapi/`（原 SCAD API/core/stdlib/legacy 文档，已随 2026-08-05 清理移除，见 git 历史）

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

# W-0027: services/ifc Dockerfile 冒烟 + 独立部署文档对账

- **状态：** open
- **优先级：** P1
- **Milestone：** v0.5（可移植复用）
- **来源：** spec 2026-08-12-portability-reuse-design.md §2
- **执行者/分支：** opencode / feat/v0.5-portability-reuse

## 背景

services/ifc 目前只能在本仓骨架内以 uv 起服务，第三方想单组件独立部署没有可复现路径。补 `services/ifc/Dockerfile`（uv + ifcopenshell，`VIEWER_DATA_DIR` 挂载），使 edit-service 单容器可跑、脱离本仓骨架独立部署，并把现有独立部署指南对账更新。

## 涉及位置

- `services/ifc/Dockerfile`（新增）
- `docs/site/guide/services-ifc.md`（+ 英文页）：补 Docker 段

## 方案

1. 编写 Dockerfile：基于 Python 3.10+ 镜像，uv 安装依赖（ifcopenshell 等），暴露 :8100，`VIEWER_DATA_DIR` 作为挂载点。
2. 冒烟命令序列（记入本 item，实施时逐条执行）：
   - `docker build -t aiifc-ifc services/ifc`
   - `docker run -d -p 8100:8100 -v <data>:/data aiifc-ifc`
   - `curl -sf http://127.0.0.1:8100/openapi.json` → 200
3. 文档：`docs/site/guide/services-ifc.md`（+en）补 Docker 构建/运行段，与冒烟序列一致。

## 验收标准

- 镜像构建成功。
- 容器起后 `GET /openapi.json` 返回 200。
- `docs/site/guide/services-ifc.md`（+en）补 Docker 段，`npm run docs:build` 绿。

## 测试要求

- 冒烟命令序列记入 item（见方案 2），实施时逐条实测通过；Dockerfile 无单测，冒烟即验收。

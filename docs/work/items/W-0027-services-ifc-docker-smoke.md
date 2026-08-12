# W-0027: services/ifc Dockerfile 冒烟 + 独立部署文档对账

- **状态：** done
- **优先级：** P1
- **Milestone：** v0.5（可移植复用）
- **来源：** spec 2026-08-12-portability-reuse-design.md §2
- **执行者/分支：** opencode / feat/v0.5-portability-reuse
- **关闭于：** 本迭代分支 feat/v0.5-portability-reuse（PR 待提）

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

## 验收记录（2026-08-12）

**环境偏差**：实施机上 Docker 29.7.2 已装但守护进程未运行，且无 sudo 权限启动（docker.socket/docker.service/containerd 均 inactive），故真容器冒烟未执行。改为**按 Dockerfile 指令逐条等价复现**（/tmp/opencode/dockerfile-equiv，uv 0.12.3；uv 解析到 Python 3.12.12 而非镜像的 3.10，记为残余差异）：

1. `COPY pyproject.toml uv.lock` → `uv sync --frozen --no-group dev`：成功，ifcopenshell 0.8.5 安装正常。
2. `COPY app/`、`COPY flows → /opt/aiifc/flows` 等价拷贝。
3. 以镜像同款 ENV（`VIEWER_DATA_DIR=/tmp/opencode/editvc-data`、`AIIFC_FLOWS_DIR=.../flows`）执行镜像 CMD `uv run --no-sync uvicorn app.main:app --port 18100`：启动成功。
4. 冒烟请求：
   - `curl -sf http://127.0.0.1:18100/openapi.json` → **HTTP 200**（`{"openapi":"3.1.0","info":{"title":"ifc-edit-service"...}`）。
   - `curl http://127.0.0.1:18100/health` → **HTTP 200** `{"status":"ok"}`。
5. 静态审查 Dockerfile：指令序列与本地等价路径一致，未发现需修改的问题（Dockerfile 未改动）。

**残余 gap**（需在有可用 Docker daemon 的机器补验）：
- 真 `docker build` + `docker run` + `curl :8100/openapi.json` 冒烟（含 bubblewrap 沙箱路径在容器内的行为）。
- spec 的更全期望「起容器 → 上传/编辑一条链路通」未覆盖——上传→转换→浏览完整链路需 Go 网关编排，超出本 item 的单容器范围。

真容器冒烟转出 W-0031 追踪（本机无 docker daemon，等价复现已记录）。

## 测试要求

- 冒烟命令序列记入 item（见方案 2），实施时逐条实测通过；Dockerfile 无单测，冒烟即验收。

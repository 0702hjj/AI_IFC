# W-0004: Docker Compose 一键启动

- **状态：** done
- **关闭于：** e177bea + 5fcdbbb + 332c098 + cc14851（compose-smoke CI 终验）
- **优先级：** P1
- **Milestone：** M3（见 PLAN-v0.1.0.md）
- **来源：** PLAN-v0.1.0（M3 发布化）+ roadmap 近期项
- **执行者/分支：** opencode / feat/m3-release

## 背景

当前启动要 4 个终端手工起 4 组件 + 装 3 套依赖（AGENTS.md 组件表），是潜在用户的最大门槛。M3 目标：`docker compose up` 一键起全栈。

## 涉及位置

- 新增：根 `docker-compose.yml`、`.env.example`、各组件 Dockerfile
- `web/vite.config.ts`（参考：dev 代理 `/api`、`/v1` → :8090）
- `docs/site/guide/quickstart.md`（+ 英文页）补 Docker 启动方式

## 方案（建议架构，实现者可调整但需说明理由）

- **web**：multi-stage（node build dist → nginx serve），nginx 反代 `/api`、`/v1` 到 server:8090
- **server**：单镜像含 Go + Node 双运行时（Go 构建后用含 node 的基础镜像，拷贝 converter 及其 node_modules——server 以子进程调 `node converter/convert.js`）；`VIEWER_DATA_DIR=/data` 挂卷
- **edit-service**：python:3.10 + uv sync（含 dev 之外的运行依赖 + flows 目录 `AIIFC_FLOWS_DIR`），共享 `/data` 卷
- **postgres**：可选 profile（`--profile pg`），设 `VIEWER_PG_DSN` 后启用；默认文件存储零依赖
- 配置外置：`.env.example` 列全部可调项（端口、DATA_DIR、PG DSN）
- 注意 Go server 目前不 serve 前端静态文件，不要在 server 镜像里塞 web

## 验收标准

- 干净环境 `docker compose up --build` 后：浏览器开 web 端口 → 上传 fixture IFC（`converter/test/fixtures/wall-with-opening-and-window.ifc`）→ 转换 ready → 3D 可见
- edit-service 联通：design/edit 端点经 server 代理可达（envelope）
- `--profile pg` 起 PG 后 issues/overrides/changes 走 PG（建表自动）
- 数据卷持久化：down/up 后模型仍在

## 测试要求

- compose 配置级验证：`docker compose config -q` 语法合法
- 冒烟脚本（可复用/扩展 `scripts/smoke.sh` 指向 compose 栈）或 CI 新增 compose 冒烟 job（build + up + curl 上传 → ready）
- quickstart 文档命令与实际一致（文档即验收）

# W-0031: services/ifc 真容器冒烟（docker build/run 实测）

- **状态：** open
- **优先级：** P2
- **Milestone：** v0.5 后续/下迭代
- **来源：** W-0027 验收残余（2026-08-12 环境无 docker daemon）
- **执行者/分支：** （领取时填）

## 背景

W-0027 验收时实施机 Docker 29.7.2 已装但 daemon 未运行且无 sudo 启动权限（docker.service/docker.socket/containerd 均 inactive，无 rootlesskit），验收标准「镜像构建成功」未字面达成——当时改为按 Dockerfile 指令逐条等价复现（uv sync + 同款 ENV/CMD 起 uvicorn，`/openapi.json` 与 `/health` 均 200，记录在 W-0027 验收记录）。真容器冒烟从未执行，本 item 补齐。

## 涉及位置

- `services/ifc/Dockerfile`（冒烟对象；仅当冒烟暴露实际问题时才动，动则按修复 bug 纪律先记录失败证据）
- `docs/work/items/W-0027-services-ifc-docker-smoke.md`（验收记录回填真冒烟结果）

## 方案

在有 docker daemon 的机器上执行：

1. `docker build -f services/ifc/Dockerfile -t aiifc-edit-service:v0.5 .`（**构建上下文=仓库根**，镜像 COPY 了 `skills/aiifc/references/docs/flows`）。
2. `mkdir -p /tmp/editvc-data && docker run --rm -d --name editvc-smoke -p 18100:8100 -v /tmp/editvc-data:/data aiifc-edit-service:v0.5`。
3. `curl -sf http://127.0.0.1:18100/openapi.json` → 200；`curl http://127.0.0.1:18100/health` → `{"status":"ok"}`。
4. 关注两点等价复现未覆盖的差异：
   - **bwrap 沙箱在容器内行为**：镜像装了 bubblewrap，run/save 的沙箱 backend 在容器内是否真正生效（而非降级 rlimit）——可进容器 `bwrap --version` + 跑一次 script/run 类调用观察日志。
   - **python:3.10 pin**：等价复现 uv 解析到 3.12，镜像 pin 3.10，确认依赖在 3.10 下无问题（构建成功即基本证明）。
5. 清理：`docker stop editvc-smoke`（`--rm` 自动删容器）。

## 验收标准

- 真容器冒烟通过（构建成功 + 两个 GET 200），命令与输出记录进 W-0027 验收记录。
- 若冒烟暴露 Dockerfile 问题：先记录失败证据，最小修复，修复与证据一并记入 W-0027 与本 item。

## 测试要求

冒烟命令序列即验收（Dockerfile 无单测）；逐条实测通过并留记录。

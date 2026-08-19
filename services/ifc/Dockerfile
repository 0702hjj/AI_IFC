# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj
# edit-service 镜像（FastAPI + ifcopenshell，uv 管理依赖）。
# 构建上下文为仓库根（flows 目录在 skills/aiifc/references/docs/flows）。

FROM python:3.10-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# bubblewrap：脚本沙箱的 bwrap backend（ro root + unshare-net）；缺它降级为 rlimit。
# 非 root 运行仍可用：bwrap 走 unprivileged user namespace（Docker ≥20.10 默认
# seccomp 放行 CLONE_NEWUSER；宿主内核需允许 unprivileged userns，Debian/Ubuntu 默认开）。
RUN apt-get update \
    && apt-get install -y --no-install-recommends bubblewrap \
    && rm -rf /var/lib/apt/lists/*

# 专用非 root 用户（uid/gid 1000，bind mount 数据目录时与宿主力用户对齐）。
RUN groupadd -g 1000 app && useradd -u 1000 -g app -m app

WORKDIR /app
COPY services/ifc/pyproject.toml services/ifc/uv.lock ./
RUN uv sync --frozen --no-group dev
COPY services/ifc/app ./app
COPY skills/aiifc/references/docs/flows /opt/aiifc/flows
# named volume 首次挂载继承镜像内 /data 属主；bind mount 需宿主目录可被 uid 1000 写。
RUN mkdir -p /data && chown app:app /data

ENV VIEWER_DATA_DIR=/data \
    AIIFC_FLOWS_DIR=/opt/aiifc/flows \
    EDIT_SERVICE_PORT=8100
EXPOSE 8100
USER app
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]

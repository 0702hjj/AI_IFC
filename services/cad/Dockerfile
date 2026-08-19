# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj
# cad-edit-service 镜像（FastAPI + ezdxf，uv 管理依赖）。
# 构建上下文为仓库根（flows 沙箱契约层在 services/cad/flows）。

FROM python:3.10-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# bubblewrap：脚本沙箱的 bwrap backend（与 services/ifc 同构）；缺它降级为 rlimit。
# 非 root 下走 unprivileged user namespace（宿主要求同 services/ifc/Dockerfile）。
RUN apt-get update \
    && apt-get install -y --no-install-recommends bubblewrap \
    && rm -rf /var/lib/apt/lists/*

# 专用非 root 用户（uid/gid 1000，与 edit-service 镜像一致，共享同一数据卷）。
RUN groupadd -g 1000 app && useradd -u 1000 -g app -m app

WORKDIR /app
COPY services/cad/pyproject.toml services/cad/uv.lock ./
RUN uv sync --frozen --no-group dev
COPY services/cad/app ./app
COPY services/cad/flows ./flows
# named volume 首次挂载继承镜像内 /data 属主；bind mount 需宿主目录可被 uid 1000 写。
RUN mkdir -p /data && chown app:app /data

ENV VIEWER_DATA_DIR=/data \
    AIDXF_FLOWS_DIR=/app/flows \
    CAD_SERVICE_PORT=8200
EXPOSE 8200
USER app
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8200"]

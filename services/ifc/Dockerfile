# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj
# edit-service 镜像（FastAPI + ifcopenshell，uv 管理依赖）。
# 构建上下文为仓库根（flows 目录在 skills/aiifc/references/docs/flows）。

FROM python:3.10-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# bubblewrap：脚本沙箱的 bwrap backend（ro root + unshare-net）；缺它降级为 rlimit。
RUN apt-get update \
    && apt-get install -y --no-install-recommends bubblewrap \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY services/ifc/pyproject.toml services/ifc/uv.lock ./
RUN uv sync --frozen --no-group dev
COPY services/ifc/app ./app
COPY skills/aiifc/references/docs/flows /opt/aiifc/flows

ENV VIEWER_DATA_DIR=/data \
    AIIFC_FLOWS_DIR=/opt/aiifc/flows \
    EDIT_SERVICE_PORT=8100
EXPOSE 8100
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]

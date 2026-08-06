# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj
# edit-service 镜像（FastAPI + ifcopenshell，uv 管理依赖）。
# 构建上下文为仓库根（flows 目录在 skills/aiifc/references/docs/flows）。

FROM python:3.10-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY viewer/edit-service/pyproject.toml viewer/edit-service/uv.lock ./
RUN uv sync --frozen --no-group dev
COPY viewer/edit-service/app ./app
COPY skills/aiifc/references/docs/flows /opt/aiifc/flows

ENV VIEWER_DATA_DIR=/data \
    AIIFC_FLOWS_DIR=/opt/aiifc/flows \
    EDIT_SERVICE_PORT=8100
EXPOSE 8100
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]

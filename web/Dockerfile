# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj
# web 镜像：node 构建 dist → nginx 托管，反代 /api、/v1 到 server:8090。
# 构建上下文为 web/。

FROM node:22-bookworm-slim AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 80

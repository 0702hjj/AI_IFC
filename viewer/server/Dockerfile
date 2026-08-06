# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj
# Go server 镜像：构建期用 golang，运行期用 node 基础镜像
# （server 以子进程调 `node /opt/converter/convert.js` 做 IFC→XKT）。
# 构建上下文为 viewer/（需要 server + converter 两个目录）。

FROM golang:1.26-bookworm AS server-build
WORKDIR /src/server
COPY server/go.mod server/go.sum ./
RUN go mod download
COPY server/ ./
RUN CGO_ENABLED=0 go build -o /out/server ./cmd/server

FROM node:22-bookworm-slim AS converter-deps
WORKDIR /src/converter
COPY converter/package.json converter/package-lock.json ./
RUN npm ci --omit=dev

FROM node:22-bookworm-slim
WORKDIR /app
COPY --from=server-build /out/server /app/server
COPY server/server_config.docker.json /app/server_config.json
COPY --from=converter-deps /src/converter/node_modules /opt/converter/node_modules
COPY converter/package.json converter/convert.js /opt/converter/
COPY converter/lib /opt/converter/lib
EXPOSE 8090
CMD ["/app/server", "-config", "/app/server_config.json"]

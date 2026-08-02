# 环境要求与本地部署

## 环境依赖

| 依赖 | 版本 | 用途 | 必需性 |
| --- | --- | --- | --- |
| Go | 1.26+ | server | 必需 |
| Node.js | 18+ | converter（`npm install` 一次即可，无需常驻） | 必需 |
| Python + [uv](https://docs.astral.sh/uv/) | 3.10+ | edit-service | 编辑/diff 功能必需；纯浏览可不要 |
| PostgreSQL | 14+ | issues/changes/overrides 持久化 | 可选（默认文件存储） |
| IfcOpenShell 源码 checkout | v0.8 | ifcdiff 的本地 editable 依赖 | 当前必需（见下方说明） |

> **ifcdiff 依赖说明**：edit-service 的 `pyproject.toml` 目前以本地 editable 路径引用同级目录的 IfcOpenShell 源码（`src/ifcdiff`）。即运行 edit-service 前，需要在仓库同级目录准备一份 IfcOpenShell v0.8 checkout。这是已记录的部署限制，自包含处理（vendor 或 git source）在 [Roadmap](/project/roadmap) 中。

## 启动（四个终端）

```bash
# 0. 一次性：安装依赖
cd viewer/converter && npm install
cd ../web && npm install
cd ../edit-service && uv sync

# 1. edit-service（:8100）—— VIEWER_DATA_DIR 必须指向 viewer/data 的绝对路径
cd viewer/edit-service
VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100

# 2. Go server（:8090）
cd viewer/server && go run ./cmd/server

# 3. web（:5173）
cd viewer/web && npm run dev
```

打开 `http://localhost:5173` 即可使用。完整配置项见 [配置说明](/guide/configuration)。

## 验证

```bash
# 端到端冒烟（需 server 运行；edit-flow 段在 edit-service 不可达时自动跳过）
cd viewer && ./scripts/smoke.sh

# 各层测试
cd viewer/server && go test ./...
cd viewer/edit-service && uv run pytest
cd viewer/web && npm test
cd viewer/converter && npm test
```

> 注意：上传、转换、审查等浏览功能不依赖 edit-service 与 PostgreSQL；编辑、版本、diff 需要 edit-service 运行。

# 环境要求与本地部署

## 环境依赖

| 依赖 | 版本 | 用途 | 必需性 |
| --- | --- | --- | --- |
| Go | 1.26+ | server | 必需 |
| Node.js | 18+ | converter（`npm install` 一次即可，无需常驻） | 必需 |
| Python + [uv](https://docs.astral.sh/uv/) | 3.10+ | edit-service | 编辑/diff 功能必需；纯浏览可不要 |
| PostgreSQL | 14+ | issues/changes/overrides 持久化 | 可选（默认文件存储） |

> **Python 依赖说明**：edit-service 依赖 `ifcopenshell` / `ifcdiff` / `ifcquery`（均为 PyPI 官方发布，对齐 IfcOpenShell 0.8.5），`uv sync` 直接安装，无需本机 IfcOpenShell 源码 checkout。

## Docker Compose（推荐）

只需 Docker，一条命令起全栈（web / server / converter / edit-service）：

```bash
cp .env.example .env   # 可选：所有项均有默认值
docker compose up --build
```

打开 `http://localhost:8080` 即可使用。数据存 named volume（`aiifc-data`），`down`/`up` 后模型仍在。

追加 PostgreSQL（issues/changes/overrides 走 PG，建表自动）：

```bash
# 在 .env 中设置：VIEWER_PG_DSN=postgres://aiifc:aiifc@postgres:5432/aiifc?sslmode=disable
docker compose --profile pg up -d
```

可调项（端口、`DATA_DIR`、`VIEWER_PG_DSN` 等）见 `.env.example`。

## 启动（四个终端，无 Docker）

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
cd viewer/edit-service && uv run --group dev pytest
cd viewer/web && npm test
cd viewer/converter && npm test
```

> 注意：上传、转换、审查等浏览功能不依赖 edit-service 与 PostgreSQL；编辑、版本、diff 需要 edit-service 运行。

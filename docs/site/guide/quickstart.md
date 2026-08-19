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

只需 Docker，一条命令起全栈（web / server / converter / edit-service / cad-edit-service）：

```bash
cp .env.example .env   # 可选：所有项均有默认值
docker compose up --build
```

打开 `http://localhost:8080` 即可使用。数据存 named volume（`aiifc-data`），`down`/`up` 后模型仍在。

> **生产部署必读**：`VIEWER_API_TOKEN` 在生产/多用户环境**必填**（`.env` 中设置，compose 透传给 server）。威胁模型：编辑 API 会在服务端沙箱中执行构建脚本——**脚本执行 = 代码执行**；鉴权关闭（token 为空）仅限本机单机开发，任何对外暴露的部署都必须设置 token。

server、edit-service 与 cad-edit-service 容器均以**非 root 用户**（uid/gid 1000）运行（三者同 uid，共享 `/data` 卷跨容器读写一致）。沙箱 bwrap 在镜像内为 setuid root（bwrap 为 setuid 安全设计，启动即降权），**不依赖宿主的 unprivileged userns**（兼容 Ubuntu 24.04+ 的 AppArmor 限制与 RHEL 系默认配置）。若用 `DATA_DIR` bind mount 宿主机目录，需保证该目录可被 uid 1000 写入（如 `chown -R 1000:1000`）；named volume 默认无此问题。**从旧版升级**：已存在的 named volume 归 root 所有，需 `docker compose down -v` 重建（数据清掉）或 `docker run --rm -v aiifc-data:/data alpine chown -R 1000:1000 /data` 修正属主。

追加 PostgreSQL（issues/changes/overrides 走 PG，建表自动）：

```bash
# 在 .env 中设置：VIEWER_PG_DSN=postgres://aiifc:aiifc@postgres:5432/aiifc?sslmode=disable
docker compose --profile pg up -d
```

可调项（端口、`DATA_DIR`、`VIEWER_PG_DSN` 等）见 `.env.example`。

## 启动（四个终端，无 Docker）

```bash
# 0. 一次性：安装依赖
cd converter && npm install
cd ../web && npm install
cd ../services/ifc && uv sync

# 1. edit-service（:8100）—— VIEWER_DATA_DIR 必须指向 data 的绝对路径
cd services/ifc
VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100

# 2. Go server（:8090）
cd server && go run ./cmd/server

# 3. web（:5173）
cd web && npm run dev
```

打开 `http://localhost:5173` 即可使用。完整配置项见 [配置说明](/guide/configuration)。

## 验证

```bash
# 端到端冒烟（需 server 运行；edit-flow 段在 edit-service 不可达时自动跳过）
./scripts/smoke.sh

# 各层测试
cd server && go test ./...
cd services/ifc && uv run --group dev pytest
cd web && npm test
cd converter && npm test
```

> 注意：上传、转换、审查等浏览功能不依赖 edit-service 与 PostgreSQL；编辑、版本、diff 需要 edit-service 运行。

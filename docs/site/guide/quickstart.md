# 环境要求与本地部署

部署形态：宿主机直跑（无 Docker）。web 构建产物由 Go server 直接托管，edit-service / cad-edit-service 以本机进程运行。

## 环境依赖

| 依赖 | 版本 | 用途 | 必需性 |
| --- | --- | --- | --- |
| Go | 1.26+ | server | 必需 |
| Node.js | 22+ | converter（`npm install` 一次即可，无需常驻）+ web 构建 | 必需 |
| Python + [uv](https://docs.astral.sh/uv/) | 3.10+ | edit-service / cad-edit-service | 编辑/diff 功能必需；纯浏览可不要 |
| Linux + bubblewrap | — | 脚本沙箱后端（bwrap） | 生产必需；缺失时沙箱 fail-closed（run/save 拒绝执行） |
| PostgreSQL | 14+ | issues/changes/overrides 持久化 | 可选（默认文件存储） |

> **Python 依赖说明**：edit-service 依赖 `ifcopenshell` / `ifcdiff` / `ifcquery`（均为 PyPI 官方发布，对齐 IfcOpenShell 0.8.5），`uv sync` 直接安装，无需本机 IfcOpenShell 源码 checkout。
>
> **bubblewrap 安装**：Debian/Ubuntu `sudo apt install bubblewrap`；RHEL 系 `sudo dnf install bubblewrap`。沙箱在本机用户态直接可用（bwrap 走 unprivileged user namespace；Ubuntu 24.04+ 的 AppArmor 限制不影响 bwrap 常见用法，本机实测）。无 bwrap 的开发机可设 `ALLOW_RLIMIT_FALLBACK=1` 降级为 rlimit 沙箱（FS/网络隔离弱化），**生产勿设**。

## 启动（开发，四个终端）

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

## 生产部署（宿主直跑）

生产形态为单端口：Go server 托管 web 构建产物 + 代理 API，浏览器只访问 server 端口（默认 :8090）。

```bash
# 1. 构建前端（产物在 web/dist）
cd web && npm ci && npm run build

# 2. 构建并启动 server（默认自动服务 ../web/dist；可用 server_config.json 的
#    webDist 或环境变量 VIEWER_WEB_DIST 改路径）
cd ../server && go build -o server ./cmd/server && ./server

# 3. 启动业务服务（edit-service :8100 / cad-edit-service :8200，绑 127.0.0.1）
cd ../services/ifc && uv sync && VIEWER_DATA_DIR=/srv/aiifc/data uv run uvicorn app.main:app --host 127.0.0.1 --port 8100
cd ../services/cad && uv sync && VIEWER_DATA_DIR=/srv/aiifc/data uv run uvicorn app.main:app --host 127.0.0.1 --port 8200
```

> **生产部署必读**：`VIEWER_API_TOKEN` 在生产/多用户环境**必填**（环境变量传给 server）。威胁模型：编辑 API 会在服务端沙箱中执行构建脚本——**脚本执行 = 代码执行**；鉴权关闭（token 为空）仅限本机单机开发，任何对外暴露的部署都必须设置 token。

PostgreSQL（可选）：宿主机自装 PostgreSQL 14+，给 server 传 `VIEWER_PG_DSN=postgres://user:pass@127.0.0.1:5432/aiifc` 即可（建表自动）。

### systemd 最小示例

```ini
# /etc/systemd/system/aiifc-server.service
[Unit]
Description=AI_IFC Go server
After=network.target

[Service]
WorkingDirectory=/opt/AI_IFC/server
Environment=VIEWER_API_TOKEN=换成强随机串
ExecStart=/opt/AI_IFC/server/server -config server_config.json
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/aiifc-ifc.service（cad 同构：WorkingDirectory 换 services/cad、端口 8200）
[Unit]
Description=AI_IFC edit-service
After=network.target

[Service]
WorkingDirectory=/opt/AI_IFC/services/ifc
Environment=VIEWER_DATA_DIR=/opt/AI_IFC/data
ExecStart=/usr/local/bin/uv run uvicorn app.main:app --host 127.0.0.1 --port 8100
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

注意：`VIEWER_DATA_DIR`（两个 Python 服务）与 server `dataDir`（server_config.json）必须指向**同一目录**；server 以何用户运行，该目录就需对该用户可写。

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

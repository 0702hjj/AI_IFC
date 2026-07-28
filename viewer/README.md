# IFC Web Viewer

基于 Web 的 IFC 模型查看器：上传 IFC 文件，后台转换为 XKT 格式，在浏览器中通过 xeokit 进行三维可视化、构件拾取、属性查看、剖切与测量。

## 架构

系统由三个模块组成：

- **converter**（Node.js）：IFC → XKT 转换器，基于 web-ifc。被 server 以子进程方式调用，无需常驻进程。
- **server**（Go）：HTTP API 服务（默认端口 `:8090`），负责模型上传、转换任务调度、XKT/元数据静态服务与模型管理。
- **web**（React + xeokit）：前端应用（开发端口 `:5173`），包含模型库页面与三维查看器。

详细设计见 [docs/design.md](docs/design.md)，API 说明见 [docs/api.md](docs/api.md)，测试覆盖与验证方法见 [docs/README.md](docs/README.md)。

```
web (React/xeokit)  ──HTTP──>  server (Go :8090)  ──子进程──>  converter (Node)
                                     │
                                     └── data/  (上传的 IFC、生成的 XKT 与元数据)
```

## 依赖版本

- Node.js ≥ 18
- Go ≥ 1.22
- python3（仅冒烟脚本用于解析 JSON）

## 运行

### converter

无需启动守护进程，首次使用安装依赖即可：

```bash
cd converter
npm install
npm test        # 可选：运行测试
```

### server

```bash
cd server
go run ./cmd/server
```

服务监听 `:8090`，运行时数据写入 `../data`（由 `server_config.json` 的 `dataDir` 配置）。

### web

```bash
cd web
npm install
npm run dev
```

开发服务器运行在 `:5173`，通过代理访问后端 API。

## 冒烟测试

前提：server 已在 `:8090` 运行。脚本会上传测试构件、轮询转换状态、校验 XKT/元数据/下载接口，最后删除模型：

```bash
cd viewer
./scripts/smoke.sh
```

成功输出以 `smoke OK` 结尾。

## 目录说明

```
viewer/
├── converter/        IFC→XKT 转换器（Node.js）
│   └── test/fixtures/  测试用 IFC 文件
├── server/           后端 API 服务（Go）
│   ├── cmd/server/     服务入口
│   └── server_config.json
├── web/              前端应用（React + xeokit + Vite）
├── scripts/smoke.sh  端到端冒烟脚本
├── docs/             设计文档、API 文档、计划
└── data/             运行时数据（不纳入版本管理）
```

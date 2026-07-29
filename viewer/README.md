# IFC Web Viewer

基于 Web 的 IFC 模型审查平台：上传 IFC 文件，后台转换为 XKT 格式，在浏览器中通过 xeokit 进行三维可视化、构件拾取、属性审查、模型树搜索/过滤、显隐控制、剖切、测量与 Issue/Markup 审查协同。

## 功能

- **模型库**：上传（≤200MB）、转换状态轮询、重试、下载、删除
- **三维查看**：xeokit 渲染、轨道旋转/缩放、NavCube、构件拾取高亮
- **模型树**：搜索（名称/类型）、IFC 类型过滤、逐节点显隐、点击定位
- **可见性工具栏**：隐藏选中 / 隔离 / X-Ray / 重置可见性
- **属性面板**：Pset 分组折叠、属性搜索、属性复制；白名单字段（Name/Description/Classification/FireRating/Comments）可编辑，保存为 metadata override 覆盖显示并带修改标记
- **Issue/Markup**：选中构件创建 Issue（自动保存相机视角 + 截图）、状态流转（Open/Checking/Resolved）、点击恢复视角、删除；3D Issue Pin（HTML overlay 钉，点击定位）
- **修改历史**：IssuePanel「修改历史」tab 展示 change log（实体/字段/old→new/时间），每次属性修改自动记录
- **工具**：剖切（X/Y/Z 滑杆）、距离测量

## 架构

系统由三个模块组成：

- **converter**（Node.js）：IFC → XKT 转换器，基于 web-ifc。被 server 以子进程方式调用，无需常驻进程。
- **server**（Go，stdlib + pgx/v5）：HTTP API 服务（默认端口 `:8090`），负责模型上传、转换任务调度、XKT/元数据静态服务、模型管理、Issue CRUD、属性 override 与修改记录。
- **web**（React + xeokit）：前端应用（开发端口 `:5173`），包含模型库页面与三维审查界面。

详细设计见 [docs/design.md](docs/design.md)，API 说明见 [docs/api.md](docs/api.md)，测试覆盖与验证方法见 [docs/README.md](docs/README.md)。

```
web (React/xeokit)  ──HTTP──>  server (Go :8090)  ──子进程──>  converter (Node)
                                      │
                                      └── data/  (上传的 IFC、生成的 XKT 与元数据、
                                                  issues/changes/overrides 持久化)
```

Issue / 属性 override / 修改记录三类持久化默认均为文件存储（`internal/{issue,override,change}.Store` 接口抽象）。配置后切换为 PostgreSQL（`PgStore`，pgx/v5 驱动，启动自动建表 `issues/changes/overrides`，API/前端零改动）：

```json
// server/server_config.json
{"pgDSN": "postgres://user:pass@host:port/dbname"}
```

也可设环境变量 `VIEWER_PG_DSN`（优先级高于配置文件）。未配置时保持文件存储，无需任何数据库。

## 依赖版本

- Node.js ≥ 18
- Go ≥ 1.22
- python3（仅冒烟脚本用于解析 JSON）

## 快速启动（本机验证）

```bash
# 0. 一次性：安装依赖
cd converter && npm install && cd ../web && npm install && cd ..

# 1. 终端 1：后端（:8090）
cd server && go run ./cmd/server

# 2. 终端 2：前端（:5173，/api 与 /models 已代理到 :8090）
cd web && npm run dev

# 3. 浏览器打开 http://localhost:5173 ，上传 .ifc 验证
```

端到端冒烟（覆盖上传→转换→下载→Issue CRUD→属性 override/修改记录 全链路，需 server 已运行）：

```bash
./scripts/smoke.sh    # 成功输出以 smoke OK 结尾
```

运行测试：

```bash
cd converter && npm test          # 转换器集成测试
cd server && go test ./...        # 后端 56 个测试
cd web && npm test                # 前端 84 个测试（另：npm run build 类型检查）
```

## 目录说明

```
viewer/
├── converter/        IFC→XKT 转换器（Node.js）
│   └── test/fixtures/  测试用 IFC 文件
├── server/           后端 API 服务（Go）
│   ├── cmd/server/     服务入口
│   ├── internal/issue/ Issue 存储（Store 接口 + File/Pg 双实现）
│   ├── internal/change/ 修改记录 change log（Store 接口 + File/Pg 双实现）
│   ├── internal/override/ 属性 override（白名单字段，Store 接口 + File/Pg 双实现）
│   └── server_config.json
├── web/              前端应用（React + xeokit + Vite）
├── scripts/smoke.sh  端到端冒烟脚本（含 Issue CRUD + override/changes）
├── docs/             设计文档、API 文档、计划
└── data/             运行时数据（不纳入版本管理）
```
